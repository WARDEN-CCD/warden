# Completion plan against the submitted synopsis

The synopsis promises four demonstrations: one-command service delivery, refusal of an unverifiable image,
automatic rollback of a faulty release, and a database provisioned from a short request. The first and third
have local evidence. The second is demonstrated by the attack suite, but live image verification is still in
Audit; the fourth currently uses CloudNativePG on both kind and AKS. Do not present either gap as complete.

## 1. Finish and verify the release path

Owner: Abhyuday Gupta, with Shaurya Jain reviewing the GitOps result.

1. Update all four service callers and the CLI default to the released `warden-platform@v0.1.2`.
2. Merge one service caller PR and observe a push-to-`main` workflow. Save the run URL, pushed digest, promotion
   PR URL, required `digest-only` result, merge actor, Argo CD sync, and healthy Rollout in `evidence/`.
3. Confirm the promotion PR merged through the app without an owner bypass. If it fails, diagnose the precise
   GitHub response, fix the workflow in a new reviewed release, and repeat the test.
4. Repeat E5 using a release merged through this path. Update ADR-034, EVALUATION and the report from the run.

Exit: a service release reaches a healthy Rollout by GitOps with no cluster credentials in CI and no human
merge of the digest-only PR.

## 2. Make image verification enforceable

Owner: Sankalp Arya, with Abhyuday Gupta reviewing the trust boundary and measurements.

1. Track the filed Kyverno issues ([ReplicaSet admission](https://github.com/kyverno/kyverno/issues/18314),
   [transient fetch errors](https://github.com/kyverno/kyverno/issues/18315)) and the
   [request-count report](https://github.com/kyverno/kyverno/issues/17832#issuecomment-6441526018). Reproduce
   the failures and long Pod admission times with the pinned version. Keep the raw output in
   `evidence/verification/`.
2. Evaluate a newer Kyverno release on kind through a `versions.yaml` change and reviewed policy/GitOps PRs.
   Run the supply-chain policy tests, attack suite, and E8 timing procedure. Test ordinary service Pods, CNPG
   Pods and Jobs, and recovery after registry or Sigstore fetch failures.
3. Require ADR-020's five consecutive legitimate deployments of each of the four services with zero policy
   failures, every attack refused for its expected threat, and admission completing within the webhook timeout.
   Recheck the complete result on AKS before switching the supply-chain policy to `Deny` with `failurePolicy: Fail`.
4. If no compatible release meets those gates, retain Audit and state explicitly in the report that Warden
   detects unverifiable images but does not yet refuse them at live admission. Do not weaken the checks to
   claim the synopsis outcome.

Exit: signed legitimate workloads are admitted reliably and unsigned, tampered, wrong-builder, missing-SBOM,
and foreign-registry workloads are refused on kind and AKS under the live Deny policy.

## 3. Finish the managed database path

Owner: Aditya Chetan Thakur, with Abhyuday Gupta reviewing the Crossplane contract.

1. Confirm the Azure for Students subscription can afford PostgreSQL Flexible Server and has the necessary
   region quota. Keep the AKS cluster ephemeral and set the budget alert before provisioning.
2. Implement and pin the PostgreSQL Crossplane provider package and Azure `ProviderConfig`. Add a namespaced
   `database-azure` Composition that creates the server, database, network access and the six-key
   `<name>-conn` Secret without storing credentials in Git.
3. Select `database-azure` only in the AKS overlay; leave kind on `database-cnpg`. Test the same `Database`
   manifest on both clusters, including connection from a service Pod, readiness, deletion, and full teardown.
4. Record elapsed time, cost and cleanup in E4. If the student subscription cannot support the managed server,
   revise the report and supervisor-approved project scope rather than asserting that the path exists.

Exit: one unchanged developer request provisions a usable database on kind and a managed Azure PostgreSQL
instance on AKS, and `down:azure` leaves no billable Warden resources.

## 4. Complete the evaluation and submission

Owner: Abhyuday Gupta for integration and final evidence review; each member owns evidence from their area.

1. Complete E1's planned run count and Azure measurements, plus its hand-timed baseline, or document the smaller
   sample as a limitation. Preserve the existing E2, E3, E6, E7 and E8 evidence and repeat only when a relevant
   component changes.
2. Confirm each member's actual contribution in report section 9. Recordings must show the four synopsis
   scenarios and their backing evidence. Export the presentation into a team-accessible submission file and
   rehearse on a fresh local rebuild.
3. Obtain supervisor review, reconcile every claim in the report and slides with EVALUATION, then tag `v1.0.0`
   in the hub and four platform repositories from reviewed `main`. Keep immutable workflow releases intact.
4. Invite the remaining teammate to the organization and enable the 2FA requirement only after every member
   has enabled 2FA. Decide code-owner review with the team.

Exit: the report, source repositories, evidence, recordings and slides agree on what was demonstrated and on
what remains limited.
