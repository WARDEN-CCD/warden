# Evidence

Raw data behind every claim in [EVALUATION.md](../EVALUATION.md). Commit machine-readable files (JSON/CSV);
screenshots alone are not evidence.

| Folder | Written by | Experiment |
|--------|-----------|------------|
| `scaffold-timings/` | `warden new` (one JSON per run) | E1 |
| `attacks/` | `warden-policy/attacks/run-all` | E2 |
| `rollbacks/` | rollback experiment script + Grafana snapshot | E3 |
| `dora/` | `warden dora --json` snapshots | E5 |
| `rebuilds/rebuild-ledger.csv` | `task up:*` / `task rebuild:*` in `warden-infra` | E6 |
| `recordings/` | demo recordings (link large files instead of committing them) | all |

Spike outcomes (S1–S3) go in `spikes/` as short Markdown write-ups: question, setup, result, decision.
