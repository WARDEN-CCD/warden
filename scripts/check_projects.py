"""Check that every Argo CD Application fits its AppProject (ADR-029).

Run with a cluster up:  ./.venv/Scripts/python.exe scripts/check_projects.py [--gitops PATH]
Exit code 0 = every resource permitted, every probe denied, every live Application covered.

Standard library only; kubectl turns the YAML into JSON. For each overlay (bootstrap/root-<name>.yaml):
  1. Render the Applications the root Application and the ApplicationSets of clusters/<name>/ produce.
  2. Take each Application's resources from the live Application of the same name and source on the current
     cluster (`.status.resources`), else from its manifests in warden-gitops. Add the Namespace that
     CreateNamespace=true writes.
  3. Test sources, destinations and resources with a copy of Argo CD v3.5.5's rules (IsSourcePermitted,
     isDestinationMatched, IsGroupKindNamePermitted in pkg/apis/application/v1alpha1/app_project_types.go)
     against platform/projects/ as server-side apply would leave them (server dry-run, Argo CD's field manager).
  4. Probe that objects outside each project's role are denied.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from fnmatch import fnmatchcase
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SERVER, SERVER_NAME = "https://kubernetes.default.svc", "in-cluster"
TEMPLATE_RE = re.compile(r"\{\{\s*\.([\w.]+)\s*\}\}")
GITOPS_URL = "https://github.com/WARDEN-CCD/warden-gitops.git"

# (project, group, kind, name, namespace or None): objects each project must refuse.
PROBES = [
    ("default", "", "ConfigMap", "probe", "argocd"),
    ("default", "", "Namespace", "probe", None),
    ("root", "rbac.authorization.k8s.io", "ClusterRoleBinding", "probe", None),
    ("root", "apps", "Deployment", "probe", "argocd"),
    ("warden-gitops", "argoproj.io", "AppProject", "probe", "argocd"),
    ("warden-gitops", "argoproj.io", "ApplicationSet", "probe", "argocd"),
    ("warden-policy", "rbac.authorization.k8s.io", "ClusterRoleBinding", "probe", None),
    ("warden-policy", "apps", "Deployment", "probe", "kyverno"),
    ("warden-policy", "admissionregistration.k8s.io", "ValidatingAdmissionPolicy", "envoy-gateway", None),
    ("warden-policy", "policies.kyverno.io", "GeneratingPolicy", "warden-probe", None),
    ("warden-policy", "policies.kyverno.io", "MutatingPolicy", "warden-probe", None),
    ("warden-policy", "argoproj.io", "AppProject", "warden-policy", "argocd"),
    ("warden-infra", "rbac.authorization.k8s.io", "ClusterRole", "cluster-admin", None),
    ("warden-infra", "rbac.authorization.k8s.io", "ClusterRoleBinding", "probe", None),
    ("warden-infra", "apiextensions.crossplane.io", "CompositeResourceDefinition", "things.example.org", None),
    ("warden-infra", "", "Pod", "probe", "crossplane-system"),
    ("warden-platform", "apps", "Deployment", "probe", "k6-operator-system"),
    ("warden-platform", "", "ConfigMap", "probe", "kube-system"),
    ("warden-platform", "rbac.authorization.k8s.io", "ClusterRole", "probe", None),
    ("platform", "", "ConfigMap", "probe", "svc-books"),
    ("platform", "", "Namespace", "svc-books", None),
    ("apps", "", "Namespace", "kube-system", None),
    ("apps", "rbac.authorization.k8s.io", "RoleBinding", "probe", "svc-books"),
]
# (project, repoURL): sources each project must refuse.
SOURCE_PROBES = [
    ("default", GITOPS_URL),
    ("root", "https://github.com/WARDEN-CCD/warden-platform.git"),
    ("warden-policy", "https://github.com/WARDEN-CCD/warden-infra.git"),
    ("warden-infra", GITOPS_URL),
    ("warden-platform", "https://github.com/WARDEN-CCD/warden-policy.git"),
    ("platform", "https://github.com/WARDEN-CCD/warden-policy.git"),
]


def kubectl(*args: str) -> str:
    return subprocess.run(["kubectl", *args], check=True, capture_output=True, text=True, encoding="utf-8").stdout


def load(path: Path, recursive: bool = False) -> list[dict]:
    """Objects in a manifest file or directory. kubectl prints one JSON document per object, or a List."""
    text = kubectl("create", "--dry-run=client", "-o", "json", "-f", str(path), *(["-R"] if recursive else []))
    objs, pos, decoder = [], 0, json.JSONDecoder()
    while pos < len(text.rstrip()):
        doc, end = decoder.raw_decode(text, pos)
        objs += doc["items"] if doc.get("kind") == "List" else [doc]
        pos = end + len(text[end:]) - len(text[end:].lstrip())
    return objs


def scopes() -> dict[tuple[str, str], bool]:
    """(group, kind) -> namespaced, from the aligned columns of `kubectl api-resources`."""
    head, *rows = kubectl("api-resources").splitlines()
    a, n, k = head.index("APIVERSION"), head.index("NAMESPACED"), head.index("KIND")
    out = {}
    for row in rows:
        api = row[a:n].strip()
        out[(api.split("/")[0] if "/" in api else "", row[k:].strip())] = row[n:k].strip() == "true"
    return out


# --- Argo CD v3.5.5 matching -------------------------------------------------------------------------------

def glob_match(pattern: str, value: str, separator: str = "") -> bool:
    if pattern.startswith("!"):
        return not glob_match(pattern[1:], value, separator)
    star = f"[^{re.escape(separator)}]*" if separator else ".*"
    regex = "".join(star if c == "*" else "." if c == "?" else re.escape(c) for c in pattern)
    return re.fullmatch(regex, value) is not None


def normalize(url: str) -> str:
    return url.strip().lower().removesuffix(".git")


def source_ok(proj: dict, repo: str) -> bool:
    matched = False
    for pattern in proj["spec"].get("sourceRepos") or []:
        norm = "!" + normalize(pattern[1:]) if pattern.startswith("!") else normalize(pattern)
        if glob_match(norm, normalize(repo), "/"):
            matched = True
        elif norm.startswith("!"):
            return False
    return matched


def dest_ok(proj: dict, namespace: str) -> bool:
    matched_any = False
    for item in proj["spec"].get("destinations") or []:
        name_ok = glob_match(item.get("name", ""), SERVER_NAME)
        server_ok = glob_match(item.get("server", ""), SERVER)
        ns_ok = glob_match(item.get("namespace", ""), namespace)
        if (server_ok or name_ok) and ns_ok:
            matched_any = True
        elif (not name_ok and item.get("name", "").startswith("!")) or (
                not server_ok and item.get("server", "").startswith("!") and ns_ok):
            return False
        elif not ns_ok and item.get("namespace", "").startswith("!") and server_ok:
            return False
    return matched_any


def in_list(group: str, kind: str, name: str | None, items: list[dict]) -> bool:
    for item in items:
        if fnmatchcase(kind, item.get("kind", "")) and fnmatchcase(group, item.get("group", "")):
            if name is None or not item.get("name") or fnmatchcase(name, item["name"]):
                return True
    return False


def kind_ok(proj: dict, group: str, kind: str, name: str, namespaced: bool) -> bool:
    spec = proj["spec"]
    if namespaced:
        white, black = spec.get("namespaceResourceWhitelist"), spec.get("namespaceResourceBlacklist") or []
        listed = white is None or (len(white) != 0 and in_list(group, kind, None, white))
        return listed and not in_list(group, kind, None, black)
    white, black = spec.get("clusterResourceWhitelist") or [], spec.get("clusterResourceBlacklist") or []
    return in_list(group, kind, name, white) and not in_list(group, kind, name, black)


def resource_ok(proj: dict, group: str, kind: str, name: str, namespace: str | None) -> bool:
    return kind_ok(proj, group, kind, name, namespace is not None) and (namespace is None or dest_ok(proj, namespace))


# --- Applications ------------------------------------------------------------------------------------------

def render(node, params: dict):
    """Go-template subset the ApplicationSets use: {{ .key }} and {{ .a.b }}, missingkey=error."""
    if isinstance(node, str):
        def lookup(m: re.Match) -> str:
            value = params
            for key in m.group(1).split("."):
                value = value[key]
            return str(value)
        return TEMPLATE_RE.sub(lookup, node)
    if isinstance(node, list):
        return [render(n, params) for n in node]
    if isinstance(node, dict):
        return {k: render(v, params) for k, v in node.items()}
    return node


def generator_params(gen: dict, gitops: Path) -> list[dict]:
    if "list" in gen:
        return gen["list"]["elements"]
    if "git" in gen and set(gen["git"]) <= {"repoURL", "revision", "directories"}:
        return [{"path": {"path": p.relative_to(gitops).as_posix(), "basename": p.name}}
                for d in gen["git"]["directories"] for p in sorted(gitops.glob(d["path"])) if p.is_dir()]
    raise SystemExit(f"unsupported generator: {gen}")


def overlay_apps(gitops: Path, overlay: str) -> list[dict]:
    apps = [o for o in load(gitops / "bootstrap" / f"root-{overlay}.yaml") if o["kind"] == "Application"]
    for path in sorted((gitops / "clusters" / overlay).glob("*.yaml")):
        for obj in load(path):
            if obj["kind"] == "ApplicationSet":
                for gen in obj["spec"]["generators"]:
                    apps += [render(obj["spec"]["template"], p) for p in generator_params(gen, gitops)]
    return apps


def sources(app: dict) -> list[dict]:
    return app["spec"].get("sources") or [app["spec"]["source"]]


def source_key(app: dict) -> tuple:
    s = sources(app)[0]
    return normalize(s["repoURL"]), s.get("path"), s.get("chart"), s.get("targetRevision")


def resources(app: dict, live: dict, gitops: Path, scope: dict) -> tuple[str, list[tuple]]:
    """Resources as (group, kind, name, namespace or None), and where they came from."""
    name, dest = app["metadata"]["name"], app["spec"]["destination"]["namespace"]
    other = live.get(name)
    if other and source_key(other) == source_key(app):
        origin = "live"
        found = [(r.get("group", ""), r["kind"], r["name"], r.get("namespace") or None)
                 for r in other["status"].get("resources", [])]
    elif normalize(sources(app)[0]["repoURL"]) == normalize(GITOPS_URL) and "path" in sources(app)[0]:
        origin = "manifests"
        directory = sources(app)[0].get("directory") or {}
        found = []
        for obj in load(gitops / sources(app)[0]["path"], recursive=bool(directory.get("recurse"))):
            api, kind = obj["apiVersion"], obj["kind"]
            group = api.split("/")[0] if "/" in api else ""
            namespaced = scope.get((group, kind), True)
            ns = (obj["metadata"].get("namespace") or dest) if namespaced else None
            found.append((group, kind, obj["metadata"]["name"], ns))
    else:
        return "unknown", []
    if "CreateNamespace=true" in (app["spec"].get("syncPolicy") or {}).get("syncOptions", []):
        found.append(("", "Namespace", dest, None))
    return origin, found


def check_overlay(gitops: Path, overlay: str, projects: dict, live: dict, scope: dict,
                  deployed: bool) -> tuple[list[str], set]:
    errors, seen = [], set()
    print(f"\noverlay {overlay}: bootstrap/root-{overlay}.yaml + clusters/{overlay}/")
    if not deployed:
        print("  not deployed on this cluster: 'kind-same' = resources of the live Application with the same source")
    print(f"  {'APPLICATION':24} {'PROJECT':16} {'FROM':10} {'RESOURCES':>9}  RESULT")
    for app in overlay_apps(gitops, overlay):
        name, project = app["metadata"]["name"], app["spec"].get("project", "")
        seen.add(name)
        problems = []
        proj = projects.get(project)
        origin, found = resources(app, live, gitops, scope)
        origin = "kind-same" if origin == "live" and not deployed else origin
        if project in ("", "default") or proj is None:
            problems.append(f"project '{project}' is missing or default")
        else:
            problems += [f"source {s['repoURL']} not permitted" for s in sources(app) if not source_ok(proj, s["repoURL"])]
            if not dest_ok(proj, app["spec"]["destination"]["namespace"]):
                problems.append(f"destination namespace {app['spec']['destination']['namespace']} not permitted")
            problems += [f"{g or 'core'}/{k} {n}" + (f" in {ns}" if ns else "") + " not permitted"
                         for g, k, n, ns in found if not resource_ok(proj, g, k, n, ns)]
        if origin == "unknown":
            problems.append("no live Application with the same source and no manifests in warden-gitops")
        print(f"  {name:24} {project:16} {origin:10} {len(found):9d}  {'ok' if not problems else 'FAIL'}")
        errors += [f"{overlay}/{name}: {p}" for p in problems]
    return errors, seen


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--gitops", type=Path, default=ROOT / "warden-gitops", help="warden-gitops checkout")
    args = parser.parse_args()
    gitops = args.gitops.resolve()

    projects = {p["metadata"]["name"]: p for p in json.loads(kubectl(
        "apply", "--server-side", "--force-conflicts", "--field-manager=argocd-controller", "--dry-run=server",
        "-o", "json", "-f", str(gitops / "platform" / "projects")))["items"]}
    live = {a["metadata"]["name"]: a for a in json.loads(kubectl("-n", "argocd", "get", "applications", "-o", "json"))["items"]}
    scope = scopes()
    live_overlay = Path(sources(live["root"])[0]["path"]).name if "root" in live else None
    print(f"check_projects: context {kubectl('config', 'current-context').strip()}, {len(live)} live Applications "
          f"(overlay {live_overlay}); projects from {gitops.name}/platform/projects: {', '.join(sorted(projects))}")

    errors = []
    for bootstrap in sorted((gitops / "bootstrap").glob("root-*.yaml")):
        overlay = bootstrap.stem.removeprefix("root-")
        if not (gitops / "clusters" / overlay).is_dir():
            print(f"\noverlay {overlay}: skipped, clusters/{overlay}/ does not exist in this checkout")
            continue
        found, seen = check_overlay(gitops, overlay, projects, live, scope, overlay == live_overlay)
        errors += found
        if overlay == live_overlay:
            errors += [f"{overlay}: live Application {n} is not produced by the overlay" for n in sorted(set(live) - seen)]

    denied = sum(not resource_ok(projects[p], g, k, n, ns) for p, g, k, n, ns in PROBES)
    denied += sum(not source_ok(projects[p], repo) for p, repo in SOURCE_PROBES)
    errors += [f"probe: {p} permits {g or 'core'}/{k} {n}" + (f" in {ns}" if ns else "")
               for p, g, k, n, ns in PROBES if resource_ok(projects[p], g, k, n, ns)]
    errors += [f"probe: {p} permits source {repo}" for p, repo in SOURCE_PROBES if source_ok(projects[p], repo)]
    print(f"\nprobes: {denied}/{len(PROBES) + len(SOURCE_PROBES)} out-of-role objects and sources denied")

    for e in errors:
        print(f"  ERROR {e}")
    print("check_projects: OK" if not errors else f"check_projects: FAILED ({len(errors)} errors)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
