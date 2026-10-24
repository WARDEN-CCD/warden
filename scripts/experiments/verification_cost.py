"""Evaluation E8: what image verification adds to admission (hub EVALUATION.md).

  python scripts/experiments/verification_cost.py [--n 50]

Every request is a server-side dry-run Pod create in svc-books: it passes through all admission webhooks, Kyverno
included (its IVP webhooks are NoneOnDryRun), but nothing is scheduled. Three conditions:

  cold      first request for each signed service digest, right after the Kyverno admission pod was replaced
  warm      the same digests again, round-robin, n requests
  baseline  n requests for an image the IVPs do not match (same namespace, same webhooks, no verification)

Added latency = verified minus baseline. Also reports Kyverno's own kyverno_admission_review_duration_seconds over
the run. Writes evidence/verification/<UTC>.json. Needs kubectl; stdlib only.
"""

import argparse
import json
import re
import statistics
import subprocess
import sys
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

HUB = Path(__file__).resolve().parents[2]
NS = "svc-books"
# Matched by no IVP (matchImageReferences is ghcr.io/warden-ccd/*); the CNPG image VAP only warns in Audit.
BASELINE = ("ghcr.io/cloudnative-pg/postgresql:18.6-system-trixie"
            "@sha256:f7e00138159bb45d70b624ba25e446924cb3ed1bf366d13e936c3f81b914064e")
TIMEOUT_S = 30  # IVP webhook timeoutSeconds; failurePolicy Ignore admits after it


def run(*cmd, stdin=None, check=True):
    r = subprocess.run(cmd, input=stdin, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)}: {r.stderr.strip()}")
    return r


def service_digests():
    """Current signed images of the four services, as deployed from warden-gitops."""
    out = []
    for path in sorted((HUB / "warden-gitops" / "apps").glob("*/rollout.yaml")):
        m = re.search(r"(ghcr\.io/warden-ccd/svc-[a-z]+@sha256:[0-9a-f]{64})", path.read_text())
        if m:
            out.append(m.group(1))
    return out


def admit(image, i):
    pod = {"apiVersion": "v1", "kind": "Pod",
           "metadata": {"name": f"e8-{i}", "namespace": NS, "labels": {"warden.dev/experiment": "e8"}},
           "spec": {"securityContext": {"runAsNonRoot": True, "runAsUser": 65532},
                    "containers": [{"name": "app", "image": image,
                                    "securityContext": {"allowPrivilegeEscalation": False,
                                                        "readOnlyRootFilesystem": True,
                                                        "capabilities": {"drop": ["ALL"]}},
                                    "resources": {"requests": {"cpu": "10m", "memory": "16Mi"},
                                                  "limits": {"memory": "64Mi"}}}]}}
    t0 = time.perf_counter()
    r = run("kubectl", "create", "--dry-run=server", "-f", "-", stdin=json.dumps(pod), check=False)
    seconds = time.perf_counter() - t0
    return {"image": image.split("@")[0].rsplit("/", 1)[-1], "seconds": round(seconds, 3), "ok": r.returncode == 0,
            "warnings": [l for l in r.stderr.splitlines() if l.startswith("Warning")][:3],
            "error": None if r.returncode == 0 else r.stderr.strip()[:300]}


def summary(samples):
    xs = sorted(s["seconds"] for s in samples)
    if not xs:
        return {}
    q = lambda p: xs[min(len(xs) - 1, int(round(p * (len(xs) - 1))))]
    return {"n": len(xs), "p50": round(statistics.median(xs), 3), "p95": round(q(0.95), 3), "max": round(xs[-1], 3),
            "min": round(xs[0], 3), "at_or_over_webhook_timeout": sum(x >= TIMEOUT_S for x in xs),
            "denied_or_failed": sum(not s["ok"] for s in samples)}


def prom(query):
    q = urllib.parse.urlencode({"query": query})
    r = run("kubectl", "get", "--raw",
            f"/api/v1/namespaces/monitoring/services/kube-prometheus-stack-prometheus:9090/proxy/api/v1/query?{q}")
    return [{"labels": x["metric"], "value": x["value"][1]} for x in json.loads(r.stdout)["data"]["result"]]


def replace_kyverno_admission_pod():
    sel = "app.kubernetes.io/component=admission-controller"
    run("kubectl", "-n", "kyverno", "delete", "pod", "-l", sel, "--wait=true")
    run("kubectl", "-n", "kyverno", "rollout", "status", "deploy/kyverno-admission-controller", "--timeout=300s")
    time.sleep(20)  # webhook endpoints and policy cache settle after the pod is Ready


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=50)
    args = ap.parse_args()
    digests = service_digests()
    if not digests:
        raise SystemExit("no service digests found under warden-gitops/apps")
    started = datetime.now(timezone.utc)
    t_start = time.time()

    print("replacing the Kyverno admission pod (cold cache)", flush=True)
    replace_kyverno_admission_pod()
    cold = [admit(img, f"cold-{i}") for i, img in enumerate(digests)]
    print("cold", summary(cold), flush=True)
    warm = [admit(digests[i % len(digests)], f"warm-{i}") for i in range(args.n)]
    print("warm", summary(warm), flush=True)
    base = [admit(BASELINE, f"base-{i}") for i in range(args.n)]
    print("baseline", summary(base), flush=True)

    window = f"{int(time.time() - t_start) + 30}s"
    kyverno = {f"p{int(p * 100)}": prom(
        f"histogram_quantile({p}, sum by (le) (rate(kyverno_admission_review_duration_seconds_bucket"
        f'{{resource_kind="Pod", resource_namespace="{NS}"}}[{window}])))') for p in (0.5, 0.95)}

    sc, sw, sb = summary(cold), summary(warm), summary(base)
    rec = {"experiment": "E8", "cluster": "local (kind)", "started_utc": started.strftime("%Y-%m-%dT%H:%M:%SZ"),
           "method": "kubectl create --dry-run=server, sequential, client wall time (includes kubectl start-up, "
                     "equal in every condition)",
           "namespace": NS, "baseline_image": BASELINE, "signed_images": digests,
           "policy_mode": "Audit, failurePolicy Ignore, webhook timeout 30 s (pre-M3)",
           "summary": {"cold": sc, "warm": sw, "baseline": sb,
                       "added_p50_warm_s": round(sw["p50"] - sb["p50"], 3),
                       "added_p95_warm_s": round(sw["p95"] - sb["p95"], 3),
                       "added_p50_cold_s": round(sc["p50"] - sb["p50"], 3)},
           "kyverno_admission_review_duration_seconds": kyverno,
           "samples": {"cold": cold, "warm": warm, "baseline": base}}
    out = HUB / "evidence" / "verification"
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{started.strftime('%Y-%m-%dT%H%M%SZ')}.json"
    path.write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(rec["summary"], indent=1), "\n", path, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
