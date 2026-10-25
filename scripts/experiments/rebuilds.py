"""Evaluation E6: rebuild the local environment from Git, repeatedly (hub EVALUATION.md).

  python scripts/experiments/rebuilds.py [--n 10]

Each round runs `task rebuild:local` in warden-infra (kind cluster deleted and recreated, Argo CD bootstrapped
from warden-gitops; the Taskfile appends the timed row to evidence/rebuilds/rebuild-ledger.csv). Then, with no
human action, it checks that every Argo CD Application is Synced/Healthy and that the four services answer
through the gateway. One JSON line per round goes to evidence/rebuilds/smoke.jsonl. Needs task, kind, kubectl.
"""

import argparse
import json
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HUB = Path(__file__).resolve().parents[2]
SERVICES = ["books", "loans", "members", "notify"]
GATEWAY = "http://127.0.0.1:18080/api/info"


def apps():
    r = subprocess.run(["kubectl", "-n", "argocd", "get", "applications", "-o", "json"], capture_output=True, text=True)
    if r.returncode != 0:
        return 0, 0, []
    items = json.loads(r.stdout)["items"]
    bad = [f'{a["metadata"]["name"]}={a.get("status", {}).get("sync", {}).get("status")}/'
           f'{a.get("status", {}).get("health", {}).get("status")}' for a in items
           if (a.get("status", {}).get("sync", {}).get("status"), a.get("status", {}).get("health", {}).get("status"))
           != ("Synced", "Healthy")]
    return len(items), len(items) - len(bad), bad


def service(name):
    req = urllib.request.Request(GATEWAY, headers={"Host": f"{name}.warden.localhost"})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status
    except Exception as exc:
        return getattr(exc, "code", None) or type(exc).__name__


def smoke(deadline_s=900):
    """Wait (no human action) until all apps are Synced/Healthy and every service answers 200."""
    t0 = time.time()
    while True:
        total, good, bad = apps()
        codes = {s: service(s) for s in SERVICES}
        ok = total > 0 and not bad and all(c == 200 for c in codes.values())
        if ok or time.time() - t0 > deadline_s:
            return {"ok": ok, "seconds_after_task": round(time.time() - t0, 1), "apps_total": total,
                    "apps_synced_healthy": good, "not_ready": bad[:10], "services": codes}
        time.sleep(15)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=10)
    args = ap.parse_args()
    out = HUB / "evidence" / "rebuilds" / "smoke.jsonl"
    for i in range(args.n):
        started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        print(f"round {i + 1}/{args.n} started {started}", flush=True)
        t0 = time.time()
        r = subprocess.run(["task", "rebuild:local"], cwd=HUB / "warden-infra", capture_output=True, text=True,
                           encoding="utf-8", errors="replace")  # helm/kind print UTF-8; Windows defaults to cp1252
        task_s = round(time.time() - t0, 1)
        rec = {"round": i + 1, "started_utc": started, "task_exit": r.returncode, "task_seconds": task_s,
               "manual_steps": 0, **smoke()}
        if r.returncode != 0:
            rec["task_tail"] = (r.stdout + r.stderr)[-1500:]
        with out.open("a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(rec) + "\n")
        print(json.dumps({k: rec[k] for k in ("round", "task_exit", "task_seconds", "ok", "apps_synced_healthy",
                                              "apps_total", "services")}), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
