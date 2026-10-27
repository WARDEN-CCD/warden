# CLAUDE.md — Warden workspace

Warden is a Kubernetes internal delivery platform with a verifiable software supply chain (student project,
4 people, free/student cloud tiers). **The platform is the product; the sample services are deliberately trivial.**

**Resuming? Read [STATUS.md](STATUS.md) first**: current state, the ordered list of what is left, and known traps.

Read before non-trivial work: [DESIGN.md](DESIGN.md) (architecture), [DECISIONS.md](DECISIONS.md) (ADRs),
[THREAT_MODEL.md](THREAT_MODEL.md) (threat → control → test). Plan and milestones: [ROADMAP.md](ROADMAP.md).

## Workspace layout

This folder is the `warden` hub repo. The four platform repos are separate Git repos nested inside it and listed
in `.gitignore`. Each has its own `CLAUDE.md` with repo-specific rules.

```
./                  hub: docs, versions.yaml, workspace.yaml, scripts/, evidence/
warden-infra/       OpenTofu (Azure/AKS), kind config, Crossplane XRDs + Compositions
warden-gitops/      Argo CD desired state (root app, platform apps, apps/<svc>)
warden-policy/      VAP + Kyverno CEL policies, policy tests, attack suite A01–A12
warden-platform/    reusable build-sign-attest workflow, warden CLI (Go), service template, dashboards
```

Run Git commands in the right repo: a change under `warden-policy/` is committed in `warden-policy`, not the hub.

## Non-negotiables

These encode the project's thesis. Violating one is a bug even if everything works.

1. **Digests, not tags.** Every image reference in manifests is `name@sha256:<64 hex>`.
2. **Pin third-party GitHub Actions by full commit SHA** with the version as a trailing comment
   (`uses: actions/checkout@<sha> # v7.0.1`). Resolve SHAs with `gh api`, never invent them.
3. **CI never gets cluster credentials.** No kubeconfig, no `kubectl` in any workflow. CI writes to Git; Argo CD pulls.
4. **Only the `sign-attest` job has `id-token: write`**, and it runs no project code. Workflows declare
   `permissions: {}` at the top and grant per job.
5. **Kyverno: CEL policy types only** (`policies.kyverno.io/v1` `ImageValidatingPolicy`, `ValidatingPolicy`,
   `PolicyException`). Never write `kind: ClusterPolicy` — it is removed in Kyverno 1.20.
6. **Ingress is retired here.** Use Gateway API (`HTTPRoute`) with Envoy Gateway.
7. **Crossplane v2 semantics:** namespaced XRs, no claims, composition functions only, connection Secrets are composed.
8. **No secrets in Git.** Repos are public. Out-of-band secrets live in `~/.warden/`.
9. **Versions come from [versions.yaml](versions.yaml).** Changing a version there is the only way to upgrade.
10. **New component, changed trust boundary, or scope change → write an ADR first** (append to DECISIONS.md).
11. Staged M3 (ADR-032, owner-approved 2026-10-26): the VAPs and `warden-pod-hygiene` enforce (`Deny` + `Audit`).
    The image-verification policies (`ImageValidatingPolicy`) stay in `Audit` with `failurePolicy: Ignore` until
    Kyverno verification is reliable; do not flip them early. Before enforcing anything new, run every legitimate pod
    class under it, including CNPG-managed pods and Jobs (ADR-033): Audit mode hides denials.

## Environment

- Windows 11, Git Bash for shell; Docker Desktop (WSL2) for kind. Python: use `./.venv/Scripts/python.exe`
  (never `.venv/bin/python`, never global pip installs).
- Azure for Students: only regions `indiasouthcentral` (default), `koreacentral`, `eastasia`, `uaenorth`,
  `indonesiacentral`; B-series quota 4 vCPU. AKS clusters are ephemeral — never leave one running.
- `gh` is authenticated; prefer it for GitHub lookups.

## Commands

```bash
./.venv/Scripts/python.exe scripts/verify.py   # workspace checks (YAML, SHA pins, links, threat IDs)
./.venv/Scripts/python.exe scripts/doctor.py   # local tool check against versions.yaml
task up:local / task down:local                # (warden-infra) kind cluster + GitOps bootstrap
```

## Verification

`.claude/verify.cmd` holds the check that must pass before claiming work complete. Run it and show the output.
It is executed by a Stop hook through **cmd.exe**, so it uses backslash paths (`.venv\Scripts\python.exe`), not `./`.
In policy work also run the repo's `kyverno test`; in workflow work run zizmor.

## Writing style for docs

Plain, specific, sourced. State limitations honestly (the evaluation is graded on rigor, not on adjectives).
Facts about tool versions or cloud limits need a date and a source in RESEARCH.md.

## Marked drafts

Files with a `DRAFT` header (policies, workflows, analysis templates) encode the design but have **not been run**.
Spike S1 validates the supply-chain ones. Remove the header only after the file has been exercised on a cluster.
