Second release of Warden's trusted build workflow (`build-sign-attest.yml`) and the `warden` CLI.

- The promote job now merges its own digest-only pull request. GitHub's auto-merge ignores a ruleset bypass, so bot pull requests used to wait for a review nobody would give. The job retries the merge until the required `digest-only` check passes, and pins the merge to the commit it pushed (`--match-head-commit`). The app token is limited to `contents: write` and `pull-requests: write` (hub ADR-034).
- `warden dora` counts each promotion once and takes the newest success or failure as a deployment's outcome. New flags: `--until` and `--by-service`.

Admission trusts this workflow at any protected `v*` tag (hub ADR-009 and ADR-010). Tags cannot be moved or deleted.
