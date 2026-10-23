# Warden — System Design

> Status: **Draft v0.1** (2026-10-21). This is the high-level design the four repositories implement.
> Anything here that contradicts [DECISIONS.md](DECISIONS.md) is a bug in this file; a design change needs a new ADR first.
> Versions referenced below are pinned in [versions.yaml](versions.yaml) and were verified on 2026-10-21 ([RESEARCH.md](RESEARCH.md)).

---

## 1. What Warden is

Warden is an internal delivery platform for Kubernetes. It makes two promises and backs each with evidence:

1. **Golden path.** `warden new <service>` produces a repository, build pipeline, deployment manifests,
   dashboards, a catalog entry and a running canary-deployed service. The only manual step is one click to make
   the new image public, which GitHub offers no API for (ADR-028).
2. **Verifiable supply chain.** In workload namespaces, a container runs only if it was built by Warden's own
   build workflow, from a `main`-branch commit of a repository the organisation owns, with a signature, a
   transparency-log entry, an SBOM and SLSA provenance. Everything else is refused at admission.

On top of that: faulty releases roll back automatically, and the whole environment is destroyable and
rebuildable from Git.

The application code is deliberately trivial. **The platform is the product.**

## 2. Goals and non-goals

| ID | Goal | Measured by (see [EVALUATION.md](EVALUATION.md)) |
|----|------|------|
| G1 | One-command service creation | E1: median time `warden new` → healthy pod, manual steps ≤ 1 (package visibility, ADR-028) |
| G2 | Unverifiable artifacts never run | E2: attack suite A01–A12 all denied with the correct reason; 0 false denials |
| G3 | Faulty releases revert without humans | E3: injected-fault releases auto-aborted 10/10; healthy releases 0 false aborts |
| G4 | Self-service database behind one interface | E4: same 10-line manifest provisions on CNPG (local) and Azure PostgreSQL |
| G5 | Delivery performance is measured, not claimed | E5: DORA metrics from real pipeline history |
| G6 | No undocumented manual state | E6: rebuild ledger, median rebuild time, drift = 0 after rebuild |

**Out of scope** (from the synopsis, unchanged): multi-tenancy, secrets management beyond Kubernetes Secrets,
service mesh, multi-region, cost chargeback, production-grade HA.
**Also out of scope** (added): private repositories ([ADR-002](DECISIONS.md#adr-002-all-repositories-are-public)),
runtime threat detection (Falco etc.), Windows containers, multi-cluster promotion.

## 3. Architecture overview

```mermaid
flowchart LR
  dev([Developer]) -->|warden new · git push| svc[svc-* repo]
  subgraph GH[GitHub]
    svc -->|uses @vX.Y.Z| rw[[warden-platform<br/>reusable build workflow]]
    rw -->|push by digest| ghcr[(GHCR<br/>image@sha256 + referrers)]
    rw -->|bot PR: new digest| gitops[(warden-gitops)]
    policy[(warden-policy)]
    infra[(warden-infra)]
  end
  rw -->|keyless sign + attest| sig[Sigstore public good<br/>Fulcio · Rekor]
  subgraph K8S[Cluster — kind locally, AKS in Azure]
    argocd[Argo CD] --> adm{Admission<br/>VAP + Kyverno IVP}
    adm -->|deny| refused[Pod refused]
    adm -->|admit| ro[Argo Rollouts<br/>canary via Gateway API]
    k6[k6 synthetic load] --> gw[Envoy Gateway] --> ro
    ro --> prom[Prometheus]
    prom -->|AnalysisRun| ro
    xp[Crossplane v2] --> cnpg[CloudNativePG]
  end
  gitops -->|pull| argocd
  policy -->|pull| argocd
  infra -->|pull: XRDs + compositions| argocd
  adm -. fetch signatures .-> ghcr
  adm -. trusted root .-> sig
  xp -. azure composition .-> azpg[(Azure PostgreSQL<br/>Flexible Server)]
  tofu[OpenTofu] -->|creates AKS, budget, OIDC| K8S
```

The cluster pulls; CI never pushes to the cluster. CI holds **no cluster credentials** of any kind.

## 4. Repositories and trust boundaries

Warden is a polyrepo on purpose ([ADR-001](DECISIONS.md#adr-001-polyrepo-four-platform-repositories-plus-a-docs-hub)):
each repository is a separate trust boundary with its own reviewers and its own token scopes.

| Repo | Contents | Who may change it | What trusts it |
|------|----------|-------------------|----------------|
| `warden` (this hub) | Design docs, ADRs, threat model, evaluation evidence, workspace tooling | Whole team | Humans only |
| `warden-infra` | OpenTofu (Azure bootstrap, AKS, budget, GitHub→Azure OIDC), kind config, Crossplane XRDs + Compositions, rebuild ledger tooling | Infra owner + 1 reviewer | OpenTofu runs; Argo CD (Crossplane path only) |
| `warden-gitops` | Argo CD root app, platform component Applications (Helm charts pinned), per-cluster overlays, `apps/<svc>/` desired state | Humans via PR; **bot only via digest-only PRs** | Argo CD — this repo *is* the cluster |
| `warden-policy` | ValidatingAdmissionPolicies, Kyverno ImageValidatingPolicies / ValidatingPolicies / PolicyExceptions, policy tests, attack suite | Security owner + 2 reviewers (CODEOWNERS) | Argo CD (policy Applications) |
| `warden-platform` | Reusable build/sign/attest workflow, `warden` CLI (Go), service template, dashboards, alert rules, AnalysisTemplates, k6 profiles, DORA tooling | Platform owner + 1 reviewer; workflow changes need security review | Every service pipeline; admission pins its workflow identity |
| `svc-*` | One per service, generated by `warden new`: app code, a ~15-line caller workflow, `warden.yaml` | Service developers | Nothing trusts it directly; its images are verified |

### Token scopes (least privilege)

| Actor | Credential | Can do | Cannot do |
|-------|-----------|--------|-----------|
| Service CI — build job | `GITHUB_TOKEN` (`contents: read`, `packages: write`) | Push its own image to GHCR | Request an OIDC token; sign; touch gitops |
| Service CI — sign job | `GITHUB_TOKEN` (`id-token: write`, `attestations: write`, `packages: write`) | Obtain a Fulcio cert, sign, attest | Runs **no project code** |
| Service CI — promote job | GitHub App `warden-promoter` installation token, installed on `warden-gitops` only | Open a PR in `warden-gitops` | Merge without the `digest-only` check passing; touch any other repo |
| Argo CD | None needed (public repos, read-only) | Read Git | Write Git |
| Kyverno, kubelet | None needed (public GHCR images, ADR-028) | Pull images and attestations anonymously | Push anything |
| Argo CD Notifications | GitHub App `warden-deployments` (`deployments: write` on `svc-*`) | Record GitHub Deployment statuses (DORA ledger) | Read code, push |
| Infra pipeline | Azure federated credential (OIDC), GitHub environment `azure` with required reviewer | `tofu apply` in the Warden resource group | Anything outside it; no client secret exists |

## 5. Delivery path

```mermaid
sequenceDiagram
  autonumber
  actor Dev as Developer
  participant Svc as svc-* repo
  participant RW as Reusable workflow (warden-platform)
  participant Reg as GHCR
  participant SS as Sigstore (Fulcio/Rekor)
  participant GO as warden-gitops
  participant CD as Argo CD
  participant AD as Admission (VAP + Kyverno)
  participant RO as Argo Rollouts + Prometheus

  Dev->>Svc: PR (build + test + SAST + fs scan; nothing pushed, nothing signed)
  Dev->>Svc: merge to main
  Svc->>RW: workflow_call @vX.Y.Z
  RW->>Reg: [build job] Jib build, push image, output digest
  RW->>RW: [scan job] Syft SBOM (CycloneDX), Trivy vuln report; fail on fixable CRITICAL
  RW->>SS: [sign job] OIDC → Fulcio cert (SAN = reusable workflow ref)
  RW->>Reg: cosign sign; attest provenance (SLSA v1), SBOM, vuln — all as OCI referrers
  SS-->>RW: Rekor inclusion proof (in bundle)
  RW->>GO: [promote job] bot PR: apps/<svc> image digest only
  GO->>GO: digest-only guard check → auto-merge
  CD->>GO: poll (60 s) and sync
  CD->>AD: Rollout creates canary ReplicaSet → Pod CREATE
  AD->>Reg: fetch signature + attestations for digest
  AD-->>CD: admit (or deny with reason)
  RO->>RO: 5% → analysis → 25% → 50% → 100%, abort on SLO breach
```

Design rules that fall out of this path:

- **Sign only on `main`.** PR builds never push and never get an OIDC token. Admission re-checks this from the
  provenance (`ref == refs/heads/main`), so the rule holds even if a workflow is misconfigured.
- **Digest everywhere.** Manifests reference `image@sha256:…`. Tags exist only as human labels on the registry.
- **Build and sign are separate jobs.** Only the sign job has `id-token: write`, and it executes no project code,
  so a malicious build plugin cannot mint a signing certificate. This isolation is what lets us claim
  SLSA v1 **Build Level 3** ([ADR-009](DECISIONS.md#adr-009-platform-owned-reusable-workflow-is-the-only-trusted-builder-slsa-build-l3)).

## 6. Identity and trust model

A Fulcio certificate issued to a GitHub Actions job encodes *which workflow file ran*. For a reusable workflow, the
certificate's subject (SAN) is the **reusable workflow's** ref, not the caller's:

```
https://github.com/WARDEN-CCD/warden-platform/.github/workflows/build-sign-attest.yml@refs/tags/v1.2.0
```

That is exactly what we want: the trusted builder is the platform's workflow, which service repos cannot modify.
But *any* public repository on GitHub can call a public reusable workflow — a confused-deputy risk (T04 in the
[threat model](THREAT_MODEL.md)). So admission checks **two** things:

1. **Who built it** — certificate subject matches the platform workflow at a released tag; issuer is
   `https://token.actions.githubusercontent.com`; a Rekor inclusion proof exists.
2. **What it was built from** — the SLSA provenance, signed by that same identity, says the caller repository is
   `https://github.com/WARDEN-CCD/svc-*` and the ref is `refs/heads/main`. The provenance is generated inside the
   reusable workflow from OIDC claims, so the caller cannot forge it.

Callers reference the reusable workflow by a semver tag (`@v1.2.0`). Those tags are protected by a repository
ruleset (no update, no delete) and published as GitHub immutable releases
([ADR-010](DECISIONS.md#adr-010-reusable-workflow-is-referenced-by-protected-semver-tags)).

## 7. Admission control

Admission is layered so that the cheap invariants survive a Kyverno outage
([ADR-007](DECISIONS.md#adr-007-layered-admission-native-vap-for-invariants-kyverno-for-cryptography)).

| Layer | Engine | Checks | Why here |
|-------|--------|--------|----------|
| 0. Scope | Namespace selector | Applies to **every namespace except** an explicit platform allowlist (`kube-system`, `argocd`, `kyverno`, …) | Default-deny: a new namespace is covered automatically |
| 1. Invariants | Kubernetes `ValidatingAdmissionPolicy` (in-process, GA) | Registry is `ghcr.io/warden-ccd/`; reference is pinned by `@sha256:`; applied to Pods **and** Rollout templates | No webhook to fail; Rollout check makes Argo CD sync show the error early |
| 2. Cryptography | Kyverno `ImageValidatingPolicy` | Signature valid; cert subject + issuer pinned; tlog proof; provenance attestation (builder, source repo, ref); SBOM attestation present; vuln attestation (Audit) | Needs registry + Sigstore trust root |
| 3. Hygiene | Kyverno `ValidatingPolicy` | Non-root, read-only rootfs, resource requests/limits, probes | Golden-path defaults, enforced not just templated |

- **Failure policy:** `Fail` (fail closed) for workload namespaces. Platform namespaces are exempt so the cluster
  can always recover.
- **Policy lifecycle:** all policies start in `Audit` and flip to `Deny` at milestone M3 (week 8–9) once the
  exit criteria in [ROADMAP.md](ROADMAP.md) hold ([ADR-020](DECISIONS.md#adr-020-policies-move-audit--enforce-with-exit-criteria-break-glass-has-an-expiry)).
- **Break glass:** a Kyverno `PolicyException` (CEL type) with an `expires-at` annotation, created only via PR to
  `warden-policy`, reviewed by two people, and reported on the admission dashboard.
- **Kyverno version:** CEL policy types only. `ClusterPolicy` is deprecated in Kyverno 1.19 and is removed in
  1.20 ([ADR-006](DECISIONS.md#adr-006-kyverno-cel-policy-types-only-no-clusterpolicy)).

## 8. GitOps layout

```
warden-gitops/
├── bootstrap/root-app.yaml          # the one object `task up` applies by hand-equivalent (scripted)
├── clusters/
│   ├── local/                       # kind: lite profile, NodePort gateway, CNPG default composition
│   └── azure/                       # AKS: LoadBalancer gateway, Azure DB composition available
├── platform/                        # one Argo CD Application per component, Helm chart versions pinned
│   ├── kyverno/  argo-rollouts/  envoy-gateway/  observability/  crossplane/  cnpg/  k6/
└── apps/<svc>/                      # generated by `warden new`; image digest written by bot PRs only
```

- **App-of-apps** from `bootstrap/root-app.yaml` → `clusters/<name>` → platform Applications. An
  **ApplicationSet** with a Git directory generator creates one Application per `apps/*` directory.
- **Sync waves:** CRDs/operators (0) → policies in Audit (1) → observability (2) → gateway (3) → apps (10).
- **Multi-repo sources:** policy Applications point at `warden-policy`, Crossplane APIs at `warden-infra`,
  AnalysisTemplates/dashboards at `warden-platform`. The gitops repo composes; each repo owns its content.
- **Drift:** `selfHeal: true` and `prune: true` everywhere, so a `kubectl edit` on a policy is reverted
  within one reconcile (tested as attack A12).

## 9. Progressive delivery

Every service gets an Argo Rollouts `Rollout` with the Gateway API traffic-router plugin
([ADR-012](DECISIONS.md#adr-012-gateway-api-envoy-gateway-replaces-ingress)):

```
setWeight 5  → analysis (2 min) → setWeight 25 → analysis (2 min) → setWeight 50 → pause 1 min → 100
```

`ClusterAnalysisTemplate`s live in `warden-platform/observability/analysis/`:

| Metric | Query basis | Pass | Fail |
|--------|-------------|------|------|
| Success rate | Micrometer `http_server_requests_seconds_count`, non-5xx / total, canary pods only | ≥ 99 % | < 95 % |
| Latency p95 | `http_server_requests_seconds_bucket` | < 300 ms | ≥ 500 ms |
| Sample size guard | request count in window | ≥ 200 | — (Inconclusive → rollout pauses, never promotes on silence) |

**Why synthetic load matters.** Canary sample size is `n = weight × rps × window`. At 5 % weight and a 2-minute
window, reaching `n ≥ 200` needs about **35 rps** per service. A k6 `constant-arrival-rate` scenario at 40 rps runs
continuously via the k6-operator ([ADR-015](DECISIONS.md#adr-015-canary-analysis-uses-a-minimum-sample-guard-and-continuous-k6-load)).

**After an abort** traffic is 100 % stable, but Git still names the bad digest. The promote bot opens a revert PR
in `warden-gitops` so Git matches reality again (stretch goal S-3 in the roadmap).

## 10. Self-service database (Crossplane v2)

Developer-facing API — identical on every cluster:

```yaml
apiVersion: platform.warden.dev/v1alpha1
kind: Database
metadata:
  name: books-db
  namespace: svc-books
spec:
  size: small        # small | medium
  version: "17"
```

- **XRD** (`apiextensions.crossplane.io/v2`, namespaced; claims no longer exist in Crossplane v2).
- **Compositions** (pipeline mode, `function-go-templating` + `function-auto-ready`):
  - `database-cnpg` — composes a CloudNativePG `Cluster` directly (Crossplane v2 can compose any Kubernetes
    resource, no provider-kubernetes needed). Default on `local`.
  - `database-azure` — composes `FlexibleServer`, `FlexibleServerDatabase` and a firewall rule from
    `crossplane-contrib/provider-upjet-azure`. Default on `azure` (B1ms, 32 GB).
- **Backend choice is the platform's, not the developer's:** each cluster overlay patches the XRD's default
  composition, so the manifest above never changes.
- **Connection details:** Crossplane v2 removed native XR connection secrets, so both compositions compose a
  `Secret` named `<name>-conn` (`host`, `port`, `dbname`, `username`, `password`, `uri`) in the XR's namespace.

## 11. Scaffolding — the `warden` CLI

Go, single binary, released through Warden's own signed pipeline (dogfooding).
See `warden-platform/cli/README.md` for the full spec.

| Command | Does |
|---------|------|
| `warden new <name> [--db] [--owner <team>]` | Creates `svc-<name>` from the template, applies repo rulesets, opens the `apps/<name>` PR in `warden-gitops`, waits for the first healthy rollout, prints a timing breakdown and appends it to `evidence/scaffold-timings/` |
| `warden verify <image@digest>` | Runs the **same checks as admission** locally and explains each pass/fail — lets a developer see why a deploy would be refused before it is |
| `warden doctor` | Checks local tooling against `versions.yaml`, Docker memory, cluster reachability |
| `warden status <svc>` | Rollout phase, last admission decision, last analysis result |
| `warden dora [--since]` | Computes the DORA metrics from the GitHub Deployments ledger |

What a generated service contains: Spring Boot 4.1 app (Java 25) with Actuator, Micrometer Prometheus and
OpenTelemetry; Jib config (daemonless, reproducible image); a caller workflow; `warden.yaml` (owner, tier, SLO,
`database: true|false`) from which all manifests are rendered; Backstage-compatible `catalog-info.yaml`;
CODEOWNERS; Renovate config; demo fault toggles (`WARDEN_DEMO_ERROR_RATE`, `WARDEN_DEMO_LATENCY_MS`) baked in
at build time so a faulty release is a *real, signed* release.

The four exercise services are created **by `warden new` itself** (tentative names: `books`, `loans`, `members`,
`notify`; `books` uses a `Database`; the call chain gives traces something to show).

## 12. Observability and delivery metrics

- **Metrics:** kube-prometheus-stack (Prometheus, Alertmanager, Grafana). ServiceMonitors come from the template.
- **Traces:** OpenTelemetry Java instrumentation → OTel Collector → Tempo, **full profile only**.
- **Dashboards** (`warden-platform/observability/dashboards/`): service golden signals, rollout timeline,
  admission decisions (Kyverno metrics + PolicyReports), DORA.
- **DORA ledger** ([ADR-019](DECISIONS.md#adr-019-dora-five-metric-model-github-deployments-api-is-the-event-ledger)):
  Argo CD Notifications write a **GitHub Deployment** + status (`success` / `failure`) on the service repo for
  every sync of `apps/<svc>`. A Rollout abort makes the app Degraded → `failure`. `warden dora` reads only the
  GitHub API, so metrics survive a cluster rebuild.

| DORA metric (2024+ model) | Definition used here |
|------|------|
| Deployment frequency | successful production deployments per day, per service |
| Change lead time | first commit of the merged PR → deployment status `success` |
| Change fail rate | deployments with status `failure` ÷ all deployments |
| Failed deployment recovery time | `failure` → next `success` on the same service |
| Deployment rework rate | deployments whose merge commit is a `fix:`/`revert:` within 7 days of a previous deployment ÷ all deployments |

The synopsis promised four metrics; the current DORA model has five, so we report all five and keep the
synopsis' four as the headline.

## 13. Environments and profiles

| | `local` (kind) | `azure` (AKS Free tier) |
|---|---|---|
| Kubernetes | 1.37 (`kindest/node:v1.37.0`, pinned digest) | 1.37 |
| Nodes | 1 control-plane + 1 worker | 2 × `Standard_B2ms` (2 vCPU / 8 GiB) — fits the 4-vCPU B-series quota |
| Gateway exposure | NodePort → kind `extraPortMappings` (80/443) | `LoadBalancer` (one public IP) |
| Database default | CNPG | Azure PostgreSQL Flexible Server B1ms |
| Lifetime | as needed | **ephemeral**: created for a session/demo, destroyed after |
| Profile | `lite` (default) or `full` | `lite` |

`lite` = Argo CD, Argo Rollouts, Kyverno, Envoy Gateway, Prometheus + Grafana, CNPG, Crossplane, k6, four services.
`full` = `lite` + OTel Collector + Tempo + Policy Reporter UI. Memory budgets get validated in spike S2.

## 14. Bootstrap and rebuild

```
task up:local   → kind create → helm install argo-cd (pinned) → kubectl apply root-app (cluster=local) → wait Synced/Healthy → ledger row
task up:azure   → tofu apply (RG, AKS, budget, OIDC) → same bootstrap → ledger row
task down:*     → destroy; nothing survives except Git, GHCR and the tofu state container
task rebuild:*  → down + up, timed
```

Every run appends to `evidence/rebuilds/rebuild-ledger.csv` (timestamp, env, commit SHA of each repo, duration,
result, operator). **Rule:** if a step is not in a Taskfile or in Git, it does not exist. The only out-of-band
inputs are the two GitHub App private keys, read from `~/.warden/` (never in Git).

## 15. Cost guardrails (Azure for Students)

Facts observed on a team member's subscription on 2026-10-21 (see [RESEARCH.md](RESEARCH.md#azure-for-students-subscription-facts)):
allowed regions are `indonesiacentral`, `eastasia`, `indiasouthcentral`, `uaenorth`, `koreacentral`; regional
quota is 6 vCPU total, **4 vCPU for B-series**; AKS 1.37 is available in all of them.

- Region: `indiasouthcentral` (closest to the team); `koreacentral` as fallback.
- 2 × B2ms ≈ US$0.21/h (Linux PAYG, koreacentral reference price). A 4-hour session ≈ US$1; US$100 credit
  covers the semester if clusters are ephemeral. Four members = four subscriptions to rotate between.
- OpenTofu creates a subscription budget with alerts at 25/50/75 % of US$100.
- A scheduled "reaper" workflow in `warden-infra` destroys any cluster older than 8 hours.

## 16. Failure behaviour

| Failure | Behaviour | Acceptable because |
|---------|-----------|--------------------|
| Kyverno down | Workload Pod creation fails closed; VAP still enforces registry + digest | Integrity over availability; system namespaces unaffected |
| Sigstore outage | Signing (and so deploying) stops; running workloads unaffected | Same as any CI outage; admission verification behaviour verified in spike S1 |
| Prometheus down | AnalysisRuns error → rollout pauses/aborts, never promotes | Unknown health must not promote |
| Argo CD down | No reconciliation; cluster keeps last good state | Pull model degrades safely |
| GitHub down | No builds, no deploys | Accepted dependency |

## 17. Open questions (resolved by spikes in ROADMAP weeks 1–3)

| ID | Question | Spike |
|----|----------|-------|
| Q1 | Does Kyverno 1.19.2 IVP find GitHub-generated provenance bundles on GHCR (referrers fallback tag)? | **S1: yes** |
| Q2 | Does `extractPayload()` return the in-toto statement or the predicate? (Kyverno samples disagree) | **S1: the statement** (`.predicate.` paths) |
| Q3 | Does IVP verify Rekor v2 entries written by cosign ≥ 3.1? | **S1:** cosign 3.1.4 still wrote Rekor v1 (`dsse 0.0.1`) entries; verified fine |
| Q4 | Does the `lite` profile fit a 16 GB Windows laptop (WSL2 limit ~10 GB)? | S2 |
| Q5 | Is PostgreSQL B1ms free on the Azure for Students offer, or only on the Free account? | S3 |
| Q6 | Can one Argo CD Notifications GitHub App write Deployments to all `svc-*` repos? | S4 |
| Q7 | GHCR packages pushed by Actions are **private** (S1). Make them public at `warden new`, or give clusters pull credentials? | **Resolved:** public, one UI step at `warden new` ([ADR-028](DECISIONS.md#adr-028-service-images-are-public-on-ghcr-clusters-hold-no-registry-credentials)) |
