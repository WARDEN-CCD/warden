"""ADR-020 exit criterion (a): N consecutive legitimate deployments of all four services, zero audit violations.

  python scripts/experiments/m3_readiness.py <start UTC> <kyverno metrics snapshot taken at start> [--n 5]

Collects, for the window since <start>, every admission layer that can record a violation:
- runner records (evidence/rollbacks/*-healthy.json written after <start>): N promoted releases per service;
- supply-chain IVP (Audit, admission): Kyverno's own result and execution counters, delta since the snapshot.
  Executions without a result are verifications that did not finish (webhook timeout, failurePolicy Ignore);
- pod hygiene (Kyverno ValidatingPolicy): PolicyReports of the Pods created in the window;
- image-reference VAPs (Audit+Warn) have no counter or report. They are deterministic on the manifest, so every
  deployed Rollout and a Pod from its template are re-submitted as server-side dry runs: any T01/T06/HYG warning
  is a violation.
Writes evidence/m3/readiness-<start>.json. Needs kubectl.
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HUB = Path(__file__).resolve().parents[2]
SERVICES = ["books", "loans", "members", "notify"]
METRICS = "/api/v1/namespaces/kyverno/services/kyverno-svc-metrics:8000/proxy/metrics"


def kubectl(*args, stdin=None):
    return subprocess.run(["kubectl", *args], input=stdin, capture_output=True, text=True)


def counters(text, metric):
    out = {}
    for line in text.splitlines():
        m = re.match(rf"{metric}\{{([^}}]*)\}} (\S+)", line)
        if m:
            labels = dict(re.findall(r'(\w+)="([^"]*)"', m.group(1)))
            key = "|".join(f"{k}={labels[k]}" for k in ("policy_name", "result", "resource_kind") if k in labels)
            out[key] = out.get(key, 0) + float(m.group(2))
    return out


def delta(before, after):
    return {k: round(after.get(k, 0) - before.get(k, 0)) for k in sorted(set(before) | set(after))
            if round(after.get(k, 0) - before.get(k, 0))}


def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("start")
    ap.add_argument("snapshot")
    ap.add_argument("--n", type=int, default=5)
    args = ap.parse_args()
    start = ts(args.start)
    stamp = start.strftime("%Y%m%dT%H%M%SZ")
    rec = {"criterion": "ADR-020 (a)", "start_utc": args.start, "n_required": args.n}

    # 1. the deployments
    runs = {s: [] for s in SERVICES}
    for p in sorted((HUB / "evidence" / "rollbacks").glob("*-healthy.json")):
        when = datetime.strptime(p.name[:18], "%Y-%m-%dT%H%M%SZ").replace(tzinfo=start.tzinfo)
        if when >= start:
            r = json.loads(p.read_text())
            runs[r["service"]].append({"file": p.name, "outcome": r.get("outcome"), "commit": r.get("commit"),
                                       "seconds": r.get("seconds_rollout_start_to_outcome"), "error": r.get("error")})
    # A run that errored before anything reached the cluster (outcome None, e.g. a rejected git push) is not a
    # deployment; it is listed separately and does not break the streak.
    rec["not_deployed"] = {s: [x for x in v if x["outcome"] is None] for s, v in runs.items()}
    runs = {s: [x for x in v if x["outcome"] is not None] for s, v in runs.items()}
    rec["deployments"] = runs
    consecutive_ok = {s: all(x["outcome"] == "promoted" for x in v) and len(v) >= args.n for s, v in runs.items()}

    # 2. supply-chain IVP counters
    before = Path(args.snapshot).read_text()
    after = kubectl("get", "--raw", METRICS).stdout
    results = delta(counters(before, "kyverno_image_validating_policy_results_total"),
                    counters(after, "kyverno_image_validating_policy_results_total"))
    executions = delta(counters(before, "kyverno_image_validating_policy_execution_duration_seconds_count"),
                       counters(after, "kyverno_image_validating_policy_execution_duration_seconds_count"))
    rec["ivp_results_delta"] = results
    rec["ivp_executions_delta"] = executions
    ivp_fail = sum(v for k, v in results.items() if "warden-verify-supply-chain" in k and "result=fail" in k)

    # 3. hygiene PolicyReports for Pods created in the window
    hyg = {"pass": 0, "fail": 0, "error": 0, "pods": 0}
    hyg_fail = []
    for s in SERVICES:
        pods = json.loads(kubectl("-n", f"svc-{s}", "get", "pods", "-o", "json").stdout)["items"]
        new = {p["metadata"]["uid"]: p["metadata"]["name"] for p in pods if ts(p["metadata"]["creationTimestamp"]) >= start}
        hyg["pods"] += len(new)
        for uid, name in new.items():
            r = kubectl("-n", f"svc-{s}", "get", "policyreports.wgpolicyk8s.io", uid, "-o", "json")
            if r.returncode != 0:
                continue
            for res in json.loads(r.stdout).get("results", []):
                if res.get("policy") == "warden-pod-hygiene":
                    hyg[res.get("result", "error")] = hyg.get(res.get("result", "error"), 0) + 1
                    if res.get("result") != "pass":
                        hyg_fail.append(f"{s}/{name}: {res.get('message', '')[:120]}")
    rec["hygiene_reports"] = hyg
    rec["hygiene_failures"] = hyg_fail

    # 4. VAPs: re-submit the deployed objects as server-side dry runs
    vap = []
    for s in SERVICES:
        ro = json.loads(kubectl("-n", f"svc-{s}", "get", "rollout", s, "-o", "json").stdout)
        tmpl = ro["spec"]["template"]
        clean = {"apiVersion": ro["apiVersion"], "kind": "Rollout",
                 "metadata": {"name": f"m3-{s}", "namespace": f"svc-{s}"}, "spec": dict(ro["spec"])}
        clean["spec"]["selector"] = {"matchLabels": {"m3": s}}
        clean["spec"]["template"] = {**tmpl, "metadata": {"labels": {"m3": s}}}
        pod = {"apiVersion": "v1", "kind": "Pod", "metadata": {"name": f"m3-{s}", "namespace": f"svc-{s}"},
               "spec": tmpl["spec"]}
        for kind, obj in (("Rollout", clean), ("Pod", pod)):
            r = kubectl("create", "--dry-run=server", "-f", "-", stdin=json.dumps(obj))
            warnings = [l for l in r.stderr.splitlines() if re.search(r"T0[16]:|HYG:", l)]
            vap.append({"service": s, "kind": kind, "admitted": r.returncode == 0, "violations": warnings[:3]})
    rec["vap_dry_runs"] = vap
    vap_violations = sum(len(x["violations"]) for x in vap) + sum(not x["admitted"] for x in vap)

    rec["verdict"] = {
        "every_service_has_n_consecutive_promoted_releases": all(consecutive_ok.values()),
        "ivp_fail_results": ivp_fail,
        "ivp_executions_without_result": max(0, sum(v for k, v in executions.items() if "warden-verify-supply-chain" in k)
                                              - sum(v for k, v in results.items() if "warden-verify-supply-chain" in k)),
        "hygiene_failures": len(hyg_fail),
        "vap_violations": vap_violations,
    }
    v = rec["verdict"]
    rec["criterion_a_met"] = (v["every_service_has_n_consecutive_promoted_releases"] and v["ivp_fail_results"] == 0
                              and v["hygiene_failures"] == 0 and v["vap_violations"] == 0)
    out = HUB / "evidence" / "m3"
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"readiness-{stamp}.json"
    path.write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: rec[k] for k in ("verdict", "criterion_a_met", "ivp_results_delta", "ivp_executions_delta",
                                          "hygiene_reports")}, indent=1))
    print({s: [x["outcome"] for x in v] for s, v in runs.items()})
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
