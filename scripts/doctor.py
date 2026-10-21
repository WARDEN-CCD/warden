"""Check local tooling against versions.yaml.

Run:  ./.venv/Scripts/python.exe scripts/doctor.py
Exit code 1 if a required tool is missing or Docker is not running.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent

# How to ask each tool for its version. Output is searched for the first version-looking token.
VERSION_ARGS = {
    "docker": ["version", "--format", "{{.Client.Version}}"],
    "git": ["--version"],
    "gh": ["--version"],
    "kind": ["version"],
    "kubectl": ["version", "--client"],
    "helm": ["version", "--short"],
    "task": ["--version"],
    "tofu": ["version"],
    "az": None,  # `az version` is slow; presence is enough
    "cosign": ["version"],
    "kyverno": ["version"],
    "chainsaw": ["version"],
    "zizmor": ["--version"],
    "go": ["version"],
    "java": ["-version"],
    "mvn": ["-v"],
}
VERSION_RE = re.compile(r"v?(\d+)(?:\.(\d+))?(?:\.(\d+))?")


def run(cmd: list[str], timeout: int = 20) -> str:
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return (res.stdout or "") + (res.stderr or "")
    except (OSError, subprocess.TimeoutExpired):
        return ""


def major_minor(text: str) -> tuple[int, ...] | None:
    """(major, minor), or (major,) when the text has no minor part, e.g. java "25"."""
    m = VERSION_RE.search(text)
    if not m:
        return None
    return (int(m.group(1)),) if m.group(2) is None else (int(m.group(1)), int(m.group(2)))


def check_tool(name: str, spec: dict) -> tuple[str, str, str]:
    exe = shutil.which(name)
    wanted = str(spec["version"])
    if not exe:
        return ("MISSING" if spec.get("required") else "absent", "-", wanted)
    args = VERSION_ARGS.get(name)
    if args is None:
        return ("ok", "present", wanted)
    out = run([exe, *args])
    found_mm = major_minor(out)
    found = VERSION_RE.search(out).group(0) if found_mm else "?"
    if wanted == "any" or not found_mm:
        return ("ok", found, wanted)
    want_mm = major_minor(wanted)
    if want_mm is None:
        return ("ok", found, wanted)
    found_mm = found_mm[: len(want_mm)]  # wanted "25" compares major only
    if found_mm < want_mm:
        return ("OLDER", found, wanted)
    if found_mm > want_mm:
        return ("newer", found, wanted)
    return ("ok", found, wanted)


def docker_memory_gib() -> float | None:
    exe = shutil.which("docker")
    if not exe:
        return None
    out = run([exe, "info", "--format", "{{.MemTotal}}"]).strip()
    return int(out) / 2**30 if out.isdigit() else None


def main() -> int:
    versions = yaml.safe_load((ROOT / "versions.yaml").read_text(encoding="utf-8"))
    failed = False

    print(f"{'tool':<10} {'status':<8} {'found':<12} wanted")
    for name, spec in versions["tools"].items():
        status, found, wanted = check_tool(name, spec)
        failed |= status == "MISSING"
        print(f"{name:<10} {status:<8} {found:<12} {wanted}")

    mem = docker_memory_gib()
    if mem is None:
        print("\nDocker daemon: NOT RUNNING - start Docker Desktop before using kind.")
        failed = True
    else:
        verdict = "ok" if mem >= 8 else "LOW - kind 'lite' profile needs ~8 GiB (spike S2 will refine)"
        print(f"\nDocker memory: {mem:.1f} GiB ({verdict})")

    if sys.platform == "win32":
        wslconfig = Path(os.environ.get("USERPROFILE", "~")) / ".wslconfig"
        if not wslconfig.exists() or "memory" not in wslconfig.read_text(encoding="utf-8", errors="ignore"):
            print("Hint: set memory=10GB (or more) under [wsl2] in %USERPROFILE%\\.wslconfig, then `wsl --shutdown`.")

    print("\ndoctor: " + ("FAILED (required tools missing or Docker down)" if failed else "OK"))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
