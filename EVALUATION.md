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
| A13 | Signed app container plus an unsigned org image as an initContainer | IVP deny: image not verified (added 2026-10-25) |
| A14 | A real ReplicaSet whose template has an unsigned org image | its Pods are refused (FailedCreate T02); Kyverno 1.19.2 does not verify ReplicaSets themselves (ADR-031) |

- **False-positive check:** 20 legitimate deployments across the four services → **0** denials.
- **Pass:** every attack (A01–A14) fails for the expected reason; 0 false denials.
- **Evidence:** `evidence/attacks/<date>-results.json` (attack, expected, observed, policy message).
- **Result so far (2026-10-24, kind):** **13/13**: one legitimate deployment admitted, A01–A12 refused for the
  expected reason ([final run](evidence/attacks/2026-10-24T184535Z-results.json)). Policies are `Audit` until M3,
  so the suite runs against `Deny` clones made by `warden-policy/attacks/lab.py`. A05 is stopped before
  admission (the workflow pushes only from `main`). A12: Argo CD restored the policy in 1.4 s. Earlier runs
  (9/13, then 12/13) found real defects, fixed before the final run, most importantly that the vulnerability
  IVP's default `mutateDigest: true` rewrote tags to digests and so admitted A01 (`verify.py` now forbids it).
  **Latest (2026-10-25, [run](evidence/attacks/2026-10-25T024642Z-results.json)): 15/15** on a freshly rebuilt
  cluster, after ADR-030, with two new attacks:
  - A13 (an unsigned org image as an initContainer) is refused because `required: true` rejects any image no
    validation verified; the validations themselves iterate only `images.containers`.
  - A14 (a ReplicaSet with an unsigned template): its Pods are refused.
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
- **Result (2026-10-25, kind, [summary](evidence/rollbacks/summary-2026-10-25T09.json)): pass on rollback and false
  aborts; blast radius at the predicted value.** 20 real, signed releases ran through CI, promotion, Argo CD and
  the canary, after the two fixes below (warden-gitops #16 merged).
  - **Faulty releases: 10/10 aborted with no human action**, median **147 s** from canary start to abort
    (141–150 s): the 2-minute `initialDelay` plus the first measurement. Error runs were caught by
    `success-rate`, latency runs by `latency-p95`, in every case.
  - **Healthy releases: 10/10 promoted**, 0 false aborts, median **472 s** (466–1210 s) through 5 → 25 → 50 %
    with two analyses.
  - **Blast radius, error runs:** median **0.40 %** of all requests failed during the rollout (0.33–0.51 %),
    against the predicted 5 % weight × 10 % error rate = 0.50 %. Four of five runs were under 0.5 %; one was
    at 0.509 %, which is binomial noise around the predicted value. So the criterion is met in expectation, not
    as a hard bound.
  - **Blast radius, latency runs:** each aborted canary's requests were all slower than 0.54 s (239–243
    requests), i.e. **4.1 %** of the service's requests were slowed (none failed).
  - **Recovery:** abort → fix release fully promoted, median **759 s** (678–1515 s), including the fix's
    CI build (~4 min) and a full canary. Commit → canary start: median 263 s.
- **Defects found on the way:**
  1. The AnalysisRun measured 9 s after the canary started and paused every rollout (fixed: `initialDelay`).
  2. Argo CD reverted the Rollouts-managed Service selector hash and route weights, so the canary took 1/3 of
     traffic (fixed: warden-gitops #16, verified by a forced sync that kept the hash).
  3. Injected faults carry `uri="UNKNOWN"` (fixed in the runner).
- **Argo Rollouts quirk (open):** once, an AnalysisRun's first measurement came 14 min after creation instead of
  after its 2-minute `initialDelay`. The controller log shows *Taking 0 Measurement(s)* at 09:40:20, then
  nothing until 09:54:34, with no restart. That healthy rollout took 1210 s instead of ~470 s. Two fix releases
  were slow by a similar amount (recovery 1479 s and 1515 s). It costs time, never a wrong decision. A `pause`
  step before each analysis, instead of `initialDelay`, is the candidate fix.

## E4 — Self-service database

- **Procedure:** apply the 10-line `Database` manifest from [DESIGN.md](DESIGN.md#10-self-service-database-crossplane-v2)
  on `local` (CNPG) and `azure` (Flexible Server). The `books` service mounts `<name>-conn` and runs a migration.
- **Measure:** apply → XR `Ready=True`; → service healthy and connected.
- **Pass:** byte-identical manifest works on both clusters; no manual steps.
- **Result so far (local):** `Database {size: small, version: "18"}` reached `Ready` in **804 s** on a cold
  cluster (CNPG operator readiness and the PostgreSQL image pull, [run 1](evidence/databases/2026-10-24T152723Z-books-db.json))
  and in **21 s** warm ([run 2](evidence/databases/2026-10-24T192111Z-orders-db.json)). Run 1 exposed a deviation:
  connection details came from CNPG's `<name>-app` Secret, not the `<name>-conn` that DESIGN §10 specifies, so
  the Secret name depended on the backend. Fixed in warden-infra `a12d1b9`: the composition now owns
  `<name>-conn` (exactly host, port, dbname, username, password, uri) and gives it to CNPG. Run 2 checked that
  `psql` with the `uri` connects over TCP, that a wrong password is refused, and that the password survives
  forced reconciles. Not yet done: the service-side migration, repeat runs, and the azure run (needs a
  `database-azure` composition).

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
- **Result so far (local, [ledger](evidence/rebuilds/rebuild-ledger.csv), [smoke checks](evidence/rebuilds/smoke.jsonl)):**
  12 rebuilds recorded, **11 ok** (local target ≥ 10 met), 1 failed.
  - The failure was the first attempt on 2026-10-24: host port 8080 was held by `wslrelay`. The gateway now
    binds `127.0.0.1:18080`.
  - Successful rebuilds: **median 894.0 s (14.9 min), p90 1452 s (24.2 min)**, range 404–1583 s.
  - The last one (636 s) ran after ADR-029's per-source AppProjects merged. The ApplicationSets render before
    the `projects` app has created the new AppProjects, but they converge by themselves within the bootstrap
    wait; still zero manual steps. Migrating a *running* cluster needed one ApplicationSet refresh.
  - Nine consecutive rounds by `scripts/experiments/rebuilds.py` on 2026-10-25, all at clean commits of all four
    repos, had zero manual steps.
  - After each round, all 21 Argo CD applications were Synced/Healthy and all four services answered 200
    through the gateway, within a second of the task finishing.
  - The duration spread is large. The last four rounds (407–898 s) were much faster than the first five
    (881–1452 s). Not investigated: likely registry and network conditions during image pulls.
  - Not yet done: the azure rebuilds (target ≥ 5; needs `task up:azure`).

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

**Result (2026-10-25, same laptop and Docker, [evidence](evidence/comparison/2026-10-25T000834Z-idpbuilder.json)):**
idpbuilder v0.10.2 has no Windows build, and a source build fails on Windows (it creates a directory whose
name contains `:`). It was therefore run as its verified Linux binary in a container on the same Docker
Desktop. Measuring the setup also turned up this portability difference.

| Criterion | idpbuilder v0.10.2 | Warden |
|-----------|--------------------|--------|
| Time to first deployed service | **8.5 min**: platform + a pre-built public image from a local package | platform cold bootstrap 26.4 min (S2), then **8.6 min** median per new service (E1), including repo creation, build, signing and promotion |
| Supply-chain verification at admission | **absent**: no policy engine, no VAPs; an image by tag is admitted | signer identity, source repo, branch, SBOM; tag and foreign registry refused (E2 13/13) |
| Policy engine and default policies | none (only ingress-nginx's own webhook) | VAPs + Kyverno CEL policies, Audit until M3 |
| Progressive delivery and auto-rollback | absent | Argo Rollouts canary with Prometheus analysis (E3 pending) |
| Self-service infrastructure | absent in the core install | Crossplane `Database` (E4) |
| Developer portal | not in the core install (Backstage via separate stacks) | CLI + catalog files (ADR-017) |
| Resource footprint (`docker stats`, same moment) | **2.2 GiB**, 1 node, 6 CRDs | **8.8 GiB**, 2 nodes, 96 CRDs, with four services and load running |
| Cloud path | local only | local + AKS (written, not yet applied) |
| Ingress | ingress-nginx (retired March 2026, RESEARCH finding 2) | Gateway API + Envoy Gateway |

Reading: idpbuilder gets a GitOps loop running about 3× faster and in a quarter of the memory. Warden's extra
cost buys the things the synopsis is about: verified admission, canary analysis and self-service data.

## E8 — Cost of verification

- **Procedure:** create 50 Pods of a signed image with policies in Deny vs 50 with policies removed; record
  admission latency (Kyverno `kyverno_admission_review_duration_seconds`, API server audit) and Pod-ready time.
  Repeat with a warm and a cold verification cache.
- **Report:** p50/p95 added latency per Pod. Expected: noticeable on cold cache (registry + tlog lookups), small when warm.
- **Method used:** server-side dry-run Pod creates (all admission webhooks run, nothing is scheduled), so the
  number is admission time only. Baseline: the same namespace and webhooks with an image no IVP matches.
- **Result (2026-10-24, kind, [run](evidence/verification/2026-10-24T192711Z.json)):** baseline p50 0.17 s. Verified,
  cold (first request per digest after replacing the Kyverno pod): p50 23.6 s, n = 4. Warm (same four digests
  again): p50 **15.6 s**, p95 17.0 s, n = 50. Added latency: **+15.4 s warm, +23.5 s cold per Pod**. The expected
  warm-cache saving barely exists: warm is only ~8 s faster than cold, and every Pod of every release pays it.
  Kyverno's own counters attribute it to the two IVPs: about **15.2 s per verified Pod** for the supply-chain
  IVP and 8.7 s for the vulnerability IVP (warm). Those counters also count the 50 baseline requests, which
  finish instantly, so raw means must be recomputed per verified Pod; an earlier version of this section
  quoted the diluted 7.9 s / 4.4 s. The two webhooks run in parallel, so the client latency is the slower IVP,
  not the sum.
- **Spot check three hours later ([evidence](evidence/verification/2026-10-24T224721Z-spotcheck.json)):** 21.7 s, then
  30.2 s twice, the 30 s webhook timeout. Kyverno spent 35 s and 22 s per execution and was not CPU-bound;
  DNS and every Sigstore/GHCR endpoint answered in under 1.1 s. With `failurePolicy: Ignore`, those Pods were
  admitted unverified.
- **Root cause ([trace](evidence/verification/2026-10-24T225231Z-root-cause.json)):** the same policy, run through
  the kyverno CLI against the same image, takes 33–36 s and makes **95 sequential HTTPS requests**:
  - each of the 16 registry accesses re-pings `/v2/` and fetches a new anonymous GHCR token;
  - the Sigstore trust root (TUF) is initialised again for each of the three cosign verifications (signature,
    provenance, SBOM), 6 requests each;
  - nothing is reused between verifications of the same digest.

  At ~0.3 s per round trip that accounts for the time. The cost is per Pod and per policy, so replicas,
  restarts and canary steps all pay it.
- **Consequence:** verification as configured is too slow and too variable for M3. With `Fail` + `Deny`, Pods
  would be refused whenever verification exceeds 30 s (the maximum `timeoutSeconds`). Levers before M3, each to
  be measured with this runner:
  - fewer verifications per Pod: rely on the signed provenance attestation instead of a separate image
    signature, and fold the vulnerability check into the same policy (an ADR, because it changes what is
    checked);
  - a pinned trusted root instead of TUF;
  - verifying once per Rollout template instead of per Pod.

  Upstream, Kyverno could reuse the registry token and the TUF client across verifications.
- **After ADR-030 ([run](evidence/verification/2026-10-24T232000Z.json)):** the separate image-signature check
  is gone and the vulnerability IVP runs in background scans only. Warm p50 **14.8 s** (was 15.6 s), p95
  16.5 s; cold 22–30 s (n = 4, two at the timeout). **No real warm gain.** The supply-chain IVP still takes
  ≈15.7 s per verified Pod with two attestation verifications. The removed signature check was apparently
  cheap once warm, and the two uncached attestation verifications (~7.5 s each) are the cost. Moving the
  vulnerability IVP out of admission removed ~8.7 s of verification work and its GHCR traffic per Pod, but
  it never added latency, because it ran in parallel. The remaining levers are structural: an upstream
  Kyverno fix, or ReplicaSet-level verification (ADR-030, consequences).

## M3 readiness — ADR-020 exit criteria (added 2026-10-25)

ADR-020 allows `Deny` when (a) 5 consecutive legitimate deployments of all four services show zero audit
violations and (b) every attack shows its expected violation.

- **(b): met.** 15/15 (E2).
- **(a): measured on 2026-10-25 ([evidence](evidence/m3/readiness-20261025T104356Z.json)). Not met for the
  supply-chain IVP.**
  - **Deployments:** 5 consecutive promoted releases of each service, 20 in all.
  - **VAPs:** 0 violations. The VAPs have no counter or report, so every deployed Rollout and a Pod from its
    template were re-submitted as server-side dry runs.
  - **Pod hygiene:** 10/10 PolicyReports pass.
  - **Supply-chain IVP: 38 pass, 2 fail.** Both fails were transient network errors that Kyverno 1.19.2 turns
    into policy failures without retrying:
    - a truncated download of a 2 MB SBOM bundle (`failed to read layer: unexpected EOF`), reported as "required
      predicate type https://cyclonedx.org/bom not found"; cosign verifies that SBOM fine;
    - a failed fetch of Sigstore's TUF root.
  - **Timeouts:** 4 more admissions outlived the 30 s webhook timeout (E8).
- **Reading:** with `Deny` + `Fail`, about 1 in 20 legitimate Pods would be refused, more on a slow network. The
  deterministic layers (VAPs, hygiene) meet (a); image verification does not, on this Kyverno version.

