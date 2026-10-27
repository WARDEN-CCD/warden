# Warden — Roadmap

Where things stand today, and what to do next: [STATUS.md](STATUS.md).

Week numbers follow the synopsis timeline (12 weeks). Fill in the calendar date of week 1 here once agreed:
**Week 1 starts: `YYYY-MM-DD`**.

The table assigns responsibility for the remaining work. It does not establish who authored earlier commits.
Each member confirms their completed work in the final report before submission.

| Area | Primary owner | Backup |
|------|---------------|--------|
| `warden-infra` (OpenTofu, kind, Crossplane) | Aditya Chetan Thakur | Abhyuday Gupta |
| `warden-gitops` (Argo CD, Rollouts, gateway, observability install) | Shaurya Jain | Abhyuday Gupta |
| `warden-policy` (VAP, Kyverno, attack suite, threat model) | Sankalp Arya | Abhyuday Gupta |
| `warden-platform` (reusable workflow, CLI, template, dashboards, DORA) | Abhyuday Gupta | Aditya Chetan Thakur |

Abhyuday leads the architecture, supply-chain workflow, cross-repository integration, and final evidence review.
Aditya owns the managed Azure database path and rebuild evidence; Sankalp owns admission readiness and the attack
suite; Shaurya owns the GitOps release path, rollout evidence, and demo preparation. A reviewer from another area
checks each change.

## Milestones

| ID | Week | Milestone | Exit criteria (demo-able) |
|----|------|-----------|---------------------------|
| M0 | 3 | **Foundations** | Spikes S1–S3 closed with written outcomes; kind `lite` cluster up on all 4 laptops; this design reviewed by the supervisor |
| M1 | 6 | **Walking skeleton** (met 2026-10-26: both `up:local` and `up:azure` work) | `task up:local` brings up Argo CD + root app; one hand-made service builds in CI, gets committed to gitops by the bot, and is synced by Argo CD; `task up:azure` works once |
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
- [ ] Shaurya Jain accepts the organization and `warden-maintainers` invitation sent to `shry0212-max` on 2026-10-27
- [x] Org settings → Packages → Package creation → allow **Public** (prerequisite for ADR-028; no API). Done 2026-10-24
- [ ] Every member enables 2FA, **then** turn on the org's "Require two-factor authentication" (turning it on first removes members without 2FA)
- [x] `warden-security` members chosen (all three current members); owner review bypass + no-bypass history protection (ADR-027)
- [ ] Decide whether to turn on code-owner review in `main-review` (binds teammates only; the owner bypasses it)
- [x] `main-digest-only` on `warden-gitops` has no bypass actors, not even the owner (checked 2026-10-26 against the rulesets API)
- [x] GitHub Apps `warden-promoter` (bypass actor of `main-review` in pull-request mode) and `warden-deployments` created 2026-10-26
- [ ] Renovate app
- [ ] Every member: `python scripts/doctor.py` passes (Docker Desktop/WSL2 memory, kind, kubectl, helm, task, tofu, cosign, JDK 25, Go)
- [x] **S1 — supply-chain compatibility spike (highest risk, timebox 5 days).** In a throwaway repo:
      cosign 3.1.4 keyless sign + `actions/attest-build-provenance` (push to GHCR) + `cosign attest` SBOM →
      verify with Kyverno 1.19.2 `ImageValidatingPolicy` on kind. Answer Q1–Q3 in [DESIGN.md](DESIGN.md#17-open-questions-resolved-by-spikes-in-roadmap-weeks-13).
      Record a compatibility matrix in `evidence/` and update ADR-008/009. **Done 2026-10-21:** [evidence/spikes/S1.md](evidence/spikes/S1.md).
- [x] **S2 — laptop parity spike.** Done 2026-10-24: [evidence/spikes/S2.md](evidence/spikes/S2.md). Install the `lite` component set on kind; measure memory per component; set
      `.wslconfig` guidance; decide whether `lite` needs trimming (Q4)
- [x] **S3 — Azure spike** (one subscription; the other three were not checked). Confirm regions/quotas on all four subscriptions; create and destroy a 2 × B2ms AKS
      with OpenTofu; confirm B1ms PostgreSQL pricing on the Students offer (Q5) — create/destroy done on one
      subscription (indiasouthcentral; BS family 0/4 vCPUs, AKS 1.37 available); the other three subscriptions and
      live PostgreSQL pricing are open. Azure PostgreSQL composition code is staged but not exercised.
- [ ] Freeze DESIGN v1.0; supervisor review

### Weeks 4–6 — Infrastructure, bootstrap, pipeline, GitOps end to end

- [x] `warden-infra`: tofu `bootstrap/` (state storage + encryption), `modules/aks`, `modules/budget`, `modules/github-oidc`, `envs/azure`
      — applied 2026-10-26: bootstrap 5 added, envs/azure 4 added and later destroyed
      ([plan](evidence/azure/plan-2026-10-26.txt), [run summary](evidence/azure/first-run-2026-10-26.json))
- [x] `warden-infra`: `task up:local|azure`, `down`, `rebuild` + ledger writer — all run; `up:azure` took 1203 s from
      nothing with no manual steps (first run), `down:azure` followed
- [x] `warden-gitops`: root app, cluster overlays, platform Applications (pinned charts), ApplicationSet for `apps/*`
      (azure overlay: warden-gitops#17)
- [x] `warden-platform`: reusable workflow `build` + `scan` jobs; caller workflow; promote job + GitHub App; `digest-only` check in gitops
      — all done; the promote job that merges its own PR is merged (`5e48ae2`) and waits for release v0.1.1
- [x] First service deploys end to end on kind and AKS → **M1** (met 2026-10-26; generated by `warden new` rather than
      by hand; on AKS the four services answered through the load balancer)

### Weeks 6–8 — Signing, attestation, admission (Audit), canary, database

- [x] `sign-attest` job (cosign, provenance, SBOM, vuln); tag ruleset + first immutable release `v0.1.0`
- [x] `warden-policy`: VAP image references; IVP supply chain; hygiene ValidatingPolicy — all **Audit**
- [x] `warden-policy`: `kyverno test` unit tests; attack scripts (expect *audit* violations)
      — `kyverno test` (57 cases, CI) and A01–A14 (15/15 on kind and on AKS) done; the attack suite is not run in CI
- [x] Rollout + Gateway API plugin + ClusterAnalysisTemplates; k6-operator load; tune thresholds on kind
      — E3: 10/10 faulty aborted, 10/10 healthy promoted (2026-10-25)
- [x] Crossplane v2 install, `Database` XRD, `database-cnpg` composition (composes `<name>-conn`) → **M2**

### Weeks 8–9 — Integration, enforce

- [x] `warden` CLI: `new`, `verify`, `status`, `dora`, `setup-apps` (`doctor` is `scripts/doctor.py`); four services
      generated with `warden new` (E1)
- [ ] `database-azure` composition
- [x] Argo CD Notifications → GitHub Deployments ledger; `warden dora` — live; E5 has separate owner-merge and
      app-only batches, 20 releases each ([original](evidence/dora/2026-10-26-e5-kind.json),
      [app-only](evidence/dora/2026-10-27-e5-app-only.json))
- [x] Staged enforcement (ADR-032, in effect since 2026-10-26): native policies and pod hygiene deny
- [ ] Image verification to **Deny** (ADR-020 criteria; waits for a Kyverno release that retries transient errors and cuts
      per-Pod latency); attack suite in CI → full **M3**

### Weeks 9–10 — Evaluation and release

- [ ] Run E1–E8 per [EVALUATION.md](EVALUATION.md); commit evidence — all have results; gaps (Azure E1, more Azure
      rebuilds, E1 baseline) are listed in [STATUS.md](STATUS.md). Recordings are open.
- [x] Comparison run of CNOE idpbuilder (E7, one run)
- [ ] Tag `v1.0.0` across repos → **M4**

### Week 11 — Documentation

- [x] Final DESIGN, THREAT_MODEL (with test results), DECISIONS, report in `docs/report/` (individual contributions to be
      filled in by each member)

### Week 12 — Presentation → **M5**

- [x] Slide deck (14 slides) and demo script: [docs/demo-script.md](docs/demo-script.md)
- [ ] Update the last slide's open items on the day of the presentation
- [ ] Record the demo scenes
- [ ] Live demo rehearsed on a fresh `task up:local`

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
