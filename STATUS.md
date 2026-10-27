# Warden: status and hand-off

Last updated 2026-10-27. Read this first when you pick the project up again. It says where things stand, what is
left, in what order, and which traps cost us time. Anything it contradicts elsewhere is stale: fix the other file.

## Where the project stands

The platform is built and measured. Eight experiments (E1 to E8) have evidence in `evidence/`. The technical design
document is written ([docs/report/report.md](docs/report/report.md)), and the [mini project report](docs/report/Warden-Mini-Project-Report.pdf)
follows the supplied Batch C2 format. A 17-slide deck and PDF are included in [docs/submission](docs/submission/).
What remains is the managed-database live check, release housekeeping, recordings and the people tasks below.

| Milestone | State |
|-----------|-------|
| M0 Foundations | Done. Spikes S1 and S2 closed; S3 partly (one subscription) |
| M1 Walking skeleton | Done 2026-10-26 (`up:local` and `up:azure` both work) |
| M2 Trust and safety in Audit | Done |
| M3 Enforce | Staged. The native admission policies and pod hygiene deny; image verification stays in Audit until Kyverno improves (ADR-020, ADR-032, ADR-036) |
| M4 Evaluated, `v1.0.0` tags | E1 to E8 have results with gaps listed below; no `v1.0.0` tag yet |
| M5 Presented | Report and deck exist; recordings and the live demo are open |

## Experiments

| ID | State | What is missing |
|----|-------|-----------------|
| E1 scaffolding | 5 full runs on kind (median 8.6 min, range 7.6–9.6 min, 0 manual steps) | Azure runs and the hand-timed baseline |
| E2 attack suite | 15 of 15 on kind and on AKS | Nothing; wire it into CI if time allows |
| E3 canary rollback | 10 of 10 faulty aborted, 10 of 10 healthy promoted (kind) | Optional spot check on Azure |
| E4 database | Existing results: kind and AKS on CloudNativePG | Azure Flexible Server implementation is in review-ready PRs [infra #3](https://github.com/WARDEN-CCD/warden-infra/pull/3) and [GitOps #114](https://github.com/WARDEN-CCD/warden-gitops/pull/114); still needs approval, merge, live connection test, deletion and teardown |
| E5 DORA | Original owner-merge batch plus a 20-deployment app-only repeat: 12/12 measured healthy promoted, 4/4 faults aborted, 4/4 fixes promoted; DORA median lead 12.5 min and recovery 12.6 min | Nothing in kind; Azure comparison would require a separate run |
| E6 rebuilds | Local 12 of 13 ok (median 14.8 min, p90 24.2 min); Azure 5 ok (median 22 min, zero manual steps) and 4 recorded, explained failures | Nothing; target met |
| E7 comparison | One run each against idpbuilder | Nothing |
| E8 verification cost | Kind and AKS measured | Nothing; blocked on upstream for any improvement |

## What to do next, in order

0. **Platform fix verified.** [warden-platform#4](https://github.com/WARDEN-CCD/warden-platform/pull/4) merged on
   2026-10-27, and release `v0.1.2` points at `8ec5ff6`. All four services use it. Their push workflows completed,
   and the promoter app authored and merged GitOps PRs #97–#100 without an owner merge. The [svc-books run](https://github.com/WARDEN-CCD/svc-books/actions/runs/40502485200) and [GitOps PR #100](https://github.com/WARDEN-CCD/warden-gitops/pull/100) show the path. The 2026-10-27 20-deployment E5 repeat then measured the app-only path across the four services.
2. **E1 local target is now met:** five complete runs on kind; median 8.6 min, zero manual steps. The two new runs are
   `evidence/scaffold-timings/2026-10-27T131930Z-eval-final-a.json` and
   `evidence/scaffold-timings/2026-10-27T132720Z-eval-final-b.json`. Azure runs and a hand-timed baseline remain open.
3. **E6 target is met** (12/13 local and 5/9 Azure rebuilds succeeded). The fresh local rehearsal on 2026-10-27
   took 869 s; 23/23 apps were Synced/Healthy and all four services returned HTTP 200. The Azure task can be rerun with
   `scripts/experiments/azure_rebuilds.py --n <rounds>
   --kubeconfig <separate file>` runs `up:azure`, a smoke check and `down:azure` per round and appends to
   `evidence/rebuilds/smoke.jsonl` and the ledger. Leave a few minutes between rounds: starting right after a destroy hit
   Azure's `409 Conflict ... pending delete operation` once. One round took 57 minutes to bootstrap against about 22 for
   the others; the cause was not found. Never leave a cluster up.
4. **Kyverno reports filed** on 2026-10-27: the [request-count comment](https://github.com/kyverno/kyverno/issues/17832#issuecomment-6441526018),
   [ReplicaSet issue](https://github.com/kyverno/kyverno/issues/18314), and
   [transient-fetch issue](https://github.com/kyverno/kyverno/issues/18315). Track fixes before another M3 readiness run.
5. **Managed database remains open:** review and merge [infra #3](https://github.com/WARDEN-CCD/warden-infra/pull/3), then [GitOps #114](https://github.com/WARDEN-CCD/warden-gitops/pull/114); provision one Flexible Server,
   test the `<name>-conn` Secret from a service Pod and verify teardown before changing E4's claim.
6. **Tag `v1.0.0`** in every repository once the service release is verified and the docs are final. In `warden-platform` the
   tag must be created from a reviewed `main` and the services should then point at it.
7. **Recordings and presentation.** The deck and PDF are in [docs/submission](docs/submission/); scenes and commands are in
   [docs/demo-script.md](docs/demo-script.md). A fresh local rebuild rehearsal passed on 2026-10-27; record the scenes and
   update slide 15 with the state on presentation day.
8. **Individual contributions** are summarized by responsibility area in report section 9. The team has confirmed these
   areas; they are not a commit-by-commit authorship record.
9. **People tasks** from [ROADMAP.md](ROADMAP.md): the invitation for Shaurya Jain is pending acceptance; each member enables
   two-factor sign-in and then the organization requirement is switched on, decide on code-owner review.
10. **Small clean-up.** The obsolete `DRAFT` header was removed in merged [warden-platform#6](https://github.com/WARDEN-CCD/warden-platform/pull/6).
11. **Full M3** waits for a Kyverno release that retries transient errors and cuts per-Pod latency. Re-measure with
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
changed. Experiment runners are in `scripts/experiments/` and write to `evidence/`. Project rules are in the
repository READMEs and [DECISIONS.md](DECISIONS.md).

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
  backslashes. Run `./.venv/Scripts/python.exe scripts/verify.py` before merging changes.
- **Publishing actions.** Protected `main` requires a reviewed pull request. Follow the repository rulesets for
  releases and changes to other projects.

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
