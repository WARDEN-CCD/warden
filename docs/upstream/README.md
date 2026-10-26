# Upstream reports for kyverno/kyverno

Prepared 2026-10-26 from Warden's E8 and M3 work on Kyverno v1.19.2 (the latest release on that date). **Not filed.**
Posting to another project is for a team member to do from their own account.

Searched upstream first (2026-10-26): draft 1 (per-request registry re-authentication) is already
[kyverno/kyverno#17832](https://github.com/kyverno/kyverno/issues/17832), so the extra measurements go there as a
comment. The ReplicaSet gap and the missing retry have no upstream issue.

```bash
gh issue comment 17832 --repo kyverno/kyverno --body-file docs/upstream/comment-kyverno-17832.md
gh issue create --repo kyverno/kyverno --title "[Bug] ImageValidatingPolicy matching apps/v1 replicasets is not evaluated at admission" --body-file docs/upstream/issue-replicasets-not-evaluated.md
gh issue create --repo kyverno/kyverno --title "[Bug] ImageValidatingPolicy: transient registry/TUF fetch errors are not retried and are reported as 'attestation not found'" --body-file docs/upstream/issue-transient-fetch-errors.md
```

[kyverno-ivp-drafts.md](kyverno-ivp-drafts.md) is the original, longer draft.
