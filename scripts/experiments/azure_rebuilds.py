"""Evaluation E6 on Azure: rebuild the AKS environment from Git, repeatedly (hub EVALUATION.md).

  python scripts/experiments/azure_rebuilds.py [--n 4] [--kubeconfig PATH]

Each round runs `task up:azure` in warden-infra (OpenTofu creates AKS, Argo CD is bootstrapped from warden-gitops; the
Taskfile appends the timed row to evidence/rebuilds/rebuild-ledger.csv), then, with no human action, checks that every
Argo CD Application is Synced/Healthy and that the four services answer 200 through the Azure load balancer. The
environment is ALWAYS destroyed afterwards (`task down:azure`), also when the round failed, so nothing keeps billing.
One JSON line per round goes to evidence/rebuilds/smoke.jsonl (field env = "azure").

--kubeconfig keeps this cluster's credentials out of the default kubeconfig, so experiments running against the kind
cluster in the meantime keep their current context. Needs task, tofu, az (logged in), kubelogin, kubectl, helm.
"""

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HUB = Path(__file__).resolve().parents[2]
SERVICES = ["books", "loans", "members", "notify"]
ENV = dict(os.environ)


def kubectl(*args):
    return subprocess.run(["kubectl", *args], capture_output=True, text=True, env=ENV)


def apps():
    r = kubectl("-n", "argocd", "get", "applications", "-o", "json")
    if r.returncode != 0:
        return 0, 0, []
    items = json.loads(r.stdout)["items"]
    bad = [f'{a["metadata"]["name"]}={a.get("status", {}).get("sync", {}).get("status")}/'
           f'{a.get("status", {}).get("health", {}).get("status")}' for a in items
           if (a.get("status", {}).get("sync", {}).get("status"), a.get("status", {}).get("health", {}).get("status"))
           != ("Synced", "Healthy")]
    return len(items), len(items) - len(bad), bad


def gateway_ip():
    r = kubectl("-n", "envoy-gateway-system", "get", "svc", "-o", "json")
    if r.returncode != 0:
        return None
    for s in json.loads(r.stdout)["items"]:
        if s["spec"].get("type") == "LoadBalancer":
            for ing in s.get("status", {}).get("loadBalancer", {}).get("ingress", []):
                if ing.get("ip"):
                    return ing["ip"]
    return None


def service(ip, name):
    if not ip:
        return "no-gateway-ip"
    req = urllib.request.Request(f"http://{ip}/api/info", headers={"Host": f"{name}.warden.localhost"})
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            return r.status
    except Exception as exc:
        return getattr(exc, "code", None) or type(exc).__name__


def smoke(deadline_s=900):
    """Wait (no human action) until all apps are Synced/Healthy and every service answers 200."""
    t0 = time.time()
    while True:
        total, good, bad = apps()
        ip = gateway_ip()
        codes = {s: service(ip, s) for s in SERVICES}
        ok = total > 0 and not bad and all(c == 200 for c in codes.values())
        if ok or time.time() - t0 > deadline_s:
            return {"ok": ok, "seconds_after_task": round(time.time() - t0, 1), "apps_total": total,
                    "apps_synced_healthy": good, "not_ready": bad[:10], "services": codes}
        time.sleep(15)


def task(name):
    r = subprocess.run(["task", name], cwd=HUB / "warden-infra", capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=ENV)
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=4)
    ap.add_argument("--kubeconfig", help="separate kubeconfig file for the AKS cluster")
    args = ap.parse_args()
    if args.kubeconfig:
        ENV["KUBECONFIG"] = args.kubeconfig
    out = HUB / "evidence" / "rebuilds" / "smoke.jsonl"
    for i in range(args.n):
        started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        print(f"round {i + 1}/{args.n} started {started}", flush=True)
        t0 = time.time()
        up = task("up:azure")
        task_s = round(time.time() - t0, 1)
        rec = {"env": "azure", "round": i + 1, "started_utc": started, "task_exit": up.returncode,
               "task_seconds": task_s, "manual_steps": 0}
        try:
            rec.update(smoke() if up.returncode == 0 else {"ok": False})
            if up.returncode != 0:
                rec["task_tail"] = (up.stdout + up.stderr)[-1500:]
        finally:
            d0 = time.time()
            down = task("down:azure")
            rec["down_exit"] = down.returncode
            rec["down_seconds"] = round(time.time() - d0, 1)
            if down.returncode != 0:
                rec["down_tail"] = (down.stdout + down.stderr)[-1500:]
        with out.open("a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(rec) + "\n")
        print(json.dumps({k: rec.get(k) for k in ("round", "task_exit", "task_seconds", "ok", "apps_synced_healthy",
                                                  "apps_total", "services", "down_exit", "down_seconds")}),
              flush=True)
        if rec["down_exit"] != 0:
            print("destroy failed; stopping so nothing is rebuilt on top of leftovers", flush=True)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
