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
| 5 | A database from a short request | Apply a `Database` (`size: small`, `version: "18"`) in a service namespace on the tested CNPG backend | `Ready`, then the `<name>-conn` Secret with six keys; the app connects. State clearly that Azure Flexible Server is not live-tested yet. | E4, [databases](../evidence/databases/) |
| 6 | Delivery metrics | `warden dora --since <ts>` | Five DORA metrics from the recorded deployment history; distinguish the app-only 20-deployment batch from the original owner-merge batch | E5, [DORA evidence](../evidence/dora/) |
| 7 | Rebuild from Git | `task rebuild:local` in `warden-infra` (or show the Azure `up:azure` ledger row) | Empty cluster back to all apps healthy with no manual step | E6, [ledger](../evidence/rebuilds/rebuild-ledger.csv) |

Keep each scene under two minutes. Show failures as they are: scene 3 includes the harness lesson only if asked.
Scene 6 cannot be recorded honestly until E5 has real results.

## Presentation deck

The submission-ready deck is [Warden-CCD-Project-Presentation.pptx](submission/Warden-CCD-Project-Presentation.pptx), with a
matching PDF in the same folder. It has 17 slides and uses the measured E5 results. Slide 15 lists the open submission
gates; review it on presentation day. Regenerate both files with `node scripts/build_presentation.cjs` after editing the
source, then render and inspect the exported pages.

The deck covers the project outcomes, architecture, build trust boundary, admission layers, attack results, rollback,
database evaluation, DORA metrics, rebuild evidence, verification latency, engineering lessons, remaining gates and
technical references. The Azure database slide is explicitly marked as awaiting a live test.

## Checks before presenting

- Every number on a slide is copied from `EVALUATION.md` or the linked evidence file, not retyped from memory.
- No slide calls a policy "enforced" that is still in `Audit` (rule 11; check `evidence/m3/` for the current state).
- Anything not yet run is labelled as such, including the Azure Flexible Server connection and teardown test.
