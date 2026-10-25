"""Evaluation E3: aggregate the canary runs written by canary.py (hub EVALUATION.md).

  python scripts/experiments/e3_summary.py <since: evidence file prefix, e.g. 2026-10-25T09>

Reads evidence/rollbacks/<UTC>-<service>-<kind>.json from `since` on (kind healthy, error, latency), and for
latency runs asks Prometheus how many requests each aborted canary served slower than 0.5 s (its pod-template
hash is in the AnalysisRun name). Writes evidence/rollbacks/summary-<since>.json and prints a table.
"""

import json
import statistics
import subprocess
import sys
import urllib.parse
from pathlib import Path

HUB = Path(__file__).resolve().parents[2]
RPS = 40  # k6 TestRun rate per service (warden-platform/load)


def prom(query):
    q = urllib.parse.urlencode({"query": query})
    out = subprocess.run(["kubectl", "get", "--raw",
                          f"/api/v1/namespaces/monitoring/services/kube-prometheus-stack-prometheus:9090/proxy/api/v1/query?{q}"],
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out)["data"]["result"]


def canary_hash(run):
    for ar in run.get("analysis_runs", []):
        parts = ar["name"].rsplit("-", 3)  # <service>-<hash>-<revision>-<step>
        if len(parts) == 4:
            return parts[1]
    return None


def slow_requests(service, h):
    sel = f'namespace="svc-{service}", rollouts_pod_template_hash="{h}", uri!~"/actuator.*"'
    total = prom(f"max_over_time(sum(http_server_requests_seconds_count{{{sel}}})[12h:30s])")
    fast = prom(f'max_over_time(sum(http_server_requests_seconds_bucket{{{sel}, le="0.536870911"}})[12h:30s])')
    t = float(total[0]["value"][1]) if total else 0.0
    f = float(fast[0]["value"][1]) if fast else 0.0
    return round(t), round(t - f)


def stats(xs, digits=1):
    xs = sorted(xs)
    if not xs:
        return {}
    return {"n": len(xs), "median": round(statistics.median(xs), digits), "min": round(xs[0], digits),
            "max": round(xs[-1], digits)}


def main():
    since = sys.argv[1]
    runs = []
    for p in sorted((HUB / "evidence" / "rollbacks").glob("*.json")):
        if p.name < since or p.name.startswith("summary"):
            continue
        r = json.loads(p.read_text())
        if r.get("kind") not in ("healthy", "error", "latency"):
            continue
        r["file"] = p.name
        runs.append(r)
    rows = []
    for r in runs:
        row = {"file": r["file"], "service": r["service"], "kind": r["kind"], "outcome": r.get("outcome"),
               "seconds_to_outcome": r.get("seconds_rollout_start_to_outcome"),
               "seconds_commit_to_rollout_start": r.get("seconds_commit_to_rollout_start"),
               "errors": r.get("blast_radius", {}).get("errors"), "requests": r.get("blast_radius", {}).get("requests"),
               "error_share": r.get("blast_radius", {}).get("share"),
               "recovery_seconds": (r.get("recovery") or {}).get("seconds_abort_to_fixed"),
               "failed_metric": next((m for ar in r.get("analysis_runs", []) for m, ph in ar["metrics"].items()
                                      if ph == "Failed"), None)}
        if r["kind"] == "latency" and (h := canary_hash(r)):
            served, slow = slow_requests(r["service"], h)
            row.update({"canary_hash": h, "canary_requests": served, "canary_slow_requests": slow,
                        "slow_share_of_service": round(slow / (RPS * r["seconds_rollout_start_to_outcome"]), 4)})
        rows.append(row)
    faulty = [x for x in rows if x["kind"] != "healthy"]
    healthy = [x for x in rows if x["kind"] == "healthy"]
    errors = [x for x in rows if x["kind"] == "error"]
    latency = [x for x in rows if x["kind"] == "latency"]
    summary = {
        "since": since, "runs": len(rows),
        "faulty_aborted": f'{sum(x["outcome"] == "aborted" for x in faulty)}/{len(faulty)}',
        "healthy_promoted": f'{sum(x["outcome"] == "promoted" for x in healthy)}/{len(healthy)}',
        "seconds_rollout_start_to_abort": stats([x["seconds_to_outcome"] for x in faulty]),
        "seconds_rollout_start_to_promoted": stats([x["seconds_to_outcome"] for x in healthy]),
        "seconds_abort_to_fixed": stats([x["recovery_seconds"] for x in faulty if x["recovery_seconds"]]),
        "seconds_commit_to_rollout_start": stats([x["seconds_commit_to_rollout_start"] for x in rows]),
        "error_runs_blast_radius_share": stats([x["error_share"] for x in errors], 5),
        "error_runs_predicted_share": 0.05 * 0.10,
        "latency_runs_slow_share_of_service": stats([x["slow_share_of_service"] for x in latency if "slow_share_of_service" in x], 4),
        "failed_metric_by_kind": {k: sorted({x["failed_metric"] for x in rows if x["kind"] == k}) for k in ("error", "latency")},
        "rows": rows,
    }
    out = HUB / "evidence" / "rollbacks" / f"summary-{since}.json"
    out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    for x in rows:
        print(f'{x["service"]:8} {x["kind"]:8} {x["outcome"]:9} {x["seconds_to_outcome"]:7} s  '
              f'err {x["errors"]}/{x["requests"]}  slow {x.get("canary_slow_requests", "-")}  '
              f'recovery {x["recovery_seconds"]}  failed={x["failed_metric"]}')
    print(json.dumps({k: v for k, v in summary.items() if k != "rows"}, indent=1))
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
