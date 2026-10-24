# Warden — Evaluation Plan

How each claim in the synopsis is tested. Every experiment writes raw evidence under [`evidence/`](evidence/README.md)
so results can be re-derived. Report medians and spreads, not single runs.

| ID | Claim | Synopsis scenario |
|----|-------|-------------------|
| E1 | One command creates and deploys a service | Scenario 1 |
| E2 | Unverifiable artifacts are refused at admission | Scenario 2 |
| E3 | Faulty releases roll back without humans | Scenario 3 |
| E4 | A database comes from a short declarative request | Scenario 4 |
| E5 | Delivery performance (DORA) from real history | DORA metrics |
| E6 | The environment is rebuildable from Git | Reproducibility measure |
| E7 | Comparison with an open-source reference platform | CNOE idpbuilder |
| E8 | Cost of verification (admission latency overhead) | *Added* |

---

## E1 — Scaffolding time

- **Procedure:** `warden new eval-<n> --db` on a clean cluster. The CLI timestamps: repo created, first CI run
  green, digest PR merged, Argo CD synced, Rollout healthy.
- **Runs:** 5 on `local`, 5 on `azure`.
- **Pass:** median command → healthy pod **< 15 min**; manual steps **≤ 1** — the package-visibility click
  (ADR-028), timed and reported separately.
- **Baseline:** one team member creates an equivalent service by hand from a checklist (repo, workflow,
  manifests, dashboard, catalog entry) — timed once. Gives an honest version of "weeks → one command".
- **Evidence:** `evidence/scaffold-timings/*.json`.
- **Result so far (2026-10-24, local):** loans 455.5 s, members 518.6 s, notify 523.6 s, scaffolded concurrently;
  median of the three full runs **518.6 s (8.6 min)**. **0** manual steps in each (ADR-028 update). books
  finished in 271.4 s on a resumed run after two failed attempts: the scan gate blocked Tomcat CVEs (fixed by
  Spring Boot 4.1.2), then the org disallowed public packages. Not yet done: 5 runs per cluster, the azure runs,
  the hand-made baseline.

## E2 — Admission refusal (attack suite)

Each attack is a script in `warden-policy/attacks/` that attempts a deployment and asserts the denial reason.

| Attack | Attempt | Expected outcome |
|--------|---------|------------------|
| A01 | Deploy by tag (`:v1`) instead of digest | VAP deny: digest required |
| A02 | Push unsigned image to org GHCR, deploy by digest | IVP deny: no valid signature |
| A03 | Sign with attacker's own workflow (valid Fulcio cert, wrong subject) | IVP deny: identity mismatch |
| A04 | Call platform reusable workflow from a repo outside the org | IVP deny: provenance repo not allowed |
| A05 | Image built from a non-`main` ref | IVP deny: provenance ref not `refs/heads/main` |
| A06 | Image from `docker.io` | VAP deny: registry not allowed |
| A07 | Modify a signed image (new layer) → new digest | IVP deny: no signature for digest |
| A08 | Signed image with SBOM attestation removed | IVP deny: SBOM attestation missing |
| A09 | Search all CI configs/secrets for cluster credentials | None found |
| A10 | PR adds a build plugin that requests an OIDC token in the build job | Token request fails (no `id-token` permission) |
| A11 | Bot PR that changes anything besides one digest | `digest-only` check fails, PR not merged |
| A12 | `kubectl edit` an admission policy to `Audit` | Argo CD reverts within one reconcile |

- **False-positive check:** 20 legitimate deployments across the four services → **0** denials.
- **Pass:** 12/12 attacks fail for the expected reason; 0 false denials.
- **Evidence:** `evidence/attacks/<date>-results.json` (attack, expected, observed, policy message).
- **Result so far (2026-10-24, kind):** **13/13**: one legitimate deployment admitted, A01–A12 refused for the
  expected reason ([final run](evidence/attacks/2026-10-24T184535Z-results.json)). Policies are `Audit` until M3,
  so the suite runs against `Deny` clones made by `warden-policy/attacks/lab.py`. A05 is stopped before
  admission (the workflow pushes only from `main`). A12: Argo CD restored the policy in 1.4 s. Earlier runs
  (9/13, then 12/13) found real defects, fixed before the final run, most importantly that the vulnerability
  IVP's default `mutateDigest: true` rewrote tags to digests and so admitted A01 (`verify.py` now forbids it).
  Not yet done: the 20-deployment false-positive check.

## E3 — Automatic canary rollback

- **Procedure:** release a *real, signed* build with `WARDEN_DEMO_ERROR_RATE=0.10` (variant B: latency +600 ms against the 500 ms p95 failure threshold).
  k6 runs at 40 rps.
- **Measure:** time from new ReplicaSet created → AnalysisRun failed → traffic 100 % stable; fraction of all
  requests that failed during the canary (blast radius).
- **Runs:** 10 faulty (5 per variant) and 10 healthy releases.
- **Pass:** 10/10 faulty releases aborted with no human action; 0/10 healthy releases aborted; blast radius
  ≤ first canary weight × injected error rate (≈ 0.5 %).
- **Evidence:** `evidence/rollbacks/*.json` + Grafana snapshot.
- **Status (2026-10-25): no valid run yet.** The first two runs (loans healthy, members error, via
  `scripts/experiments/canary.py`) were stopped as invalid because they exposed two platform defects:
  1. The AnalysisRun measured 9 s after the canary pod started, got an empty result and paused the rollout as
     Inconclusive. Fixed in warden-platform `04ab349` (`initialDelay: 2m`, actuator traffic excluded).
  2. Argo CD's sync re-applied Git's Service selectors and HTTPRoute weights 9 s after Argo Rollouts set them,
     so the canary got **1/3 of traffic (pod count) instead of 5 %**. With the error-injected members release
     that is the blast radius the canary exists to prevent. Fix: warden-gitops #16 (`ignoreDifferences`).
  Against the recorded data, the corrected queries score the faulty members canary 0.899 (fails at < 0.95)
  and the healthy loans canary 1.0.

## E4 — Self-service database

- **Procedure:** apply the 10-line `Database` manifest from [DESIGN.md](DESIGN.md#10-self-service-database-crossplane-v2)
  on `local` (CNPG) and `azure` (Flexible Server). The `books` service mounts `<name>-conn` and runs a migration.
- **Measure:** apply → XR `Ready=True`; → service healthy and connected.
- **Pass:** byte-identical manifest works on both clusters; no manual steps.
- **Result so far (2026-10-24, local, one run):** `Database {size: small, version: "18"}` reached `Ready` in
  **804 s** on a cold cluster, including CNPG operator readiness and the PostgreSQL image pull
  ([evidence](evidence/databases/2026-10-24T152723Z-books-db.json)). **Deviation:** connection details are CNPG's
  `books-db-app` Secret (named in `status.connectionSecret`), not the composed `<name>-conn` that DESIGN §10
  specifies. Until a stable name is composed, a byte-identical service manifest cannot work on both clusters.
  The azure run waits for a `database-azure` composition.

## E5 — DORA metrics

- **Data:** GitHub Deployments ledger from the first M1 deployment to the end of week 10.
- **Report:** the synopsis' four (deployment frequency, lead time for changes, change fail rate, time to restore /
  failed deployment recovery time) plus deployment rework rate, per service and overall, with definitions from
  [DESIGN.md §12](DESIGN.md#12-observability-and-delivery-metrics).
- **Caveat stated in report:** small team, synthetic changes, injected failures inflate change fail rate by design;
  report injected failures separately from organic ones.

## E6 — Reproducibility

- **Procedure:** every `task rebuild:*` appends to `evidence/rebuilds/rebuild-ledger.csv`.
- **Pass:** ≥ 10 full rebuilds on `local` and ≥ 5 on `azure` over the project; after each, all Argo CD apps
  Synced/Healthy and the four services pass a smoke test; zero manual steps.
- **Report:** count, median and p90 duration per environment, failures and their root causes.

## E7 — Comparison with CNOE idpbuilder

Run idpbuilder v0.10.x locally on the same laptop. Compare on:

| Criterion | How measured |
|-----------|--------------|
| Time to first deployed service | Stopwatch from install |
| Supply-chain verification at admission | Present / absent; what is verified |
| Policy engine and default policies | Inspection |
| Progressive delivery and auto-rollback | Present / absent; E3-style test if present |
| Self-service infrastructure | Present / absent |
| Developer portal | idpbuilder ships Backstage; Warden ships CLI + catalog files (ADR-017) |
| Resource footprint | `kubectl top` after settle: total CPU/memory |
| Cloud path | Local-only vs local + cloud |

Be fair: idpbuilder is a reference *starter* platform, not a supply-chain product.

## E8 — Cost of verification

- **Procedure:** create 50 Pods of a signed image with policies in Deny vs 50 with policies removed; record
  admission latency (Kyverno `kyverno_admission_review_duration_seconds`, API server audit) and Pod-ready time.
  Repeat with a warm and a cold verification cache.
- **Report:** p50/p95 added latency per Pod. Expected: noticeable on cold cache (registry + tlog lookups), small when warm.
