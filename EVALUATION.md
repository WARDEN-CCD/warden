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
- **Pass:** median command → healthy pod **< 15 min**; manual steps = **0**.
- **Baseline:** one team member creates an equivalent service by hand from a checklist (repo, workflow,
  manifests, dashboard, catalog entry) — timed once. Gives an honest version of "weeks → one command".
- **Evidence:** `evidence/scaffold-timings/*.json`.

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

## E3 — Automatic canary rollback

- **Procedure:** release a *real, signed* build with `WARDEN_DEMO_ERROR_RATE=0.10` (variant B: latency +400 ms).
  k6 runs at 40 rps.
- **Measure:** time from new ReplicaSet created → AnalysisRun failed → traffic 100 % stable; fraction of all
  requests that failed during the canary (blast radius).
- **Runs:** 10 faulty (5 per variant) and 10 healthy releases.
- **Pass:** 10/10 faulty releases aborted with no human action; 0/10 healthy releases aborted; blast radius
  ≤ first canary weight × injected error rate (≈ 0.5 %).
- **Evidence:** `evidence/rollbacks/*.json` + Grafana snapshot.

## E4 — Self-service database

- **Procedure:** apply the 10-line `Database` manifest from [DESIGN.md](DESIGN.md#10-self-service-database-crossplane-v2)
  on `local` (CNPG) and `azure` (Flexible Server). The `books` service mounts `<name>-conn` and runs a migration.
- **Measure:** apply → XR `Ready=True`; → service healthy and connected.
- **Pass:** byte-identical manifest works on both clusters; no manual steps.

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
