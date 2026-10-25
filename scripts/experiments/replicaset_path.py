"""Evaluation E8, ADR-031: what verification costs on the ReplicaSet path versus direct Pods.

  python scripts/experiments/replicaset_path.py

Uses the attack lab (Deny + Fail clones of the policies under warden-policy/policies, attack-lab namespace) and
creates REAL objects: a ReplicaSet of 2 signed Pods, a scale-up to 4 (an UPDATE that leaves the template
unchanged), and, as the control, 2 Pods created directly. Records admission and ready times, and Kyverno's own
execution counters per policy, so it shows which policy verified what. Writes evidence/verification/<UTC>-replicaset-path.json.
"""

import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HUB = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(HUB / "warden-policy" / "attacks"))
import run_attacks  # noqa: E402  (setup_lab, teardown_lab, LAB_NS, resolve)

NS = run_attacks.LAB_NS
METRICS = "/api/v1/namespaces/kyverno/services/kyverno-svc-metrics:8000/proxy/metrics"


def kubectl(*args, stdin=None, check=True):
    r = subprocess.run(["kubectl", *args], input=stdin, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"kubectl {' '.join(args)}: {r.stderr.strip()}")
    return r


def counters():
    out = kubectl("get", "--raw", METRICS).stdout
    c = {}
    for line in out.splitlines():
        m = re.match(r'kyverno_image_validating_policy_execution_duration_seconds_count\{([^}]*)\} (\S+)', line)
        if m:
            labels = dict(re.findall(r'(\w+)="([^"]*)"', m.group(1)))
            key = f'{labels.get("policy_name")}/{labels.get("resource_kind")}'
            c[key] = c.get(key, 0) + float(m.group(2))
    return c


def delta(before, after):
    return {k: after.get(k, 0) - before.get(k, 0) for k in sorted(set(before) | set(after))
            if after.get(k, 0) != before.get(k, 0)}


def ready_count(selector):
    pods = json.loads(kubectl("-n", NS, "get", "pods", "-l", selector, "-o", "json").stdout)["items"]
    return sum(all(c.get("ready") for c in p.get("status", {}).get("containerStatuses", []) or [{}]) for p in pods)


def wait_ready(selector, n, timeout=600):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if ready_count(selector) >= n:
            return round(time.time() - t0, 1)
        time.sleep(1)
    return None


def pod_spec(image):
    return {"containers": [{"name": "app", "image": image, "ports": [{"containerPort": 8080}],
                            "resources": {"requests": {"cpu": "50m", "memory": "192Mi"}, "limits": {"memory": "512Mi"}}}]}


def main():
    fx = json.loads((HUB / "warden-policy" / "attacks" / "fixtures.json").read_text())
    image = run_attacks.resolve(fx["good"])
    started = datetime.now(timezone.utc)
    rec = {"experiment": "E8 / ADR-031", "started_utc": started.strftime("%Y-%m-%dT%H:%M:%SZ"), "image": image,
           "policies": "attack-lab clones (Deny, failurePolicy Fail) of warden-policy/policies, from the working tree"}
    run_attacks.setup_lab()
    try:
        c0 = counters()
        rs = {"apiVersion": "apps/v1", "kind": "ReplicaSet", "metadata": {"name": "e8-rs", "namespace": NS},
              "spec": {"replicas": 2, "selector": {"matchLabels": {"app": "e8-rs"}},
                       "template": {"metadata": {"labels": {"app": "e8-rs"}}, "spec": pod_spec(image)}}}
        t0 = time.time()
        kubectl("create", "-f", "-", stdin=json.dumps(rs))
        rec["replicaset_admission_s"] = round(time.time() - t0, 2)
        rec["replicaset_2_pods_ready_s_after_admission"] = wait_ready("app=e8-rs", 2)
        c1 = counters()
        t0 = time.time()
        kubectl("-n", NS, "scale", "rs", "e8-rs", "--replicas=4")
        rec["scale_to_4_ready_s"] = wait_ready("app=e8-rs", 4)
        c2 = counters()
        direct = []
        for i in range(2):
            pod = {"apiVersion": "v1", "kind": "Pod", "metadata": {"name": f"e8-direct-{i}", "namespace": NS,
                                                                    "labels": {"app": "e8-direct"}}, "spec": pod_spec(image)}
            t0 = time.time()
            kubectl("create", "-f", "-", stdin=json.dumps(pod))
            direct.append(round(time.time() - t0, 2))
        rec["direct_pod_admission_s"] = direct
        rec["direct_2_pods_ready_s_after_admission"] = wait_ready("app=e8-direct", 2)
        c3 = counters()
        rec["kyverno_executions"] = {"replicaset_create_and_its_2_pods": delta(c0, c1),
                                     "scale_2_to_4": delta(c1, c2), "two_direct_pods": delta(c2, c3)}
    finally:
        kubectl("-n", NS, "delete", "rs", "e8-rs", "--ignore-not-found", "--wait=false", check=False)
        kubectl("-n", NS, "delete", "pod", "-l", "app=e8-direct", "--ignore-not-found", "--wait=false", check=False)
        run_attacks.teardown_lab()
    out = HUB / "evidence" / "verification" / f"{started.strftime('%Y-%m-%dT%H%M%SZ')}-replicaset-path.json"
    out.write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(rec, indent=1), "\n", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
