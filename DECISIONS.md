# Warden — Decision Log

Architecture Decision Records, newest last. Format: lightweight MADR.

**Rules**
- Any change to stack, topology, trust model or scope gets an ADR **before** the code lands.
- Never edit an accepted ADR's decision. Supersede it: add a new ADR and set the old one's status to
  `Superseded by ADR-NNN`.
- Status values: `Proposed` → `Accepted` | `Rejected` | `Superseded by ADR-NNN`. `Accepted (pending Sx)` means
  accepted with a spike that can still overturn it.
- Facts cited here were verified on 2026-10-21; sources are in [RESEARCH.md](RESEARCH.md).

| # | Decision | Status |
|---|----------|--------|
| 001 | Polyrepo: four platform repositories plus a docs hub | Accepted |
| 002 | All repositories are public | Accepted |
| 003 | Kubernetes 1.37 on kind locally and AKS Free tier in Azure | Accepted |
| 004 | Azure region and sizing fit the student subscription; clusters are ephemeral | Accepted |
| 005 | OpenTofu instead of Terraform; OIDC to Azure, no client secrets | Accepted |
| 006 | Kyverno CEL policy types only, no ClusterPolicy | Accepted |
| 007 | Layered admission: native VAP for invariants, Kyverno for cryptography | Accepted |
| 008 | Signature and attestation formats | Accepted (S1 passed) |
| 009 | Platform-owned reusable workflow is the only trusted builder (SLSA Build L3) | Accepted (S1 passed) |
| 010 | Reusable workflow is referenced by protected semver tags | Accepted |
| 011 | Third-party actions pinned by SHA; security tools installed as verified binaries | Accepted |
| 012 | Gateway API (Envoy Gateway) replaces Ingress | Accepted |
| 013 | Promotion is a bot PR guarded by a digest-only check | Accepted |
| 014 | Argo CD app-of-apps with ApplicationSet and sync waves | Accepted |
| 015 | Canary analysis uses a minimum-sample guard and continuous k6 load | Accepted |
| 016 | Crossplane v2 namespaced Database API with two compositions | Accepted |
| 017 | Scaffolder is a Go CLI; Backstage is a stretch goal | Accepted |
| 018 | Service runtime: Java 25, Spring Boot 4.1, Jib | Accepted |
| 019 | DORA five-metric model; GitHub Deployments API is the event ledger | Accepted |
| 020 | Policies move Audit → Enforce with exit criteria; break-glass has an expiry | Accepted |
| 021 | Task (go-task) as the cross-platform task runner | Accepted |
| 022 | Vulnerability gate: enforce in CI, audit at admission | Accepted |
| 023 | Static analysis: Semgrep CE for code, zizmor for workflows | Accepted |
| 024 | Observability: kube-prometheus-stack; tracing only in the full profile | Accepted |
| 025 | Repository rulesets and push protection; temporary admin PR bypass | Superseded in part by ADR-027 |
| 026 | GitHub teams grant write access; approvals count only from team members | Accepted |
| 027 | Project owner bypasses review; history protection has no bypass | Accepted |
| 028 | Service images are public on GHCR; clusters hold no registry credentials | Accepted |
| 029 | One Argo CD AppProject per source repository; the `default` project is locked | Accepted |

---

## ADR-001: Polyrepo: four platform repositories plus a docs hub

- **Status:** Accepted (2026-10-21)
- **Context:** The synopsis commits to four repositories (infrastructure, delivery/GitOps, security policy,
  scaffolding/observability). A monorepo is easier to navigate, but Warden's thesis is about trust boundaries:
  who may change cluster state, who may change policy, which workflow may sign.
- **Decision:** Keep four platform repos — `warden-infra`, `warden-gitops`, `warden-policy`, `warden-platform` —
  plus this `warden` hub for docs, ADRs, evaluation evidence and workspace tooling. Locally the four repos are
  cloned *inside* the hub folder and ignored by the hub's Git. Each generated service gets its own `svc-*` repo.
- **Consequences:** Each repo has its own CODEOWNERS, rulesets and token scope; a CI bot that can write
  `warden-gitops` cannot touch `warden-policy`. Cost: cross-repo changes need coordinated PRs; versions are kept
  consistent via [versions.yaml](versions.yaml) and Renovate.
- **Alternatives:** Monorepo with path-based CODEOWNERS (rejected: one token scope for everything; contradicts
  the synopsis deliverable). Git submodules (rejected: pointer churn, poor tooling on Windows).

## ADR-002: All repositories are public

- **Status:** Accepted
- **Context:** Keyless signing writes to a transparency log. GitHub artifact attestations for **public** repos use
  the Sigstore public-good instance (Fulcio + Rekor). For **private** repos GitHub uses its own Sigstore instance,
  which has no public transparency log — that would break the "log entry" check in the synopsis. Public repos
  also get free GitHub Actions minutes and free GHCR storage.
- **Decision:** All Warden and `svc-*` repos and GHCR packages are public, under one GitHub organisation
  (`WARDEN-CCD`; GHCR paths use the lowercase `warden-ccd`).
- **Consequences:** No secrets in Git, ever (enforced by GitHub push protection + secret scanning). Anyone can
  call our public reusable workflow — handled in ADR-009.

## ADR-003: Kubernetes 1.37 on kind locally and AKS Free tier in Azure

- **Status:** Accepted
- **Context:** Kubernetes 1.37 was released 2026-08-26 (latest patch 1.37.1). kind v0.33.0 ships
  `kindest/node:v1.37.0` as default. AKS offers 1.37 in every region our subscription allows.
- **Decision:** Kubernetes 1.37 everywhere. kind for daily development on all four laptops; AKS Free tier
  (no control-plane charge) for cloud runs and demos. One GitOps tree, two cluster overlays.
- **Consequences:** Local/cloud parity is testable. AKS Free has no uptime SLA — fine, we are not production.

## ADR-004: Azure region and sizing fit the student subscription; clusters are ephemeral

- **Status:** Accepted
- **Context:** On a team member's Azure for Students subscription (checked 2026-10-21): allowed regions are
  `indonesiacentral`, `eastasia`, `indiasouthcentral`, `uaenorth`, `koreacentral`; regional vCPU quota is 6;
  B-series quota is 4 vCPU; DSv5/DASv5 families have quota 0. Credit is US$100/year per student.
  B2ms costs ≈ US$0.104/h (Linux PAYG, koreacentral).
- **Decision:** `indiasouthcentral` (fallback `koreacentral`), one node pool of 2 × `Standard_B2ms`.
  Clusters are created per session and destroyed after; a scheduled reaper destroys any cluster older than 8 h;
  OpenTofu creates a budget with alerts at 25/50/75 %. Each member's subscription is usable, so credit can rotate.
- **Consequences:** The reproducibility claim becomes a daily habit rather than a one-off demo. Burstable VMs can
  throttle under sustained load — canary thresholds are tuned on kind first.
- **Alternatives:** Always-on AKS (rejected: credit gone in ~3 weeks). DigitalOcean / Oracle (the synopsis notes
  both student offers were cut in 2026; not re-evaluated).

## ADR-005: OpenTofu instead of Terraform; OIDC to Azure, no client secrets

- **Status:** Accepted
- **Context:** Terraform is under the BSL; OpenTofu (MPL-2.0, v1.13.1) is a CNCF-hosted drop-in with native state
  encryption. The `azurerm` backend supports OIDC (`use_oidc`, `use_azuread_auth`).
- **Decision:** OpenTofu, pinned in `versions.yaml`. State in Azure Blob Storage with native state encryption.
  GitHub Actions authenticate to Azure with a federated credential bound to the `warden-infra` repo's `azure`
  environment (required reviewer). No service-principal secret is ever created.
- **Consequences:** Team members install `tofu` (Terraform 1.16 is on at least one laptop and would also work
  for local experiments, but CI and docs use `tofu`).
- **Update (2026-10-25), cluster access:** the AKS module disables local accounts and uses Entra ID with Azure
  RBAC. The operator who runs `tofu apply` (plus `extra_admin_object_ids`) gets *Azure Kubernetes Service RBAC
  Cluster Admin* on that cluster only, so access disappears with the cluster and no static kubeconfig exists.
  The API server accepts only `operator_cidrs` (the operator's current IP, set by `task up:azure`); CI never
  talks to the cluster (T09). Operators need `kubelogin`, pinned in `versions.yaml`.

## ADR-006: Kyverno CEL policy types only, no ClusterPolicy

- **Status:** Accepted
- **Context:** Kyverno 1.19 (Aug 2026) deprecated `ClusterPolicy`/`Policy`; removal is planned for **1.20,
  estimated Nov 2026** — inside our project window. `ImageValidatingPolicy` has been GA since 1.17. Kyverno
  1.19.2 (2026-10-20) includes fixes for cosign v3 bundle verification via the GHCR referrers fallback tag.
- **Decision:** Write every policy as `policies.kyverno.io/v1` CEL types: `ImageValidatingPolicy`,
  `ValidatingPolicy`, `PolicyException`. Minimum Kyverno 1.19.2. Upgrade to 1.20 via a normal GitOps PR when it
  ships (a good live demo of platform upgrades).
- **Consequences:** Most blog posts and examples still show `ClusterPolicy verifyImages` — do not copy them.

## ADR-007: Layered admission: native VAP for invariants, Kyverno for cryptography

- **Status:** Accepted
- **Context:** A webhook can be down; an in-process `ValidatingAdmissionPolicy` cannot. Also, an
  `ImageValidatingPolicy` only checks images that match its references — an image from `docker.io` would simply
  not match and be skipped.
- **Decision:** Registry allowlist and digest pinning are a native VAP applied to Pods and Argo Rollouts. Kyverno
  IVP does signatures/attestations. Scope is default-deny: every namespace except an explicit platform list.
- **Consequences:** Two engines to test, but each check lives where it is cheapest and hardest to bypass.

## ADR-008: Signature and attestation formats

- **Status:** Accepted. Spike S1 passed on 2026-10-21 ([evidence/spikes/S1.md](evidence/spikes/S1.md)): Kyverno 1.19.2 verified all four bundles from
  the GHCR fallback tag; entries are `dsse 0.0.1` in Rekor v1. The fallback below was not needed.
- **Context:** cosign v3 (latest v3.1.4) defaults to Sigstore bundles stored as OCI 1.1 referrers and logs to
  Rekor v2. GHCR returns an empty referrers list, so clients use the `sha256-<digest>` fallback tag. Several
  Kyverno issues in 2026 concerned exactly this combination; most are fixed in 1.19.x.
- **Decision:**
  - Signature: `cosign sign` keyless (v3.1.4).
  - Provenance: `actions/attest-build-provenance` (SLSA v1 predicate `https://slsa.dev/provenance/v1`),
    `push-to-registry: true`.
  - SBOM: Syft → CycloneDX JSON, attached with `cosign attest --type cyclonedx`.
  - Vulnerabilities: Trivy → `cosign attest --type vuln`.
- **Fallback if S1 fails:** generate the same predicates but attach all of them with `cosign attest`, and if
  needed sign with the legacy (`.sig`/`.att` tag) layout. The admission checks stay the same.
- **Alternatives:** `slsa-github-generator` (rejected: last release Feb 2025, heavier; GitHub's native
  attestations reach the same SLSA level with ADR-009). Notary v2 (rejected: no keyless + public log story).

## ADR-009: Platform-owned reusable workflow is the only trusted builder (SLSA Build L3)

- **Status:** Accepted. Spike S1 confirmed the certificate subject is the reusable workflow's ref and the
  provenance names the caller repo/ref ([evidence/spikes/S1.md](evidence/spikes/S1.md)).
- **Context:** GitHub documents that artifact attestations alone give SLSA v1 Build L2, and that building inside a
  shared reusable workflow gives Build L3 by isolating the build definition from the caller. For a reusable
  workflow, the Fulcio certificate subject is the *reusable* workflow's ref. Any public repo can call a public
  reusable workflow (confused deputy).
- **Decision:**
  1. `warden-platform/.github/workflows/build-sign-attest.yml` is the only workflow whose identity admission trusts.
  2. It has three jobs: `build` (no OIDC), `scan`, `sign-attest` (`id-token: write`, runs no project code).
  3. Admission checks the cert subject **and** the provenance's caller repository (`WARDEN-CCD/svc-*`) and ref
     (`refs/heads/main`).
- **Consequences:** Services cannot customise their build beyond declared inputs. That is the point of a golden
  path; escape hatches need an ADR.

## ADR-010: Reusable workflow is referenced by protected semver tags

- **Status:** Accepted
- **Context:** The certificate subject contains whatever ref the caller used. Branch refs move; SHA refs make the
  admission identity change on every platform commit.
- **Decision:** Callers use `@vMAJOR.MINOR.PATCH`. In `warden-platform`, a tag ruleset blocks updates and
  deletion of `v*` tags and releases are published as immutable releases. Admission allows
  `@refs/tags/v<semver>` only. Renovate bumps callers.
- **Consequences:** Releasing the platform workflow is a deliberate act — which is exactly the property the
  third-party incidents in 2025–2026 lacked.

## ADR-011: Third-party actions pinned by SHA; security tools installed as verified binaries

- **Status:** Accepted
- **Context:** In March 2026 attackers repointed 76 of 77 version tags of `aquasecurity/trivy-action`; in 2025
  `tj-actions/changed-files` was compromised the same way; more tag-repoint incidents followed in 2026
  (see [THREAT_MODEL.md](THREAT_MODEL.md)). A supply-chain platform that runs unpinned actions would refute its
  own thesis.
- **Decision:** Every third-party `uses:` is pinned to a full 40-character commit SHA with the version in a
  comment. `scripts/verify.py` fails otherwise; zizmor runs in every repo's CI; Renovate updates pins.
  Trivy, Syft and cosign are installed as release binaries whose checksum files are verified with
  `cosign verify-blob` against the publisher's Sigstore bundle — not through wrapper actions.
- **Consequences:** Slightly more YAML. Updates arrive as reviewable Renovate PRs.

## ADR-012: Gateway API (Envoy Gateway) replaces Ingress

- **Status:** Accepted
- **Context:** The synopsis lists an Ingress per service. The community ingress-nginx project was retired in
  March 2026 (no further releases or security fixes). Gateway API (v1.6) is the Kubernetes successor, and Argo
  Rollouts has an official Gateway API traffic-router plugin (v0.17.0).
- **Decision:** Envoy Gateway (v1.9.2) as the Gateway API implementation; each service gets an `HTTPRoute`;
  canary weights are set on the route by the Rollouts plugin.
- **Consequences:** Precise traffic percentages (replica-count canaries cannot do 5 % with 2 pods). Not a
  service mesh — east-west traffic is unaffected, consistent with scope.

## ADR-013: Promotion is a bot PR guarded by a digest-only check

- **Status:** Accepted
- **Context:** CI must update the desired digest in `warden-gitops` without being able to change anything else
  (for example, disabling a policy Application).
- **Decision:** The promote job uses a GitHub App installed only on `warden-gitops` to open a PR. A required
  status check, `digest-only`, passes only if the diff changes exactly one `image@sha256:` value under
  `apps/<svc>/`. With the check green, the PR auto-merges. Humans' PRs need review as usual.
- **Consequences:** Adds ~1 minute to lead time; gives an audit trail per deployment.

## ADR-014: Argo CD app-of-apps with ApplicationSet and sync waves

- **Status:** Accepted
- **Decision:** One root Application per cluster; platform components as individual Applications with pinned
  Helm chart versions; an ApplicationSet (Git directory generator) for `apps/*`; sync waves CRDs → policies
  (Audit) → observability → gateway → apps; `selfHeal` and `prune` on; reconciliation timeout 60 s.
- **Alternatives:** Flux (rejected: the synopsis names Argo CD, and Argo Rollouts integrates natively).

## ADR-015: Canary analysis uses a minimum-sample guard and continuous k6 load

- **Status:** Accepted
- **Context:** A 5 % canary with little traffic produces analyses based on a handful of requests.
- **Decision:** Every AnalysisTemplate has a request-count guard (≥ 200 requests in the window, else
  Inconclusive → the rollout pauses). The k6-operator runs a 40 rps `constant-arrival-rate` scenario per service
  continuously. Thresholds start at success ≥ 99 % and p95 < 300 ms and are tuned in week 7–8.
- **Consequences:** Rollout decisions are defensible statistically, and the evaluation can state its sample sizes.

## ADR-016: Crossplane v2 namespaced Database API with two compositions

- **Status:** Accepted
- **Context:** Crossplane v2 (latest v2.4.2) removed claims, made XRs namespaced, removed native XR connection
  secrets and native patch-and-transform, and can compose arbitrary Kubernetes resources.
- **Decision:** XRD `Database` (`platform.warden.dev/v1alpha1`, namespaced). Compositions `database-cnpg`
  (CloudNativePG `Cluster`) and `database-azure` (`provider-upjet-azure` from crossplane-contrib), both pipeline
  mode with `function-go-templating`; each composes a `<name>-conn` Secret. Each cluster overlay sets the default
  composition, so the developer manifest is identical everywhere.
- **Consequences:** Upbound's official provider packages may need a subscription for some versions; the
  crossplane-contrib Upjet provider avoids that.

## ADR-017: Scaffolder is a Go CLI; Backstage is a stretch goal

- **Status:** Accepted
- **Context:** Backstage (v1.56) is the common portal but needs a database, auth and ~1–2 GB of RAM — heavy on a
  4-vCPU budget, and the synopsis promises "one command", not a portal.
- **Decision:** `warden` CLI in Go (cobra, go-github, sigstore-go), templates embedded with `go:embed`, released
  with GoReleaser through Warden's own signing pipeline. Generated services include Backstage-compatible
  `catalog-info.yaml`, so a portal can be added later without changing services.
- **Consequences:** The comparison with CNOE idpbuilder (which ships Backstage) should note the trade-off honestly.

## ADR-018: Service runtime: Java 25, Spring Boot 4.1, Jib

- **Status:** Accepted
- **Context:** Spring Boot 4.1.1 is current (3.5 OSS support ended June 2026). Java 25 is the current LTS.
  Jib builds OCI images without a Docker daemon and with reproducible timestamps.
- **Decision:** Java 25 (Temurin), Spring Boot 4.1.x, Maven wrapper, Jib (`jib-maven-plugin` 3.5.x); base image
  pinned by digest. Micrometer Prometheus registry + Actuator; OpenTelemetry for traces.
- **Consequences:** Team members need JDK 25 (one laptop currently has 17). Reproducible images enable a stretch
  goal: rebuild the same commit and assert an identical digest.

## ADR-019: DORA five-metric model; GitHub Deployments API is the event ledger

- **Status:** Accepted
- **Context:** DORA's current model has five metrics: deployment frequency, change lead time, failed deployment
  recovery time (renamed from time to restore), change fail rate, and deployment rework rate (added 2024).
  Metrics stored in-cluster would vanish on every rebuild.
- **Decision:** Argo CD Notifications create GitHub Deployments and statuses on each service repo (via a GitHub
  App with `deployments: write`). `warden dora` computes all five from the GitHub API. The synopsis' four remain
  the headline numbers.
- **Consequences:** The cluster holds one narrowly scoped credential (documented in the threat model).

## ADR-020: Policies move Audit → Enforce with exit criteria; break-glass has an expiry

- **Status:** Accepted
- **Decision:** All admission policies are `Audit` until milestone M3. Switch to `Deny` when: (a) 5 consecutive
  legitimate deployments of all four services show zero audit violations; (b) attack suite A01–A12 shows the
  expected violation for each. Break-glass = a CEL `PolicyException` merged via PR in `warden-policy` with an
  `warden.dev/expires-at` annotation; a scheduled job opens an issue when one expires.

## ADR-021: Task (go-task) as the cross-platform task runner

- **Status:** Accepted
- **Context:** The team develops on Windows; `make` is not installed. Task (v3.54) is a single binary that runs
  on Windows, macOS and Linux.
- **Decision:** Each repo has a `Taskfile.yml`. Shell steps are written for Git Bash / POSIX sh; anything more
  complex is a Python script run from the repo's `.venv`.

## ADR-022: Vulnerability gate: enforce in CI, audit at admission

- **Status:** Accepted
- **Context:** A vuln scan is a snapshot. Blocking at admission on CVEs means a rollback to last week's image can
  be refused because of a CVE published yesterday — the worst moment to block.
- **Decision:** CI fails the build on fixable CRITICAL vulnerabilities. The signed vuln attestation is checked at
  admission in `Audit` mode only and surfaced on the admission dashboard. A weekly rescan job re-attests running
  digests.

## ADR-023: Static analysis: Semgrep CE for code, zizmor for workflows

- **Status:** Accepted
- **Context:** The synopsis names Semgrep. Opengrep (v1.31) is a community fork created after Semgrep's 2024 rules
  licence change.
- **Decision:** Semgrep CE with community rules in PR checks; Opengrep is a drop-in alternative if licensing
  becomes a concern. zizmor (v1.31.1) audits GitHub Actions workflows in every repo.

## ADR-024: Observability: kube-prometheus-stack; tracing only in the full profile

- **Status:** Accepted
- **Decision:** kube-prometheus-stack (chart 92.x) for Prometheus/Alertmanager/Grafana in every profile.
  OpenTelemetry Collector + Tempo only in the `full` profile, to keep `lite` within laptop memory.

## ADR-025: Repository rulesets and push protection; temporary admin PR bypass

- **Status:** Accepted (2026-10-21). Exit criteria met the same day: the temporary bypass was removed from all
  five `main` rulesets after two teammates joined (see ADR-026). Bypass and ruleset layout are superseded by
  ADR-027.
- **Context:** The `WARDEN-CCD` org is on GitHub Free with public repos, so repository rulesets and secret
  scanning are available (org-level rulesets are not). On 2026-10-21 the org had a single member; any approval
  requirement would block every merge until teammates join, because authors cannot approve their own PRs.
- **Decision:** Repo-level rulesets on all five repos, created via the REST API:
  - `main` (branch `~DEFAULT_BRANCH`): no deletion, no force-push, linear history, PR required with
    1 approval (2 in `warden-policy`), stale approvals dismissed on push, review threads resolved,
    squash/rebase merges only. The hub also requires the `verify` and `zizmor` checks.
  - `main-digest-only` (`warden-gitops` only): requires the `digest-only` check, **no bypass** (ADR-013).
  - `release-tags` (`refs/tags/v*`): no deletion, no update, no force-push, **no bypass** (ADR-010).
  - Secret scanning and push protection enabled on every repo.
  - **Temporary:** the `main` ruleset lets the `OrganizationAdmin` role bypass in `pull_request` mode, so an admin
    can merge a PR without approval. Direct pushes to `main` stay blocked for everyone (verified: a direct push
    was rejected with `GH013`).
- **Exit criteria for the temporary bypass:** remove it from all five `main` rulesets once at least one more
  team member has joined the org (ROADMAP weeks 1–3). From then on, approvals apply to admins too.
- **Deferred:** `require_code_owner_review` (CODEOWNERS teams do not exist yet); adding the `warden-promoter`
  GitHub App to the `warden-gitops` `main` bypass list (the App does not exist yet).
- **Consequences:** Every change, including automated ones, goes through a PR from now on. Merges by admin
  bypass before the exit criteria are met should be rare and noted in the PR description.

## ADR-026: GitHub teams grant write access; approvals count only from team members

- **Status:** Accepted (2026-10-21)
- **Context:** The org's base permission is `read`. GitHub counts a PR approval toward a ruleset's required
  reviews only if the reviewer has write access, so members with read access cannot unblock merges. CODEOWNERS
  entries are only valid for teams that exist and have write access to the repo.
- **Decision:**
  - Org base permission stays `read`; access is granted through teams.
  - `warden-maintainers`: every developer; `push` (write) on all five repos.
  - `warden-security`: code owners for `warden-policy` and for `warden-platform/.github/workflows/`; `push` on
    those two repos. Membership is chosen by the team (currently only the org owner).
  - Owners stay `admin` via org ownership; nobody else gets `admin` or `maintain`.
- **Follow-ups:** invite the fourth member; require 2FA for the org once every member has enabled it (enabling it
  earlier removes members without 2FA); enable `require_code_owner_review` once `warden-security` has at least two
  members.
- **Consequences:** Adding a person is one team membership, and removing them is one team removal. The
  `warden-policy` rule of 2 approvals means a policy PR needs both other reviewers while the team has three people.
- **Update (2026-10-21):** `warden-security` now has three members (`Legion-Corpse`, `lynch-45`, `SankalpArya-255`).

## ADR-027: Project owner bypasses review; history protection has no bypass

- **Status:** Accepted (2026-10-21). Supersedes the bypass part of ADR-025.
- **Context:** One team member (`Legion-Corpse`, the only org owner) writes most of the project and decided that
  their changes must not wait on reviews. Rulesets cannot name individual users as bypass actors; the
  `OrganizationAdmin` role is used, which today is exactly that one person. A bypass actor skips **every** rule in a
  ruleset, including force-push protection, so the rules were split.
- **Decision:** On all five repos, the default branch is covered by three rulesets:
  - `main-review`: linear history, PR with 1 approval (2 in `warden-policy`), and the hub's `verify` + `zizmor`
    checks. `OrganizationAdmin` bypass **always**: the owner may push directly to `main` and merge PRs without
    approval or passing checks. Everyone else needs a PR and approvals.
  - `main-protection`: no branch deletion, no force-push. **No bypass**, so history stays append-only for everyone.
  - `release-tags` (`v*`): unchanged, **no bypass** (ADR-010).
  - `main-digest-only` (`warden-gitops`): currently **no bypass**, so the owner's direct pushes to gitops `main` are
    rejected (the required check only runs on PRs). The owner's PRs there pass the check automatically and can be
    merged without approval. Adding an owner bypass is pending.
- **Consequences:**
  - The owner's changes reach `main` unreviewed. Threat T17 now explicitly includes the owner account; mitigations
    are 2FA on that account, CI still running on every push, append-only history, and admission control, which
    still verifies everything that gets built: provenance proves where an image came from, not that its code was
    reviewed.
  - Any future org owner gains the same bypass. Promote someone to owner only deliberately.
  - For the evaluation, report which merges were reviewed and which went in through the owner bypass.


## ADR-028: Service images are public on GHCR; clusters hold no registry credentials

- **Status:** Accepted (2026-10-23)
- **Context:** Spike S1 found that a GHCR package pushed by GitHub Actions starts **private**, even when its
  repository is public: the packages API reports `visibility=private` and an anonymous manifest fetch returns
  HTTP 403 ([evidence/spikes/S1.md](evidence/spikes/S1.md)). The GitHub REST API for packages has no endpoint
  that changes visibility. Its 27 endpoints are all GET, POST or DELETE (checked 2026-10-23), so visibility can only
  be changed in the web UI. Two ways out:
  1. make each service's package public once;
  2. keep packages private and give every cluster a registry credential, used by Kyverno (`credentials`) and the
     kubelet (`imagePullSecrets`), refreshed from a GitHub App because installation tokens expire after an hour.
- **Decision:** Option 1. Every `svc-*` image is public. `warden new` handles the one UI step:
  1. After the first image push, it prints the package settings URL
     (`https://github.com/orgs/WARDEN-CCD/packages/container/svc-<name>/settings`) and opens it in the browser.
  2. It waits until an **anonymous** manifest fetch for the new digest succeeds, so the step cannot be skipped
     silently.
  3. It records the step in the scaffold timing JSON as `manual_steps: 1` with its duration.
- **Consequences:**
  - Clusters hold **no registry credential**: nothing to steal, rotate or refresh, and Kyverno and the kubelet pull
    anonymously. This fits the "CI and clusters hold no standing credentials" line of the threat model.
  - Image contents are public. That adds nothing beyond the already-public source repos, and images never contain
    secrets (ADR-002).
  - Goal G1 / evaluation E1 now allows **one** manual step per new service, and reports it rather than hiding it.
    If GitHub adds a visibility API, `warden new` automates it and E1 returns to zero.
  - The IVP drafts stay credential-free (no `credentials` block). The S1 harness used credentials only because
    its package is private.
- **Alternatives:** Option 2 (rejected: adds a standing, refreshing secret to every cluster for no security gain on
  already-public code). Org-level default visibility (rejected: GitHub offers no such setting for packages created
  by Actions).
- **Update (2026-10-24), prerequisite found while scaffolding svc-books:** by default the organisation only lets
  packages be *private*, so the "Public" option is greyed out ("Setting is disabled by organization
  administrators"), even for owners. An org owner must enable it once: Organization settings → Packages →
  **Package creation → Public**. Like package visibility, this setting has no REST API, so it joins the
  week-1 org setup checklist (ROADMAP). It is a one-time org setting, not a per-service step.
- **Update (2026-10-25), measured:** with that org setting on, a package pushed by a public repo's build is
  public from the first push (it inherits the repository's visibility). `warden new` for loans, members and
  notify found the image anonymously on its first check and recorded `manual_steps: 0`
  ([evidence/scaffold-timings](evidence/scaffold-timings/)). E1 is back to **zero** manual steps per service.
  `warden new` keeps the anonymous-fetch check; the settings-URL prompt appears only if that check fails.

## ADR-029: One Argo CD AppProject per source repository; the `default` project is locked

- **Status:** Accepted (2026-10-25)
- **Context:** An automated security review found that every Application outside `apps/*` runs in Argo CD's
  `default` project: the root Application, the nine Helm charts (`platform` ApplicationSet) and the seven
  Git-sourced configuration Applications (`config` ApplicationSet, in `warden-gitops/clusters/local/config.yaml`
  and its AKS copy in warden-gitops#17). Argo CD creates `default` with `sourceRepos: ['*']`, every destination and
  every kind, cluster-scoped included (`server/server.go` `initializeDefaultProject`, v3.5.5). A change merged to
  `warden-policy`, `warden-infra` or `warden-platform` could therefore create anything Argo CD can: a
  `ClusterRoleBinding` to `cluster-admin`, a Pod in a namespace the image policies exempt (every config Application
  targets an exempt platform namespace), or an `AppProject` that widens itself. Each of those repos was as powerful
  as `warden-gitops`, which breaks the per-repo trust boundaries of DESIGN §4 (ADR-001). Only service Applications
  (project `apps`) were restricted.
  - **What the config Applications manage**, from `.status.resources` on kind (2026-10-25; the same set before and
    after a rebuild from Git):

    | Application | Source | Cluster-scoped | Namespaced |
    |-------------|--------|----------------|------------|
    | `policies` | warden-policy | 3 ValidatingAdmissionPolicy, 3 ValidatingAdmissionPolicyBinding, 2 ImageValidatingPolicy, 1 ValidatingPolicy (all `warden-*`) | none |
    | `crossplane-api` | warden-infra | CompositeResourceDefinition `databases.platform.warden.dev`, Composition, 2 Function, ClusterRole `crossplane-compose-cnpg` | none |
    | `observability` | warden-platform | ClusterAnalysisTemplate `warden-canary` | 3 ConfigMap in `monitoring` |
    | `load` | warden-platform | none | ConfigMap, k6 TestRun in `k6-operator-system` |
    | `gateway` | warden-gitops | GatewayClass | Gateway in `envoy-gateway-system` |
    | `local-config` | warden-gitops | none | EnvoyProxy in `envoy-gateway-system` |
    | `projects` | warden-gitops | none | AppProject in `argocd` |
    | `root` | warden-gitops | none | 3 ApplicationSet, 1 Secret (OCI repository entry) in `argocd` |

  - **Argo CD v3.5.5 behaviour this relies on** (argo-cd tag `v3.5.5`: `IsGroupKindNamePermitted` and
    `IsSourcePermitted` in `pkg/apis/application/v1alpha1/app_project_types.go`, `validateSyncPermissions` in
    `controller/sync.go`, `util/argo/argo.go`, `gitops-engine/pkg/sync/sync_context.go`):
    1. Every source of a multi-source Application must match `sourceRepos`, including a `ref: values` source.
    2. A cluster-scoped object needs a `clusterResourceWhitelist` entry. An entry can also restrict the object
       `name` with a glob.
    3. Namespaced kinds are all allowed unless a `namespaceResourceWhitelist` is set or the blacklist matches. The
       namespace of **every** namespaced object must match `destinations`, not only the Application's destination.
    4. The Namespace that `CreateNamespace=true` creates, or labels through `managedNamespaceMetadata`, passes the
       same check as any other cluster-scoped object.
- **Decision:**
  1. One AppProject per source in `warden-gitops/platform/projects/`, shared by both clusters. Kinds come from the
     table above; nothing is pre-authorised for content that does not exist yet.

     | Project | Applications | `sourceRepos` | Namespaces | Cluster-scoped kinds | Namespaced kinds |
     |---------|--------------|---------------|------------|----------------------|------------------|
     | `root` | root, `projects` | warden-gitops | argocd | none | ApplicationSet, AppProject, Secret |
     | `warden-gitops` | `gateway`, `<cluster>-config` | warden-gitops | argocd, envoy-gateway-system | GatewayClass | Gateway, EnvoyProxy |
     | `warden-policy` | `policies` | warden-policy | kyverno | VAP, VAP binding, ImageValidatingPolicy, ValidatingPolicy; names `warden-*` | none |
     | `warden-infra` | `crossplane-api` | warden-infra | crossplane-system | XRD `*.platform.warden.dev`, Composition, Function, ClusterRole `crossplane-compose-*` | none |
     | `warden-platform` | `observability`, `load` | warden-platform | monitoring, k6-operator-system | ClusterAnalysisTemplate `warden-*` | ConfigMap, TestRun |
     | `platform` | the Helm charts | the 8 pinned chart repos + warden-gitops (`$values`) | the 9 chart namespaces | CRD, ClusterRole(Binding), webhook configurations, VAP(+binding), APIService, its own Namespaces by name | all |
     | `apps` (exists) | `svc-*` | warden-gitops | `svc-*` | Namespace, now only named `svc-*` | all but Role, RoleBinding, ResourceQuota, LimitRange |
     | `default` | none | none | none | none | none |

     Name globs are used where a source could otherwise overwrite an object of the same kind that someone else
     owns, such as the ValidatingAdmissionPolicy the Envoy Gateway chart ships, or Crossplane's own ClusterRoles.
  2. Each `config` generator element names its project, and the template uses it. The elements live in
     `warden-gitops`, so a config repository cannot choose its project. Only project `root` may create AppProjects
     and ApplicationSets, and only `warden-gitops` can use it: a config source cannot widen its own project.
  3. Config Applications drop `CreateNamespace=true`, so no config project needs the Namespace kind. Their
     namespaces come from the platform charts. On a fresh cluster a config Application retries (its existing retry
     policy) until the chart has created the namespace, as it already did for missing CRDs.
  4. `root` must exist before the root Application syncs, because Argo CD rejects an Application whose project is
     missing. `bootstrap/root-<cluster>.yaml` therefore applies a copy of `platform/projects/root.yaml` before the
     Application; after bootstrap the `projects` Application owns it. `scripts/verify.py` checks the copies are
     equal.
  5. `default` is locked with the manifest from the Argo CD documentation (empty `sourceRepos` and `destinations`,
     every namespaced kind blacklisted) plus an explicit empty `clusterResourceWhitelist`. Argo CD applies it with
     server-side apply and `--force-conflicts`, so it takes over the fields Argo CD set at creation. `default` and
     `root` carry `Prune=false,Delete=false`: a deleted `default` is recreated fully open the next time the Argo CD
     API server starts, and a deleted `root` would strand the root Application.
  6. `scripts/verify.py` (rule 11) rejects an Application or ApplicationSet in `warden-gitops` whose project is
     missing or `default`. `scripts/check_projects.py` tests every live resource of every Application, and the
     manifests of each overlay, against the project specs, and probes that out-of-role objects are denied.
- **Consequences:**
  - A new kind, name pattern or namespace for a config repository needs a `warden-gitops` PR that changes its
    project. This is intended: widening a repo's reach changes the cluster's trust boundary. Expected first cases:
    a break-glass `PolicyException` (ADR-020) for `warden-policy`, Crossplane `Provider`s for `warden-infra`,
    `PrometheusRule`s for `warden-platform`.
  - **Migration on a running cluster:** apply `bootstrap/root-<cluster>.yaml` once (the command `task up:*` runs)
    **before** merging. It creates `root` and moves the root Application into it. If the PR merges first, the
    `projects` Application can lock `default` while the root Application is still in it; nothing is deleted, but
    syncing stops until that command is run.
  - **Limits.** Argo CD restricts kinds, names and namespaces, not object content:
    1. `warden-infra`'s `crossplane-compose-*` ClusterRole aggregates into Crossplane's own role
       (`rbac.crossplane.io/aggregate-to-crossplane`), and Compositions create objects with Crossplane's
       permissions. A malicious `warden-infra` change can still grant Crossplane any permission and compose any
       object, so that repo stays cluster-admin-equivalent through Crossplane. A ValidatingAdmissionPolicy on the
       rules of `crossplane-compose-*` ClusterRoles would close this; not done here.
    2. `warden-platform`'s k6 `TestRun` names its runner image, and `k6-operator-system` is exempt from image
       verification. A `warden-platform` change can run any image there.
    3. `warden-policy` can still weaken admission. That is its job; T13 and the two-reviewer rule cover it.
    4. `platform` is not least-privilege inside its namespaces: the charts install cluster RBAC and Argo CD itself.
       Its limits are the pinned chart repositories and the platform namespaces.
- **Alternatives:**
  - One shared project for all config Applications (rejected: every config repo would get the union; for example
    `warden-platform` could write ClusterRoles).
  - Argo CD sync impersonation (`destinationServiceAccounts`) enforces with Kubernetes RBAC, whose escalation check
    also limits the *content* of ClusterRoles a source can write (limit 1). It is off here
    (`application.sync.impersonation.enabled: "false"`) and needs a ServiceAccount and RBAC per project. Deferred;
    it would complement the projects, not replace them.
  - Keeping `CreateNamespace=true` and allowing each config project its own Namespace by name (rejected: with
    server-side apply, that lets a config repo relabel a namespace another component owns).

## ADR-030: Admission verifies the signed provenance, not a separate image signature; vulnerability attestation in background

- **Status:** Accepted (2026-10-25)
- **Context:** E8 measured that image verification adds +15.4 s per Pod warm and +23.5 s cold, and a later spot
  check hit the 30 s webhook timeout ([EVALUATION E8](EVALUATION.md#e8--cost-of-verification)). 30 s is the
  Kubernetes maximum `timeoutSeconds`, so at M3 (`Fail` + `Deny`) slow verifications would refuse deployments.
  - **Root cause.** A trace of one supply-chain IVP evaluation showed 95 sequential HTTPS requests. Kyverno
    fetches a new GHCR token for every registry access and initialises the Sigstore TUF client again for each of
    the policy's three cosign verifications (image signature, provenance, SBOM)
    ([trace](evidence/verification/2026-10-24T225231Z-root-cause.json)). The cost is per verification, so the
    lever inside Warden is how many verifications admission performs.
  - **Measured levers** (kyverno CLI, same image, two rounds each):
    - dropping the separate image-signature check: 95 → 65 requests;
    - a pinned `trustedRoot`: no effect, because Kyverno 1.19.2 still made all 18 TUF requests.
  - **Why the image signature is redundant at admission.** Kyverno 1.19.2 verifies every attestation with
    `verify.WithArtifactDigest(<image digest>)` and `cosign.IntotoSubjectClaimVerifier`
    (`pkg/image/verifiers/ivpol/cosign/verifier.go`: lines 179, 189, 209, 333 at tag v1.19.2). A provenance
    attestation therefore verifies only if Warden's build identity signed an in-toto statement whose subject is
    this exact digest. That is what the image signature proves, so checking both costs a full verification and
    adds no assurance.
- **Decision:**
  1. `warden-verify-supply-chain` drops `verifyImageSignatures`. The provenance-signature validation carries
     T02/T03/T07/T08 (no provenance for this digest signed by Warden's build workflow), followed by T04, T05 and
     the SBOM check (T08) as before. The build still signs the image, and `warden verify` still checks that
     signature: it is the developer-facing full check and costs admission nothing.
  2. `warden-vuln-attestation` runs in background scans only (`evaluation.admission.enabled: false`). It was
     already Audit-only by design (ADR-022), so it never blocked anything; at admission it only added latency.
     Findings still reach PolicyReports and the admission dashboard.
- **Consequences:**
  - Verifications per Pod admission: 4 → 2. **Measured (E8, after):** warm p50 15.6 → 14.8 s. In other words,
    no real gain. The webhooks already ran in parallel, so the vulnerability IVP never added latency, and on a
    warm cluster the image-signature check was cheap; the two attestation verifications (~7.5 s each) are the
    cost. What the change buys is less verification work and GHCR traffic per Pod (the vulnerability check no
    longer runs at admission) and a simpler policy, at no loss of assurance. The latency problem is unchanged.
  - A02, A03, A07 and A08 now share one denial path (no Warden-signed provenance for the digest). Each is still
    refused with its expected threat ID.
  - **This alone does not give a safe margin under 30 s.** Two verifications at ~8–12 s each, with network
    variance, are still close to the timeout. Before M3, one of these is still needed:
    - an upstream Kyverno fix (reuse the registry token and the TUF client across verifications);
    - verifying ReplicaSets once per release and exempting the Pods the ReplicaSet controller creates from them
      (a trust-boundary change with its own ADR; Kyverno evaluates no ReplicaSets today).
- **Alternatives rejected:**
  - A pinned trusted root (measured: no effect in 1.19.2).
  - A longer timeout (30 s is the API server maximum).
  - Dropping the SBOM verification (gives up T08 at admission).
  - Merging the vulnerability check into the supply-chain policy (the same number of verifications, and an
    Audit-only check would then sit inside an enforcing policy).

## ADR-031: Verify images once per ReplicaSet; Pods the ReplicaSet controller creates are not re-verified

- **Status:** **Proposed, blocked on Kyverno** (2026-10-25). Not implemented; see *Result* at the end.
- **Context:**
  - **Every Pod pays the full cost.** Image verification costs ~15 s per Pod warm and up to the 30 s webhook
    timeout cold, even after ADR-030 (E8). The cost is per Pod, so every replica, restart, reschedule and canary
    step pays it. At M3 (`Fail`) any of those can be refused when verification is slow, which would turn a node
    drain into an outage.
  - **ReplicaSets are not verified today.** Kyverno's autogen registers webhooks for ReplicaSets but does not
    verify them: a server-side dry-run ReplicaSet with a Warden image is admitted in 0.22 s, the same Pod in
    16.7 s (2026-10-25).
  - **Facts the design rests on.** Argo Rollouts creates one ReplicaSet per revision, and only the ReplicaSet
    controller turns it into Pods. kind's kube-controller-manager runs with `--use-service-account-credentials`,
    so those requests carry `system:serviceaccount:kube-system:replicaset-controller`.
- **Decision:**
  1. A new IVP, `warden-verify-supply-chain-replicasets`, applies the same attestors, attestations and
     validations to `apps/v1` ReplicaSets. A CEL extractor takes the images from `spec.template` (containers and
     init containers). It runs on CREATE, and on UPDATE only when `spec.template` changed, so the scale updates
     Rollouts makes during a canary cost nothing.
  2. `warden-verify-supply-chain` (Pods) skips requests from the ReplicaSet controller's service account. Pods
     created by anyone else are verified as before: users, other controllers, Jobs, CNPG.
- **Why this keeps the guarantee:** a Pod from the ReplicaSet controller is a copy of a template that passed the
  ReplicaSet policy when it was created or last changed. The only way to get an unverified Pod through this path
  is to act as the ReplicaSet controller. Its credentials belong to kube-controller-manager, i.e. the control
  plane, which can bypass admission anyway.
- **Consequences:**
  - Verification happens once per revision instead of once per Pod. Pod admission from a verified ReplicaSet
    drops to the baseline (measured in E8).
  - **ReplicaSets created before this policy were never verified,** so their Pods are now admitted without
    verification. After the policy lands, every service must get a new revision, or the cluster must be rebuilt
    (E6 does that), before M3.
  - **Two Audit-phase gaps get longer.** A ReplicaSet admitted while verification fails open (Audit phase,
    `Ignore`) produces unverified Pods for its whole life, not just for one Pod. This is acceptable only because
    M3 flips to `Fail`.
  - If a cluster runs kube-controller-manager without service-account credentials (requests then come from
    `system:kube-controller-manager`), the exemption simply does not match and Pods are verified as before.
    That is slower, not weaker. AKS must be checked when it is first applied.
  - New attack A14: an unsigned image via a ReplicaSet must be refused at ReplicaSet admission.
- **Alternatives rejected:**
  - Keep per-Pod verification and wait for an upstream Kyverno cache (no fix exists in 1.19.2, and M3 is near).
  - Exempt Pods by an owner-reference label (the requester controls labels and owner references).
  - Verify at the Rollout object (Argo CD syncs Rollouts, but ReplicaSets can be created without one; the
    ReplicaSet is the last object every replicated Pod passes through).
- **Result (2026-10-25): blocked, reverted before it was pushed.**
  - A prototype ReplicaSet IVP, with a CEL `images` extractor over `spec.template`, behaved correctly in the
    kyverno CLI: a signed ReplicaSet passed in 20 s, an unsigned one failed with the T02/T03/T07/T08 message.
  - On the cluster, Kyverno 1.19.2 **admitted the unsigned ReplicaSet in 0.23 s without evaluating the
    policy**. That held even for the attack-lab clone (`Deny`, `Fail`) with its webhook registered for
    `replicasets`, and with `matchConditions` removed.
  - Kyverno's source (`pkg/cel/compiler/images.go`, `pkg/image/verification/evaluator/policy.go` at v1.19.2)
    does inject template extractors for ReplicaSets, so the skip happens before evaluation. The cause was not
    found.
  - Attack A14 caught it. Shipping the Pod exemption without a working ReplicaSet check would have admitted
    every replicated Pod unverified.
  - **What holds today:** Pods are verified individually, including those the ReplicaSet controller creates.
    A14 now asserts that a ReplicaSet with an unsigned template yields no Pod (refused, FailedCreate T02).
  - **Next:** report the ReplicaSet behaviour upstream and retry on a Kyverno release that evaluates IVPs for
    ReplicaSets. Until then the E8 latency stays an M3 blocker.

## ADR-032: Staged M3 - enforce the deterministic policies; image verification stays in Audit

- **Status:** **In effect since 2026-10-26 12:04 UTC**: the owner merged warden-policy PR #1, which implements it.
  The policy lifecycle changed from a single switch to staged enforcement. The first day
  of enforcement exposed a gap in the readiness evidence (Databases could not start): see ADR-033.
- **Context:** ADR-020 switches every policy to `Deny` at once, when (a) five consecutive legitimate deployments
  of each service show zero audit violations and (b) every attack shows its expected violation. Measured on
  2026-10-25 ([evidence/m3](evidence/m3/readiness-20261025T104356Z.json), [EVALUATION](EVALUATION.md#m3-readiness--adr-020-exit-criteria-added-2026-10-25)):
  - criterion (b) holds (the attack suite, 15/15 on kind and on AKS);
  - criterion (a) holds for the registry/digest VAPs (0 violations) and for pod hygiene (10/10 reports pass);
  - criterion (a) **fails for image verification**: 2 of 40 legitimate pods failed on network errors that Kyverno
    1.19.2 does not retry, and four more verifications outlived the 30 s webhook timeout. Under `Deny` + `Fail`
    about one legitimate pod in twenty would be refused.
  The deterministic policies depend on nothing outside the cluster; the verification depends on GHCR and Sigstore.
- **Proposal:**
  1. **Enforce** (`Deny` plus `Audit`, so violations stay on record): `warden-image-references-pods`,
     `warden-image-references-rollouts`, `warden-ephemeral-container-hygiene` (VAP) and `warden-pod-hygiene`
     (Kyverno ValidatingPolicy). Native or in-process, testable offline (`kyverno test`, 27 cases).
  2. **Stay in `Audit`, `failurePolicy: Ignore`:** `warden-verify-supply-chain` and `warden-vuln-attestation`, until
     Kyverno retries transient fetch errors and verification stays well under the 30 s timeout (E8; drafts in
     docs/upstream).
  3. Break-glass for the enforced policies is a PR that sets the binding back to `Audit`.
  4. Update the policy lifecycle guidance in the hub and policy repository documentation.
- **Found while preparing this:** the hygiene rule "containers need readiness and liveness probes" would have refused
  the initdb **Job pod** CloudNativePG runs for every `Database` (a run-to-completion pod has no probes), so no
  database could have been created once enforcement began. Fixed and live in Audit (warden-policy `312b9c0`): probes
  are required only of pods with `restartPolicy: Always`, with tests on both sides. Checked with a real captured pod.
- **Consequences if accepted:**
  - `T01` (tags) and `T06` (foreign registry) are prevented at admission instead of warned about. `T02`-`T05`, `T07`,
    `T08` (signature, provenance, SBOM) stay **detected, not prevented**, as THREAT_MODEL residual risk 6 says.
  - `kubectl debug` in `svc-*` namespaces then needs a hardened, registry-pinned ephemeral container.
  - Milestone M3 is only partly reached; full M3 needs image verification enforced.

## ADR-033: CloudNativePG carve-out covers the Job controller and the operator image; Jobs are gated at creation

- **Status:** **Accepted and in effect (2026-10-26)**: implemented by warden-policy PR #2 and warden-gitops PR #73,
  merged by the owner. Verified live: a `Database` is Ready under full enforcement in 26 s, with `<name>-conn` and no
  denial. It repairs what ADR-032 (staged enforcement) exposed, and changes a trust boundary (THREAT_MODEL residual risk 7).
- **Context:** warden-policy PR #1 made the image-reference VAPs enforce. A `Database` then never became Ready:
  - the initdb pod that CloudNativePG runs for each Database is created by the **Job controller**, not by the
    operator's service account, so the T06 carve-out (operator account only) did not apply;
  - the bootstrap init container of every CNPG pod runs the **operator image referenced by tag**, which fails T01
    (digest required) and was not in the trusted list either.
  In Audit mode both were warnings, so every earlier E4 run succeeded and the smoke check "operator-created pods
  pass" was vacuous. The M3 readiness measurement (20 releases) covered the four services, not CNPG-managed pods.
  Found by creating a Database right after the merge; the four services were unaffected.
- **Decision:**
  1. The operator image is pinned by digest in warden-gitops (`platform/cloudnative-pg/values.yaml`,
     `image.tag: 1.30.1@sha256:...`; the chart has no digest value, but the tag field renders it into both the
     Deployment image and `OPERATOR_IMAGE_NAME`, which the operator hands to its init containers).
  2. The pods VAP trusts three exact upstream references: two PostgreSQL images (regular or init container) and the
     operator image (**init container only**). Trusted requesters: the operator's service account, and the Job
     controller (`system:serviceaccount:kube-system:job-controller`, or `system:kube-controller-manager` where
     controllers share an identity) for a pod controlled by a `batch/v1` Job. Never in an ephemeral container.
  3. A new VAP, `warden-image-references-jobs` (**CREATE only**), makes the Job controller safe to trust: a Job's pod
     template may name only Warden images by digest, except that the operator's service account may create a Job
     with the three upstream references. Without it the Job controller would be a confused deputy: anyone able to
     create a Job could run the allow-listed images through it (raised by the automated security review of the first
     version of this change). Create-only because the template is immutable and the Job controller updates Jobs itself.
  4. `scripts/verify.py` requires the trusted lists of both policies, the `database-cnpg` composition and the
     gitops operator pin to agree, and the operator tag to equal `versions.yaml` `charts.cloudnative-pg.app`.
- **Consequences:**
  - The trusted set grows from two images to three; the new exposure is still exact upstream digests, reachable only
    through Jobs the operator creates and pods it creates.
  - An operator upgrade now needs four coordinated edits (versions.yaml, gitops pin, both policies); verify.py fails
    until they agree. The same already held for PostgreSQL images.
  - Open: `system:kube-controller-manager` as a Job-controller identity is for clusters that do not run per-controller
    service accounts; AKS was not checked for which it uses.
  - Lesson recorded for ADR-032: a policy can only be called ready to enforce after every legitimate pod class has
    been exercised under enforcement, not just reported on in Audit.

## ADR-034: The promoter app merges its own digest-only PR; auto-merge cannot

- **Status:** **Accepted (2026-10-27)**, first implementation failed live, second pending. PR #1 (`5e48ae2`, released as
  v0.1.1) called `gh pr merge`, which refuses a blocked PR on the client without `--admin`; its first run (svc-books,
  PR warden-gitops#95) failed after the 10-minute loop. warden-platform PR #4 merges through the REST endpoint instead.
  Not yet verified live; see *Result of the first live run* below.
  Amends ADR-013 (promotion by digest-only PR) and ADR-027 (owner and app bypass).
- **Context:** The promote job opens `deploy(<svc>): <digest12>` and enabled `gh pr merge --auto`. The first live run
  (PR warden-gitops#74, 2026-10-26) opened it correctly, `digest-only` passed, auto-merge was enabled, and the PR then
  sat `BLOCKED` / `REVIEW_REQUIRED` for 25 minutes. The promoter app is a bypass actor on the `main-review` ruleset
  (pull-request mode), but **GitHub's auto-merge does not apply ruleset bypass**: it waits for approvals.
- **Decision:** The promote job merges directly (`gh pr merge --squash`), retrying for up to 10 minutes. The API refuses
  until the required `digest-only` check passes (its ruleset has no bypass actors); then the app's bypass on the review
  rule applies. The minted token is limited to `contents: write` and `pull-requests: write`. The merge passes
  `--match-head-commit` with the commit the job pushed, so a branch moved after the push is refused instead of merged
  under review bypass (security review of the PR, 2026-10-26).
- **Why the check cannot be skipped (verified 2026-10-26 with the GitHub rulesets API):** `digest-only` is the only rule
  of `main-digest-only` (`required_status_checks`), whose `bypass_actors` list is empty, organization admins
  included. The app is a bypass actor only of `main-review` (`pull_request` rule). The two rulesets are independent, so
  bypassing review does not bypass the check.
- **Considered, not done:** giving the app `checks: read` to poll `digest-only` itself. It would widen the credential and
  adds nothing the empty bypass list does not already guarantee. A ruleset limiting pushes to `promote/**` to the app
  would stop other writers pre-creating a promotion branch; it is a GitHub setting for the owner to apply and is not
  yet applied.
- **Consequences:**
  - No human review of a promotion, as ADR-013 intended: the guard is the `digest-only` check (one file, one digest, bot
    author), which attack A11 tests.
  - The credential that can merge is the same one that opens the PR; it exists only in the four service repos' promote job.
  - Needs an immutable release (v0.1.1) and the service repos' `delivery.yml` moved to it.
  - **Not verified:** that a direct merge by the bypass-actor app succeeds despite `REVIEW_REQUIRED`. The first release after
    tagging is the test. Until then, bot PRs need an owner merge.
  - **Used so far (2026-10-26):** the 20-release E5 batch ran on release v0.1.0, so every bot PR was merged by the owner
    bypass (`gh pr merge --admin --match-head-commit`, only after `digest-only` passed), at the owner's explicit
    go-ahead. Each run's JSON in `evidence/rollbacks/` records it as `promoter-bot+owner-admin-merge`.
  - **Result of the first live run (2026-10-27, v0.1.1, svc-books):** build, scan and signing passed; the promote job opened
    warden-gitops#95 and `digest-only` passed; the PR stayed `BLOCKED` / `REVIEW_REQUIRED`; after 10 minutes the job failed
    with `To use administrator privileges to immediately merge the pull request, add the --admin flag.` That text is the
    `gh` client's own refusal, produced before GitHub is asked, so the run says nothing about whether GitHub lets the app
    bypass the review rule. Fix (warden-platform#4, release v0.1.2): `PUT /repos/{gitops}/pulls/{n}/merge` with
    `merge_method=squash` and `sha` set to the pushed commit. It stays an assumption until a run succeeds that GitHub
    honours the app's `pull_request`-mode bypass on that endpoint. The leftover PR #95 should be closed.
  - **Verification (2026-10-27, v0.1.2):** all four service push workflows completed through promote. The promoter app
    authored and merged warden-gitops PRs #97–#100 itself after `digest-only` passed. For example, [svc-books run
    40502485200](https://github.com/WARDEN-CCD/svc-books/actions/runs/40502485200) and [PR #100](https://github.com/WARDEN-CCD/warden-gitops/pull/100)
    show the successful path. The 20-release E5 sample remains a separate historical batch with owner-bypass merges.

## ADR-035: Report staged admission and database backends as final-project limitations

- **Status:** Proposed for supervisor review (2026-10-27). This records a proposed scope adjustment to the submitted
  synopsis; it does not mark the original outcomes as achieved.
- **Context:** The synopsis promises that unverifiable images cannot run and that the same `Database` request can use
  managed Azure PostgreSQL. On the pinned Kyverno 1.19.2, image verification in `Deny` would refuse some legitimate
  Pods after transient fetch errors or webhook timeouts (E8 and M3 readiness). The native digest/registry policies and
  pod hygiene do deny. The `database-cnpg` composition works on both kind and AKS; `database-azure` has not been
  written or tested. No later stable Kyverno release was available on 2026-10-27.
- **Decision proposed:** Keep the measured, pinned Kyverno version and current staged policy configuration for the
  submission unless the ADR-020 readiness gate can be met on kind and AKS. Present the attack-suite Deny results as
  controlled tests, and the live supply-chain policy as Audit. Present E4 as a portable database request backed by
  CloudNativePG on both clusters, with the managed Azure backend explicitly incomplete. Do not describe either
  original synopsis outcome as fully implemented.
- **To close the gaps later:** Follow [the completion plan](docs/completion-plan.md): retry/fetch fixes and a full
  readiness run before live image-verification Deny; provider/auth/network configuration and a managed-server
  connection test before claiming the Azure database backend.
- **Consequence:** The final report and demonstration are accurate, but the absolute admission claim and managed
  database option in the synopsis are unmet. Supervisor acceptance of that deviation is required before calling the
  project complete against the synopsis.
