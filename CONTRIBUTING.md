# Contributing to Warden

## Workflow

- **Trunk-based.** `main` is always deployable. Short-lived branches: `feat/…`, `fix/…`, `docs/…`, `spike/…`.
- **Every change is a PR** for team members. Direct pushes to `main` are rejected by rulesets (ADR-025/027):
  1 approval (2 in `warden-policy`), approvals dismissed on new pushes, review threads resolved, squash or rebase
  merges only. Required checks: `verify` + `zizmor` (hub), `digest-only` (`warden-gitops`).
- **Project owner exception (ADR-027):** the org owner (`Legion-Corpse`) may push directly to `main` and merge
  without approval. Exception: in `warden-gitops`, the owner still needs a PR (it merges without approval).
- **Nobody, owner included, can force-push or delete `main`.** Approvals count only from people with write
  access, i.e. members of `warden-maintainers` (ADR-026). Authors cannot approve their own PRs.
- **Release tags `v*` are immutable** in every repo: they cannot be moved or deleted, by anyone. Fix a bad release
  with a new one.
- **Push protection** blocks pushes containing detected secrets. If it fires, remove the secret from history; do
  not bypass the block.
- **Conventional Commits** (`feat:`, `fix:`, `docs:`, `chore:`, `revert:`). DORA rework rate depends on `fix:`
  and `revert:` being used honestly in service repos.
- Keep PRs small enough to review in 15 minutes.

## Definition of done

- [ ] Works on kind (`lite` profile); if it touches cloud paths, also on AKS once
- [ ] Tests: `kyverno test` for policies, unit tests for CLI/template code, `tofu validate` for infra
- [ ] `scripts/verify.py` passes in the hub; zizmor passes for workflow changes
- [ ] Docs updated (DESIGN section or repo README); ADR added if the change is architectural
- [ ] No `DRAFT` header left on a file that has now been exercised

## GitHub Actions rules

1. `permissions: {}` at workflow level; grant per job, minimum needed.
2. Third-party actions pinned by full SHA with a version comment. Get the SHA with:
   ```bash
   gh api repos/OWNER/REPO/git/ref/tags/vX.Y.Z --jq .object.sha
   ```
   (If `.object.type` is `tag`, dereference once more with `gh api repos/OWNER/REPO/git/tags/<sha> --jq .object.sha`.)
3. `actions/checkout` with `persist-credentials: false` unless the job must push.
4. Never interpolate untrusted input (`github.event.*.title`, branch names) directly into `run:`; pass via `env:`.
5. Security tools (Trivy, Syft, cosign) are installed from release binaries whose checksums are verified — not via
   wrapper actions (ADR-011).

## Adding an ADR

Append to [DECISIONS.md](DECISIONS.md): next number, add a row to the index table, use the template:

```markdown
## ADR-0NN: <decision in one line>

- **Status:** Proposed
- **Context:** <forces, facts with dates>
- **Decision:** <what we will do>
- **Consequences:** <good and bad>
- **Alternatives:** <what we rejected and why>
```

Discuss in the PR; set `Accepted` when merged.

## Version bumps

Renovate opens PRs. A bump of anything in [versions.yaml](versions.yaml) must update every place that uses it in
the same PR set (charts in `warden-gitops`, binaries in workflows, kind image in `warden-infra`). Re-verify
release dates/notes and update [RESEARCH.md](RESEARCH.md) when the change is significant.

## Evidence

Anything that backs an evaluation claim goes under `evidence/` in the hub (raw JSON/CSV, not screenshots alone).
Recordings go to `evidence/recordings/` only if small; otherwise link them.
