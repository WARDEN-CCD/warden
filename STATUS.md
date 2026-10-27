# Warden: status and hand-off

Last updated 2026-10-27. Read this first when you pick the project up again. It says where things stand, what is
left, in what order, and which traps cost us time. Anything it contradicts elsewhere is stale: fix the other file.

## Where the project stands

The platform is built and measured. Eight experiments (E1 to E8) have evidence in `evidence/`, the technical design
document is written ([docs/report/report.md](docs/report/report.md)), and a 14-slide deck exists (link in
[docs/demo-script.md](docs/demo-script.md)). What remains is release housekeeping, the Azure rebuilds, tags, recordings
and the people tasks below.

| Milestone | State |
|-----------|-------|
| M0 Foundations | Done. Spikes S1 and S2 closed; S3 partly (one subscription) |
| M1 Walking skeleton | Done 2026-10-26 (`up:local` and `up:azure` both work) |
| M2 Trust and safety in Audit | Done |
| M3 Enforce | Staged. The native admission policies and pod hygiene deny; image verification stays in Audit until Kyverno improves (ADR-020, ADR-032) |
| M4 Evaluated, `v1.0.0` tags | E1 to E8 have results with gaps listed below; no `v1.0.0` tag yet |
| M5 Presented | Report and deck exist; recordings and the live demo are open |

## Experiments

| ID | State | What is missing |
|----|-------|-----------------|
| E1 scaffolding | 3 full runs on kind (median 8.6 min, 0 manual steps) | 5 runs per cluster, Azure runs, the hand-timed baseline |
| E2 attack suite | 15 of 15 on kind and on AKS | Nothing; wire it into CI if time allows |
| E3 canary rollback | 10 of 10 faulty aborted, 10 of 10 healthy promoted (kind) | Optional spot check on Azure |
| E4 database | Ready on kind and AKS | The `database-azure` composition is not written |
| E5 DORA | 20 releases, 4 injected faults, figures cross-checked (kind) | Repeat on a release that uses the bot's own merge (after v0.1.1) |
| E6 rebuilds | Local 11 of 12 ok. Azure: see [EVALUATION.md](EVALUATION.md) E6 for the current count | Target is at least 5 Azure rebuilds |
| E7 comparison | One run each against idpbuilder | Nothing |
| E8 verification cost | Kind and AKS measured | Nothing; blocked on upstream for any improvement |

## What to do next, in order

0. **Merge the four documentation pull requests** (README and header updates only, one per repository):
   [warden-gitops#94](https://github.com/WARDEN-CCD/warden-gitops/pull/94),
   [warden-infra#1](https://github.com/WARDEN-CCD/warden-infra/pull/1),
   [warden-policy#3](https://github.com/WARDEN-CCD/warden-policy/pull/3),
   [warden-platform#3](https://github.com/WARDEN-CCD/warden-platform/pull/3). Then `git pull` in each checkout.
1. **Create release v0.1.1 of warden-platform.** Both PRs are merged (`5e48ae2` promote job, `b1813bd` CLI fix), but
   no tag exists. Run this yourself; automated sessions were refused permission to publish releases:
   ```bash
   gh release create v0.1.1 --repo WARDEN-CCD/warden-platform --target 5e48ae2 \
     --title "v0.1.1: promote job merges its own PR; warden dora counts promotions once" \
     --notes-file docs/release-notes/warden-platform-v0.1.1.md
   ```
2. **Move the services to v0.1.1 and test the bot's own merge.** In each of `svc-books`, `svc-loans`, `svc-members` and
   `svc-notify`, change `.github/workflows/delivery.yml` from `...build-sign-attest.yml@v0.1.0` to `@v0.1.1`. Change the
   default `platform-ref` in `warden-platform/cli/cmd/warden/main.go` and `new.go` (and the test in
   `internal/render`). Then ship one release **without** `--admin-merge`
   (`python scripts/experiments/canary.py books healthy`) and check that the bot's PR merges itself. If it does, mark
   ADR-034 "verified". If GitHub refuses the app's merge, the fallback is the owner bypass the E5 batch used.
   Do this only when no Azure round is running: a rollout in progress can delay the smoke check.
3. **Finish E6 on Azure.** `scripts/experiments/azure_rebuilds.py --n <rounds> --kubeconfig <separate file>` runs
   `up:azure`, a smoke check, and `down:azure` per round, and appends to `evidence/rebuilds/smoke.jsonl` and the ledger.
   The first round on 2026-10-27 took 57 minutes to bootstrap, against 20 minutes in the first run, because the
   bootstrap waited on slow applications; check round records before running more. Never leave a cluster up.
4. **File the Kyverno reports** (three texts and the exact `gh` commands are in [docs/upstream](docs/upstream/README.md)).
5. **Tag `v1.0.0`** in every repository once items 1 to 3 are settled and the docs are final. In `warden-platform` the
   tag must be created from a reviewed `main` and the services should then point at it.
6. **Recordings and presentation.** Scenes and commands: [docs/demo-script.md](docs/demo-script.md). Update the deck's
   last slide (open items) on the day.
7. **Individual contributions** in report section 9: each member writes their own row (the names are filled in).
8. **People tasks** from [ROADMAP.md](ROADMAP.md): invite Shaurya Jain to the organization, every member enables
   two-factor sign-in and then the organization requirement is switched on, decide on code-owner review.
9. **Small clean-ups.** Remove the `DRAFT` header from `warden-gitops/.github/workflows/digest-only.yml` and
   `warden-infra/Taskfile.yml` (both have run). The header in `build-sign-attest.yml` goes with the next workflow release.
10. **Full M3** waits for a Kyverno release that retries transient errors and cuts per-Pod latency. Re-measure with
    `scripts/experiments/m3_readiness.py` and `verification_cost.py`, then follow ADR-020.

## Check this before anything else

- **Azure must not be left running.** Run `az group list --query "[].name" -o tsv`. Expected: `NetworkWatcherRG` and
  `warden-tfstate` only. If `warden` or `MC_warden_*` appear, run `task -d warden-infra down:azure` (needs
  `~/.warden/env` and `az login`).
- **The kind cluster** `kind-warden` may still be running with the four services. `task -d warden-infra up:local`
  rebuilds it in about 15 minutes if it is gone.
- **Open pull requests:** `gh pr list` in each repository. `warden-gitops` normally has none.

## How to resume

```bash
./.venv/Scripts/python.exe scripts/doctor.py     # tools against versions.yaml and ~/.warden/env
./.venv/Scripts/python.exe scripts/verify.py     # workspace checks; must print "verify: OK"
task -d warden-infra up:local                    # only if the kind cluster is gone
```

The four platform repositories sit inside this folder and are ignored by the hub's Git. Run Git in the repository you
changed. Experiment runners are in `scripts/experiments/` and write to `evidence/`. Project rules are in
[CLAUDE.md](CLAUDE.md) and each repository's own `CLAUDE.md`.

## Traps we hit

- **State passphrase.** `TF_VAR_state_passphrase` in `~/.warden/env` encrypts the OpenTofu state. It changed after the
  first Azure cycle and the stored state could not be read. `~/.warden/backend.hcl` now uses
  `key = "warden-azure-2.tfstate"`; the old blob is untouched; a backup of the file is `backend.hcl.bak-20261026`. Keep
  a copy of the passphrase outside that file. After changing `key`, run `tofu init -reconfigure` once in
  `warden-infra/tofu/envs/azure`.
- **kubectl context.** `up:azure` runs `az aks get-credentials` and makes the AKS cluster the current context, which
  breaks any experiment running against kind. Use a separate kubeconfig (`KUBECONFIG=<file>` or the runner's
  `--kubeconfig`).
- **Bot pull requests do not merge themselves on v0.1.0.** GitHub's auto-merge ignores a ruleset bypass (ADR-034). The
  runner's `--admin-merge` merges them with the owner bypass once `digest-only` passes.
- **Audit hides denials.** Run each legitimate pod class under a policy in Deny before relying on it (ADR-033).
- **Windows shell.** Use `./.venv/Scripts/python.exe`. Write files with an editor, not a shell heredoc, when the text has
  backslashes. The Stop-hook check runs through cmd.exe (`.claude/verify.cmd`).
- **Publishing actions need a human.** Merging to a protected `main`, creating releases and posting to other
  projects were refused to the automated session. Pull requests and branches are fine.
- **Untracked `AGENTS.md`** in the hub and in `warden-platform` is not part of the project.

## Where things are

| Need | Where |
|------|-------|
| Architecture | [DESIGN.md](DESIGN.md) |
| Why we chose what we chose | [DECISIONS.md](DECISIONS.md) (ADR-001 to ADR-034) |
| Threats, controls, tests | [THREAT_MODEL.md](THREAT_MODEL.md) |
| Measurements and procedures | [EVALUATION.md](EVALUATION.md) and `evidence/` |
| Final report | [docs/report/report.md](docs/report/report.md) |
| Demo script and deck | [docs/demo-script.md](docs/demo-script.md) |
| Upstream Kyverno reports | [docs/upstream](docs/upstream/README.md) |
| Plan and risks | [ROADMAP.md](ROADMAP.md) |
| Every pinned version | [versions.yaml](versions.yaml) |
