"""Workspace consistency checks for Warden.

Run from anywhere:  ./.venv/Scripts/python.exe scripts/verify.py
Exit code 0 = no errors (warnings allowed), 1 = errors.

Checks:
  1. Every YAML file parses (multi-document).
  2. Every third-party GitHub Action is pinned to a full commit SHA (ADR-011), and the SHA matches
     versions.yaml when the action is listed there. Org reusable workflows may use a semver tag (ADR-010).
  3. Relative Markdown links (and #anchors) resolve.
  4. Threat IDs referenced by policies (annotation warden.dev/threat-ids) exist in THREAT_MODEL.md.
  5. Forbidden kinds: Kyverno ClusterPolicy/Policy (ADR-006) and Ingress (ADR-012).
  6. Manifests under warden-gitops/apps/ reference images by digest.
  7. Policy exempt-namespace lists equal workspace.yaml `platformNamespaces` (ADR-007).
  8. Every kind node image equals versions.yaml `kubernetes.kindNodeImage`.
  9. ApplicationSet chart versions and Crossplane Function packages equal versions.yaml.
 10. Every Kyverno ImageValidatingPolicy sets mutateDigest: false (finding from attack A01).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", "target", ".terraform", "dist"}

SHA_RE = re.compile(r"^[0-9a-f]{40}$")
SEMVER_TAG_RE = re.compile(r"^v\d+\.\d+\.\d+$")
USES_RE = re.compile(r"^\s*(?:-\s*)?uses:\s*['\"]?([^\s'\"#]+)['\"]?\s*(#.*)?$")
LINK_RE = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
THREAT_ROW_RE = re.compile(r"^\|\s*(T\d{2})\s*\|", re.MULTILINE)
DIGEST_RE = re.compile(r"@sha256:[0-9a-f]{64}$")

errors: list[str] = []
warnings: list[str] = []


def rel(p: Path) -> str:
    return p.relative_to(ROOT).as_posix()


def walk(suffixes: tuple[str, ...]) -> list[Path]:
    out = []
    for p in ROOT.rglob("*"):
        if any(part in SKIP_DIRS for part in p.relative_to(ROOT).parts):
            continue
        if p.is_file() and p.suffix.lower() in suffixes:
            out.append(p)
    return sorted(out)


PLACEHOLDER_RE = re.compile(r"\[\[\s*\.(\w+)\s*\]\]")
PLACEHOLDER_VALUES = {"Org": "WARDEN-CCD", "PlatformRef": "v0.0.0", "Digest": "sha256:" + "0" * 64}


def read_text(path: Path) -> str:
    """File text; `warden new` templates ([[ .Name ]] placeholders) are rendered with sample values first, so
    their YAML structure and action pins are checked like any other file."""
    text = path.read_text(encoding="utf-8")
    if "/templates/" in "/" + rel(path):
        text = PLACEHOLDER_RE.sub(lambda m: PLACEHOLDER_VALUES.get(m.group(1), "sample"), text)
    return text


def load_yaml_docs(path: Path) -> list:
    return [d for d in yaml.safe_load_all(read_text(path)) if d is not None]


# --- 1. YAML parses -------------------------------------------------------------------------------
def check_yaml() -> dict[Path, list]:
    parsed = {}
    for p in walk((".yaml", ".yml")):
        try:
            parsed[p] = load_yaml_docs(p)
        except yaml.YAMLError as exc:
            errors.append(f"{rel(p)}: YAML does not parse: {exc}".splitlines()[0])
    return parsed


# --- 2. Action pinning ----------------------------------------------------------------------------
def check_actions(org: str, pinned: dict) -> None:
    for p in walk((".yaml", ".yml")):
        if "/.github/workflows/" not in "/" + rel(p):
            continue
        for lineno, line in enumerate(read_text(p).splitlines(), 1):
            m = USES_RE.match(line)
            if not m:
                continue
            ref, comment = m.group(1), m.group(2)
            where = f"{rel(p)}:{lineno}"
            if ref.startswith("./") or ref.startswith("docker://"):
                continue
            if "@" not in ref:
                errors.append(f"{where}: '{ref}' has no ref; pin to a commit SHA")
                continue
            name, version = ref.rsplit("@", 1)
            owner_repo = "/".join(name.split("/")[:2])
            if owner_repo.split("/")[0] in (org, "WARDEN_ORG") and ".github/workflows/" in name:
                if not (SEMVER_TAG_RE.match(version) or SHA_RE.match(version)):
                    errors.append(f"{where}: org reusable workflow must use a vX.Y.Z tag (ADR-010), got '{version}'")
                continue
            if not SHA_RE.match(version):
                errors.append(f"{where}: '{ref}' is not pinned to a full commit SHA (ADR-011)")
                continue
            if not comment:
                warnings.append(f"{where}: add a '# vX.Y.Z' comment after the SHA for '{owner_repo}'")
            expected = pinned.get(owner_repo, {}).get("sha")
            if expected and expected != version:
                errors.append(f"{where}: SHA for {owner_repo} differs from versions.yaml ({expected[:12]}...)")


# --- 3. Markdown links ----------------------------------------------------------------------------
def github_slug(text: str) -> str:
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)  # [label](url) -> label
    text = text.replace("`", "").strip().lower()
    text = re.sub(r"[^\w\- ]", "", text)
    return text.replace(" ", "-")


def markdown_lines(path: Path) -> list[str]:
    """Lines outside fenced code blocks."""
    out, fenced = [], False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if not fenced:
            out.append(line)
    return out


_anchor_cache: dict[Path, set[str]] = {}


def anchors(path: Path) -> set[str]:
    if path not in _anchor_cache:
        seen: dict[str, int] = {}
        result = set()
        for line in markdown_lines(path):
            m = HEADING_RE.match(line)
            if not m:
                continue
            slug = github_slug(m.group(2))
            n = seen.get(slug, 0)
            result.add(slug if n == 0 else f"{slug}-{n}")
            seen[slug] = n + 1
        _anchor_cache[path] = result
    return _anchor_cache[path]


def check_links() -> None:
    for md in walk((".md",)):
        for line in markdown_lines(md):
            for target in LINK_RE.findall(line):
                if re.match(r"^[a-z][a-z0-9+.-]*:", target):  # http:, https:, mailto:
                    continue
                path_part, _, anchor = target.partition("#")
                dest = md if not path_part else (md.parent / path_part).resolve()
                if not dest.exists():
                    errors.append(f"{rel(md)}: broken link '{target}'")
                    continue
                if anchor and dest.suffix.lower() == ".md" and anchor not in anchors(dest):
                    errors.append(f"{rel(md)}: link '{target}' points to a missing heading")


# --- 4/5/6. Manifest rules ------------------------------------------------------------------------
def iter_objects(parsed: dict[Path, list]):
    for path, docs in parsed.items():
        for doc in docs:
            if isinstance(doc, dict):
                yield path, doc


def check_manifests(parsed: dict[Path, list], platform_namespaces: set[str], kind_node_image: str) -> None:
    threat_md = ROOT / "THREAT_MODEL.md"
    known_threats = set(THREAT_ROW_RE.findall(threat_md.read_text(encoding="utf-8"))) if threat_md.exists() else set()

    for path, obj in iter_objects(parsed):
        kind, api = obj.get("kind"), str(obj.get("apiVersion", ""))
        where = rel(path)

        if where.startswith("warden-policy/"):
            selector = ((obj.get("spec") or {}).get("matchConstraints") or {}).get("namespaceSelector") or {}
            for expr in selector.get("matchExpressions") or []:
                if expr.get("key") == "kubernetes.io/metadata.name" and expr.get("operator") == "NotIn":
                    if set(expr.get("values") or []) != platform_namespaces:
                        errors.append(f"{where}: exempt namespaces differ from workspace.yaml platformNamespaces")

        for image in find_images(obj):
            if image.startswith("kindest/node:") and image != kind_node_image:
                errors.append(f"{where}: kind node image differs from versions.yaml kubernetes.kindNodeImage")

        if kind in ("ClusterPolicy", "Policy") and api.startswith("kyverno.io/"):
            errors.append(f"{where}: Kyverno {kind} is removed in 1.20; use policies.kyverno.io CEL types (ADR-006)")
        if kind == "Ingress":
            errors.append(f"{where}: Ingress is not used; write a Gateway API HTTPRoute (ADR-012)")

        annotations = (obj.get("metadata") or {}).get("annotations") or {}
        ids = annotations.get("warden.dev/threat-ids")
        if ids:
            for tid in (t.strip() for t in str(ids).split(",")):
                if tid not in known_threats:
                    errors.append(f"{where}: threat ID '{tid}' not found in THREAT_MODEL.md")

        if rel(path).startswith("warden-gitops/apps/"):
            for image in find_images(obj):
                if not DIGEST_RE.search(image):
                    errors.append(f"{where}: image '{image}' is not pinned by digest")


def find_images(node) -> list[str]:
    found = []
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "image" and isinstance(v, str):
                found.append(v)
            else:
                found.extend(find_images(v))
    elif isinstance(node, list):
        for item in node:
            found.extend(find_images(item))
    return found


def check_pins(parsed: dict[Path, list], versions: dict) -> None:
    """ApplicationSet chart versions and Crossplane Function packages must equal versions.yaml (rule 9)."""
    charts = {c["chart"]: str(c["version"]) for c in versions["charts"].values()}
    components = {k: str(v) for k, v in versions["components"].items()}
    for path, obj in iter_objects(parsed):
        where = rel(path)
        if obj.get("kind") == "ApplicationSet":
            for gen in (obj.get("spec") or {}).get("generators") or []:
                for el in ((gen.get("list") or {}).get("elements")) or []:
                    if "chart" not in el:
                        continue
                    pinned = charts.get(el["chart"])
                    if pinned is None:
                        errors.append(f"{where}: chart '{el['chart']}' is not pinned in versions.yaml")
                    elif str(el.get("version")) != pinned:
                        errors.append(f"{where}: chart '{el['chart']}' {el.get('version')} != versions.yaml {pinned}")
        if obj.get("kind") == "ImageValidatingPolicy":
            vc = (obj.get("spec") or {}).get("validationConfigurations") or {}
            if vc.get("mutateDigest") is not False:
                errors.append(f"{where}: ImageValidatingPolicy must set validationConfigurations.mutateDigest: false "
                              "(Kyverno's default rewrites tags before the digest VAP runs; attack A01)")
        if obj.get("kind") == "Function":
            package = (obj.get("spec") or {}).get("package", "")
            name, _, tag = package.rpartition(":")
            short = name.rsplit("/", 1)[-1]
            if short in components and tag != components[short]:
                errors.append(f"{where}: Function {short}:{tag} != versions.yaml {components[short]}")


def check_placeholders() -> None:
    hits = 0
    for p in walk((".yaml", ".yml", ".md")):
        hits += p.read_text(encoding="utf-8").count("WARDEN_ORG")
    if hits:
        warnings.append(f"'WARDEN_ORG' placeholder appears {hits} times; replace once the GitHub org exists")


def main() -> int:
    workspace = yaml.safe_load((ROOT / "workspace.yaml").read_text(encoding="utf-8"))
    versions = yaml.safe_load((ROOT / "versions.yaml").read_text(encoding="utf-8"))
    org = workspace["github"]["org"]

    parsed = check_yaml()
    check_actions(org, versions["ci"]["actions"])
    check_links()
    check_manifests(parsed, set(workspace["platformNamespaces"]), versions["kubernetes"]["kindNodeImage"])
    check_pins(parsed, versions)
    check_placeholders()

    print(f"verify: {len(parsed)} YAML files, {len(walk(('.md',)))} Markdown files checked")
    for w in warnings:
        print(f"  WARN  {w}")
    for e in errors:
        print(f"  ERROR {e}")
    print("verify: OK" if not errors else f"verify: FAILED ({len(errors)} errors)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
