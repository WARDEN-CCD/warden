# Warden — Roadmap

Week numbers follow the synopsis timeline (12 weeks). Fill in the calendar date of week 1 here once agreed:
**Week 1 starts: `YYYY-MM-DD`**.

Owners are suggestions — one primary owner per repository, everyone reviews everyone.

| Area | Primary owner | Backup |
|------|---------------|--------|
| `warden-infra` (OpenTofu, kind, Crossplane) | _TBD_ | _TBD_ |
| `warden-gitops` (Argo CD, Rollouts, gateway, observability install) | _TBD_ | _TBD_ |
| `warden-policy` (VAP, Kyverno, attack suite, threat model) | _TBD_ | _TBD_ |
| `warden-platform` (reusable workflow, CLI, template, dashboards, DORA) | _TBD_ | _TBD_ |

## Milestones

| ID | Week | Milestone | Exit criteria (demo-able) |
|----|------|-----------|---------------------------|
| M0 | 3 | **Foundations** | Spikes S1–S3 closed with written outcomes; kind `lite` cluster up on all 4 laptops; this design reviewed by the supervisor |
| M1 | 6 | **Walking skeleton** | `task up:local` brings up Argo CD + root app; one hand-made service builds in CI, gets committed to gitops by the bot, and is synced by Argo CD; `task up:azure` works once |
| M2 | 8 | **Trust & safety in Audit** | Images signed + 3 attestations; VAP and IVP in **Audit** report correct results; canary + analysis + k6 working; `Database` XR works on CNPG |
| M3 | 9 | **Enforce** | ADR-020 exit criteria met; policies in **Deny**; attack suite green in CI against kind; `warden new` creates all four services |
| M4 | 10 | **Evaluated** | E1–E8 run and evidence committed under `evidence/`; release `v1.0.0` of every repo |
| M5 | 12 | **Presented** | Report, threat model, recordings, presentation |

## Week-by-week

### Weeks 1–3 — Analysis, spikes, parity, design

- [x] Create GitHub org `WARDEN-CCD` and the hub + four repos (public)
- [x] Rulesets (`main`, `main-digest-only`, `release-tags`) and secret scanning push protection on all five repos (ADR-025)
- [x] Teammates `lynch-45` and `SankalpArya-255` added; temporary admin bypass removed from every `main` ruleset (ADR-025)
- [x] Teams `warden-maintainers` (write on all repos) and `warden-security` (write on policy + platform) created (ADR-026)
- [ ] Invite Shaurya Jain to the org and to `warden-maintainers`
- [ ] Every member enables 2FA, **then** turn on the org's "Require two-factor authentication" (turning it on first removes members without 2FA)
- [x] `warden-security` members chosen (all three current members); owner review bypass + no-bypass history protection (ADR-027)
- [ ] Decide whether to turn on code-owner review in `main-review` (binds teammates only; the owner bypasses it)
- [ ] Owner bypass on `warden-gitops` `main-digest-only` (set by the owner in the GitHub UI; ADR-027)
- [ ] Renovate app; GitHub Apps `warden-promoter` (add to `warden-gitops` `main-review` bypass) / `warden-deployments`
- [ ] Every member: `python scripts/doctor.py` passes (Docker Desktop/WSL2 memory, kind, kubectl, helm, task, tofu, cosign, JDK 25, Go)
- [ ] **S1 — supply-chain compatibility spike (highest risk, timebox 5 days).** In a throwaway repo:
      cosign 3.1.4 keyless sign + `actions/attest-build-provenance` (push to GHCR) + `cosign attest` SBOM →
      verify with Kyverno 1.19.2 `ImageValidatingPolicy` on kind. Answer Q1–Q3 in [DESIGN.md](DESIGN.md#17-open-questions-resolved-by-spikes-in-roadmap-weeks-13).
      Record a compatibility matrix in `evidence/` and update ADR-008/009.
- [ ] **S2 — laptop parity spike.** Install the `lite` component set on kind; measure memory per component; set
      `.wslconfig` guidance; decide whether `lite` needs trimming (Q4)
- [ ] **S3 — Azure spike.** Confirm regions/quotas on all four subscriptions; create and destroy a 2 × B2ms AKS
      with OpenTofu; confirm B1ms PostgreSQL pricing on the Students offer (Q5)
- [ ] Freeze DESIGN v1.0; supervisor review

### Weeks 4–6 — Infrastructure, bootstrap, pipeline, GitOps end to end

- [ ] `warden-infra`: tofu `bootstrap/` (state storage + encryption), `modules/aks`, `modules/budget`, `modules/github-oidc`, `envs/azure`
- [ ] `warden-infra`: `task up:local|azure`, `down`, `rebuild` + ledger writer
- [ ] `warden-gitops`: root app, cluster overlays, platform Applications (pinned charts), ApplicationSet for `apps/*`
- [ ] `warden-platform`: reusable workflow `build` + `scan` jobs; caller workflow; promote job + GitHub App; `digest-only` check in gitops
- [ ] First service (hand-written from the template) deploys end to end on kind and AKS → **M1**

### Weeks 6–8 — Signing, attestation, admission (Audit), canary, database

- [ ] `sign-attest` job (cosign, provenance, SBOM, vuln); tag ruleset + first immutable release `v0.1.0`
- [ ] `warden-policy`: VAP image references; IVP supply chain; hygiene ValidatingPolicy — all **Audit**
- [ ] `warden-policy`: `kyverno test` unit tests + Chainsaw e2e; attack scripts A01–A12 (expect *audit* violations)
- [ ] Rollout + Gateway API plugin + ClusterAnalysisTemplates; k6-operator load; tune thresholds on kind
- [ ] Crossplane v2 install, `Database` XRD, `database-cnpg` composition → **M2**

### Weeks 8–9 — Integration, enforce

- [ ] `warden` CLI: `new`, `verify`, `doctor`; template finalised; generate the four services with `warden new`
- [ ] `database-azure` composition
- [ ] Argo CD Notifications → GitHub Deployments ledger; `warden dora`
- [ ] Meet ADR-020 exit criteria → switch to **Deny**; attack suite in CI → **M3**

### Weeks 9–10 — Evaluation and release

- [ ] Run E1–E8 per [EVALUATION.md](EVALUATION.md); commit evidence; record demos
- [ ] Comparison run of CNOE idpbuilder
- [ ] Tag `v1.0.0` across repos → **M4**

### Week 11 — Documentation

- [ ] Final DESIGN, THREAT_MODEL (with test results), DECISIONS, report in `docs/report/`

### Week 12 — Presentation → **M5**

## Stretch goals (only after M3)

| ID | Stretch | Value |
|----|---------|-------|
| S-1 | Verify third-party platform images (Argo CD, Kyverno…) against upstream signer identities | Closes residual risk #4 |
| S-2 | Reproducible-build check: rebuild a commit, assert identical digest | Strong supply-chain evidence |
| S-3 | Auto-revert PR in gitops after a Rollout abort | Git matches reality after rollback |
| S-4 | Backstage portal reading the generated `catalog-info.yaml` | Fairer comparison with idpbuilder |
| S-5 | Policy Reporter UI + weekly vuln re-attestation job | Visibility |

## Risk register

| ID | Risk | Likelihood | Impact | Mitigation | Trigger to act |
|----|------|-----------|--------|------------|----------------|
| R1 | Kyverno IVP cannot verify our attestation layout on GHCR | Medium | High | S1 first; ADR-008 fallback (all-cosign / legacy layout) | S1 fails by day 3 |
| R2 | Kyverno 1.20 lands mid-project with breaking changes | High | Medium | CEL types only (ADR-006); upgrade via PR with tests | 1.20 release notes |
| R3 | Laptops cannot run `lite` | Medium | High | S2 measurements; drop Grafana/Crossplane to a "core" profile; use AKS for full runs | S2 > 10 GB |
| R4 | Azure credit exhausted | Low | High | Ephemeral clusters, reaper, budget alerts, 4 subscriptions | 50 % alert |
| R5 | Burstable B-series throttling skews canary metrics | Medium | Medium | Tune thresholds on kind; note in evaluation | Analysis flakiness |
| R6 | GitHub Actions minutes/rate limits | Low | Medium | Public repos (free minutes); cache Maven | Throttling seen |
| R7 | Scope creep | High | High | Stretch goals only after M3; ADR required for new components | Any unplanned component |
