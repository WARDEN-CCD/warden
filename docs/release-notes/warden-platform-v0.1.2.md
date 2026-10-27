Third release of Warden's trusted build workflow (`build-sign-attest.yml`) and the `warden` CLI.

- The promote job merges its digest-only pull request through GitHub's REST endpoint (`PUT /pulls/{n}/merge`), pinned to the commit it pushed (`sha`). v0.1.1 called `gh pr merge`, which refuses a blocked pull request on the client unless `--admin` is given, so its merge never reached GitHub. GitHub still refuses until the required `digest-only` check passes, and then decides whether the app's review bypass applies (hub ADR-034).

Admission trusts this workflow at any protected `v*` tag (hub ADR-009 and ADR-010). Tags cannot be moved or deleted.
