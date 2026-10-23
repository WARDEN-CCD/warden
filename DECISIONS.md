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
