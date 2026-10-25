# Warden — final report

> **DRAFT, results as of 2026-10-25.** Milestone M3 (enforce) is not reached; several experiments have no valid
> run yet. Every number below links to the evidence file it comes from. Sections marked *open* are not done.

## 1. Problem and contribution

Internal delivery platforms usually solve "how do I ship a service" and leave "can I prove what is running"
to someone else. Warden puts both on one golden path: one command scaffolds a service, and every release is
built by a single trusted workflow, signed and attested. The cluster admits only images whose signature and
provenance name that workflow. Releases roll out as canaries, and a canary that fails its metrics rolls back
without a human. The sample services are deliberately trivial; the platform is the product
([DESIGN §1–2](../../DESIGN.md#1-what-warden-is)).

What is new compared with a typical student platform:

- **Admission checks provenance, not just signatures.** A valid Sigstore signature only proves *someone* with a
  GitHub OIDC token signed it ([THREAT_MODEL §7](../../THREAT_MODEL.md#7-what-a-valid-signature-does-not-prove)).
  Warden's ImageValidatingPolicy also pins the signing workflow identity, the source repository prefix and the
  branch. The attack suite tests each of those separately.
- **CI holds no cluster credentials.** Builds write to Git; Argo CD pulls (ADR-014, T09).
- **Every claim has an experiment** (E1–E8 in [EVALUATION.md](../../EVALUATION.md)), and the experiments found real
  defects (§5).

## 2. What was built

| Repository | Contents | Design |
|------------|----------|--------|
| hub `warden` | DESIGN, 28 ADRs, threat model T01–T20, evaluation plan, `versions.yaml` (every pin), `scripts/verify.py` (10 workspace checks), experiment runners, evidence | — |
| `warden-platform` | Reusable workflow `build-sign-attest.yml` (release `v0.1.0`, the only trusted builder), `warden` CLI (Go: `new`, `verify`, `status`, `dora`, `setup-apps`), Spring Boot 4.1 service template, canary analysis template, dashboards, k6 load | [§5](../../DESIGN.md#5-delivery-path), [§11](../../DESIGN.md#11-scaffolding--the-warden-cli) |
| `warden-policy` | Native VAPs (registry, digest, ephemeral-container hygiene), Kyverno IVPs (signature, provenance, SBOM, vulnerability), hygiene ValidatingPolicy, `kyverno test` suites, attack suite A01–A12 | [§7](../../DESIGN.md#7-admission-control) |
| `warden-gitops` | App-of-apps for kind and AKS, platform ApplicationSet (9 pinned charts), config and apps ApplicationSets, `digest-only` promotion guard | [§8](../../DESIGN.md#8-gitops-layout) |
| `warden-infra` | kind config, OpenTofu for AKS (Entra-only access, budget, GitHub OIDC), Crossplane v2 `Database` API with a CloudNativePG composition, Taskfile with a rebuild ledger | [§10](../../DESIGN.md#10-self-service-database-crossplane-v2), [§14](../../DESIGN.md#14-bootstrap-and-rebuild) |

Four services (books, loans, members, notify) were generated with `warden new` and run on the kind cluster.

## 3. Evaluation results

| ID | Claim | Status | Headline | Evidence |
|----|-------|--------|----------|----------|
| E1 | One command creates and deploys a service | partial | median **8.6 min**, **0** manual steps (3 full runs, kind) | [scaffold timings](../../evidence/scaffold-timings/) |
| E2 | Unverifiable artifacts are refused | partial | **14/14**: one legitimate deployment admitted, A01–A13 refused for the expected reason (A13 added: unsigned initContainer) | [latest run](../../evidence/attacks/2026-10-25T023330Z-results.json) |
| E3 | Faulty releases roll back without humans | *open* | no valid run yet; the first runs found two defects (§5) | — |
| E4 | A database from a short request | partial | `Ready` in 804 s cold, 21 s warm; `<name>-conn` Secret verified | [run 1](../../evidence/databases/2026-10-24T152723Z-books-db.json), [run 2](../../evidence/databases/2026-10-24T192111Z-orders-db.json) |
| E5 | DORA metrics from real history | *open* | needs the deployments GitHub App (`warden setup-apps`) | — |
| E6 | Environment rebuildable from Git | local done, azure open | **10/11** local rebuilds ok (the failure is understood), median **15.1 min**, p90 24.2 min, 0 manual steps, all apps and services healthy after each | [ledger](../../evidence/rebuilds/rebuild-ledger.csv), [smoke](../../evidence/rebuilds/smoke.jsonl) |
| E7 | Comparison with CNOE idpbuilder | done (one run) | idpbuilder: GitOps + first app in 8.5 min, 2.2 GiB, no admission control; Warden: 8.8 GiB with verified admission, canaries, self-service DB | [run](../../evidence/comparison/2026-10-25T000834Z-idpbuilder.json) |
| E8 | Cost of verification | done (kind) | **+15.4 s per Pod warm, +23.5 s cold**; timeouts in a later spot check | [run](../../evidence/verification/2026-10-24T192711Z.json), [spot check](../../evidence/verification/2026-10-24T224721Z-spotcheck.json) |

Details, procedures and pass criteria: [EVALUATION.md](../../EVALUATION.md). E2 runs against `Deny` clones of the
policies, because the live policies stay in `Audit` until M3 (ADR-020).

## 4. How trust flows (summary)

1. A commit on a service's `main` runs the platform's reusable workflow. The `build` job runs project code with no
   `id-token` permission. The `sign-attest` job is the only one that can mint a Sigstore certificate, and it never
   checks out code ([DESIGN §6](../../DESIGN.md#6-identity-and-trust-model), T11).
2. The image is signed and carries three attestations: SLSA provenance, a CycloneDX SBOM and a vulnerability
   scan.
3. A digest-only pull request promotes it in `warden-gitops`. Argo CD syncs it. Admission runs in three layers:
   - VAP: registry and digest (T01, T06);
   - Kyverno IVP: signer identity, source repository, branch, attestations (T02–T05, T07, T08);
   - hygiene policies.
4. Argo Rollouts shifts 5 → 25 → 50 % of traffic. Prometheus analysis aborts on error rate or p95 latency
   ([DESIGN §9](../../DESIGN.md#9-progressive-delivery)).

## 5. Defects the evaluation found

Each was found by running an experiment, not by review. The fix and the evidence are linked.

| Found by | Defect | Fix |
|----------|--------|-----|
| E2 (A01) | The vulnerability IVP's default `mutateDigest: true` rewrote tags to digests, so a tag reference was **admitted** | `mutateDigest: false`; `verify.py` now rejects any IVP without it |
| E2 (GOOD) | An Audit-mode IVP with `failurePolicy: Fail` denied a legitimate Pod on a webhook timeout | Audit phase uses `Ignore`; the lab clones use `Fail` |
| E1 | First build blocked by the scan gate (Tomcat CVEs in Spring Boot 4.1.1) | Spring Boot 4.1.2 |
| E1 | GHCR packages created by Actions start private; the org also forbade public packages | org setting, then 0 manual steps (ADR-028 update) |
| S2 | Kyverno CRDs permanently OutOfSync (`labels: {}` from the chart) | chart value `kyverno-api.labels` |
| E3 | AnalysisRun measured 9 s after the canary started, got an empty result, paused every rollout | `initialDelay: 2m`, actuator traffic excluded (warden-platform `04ab349`) |
| E3 | Argo CD's sync reverted the Service selector hash and HTTPRoute weights set by Argo Rollouts: the canary took **1/3 of traffic instead of 5 %** | `ignoreDifferences` + `RespectIgnoreDifferences` (warden-gitops#16, open) |
| E3 | Injected 500s have `uri="UNKNOWN"`, so a blast-radius query on `/api/.*` counted none | runner excludes `/actuator` instead |
| E4 | The connection Secret's name depended on the backend (`<name>-app`), breaking the cross-cluster claim | composition owns `<name>-conn` (warden-infra `a12d1b9`) |
| tests | `tests/cli` was empty; the Rollouts VAP, exempt namespaces and the ephemeral-container VAP had no test | 24 `kyverno test` cases in CI, live smoke checks for the rest |
| E8 | Verification takes 15–35 s per Pod and can exceed the 30 s webhook timeout; in the Audit phase that **fails open**. Cause: ~30 sequential HTTPS requests per attestation verification (new GHCR token per access, trust root rebuilt per verification), nothing cached | ADR-030 removed redundant work but gave no warm gain (15.6 → 14.8 s); *open*: needs an upstream Kyverno fix or ReplicaSet-level verification before M3 |

## 6. Threat model coverage

[THREAT_MODEL.md §5](../../THREAT_MODEL.md#5-threats-controls-and-tests) maps T01–T20 to a control and a test. The
attack suite exercises T01–T09 and T11–T13 on a live cluster (A13 adds a second T02 path). Accepted residual risks, including the three found
while building (fail-open verification until M3, the CNPG image carve-out, and the fields Argo CD no longer
restores), are in [§8](../../THREAT_MODEL.md#8-residual-risks-accepted).

## 7. Limitations and open work

- **M3 is not reached.** Policies are in `Audit`, and verification latency (E8) must come down before `Deny` +
  `Fail` is safe.
- **AKS has never been applied.** The OpenTofu stacks validate, but `tofu plan` waits on an Azure re-login, and
  creating the cluster spends student credit. Every number above is from kind.
- **E3 and E5 have no results.** E3 needs warden-gitops#16 merged first. E5 needs the deployments GitHub App.
- **Small samples.** E1 has 3 full runs (5 planned per cluster), E4 has 2, E8 one run plus a spot check.
- **Config apps run in Argo CD's `default` project**, so any of the four source repos can deploy any kind
  (being scoped in its own task, ADR-029).

## 8. Reproducing

```bash
./.venv/Scripts/python.exe scripts/doctor.py                            # tools vs versions.yaml
task -d warden-infra up:local                                          # kind + Argo CD + everything in Git
python warden-policy/attacks/run_attacks.py                            # E2
python scripts/experiments/canary.py <svc> error --admin-merge         # E3 (owner-approved merges only)
python scripts/experiments/verification_cost.py --n 50                 # E8
```
