"""Evaluation E3: automatic canary rollback (hub EVALUATION.md).

  python scripts/experiments/canary.py <service> <healthy|error|latency|reset> [--runs N] [--admin-merge]

Each run ships a REAL release of svc-<service> through the whole pipeline: a commit on main (signed build in
CI) -> new digest promoted in warden-gitops (the promoter bot's PR when the app exists; otherwise an owner PR
through the same digest-only check, merged by a person or, with --admin-merge, by the owner bypass) -> Argo CD
-> canary analysed by Prometheus. `reset` is housekeeping, not an E3 run: it removes any injected fault. It records when the canary started,
when analysis aborted or promoted it, the analysis result, and the blast radius (5xx share of all requests to
the service during the rollout). After a faulty release it ships the fix, which measures recovery time.

  error    warden.demo.error-rate: 0.10   -> expected: aborted at the first analysis
  latency  warden.demo.latency-ms: 600    -> expected: aborted (p95 >= 500 ms)
  healthy  version bump only              -> expected: promoted to 100 %

Writes evidence/rollbacks/<UTC>-<service>-<kind>.json. Needs gh, git, kubectl; stdlib only.
"""

import argparse
import json
import re
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HUB = Path(__file__).resolve().parents[2]
ORG = "WARDEN-CCD"


def run(*cmd, cwd=None, check=True):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)}: {r.stderr.strip() or r.stdout.strip()}")
    return r.stdout.strip()


def poll(*cmd):
    """`run` for calls inside wait loops: a transient network error is a missed poll, not a failed run."""
    try:
        return run(*cmd)
    except RuntimeError as exc:
        print(f"  (poll failed, retrying: {str(exc)[:120]})", flush=True)
        return None


def now():
    return time.time()


def iso(t):
    return datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def prom(query, at=None):
    q = urllib.parse.urlencode({"query": query, **({"time": at} if at else {})})
    out = run("kubectl", "get", "--raw",
              f"/api/v1/namespaces/monitoring/services/kube-prometheus-stack-prometheus:9090/proxy/api/v1/query?{q}")
    res = json.loads(out)["data"]["result"]
    return float(res[0]["value"][1]) if res else 0.0


def anonymous_digest(repo, tag, timeout=900):
    deadline = now() + timeout
    while now() < deadline:
        try:
            with urllib.request.urlopen(f"https://ghcr.io/token?scope=repository:{repo}:pull", timeout=20) as r:
                token = json.load(r)["token"]
            req = urllib.request.Request(f"https://ghcr.io/v2/{repo}/manifests/{tag}", method="HEAD", headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.oci.image.manifest.v1+json, application/vnd.docker.distribution.manifest.v2+json"})
            with urllib.request.urlopen(req, timeout=20) as r:
                return r.headers["Docker-Content-Digest"]
        except Exception:
            time.sleep(10)
    raise RuntimeError(f"no image {repo}:{tag}")


def wait_ci(full, sha, timeout=1800):
    deadline = now() + timeout
    while now() < deadline:
        out = poll("gh", "api", f"repos/{full}/actions/runs?head_sha={sha}&branch=main")
        if out is None:
            time.sleep(15)
            continue
        done = [r for r in json.loads(out)["workflow_runs"] if r["status"] == "completed"]
        if done:
            if done[0]["conclusion"] != "success":
                raise RuntimeError(f"CI {done[0]['conclusion']}: {done[0]['html_url']}")
            return done[0]["html_url"]
        time.sleep(15)
    raise RuntimeError("CI timeout")


def ship(service, change, message):
    """Commit `change` to svc-<service> main, wait for the signed build, return (sha, digest, commit_time)."""
    full = f"{ORG}/svc-{service}"
    with tempfile.TemporaryDirectory() as tmp:
        run("gh", "repo", "clone", full, tmp, "--", "--depth", "1")
        change(Path(tmp))
        run("git", "-c", "core.autocrlf=false", "commit", "-qam", message, cwd=tmp)
        run("git", "push", "-q", "origin", "main", cwd=tmp)
        sha = run("git", "rev-parse", "HEAD", cwd=tmp)
    t_commit = now()
    wait_ci(full, sha)
    digest = anonymous_digest(f"warden-ccd/svc-{service}", sha)
    return sha, digest, t_commit


def open_owner_pr(service, digest, sha, branch):
    """The deploy PR the promoter bot would open, opened by the owner instead (no promoter app yet)."""
    with tempfile.TemporaryDirectory() as tmp:
        run("gh", "repo", "clone", f"{ORG}/warden-gitops", tmp, "--", "--depth", "1")
        path = Path(tmp) / "apps" / service / "rollout.yaml"
        text = path.read_text()
        new = re.sub(rf"(ghcr\.io/warden-ccd/svc-{service}@)sha256:[0-9a-f]{{64}}", rf"\g<1>{digest}", text)
        if new == text:
            raise RuntimeError("digest unchanged")
        path.write_text(new)
        run("git", "switch", "-q", "-c", branch, cwd=tmp)
        run("git", "-c", "core.autocrlf=false", "commit", "-qam",
            f"deploy({service}): {digest[7:19]} from {sha[:12]}", cwd=tmp)
        run("git", "push", "-q", "-u", "origin", branch, cwd=tmp)
        return run("gh", "pr", "create", "--base", "main", "--head", branch, "--title",
                   f"deploy({service}): {digest[7:19]}", "--body",
                   f"E3 experiment release from {ORG}/svc-{service}@{sha}. Merge after the digest-only check.", cwd=tmp)


def promote(service, digest, sha, admin_merge, timeout=7200):
    """Get `digest` merged into warden-gitops; return (pr_url, how, merge_time).

    With the promoter app (`warden setup-apps`), the build's promote job has already opened
    promote/<svc>/<sha12> with auto-merge, and this only waits. Without it, the owner opens the same PR. It is
    merged with the owner bypass only under --admin-merge, the user's explicit choice; otherwise this waits for a
    person to merge it.
    """
    branch = f"promote/{service}/{sha[:12]}"
    url = run("gh", "pr", "list", "--repo", f"{ORG}/warden-gitops", "--head", branch, "--state", "all",
              "--json", "url", "--jq", ".[0].url // empty")
    how = "promoter-bot" if url else ("owner-admin-merge" if admin_merge else "owner-pr-human-merge")
    if not url:
        url = open_owner_pr(service, digest, sha, branch)
        print(f"  deploy PR {url} ({how})", flush=True)
    deadline = now() + timeout
    while now() < deadline:
        out = poll("gh", "pr", "view", url, "--json", "state,headRefOid")
        if out is None:
            time.sleep(10)
            continue
        pr = json.loads(out)
        if pr["state"] == "MERGED":
            return url, how, now()
        if pr["state"] == "CLOSED":
            raise RuntimeError(f"{url} was closed without merging")
        if how == "owner-admin-merge":
            state = run("gh", "pr", "checks", url, "--json", "name,state", "--jq",
                        '.[] | select(.name=="digest-only") | .state', check=False)
            if state == "SUCCESS":
                poll("gh", "pr", "merge", url, "--squash", "--admin", "--delete-branch",
                     "--match-head-commit", pr["headRefOid"])
        time.sleep(10)
    raise RuntimeError(f"{url} not merged within {timeout} s")


def rollout_state(service):
    raw = json.loads(run("kubectl", "-n", f"svc-{service}", "get", "rollout", service, "-o", "json"))
    st = raw.get("status", {})
    image = raw["spec"]["template"]["spec"]["containers"][0]["image"]
    return {"phase": st.get("phase"), "abort": bool(st.get("abort")), "step": st.get("currentStepIndex"),
            "stable": st.get("stableRS"), "current": st.get("currentPodHash"), "image": image,
            "weight": ((st.get("canary") or {}).get("weights") or {}).get("canary", {}).get("weight")}


def watch(service, digest, timeout=1500):
    """Follow the rollout of `digest` until it is promoted (Healthy) or aborted."""
    events, t0, seen_canary = [], None, False
    deadline = now() + timeout
    last = None
    while now() < deadline:
        try:
            s = rollout_state(service)
        except RuntimeError:
            time.sleep(2)
            continue
        if digest not in s["image"]:
            time.sleep(2)
            continue
        if t0 is None:
            t0 = now()
        key = (s["phase"], s["abort"], s["step"], s["weight"])
        if key != last:
            events.append({"t": round(now() - t0, 1), **{k: s[k] for k in ("phase", "abort", "step", "weight")}})
            last = key
        if s["weight"]:
            seen_canary = True
        if s["abort"]:
            return "aborted", t0, now(), events
        if s["phase"] == "Healthy" and s["current"] == s["stable"] and (seen_canary or len(events) > 1):
            return "promoted", t0, now(), events
        time.sleep(2)
    return "timeout", t0, now(), events


def analysis_runs(service, since):
    raw = json.loads(run("kubectl", "-n", f"svc-{service}", "get", "analysisruns", "-o", "json"))
    out = []
    for item in raw["items"]:
        created = datetime.fromisoformat(item["metadata"]["creationTimestamp"].replace("Z", "+00:00")).timestamp()
        if created >= since - 5:
            metrics = {m["name"]: m.get("phase") for m in item.get("status", {}).get("metricResults", [])}
            out.append({"name": item["metadata"]["name"], "phase": item.get("status", {}).get("phase"),
                        "message": item.get("status", {}).get("message", ""), "metrics": metrics})
    return out


def blast_radius(service, t0, t1):
    window = max(int(t1 - t0), 60)
    # Injected faults answer before handler mapping (uri="UNKNOWN"), so exclude actuator rather than match /api.
    sel = f'namespace="svc-{service}", uri!~"/actuator.*"'
    errors = prom(f'sum(increase(http_server_requests_seconds_count{{{sel}, status=~"5.."}}[{window}s]))', at=t1)
    total = prom(f"sum(increase(http_server_requests_seconds_count{{{sel}}}[{window}s]))", at=t1)
    return {"errors": round(errors), "requests": round(total), "share": round(errors / total, 5) if total else None}


def edit(path_in_repo, fn):
    def change(repo: Path):
        p = repo / path_in_repo
        p.write_text(fn(p.read_text()))
    return change


def bump_version(text):
    m = re.search(r"<version>0\.1\.(\d+)</version>", text)
    n = int(m.group(1)) + 1 if m else 1
    return re.sub(r"<version>0\.1\.\d+</version>", f"<version>0.1.{n}</version>", text, count=1)


FAULTS = {
    "error": ("warden.demo.error-rate", "error-rate: 0.0", "error-rate: 0.10"),
    "latency": ("warden.demo.latency-ms", "latency-ms: 0", "latency-ms: 600"),
}


def reset_faults(text):
    text = re.sub(r"error-rate: [0-9.]+", "error-rate: 0.0", text)
    return re.sub(r"latency-ms: [0-9]+", "latency-ms: 0", text)


def resume(service, sha):
    """An already-built release: its commit time, and its digest once anonymously pullable."""
    full = f"{ORG}/svc-{service}"
    sha = run("gh", "api", f"repos/{full}/commits/{sha}", "--jq", ".sha")
    when = run("gh", "api", f"repos/{full}/commits/{sha}", "--jq", ".commit.committer.date")
    wait_ci(full, sha)
    digest = anonymous_digest(f"warden-ccd/svc-{service}", sha)
    return sha, digest, datetime.fromisoformat(when.replace("Z", "+00:00")).timestamp()


def one_run(service, kind, admin_merge, resume_sha=None):
    record = {"service": service, "kind": kind, "started_utc": iso(now()), "resumed_from": resume_sha}
    if kind == "healthy":
        change, msg = edit("pom.xml", bump_version), f"feat: release a new {service} version (E3 healthy run)"
    elif kind == "reset":
        change = lambda repo: (edit("pom.xml", bump_version)(repo),
                               edit("src/main/resources/application.yaml", reset_faults)(repo))
        msg = f"fix: remove any injected fault from {service}"
    else:
        _, before, after = FAULTS[kind]
        change = lambda repo: (edit("pom.xml", bump_version)(repo),
                               edit("src/main/resources/application.yaml", lambda t: t.replace(before, after))(repo))
        msg = f"feat: {service} release with injected {kind} fault (E3)"
    sha, digest, t_commit = resume(service, resume_sha) if resume_sha else ship(service, change, msg)
    pr, how, t_merge = promote(service, digest, sha, admin_merge)
    outcome, t0, t1, events = watch(service, digest)
    record.update({"commit": sha, "digest": digest, "gitops_pr": pr, "promotion": how, "outcome": outcome,
                   "seconds_merge_to_rollout_start": round(t0 - t_merge, 1) if t0 else None,
                   "seconds_commit_to_rollout_start": round(t0 - t_commit, 1) if t0 else None,
                   "seconds_rollout_start_to_outcome": round(t1 - t0, 1) if t0 else None,
                   "events": events, "analysis_runs": analysis_runs(service, t0 or t_merge),
                   "blast_radius": blast_radius(service, t0 or t_merge, t1)})
    if kind in FAULTS:
        _, before, after = FAULTS[kind]
        t_fix = now()
        fsha, fdigest, _ = ship(service, lambda repo: (edit("pom.xml", bump_version)(repo),
                                                       edit("src/main/resources/application.yaml",
                                                            lambda t: t.replace(after, before))(repo)),
                                f"fix: remove the injected {kind} fault from {service}")
        promote(service, fdigest, fsha, admin_merge)
        foutcome, _, ft1, _ = watch(service, fdigest)
        record["recovery"] = {"fix_commit": fsha, "outcome": foutcome,
                              "seconds_abort_to_fixed": round(ft1 - t1, 1),
                              "seconds_fix_commit_to_fixed": round(ft1 - t_fix, 1)}
    return record


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("service")
    ap.add_argument("kind", choices=["healthy", "error", "latency", "reset"])
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--admin-merge", action="store_true",
                    help="merge the owner's deploy PR with the owner bypass (only with the user's go-ahead)")
    ap.add_argument("--resume", metavar="SHA",
                    help="continue a run whose release commit is already pushed (skips the commit; one run)")
    args = ap.parse_args()
    out = HUB / "evidence" / "rollbacks"
    out.mkdir(parents=True, exist_ok=True)
    for i in range(args.runs):
        print(f"run {i + 1}/{args.runs}: {args.service} {args.kind}", flush=True)
        try:
            rec = one_run(args.service, args.kind, args.admin_merge, args.resume if i == 0 else None)
        except Exception as exc:
            rec = {"service": args.service, "kind": args.kind, "error": str(exc)}
        path = out / f"{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H%M%SZ')}-{args.service}-{args.kind}.json"
        path.write_text(json.dumps(rec, indent=2), encoding="utf-8")
        print(json.dumps({k: rec.get(k) for k in ("outcome", "seconds_rollout_start_to_outcome",
                                                 "blast_radius", "recovery", "error")}), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
