# Demo recordings and presentation outline (M5)

Runbook for the recordings in `evidence/recordings/` and the final presentation. Every scene shows something the
evidence folder already proves; the recording is a view of the evidence, never a replacement for it. Link large video
files from `evidence/recordings/README.md` instead of committing them.

Before recording: `./.venv/Scripts/python.exe scripts/doctor.py` passes, Docker Desktop is up, and the kind cluster is
running (`task up:local` in `warden-infra`; about 15 minutes cold, see E6). Rebuild the CLI first
(`go build` in `warden-platform/cli`) so `warden dora` accepts `--since` as a timestamp.

## Scenes

| # | Scene | What to run | What the viewer must see | Backing evidence |
|---|-------|-------------|--------------------------|------------------|
| 1 | A service from one command | `warden new <name>` | Repo created, first build signed, digest-only PR merged, Rollout healthy; the printed timing JSON | E1, [scaffold timings](../evidence/scaffold-timings/) |
| 2 | The pipeline's proof | `cosign tree` on the image, then `warden verify <image@sha256:...>` | Signature, SLSA provenance, SBOM and vulnerability attestation on one digest; the local verifier agrees with admission | E2, THREAT_MODEL T02, T08 |
| 3 | Admission refuses attacks | `./.venv/Scripts/python.exe warden-policy/attacks/run_attacks.py` | The A01–A14 table: each attack refused for its expected threat ID, plus the one legitimate deployment admitted | E2, [attacks](../evidence/attacks/) |
| 4 | A bad release rolls back | `./.venv/Scripts/python.exe scripts/experiments/canary.py <svc> error` | Canary at 20 %, analysis fails, Rollout aborts, traffic returns to stable with no human action | E3, [rollbacks](../evidence/rollbacks/) |
| 5 | A database from a short request | Apply a `Database` (`size: small`, `version: "18"`) in a service namespace | `Ready`, then the `<name>-conn` Secret with six keys; the app connects | E4, [databases](../evidence/databases/) |
| 6 | Delivery metrics | `warden dora --since <ts>` | Deployment frequency, lead time, change failure rate, recovery time, rework rate from GitHub Deployments | E5 (open until the release batch runs) |
| 7 | Rebuild from Git | `task rebuild:local` in `warden-infra` (or show the Azure `up:azure` ledger row) | Empty cluster back to all apps healthy with no manual step | E6, [ledger](../evidence/rebuilds/rebuild-ledger.csv) |

Keep each scene under two minutes. Show failures as they are: scene 3 includes the harness lesson only if asked.
Scene 6 cannot be recorded honestly until E5 has real results.

## Presentation outline (about 15 slides)

A 14-slide presentation draft exists. Export it to the team submission folder before presenting. It uses the final
E5 numbers. Update the last slide's "still open" list on the day of the presentation.

1. **Problem.** Signed images prove origin, not safety (THREAT_MODEL §7). Real incidents: SolarWinds, tj-actions, trivy-action (§6).
2. **Claim.** A small platform where every Pod's image is traceable to a commit, a workflow and a review, and a bad release undoes itself.
3. **Architecture.** DESIGN §3 diagram: kind and AKS, Argo CD pull, Envoy Gateway, Crossplane, Kyverno + VAP.
4. **Trust chain.** Build with no `id-token`, sign with no checkout, promote by digest-only PR (DESIGN §6, ADR-009/013).
5. **Admission in three layers.** VAP for cheap invariants, Kyverno for signatures and attestations, pod hygiene.
6. **Scene 1 and 2 live.** E1 numbers: median 8.6 min, 0 manual steps.
7. **Threats to tests.** Table T01–T21 against A01–A14; scene 3 live (E2: 15/15 on kind and AKS).
8. **Safe releases.** Canary + analysis; E3: 10/10 aborted (median 147 s), 10/10 healthy promoted.
9. **Self-service data.** E4: 138 s on AKS, same manifest on both clusters.
10. **Reproducibility.** E6: Azure from nothing in 20 min; local median 14.9 min, p90 24.2 min.
11. **What verification costs.** E8: +14–15 s per Pod; why enforcement of image verification is staged (ADR-020/032).
12. **Comparison.** E7 against idpbuilder: 8.5 min and 2.2 GiB with no admission control, versus 8.8 GiB with verified admission.
13. **What went wrong.** The Audit-mode carve-out that would have stopped every database (ADR-033); bot PRs that could not self-merge (ADR-034); the Kyverno reports-controller crash loop with cause not established.
14. **Limits.** Residual risks 1–9 (THREAT_MODEL §8); T17 not prevented; full M3 blocked on Kyverno retry and latency; E3 and E1 not yet repeated on Azure.
15. **Delivery metrics and next steps.** E5 once measured; upstream issues for Kyverno; v1.0.0.

## Checks before presenting

- Every number on a slide is copied from `EVALUATION.md` or the linked evidence file, not retyped from memory.
- No slide calls a policy "enforced" that is still in `Audit` (rule 11; check `evidence/m3/` for the current state).
- Anything not yet run is labelled as such, including E5 until it has results.
