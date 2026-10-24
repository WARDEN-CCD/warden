# Warden — Threat Model

> Status: **Draft v0.1** (2026-10-21). A synopsis deliverable: every control maps to the attack it prevents and
> to the test that proves it. Attack IDs (`Axx`) are implemented in `warden-policy/attacks/` and run by
> evaluation E2 ([EVALUATION.md](EVALUATION.md)). Policy files reference threat IDs in a
> `warden.dev/threat-ids` annotation; `scripts/verify.py` checks those IDs exist here.

## 1. Scope

**In scope:** the path from a commit in a `svc-*` repo to a running Pod, and the platform's own build and
configuration path. **Out of scope:** runtime exploitation of a running container, node/kernel compromise,
compromise of GitHub, Sigstore or Azure themselves, and denial of service.

## 2. Assets

| ID | Asset | Why it matters |
|----|-------|----------------|
| AS1 | Running workloads and the cluster | What the attacker ultimately wants to run code in |
| AS2 | The platform signing identity (reusable workflow → Fulcio cert) | Whoever can use it can produce "trusted" images |
| AS3 | `warden-gitops` contents | It *is* the desired cluster state |
| AS4 | `warden-policy` contents | Weakening a policy silently disables the controls |
| AS5 | GHCR packages | Where admitted images come from |
| AS6 | Azure subscription and credit | Abuse burns the project's budget |
| AS7 | Delivery metrics integrity | Evaluation results depend on them |

## 3. Trust boundaries

```
 Developer laptop ─┬─► GitHub repos ──► GitHub Actions runners ──► Sigstore (Fulcio, Rekor)
                   │                          │
                   │                          ├──► GHCR (images + referrers)
                   │                          └──► warden-gitops (bot PR)
                   │
                   └─(no direct path)─╳─► Cluster API     ◄── Argo CD pulls Git
                                         ▲
                       ADMISSION BOUNDARY: VAP + Kyverno verify every Pod
```

Boundary crossings that matter: runner → registry (push), runner → Sigstore (cert issuance), Git → cluster (pull),
registry → cluster (admission-time verification, then kubelet pull by digest).

## 4. Adversaries

| ID | Adversary | Capability assumed |
|----|-----------|--------------------|
| ADV1 | Outside attacker with a stolen GHCR token | Push arbitrary images to an org package |
| ADV2 | Malicious PR author (no write access) | Open PRs with arbitrary code, including build plugins and workflow edits |
| ADV3 | Compromised third-party dependency or GitHub Action | Code execution inside CI jobs that use it |
| ADV4 | Attacker controlling their own GitHub repo | Can call our public reusable workflow and obtain a real Fulcio cert |
| ADV5 | Holder of a namespace-scoped cluster credential | Create Pods/Deployments in one workload namespace |
| ADV6 | Compromised maintainer account (insider-equivalent) | Merge to `main` of a service repo |

## 5. Threats, controls and tests

| ID | Threat | Adversary | Control | Enforced in | Test |
|----|--------|-----------|---------|-------------|------|
| T01 | Mutable tag repointed after review | ADV1 | Digest-only references; signature bound to digest | VAP `warden-image-references` | A01 |
| T02 | Unsigned image pushed with stolen registry credential | ADV1 | Signature required | Kyverno IVP | A02 |
| T03 | Image signed with a *valid* Sigstore cert from the attacker's own workflow | ADV4 | Cert subject pinned to platform workflow at a release tag; issuer pinned | Kyverno IVP | A03 |
| T04 | Attacker repo calls the platform reusable workflow (confused deputy) | ADV4 | Provenance caller repo must be `WARDEN-CCD/svc-*` | Kyverno IVP (provenance) | A04 |
| T05 | PR obtains a signed artifact | ADV2 | Sign job runs only on push to `main`; provenance ref must be `refs/heads/main` | Workflow + Kyverno IVP | A05 |
| T06 | Image from a non-allowed registry skips IVP matching | ADV5 | Registry allowlist, default-deny namespace scope | VAP | A06 |
| T07 | Image modified after signing | ADV1 | Signature verification over the digest | Kyverno IVP | A07 |
| T08 | Attestations stripped / missing | ADV1 | SBOM and provenance attestations required | Kyverno IVP | A08 |
| T09 | CI holds cluster credentials → lateral movement | ADV3 | Pull-based GitOps; no kubeconfig anywhere in CI | Architecture; secret-scan check | A09 |
| T10 | Compromised third-party Action (tag repoint) | ADV3 | SHA pinning, zizmor, minimal job permissions | `scripts/verify.py`, CI | CI check |
| T11 | Build code steals the OIDC token to sign arbitrary artifacts | ADV2/ADV3 | `id-token: write` only on the sign job, which runs no project code | Reusable workflow | A10 |
| T12 | Promotion bot abused to change non-digest config | ADV3 | Bot can only open PRs; `digest-only` required check; policies live in another repo | GitHub ruleset + check | A11 |
| T13 | Policy weakened out-of-band (`kubectl edit`) | ADV5 | Argo CD `selfHeal` reverts; policy repo CODEOWNERS (2 reviewers) | Argo CD | A12 |
| T14 | Pod created in an exempt platform namespace | ADV5 | Minimal exempt list; developers have no RBAC in platform namespaces | RBAC | Review |
| T15 | Correctly signed but faulty release | — | Canary analysis, automatic abort | Argo Rollouts | E3 |
| T16 | Known-vulnerable dependency shipped | ADV3 | CI fails on fixable CRITICAL; vuln attestation audited at admission | CI + IVP (Audit) | E2 note |
| T17 | Malicious code merged by a compromised maintainer, or pushed directly through the owner's review bypass | ADV6 | **Not prevented.** Teammates need a second reviewer; the owner account bypasses review (ADR-027) and relies on 2FA; history is append-only; provenance gives traceability | Process | — |
| T18 | Kyverno unavailable | — | `failurePolicy: Fail`; VAP still enforces invariants | Admission config | Chaos test |
| T19 | Azure credential leak | ADV3 | OIDC federation, no client secret; budget alerts; reaper | OpenTofu | Review |
| T20 | In-cluster GitHub App key (Deployments ledger) leaked | ADV5 | App scoped to `deployments: write` on `svc-*` only; key in platform namespace | GitHub App config | Review |

## 6. Real incidents and how Warden relates

| Incident | What happened (short) | Warden's relevant controls | Honest limit |
|----------|-----------------------|----------------------------|--------------|
| SolarWinds Orion (2020) | Build system compromised; malicious code inserted at build time into signed releases | T09, T11: hardened, isolated build definition; provenance from a platform-owned builder | A compromised GitHub-hosted runner would still produce valid provenance |
| Codecov (2021) | Modified CI script exfiltrated credentials from customers' CI | T10, T19: no long-lived CI credentials to steal; tools verified before use | Short-lived tokens can still be abused during the job |
| XZ Utils (2024) | Malicious maintainer shipped a backdoor through the release process | SBOM scopes impact quickly; provenance shows exactly which commit built what | Source-level malice by a trusted maintainer is T17 — not prevented |
| tj-actions/changed-files (2025) | Version tags repointed to a malicious commit; secrets dumped to logs | T10: SHA pinning; least-privilege job permissions | Pinned SHAs must be reviewed when bumped |
| trivy-action (Mar 2026) | 76 of 77 version tags poisoned; every tag-pinned pipeline ran attacker code | T10: SHA pinning; Trivy installed as a cosign-verified binary instead of the action | — |

## 7. What a valid signature does **not** prove

A signed, attested image proves **origin**: this exact digest was built by Warden's workflow from commit X of
repo Y on `main`. It does not prove the code at commit X is safe. Code review (T17), dependency scanning (T16)
and canary analysis (T15) remain necessary. This mirrors the synopsis' stated limitation.

## 8. Residual risks (accepted)

1. Single-replica Kyverno: availability, not integrity, is at risk (fails closed from M3; see 6).
2. GitHub-hosted runner or GitHub OIDC compromise is out of scope.
3. Public repos and public images (ADR-028) expose the full platform design and every image to attackers —
   Kerckhoffs's principle: security must not depend on secrecy of design. Images never contain secrets.
4. Platform namespaces are exempt from image verification. Stretch goal: verify upstream images (Argo CD,
   Kyverno, etc.) against their publishers' Sigstore identities.
5. The org owner can change `main` without review (ADR-027). A compromise of that one account skips the
   two-person rule. Admission control still limits what can *run* to images built by the platform workflow.
6. **Until M3 the image policies fail open.** In the Audit phase the IVPs use `failurePolicy: Ignore`, so a
   Kyverno outage or a slow verification admits the pod. Verification measured 16–24 s per pod on kind (about
   8 s per attestation), close to the webhook timeout. At M3, `failurePolicy: Fail` flips together with `Deny`
   (ADR-020), and the latency must be cut first (E8).
7. **CNPG carve-out.** The image VAP admits two exact PostgreSQL digests without platform provenance, and only
   when the request comes from the `cnpg-system:cloudnative-pg` service account. Compromising that account
   lets an attacker run those two upstream images, nothing else.
8. **Fields Argo CD does not restore.** The pod-template hash in Service selectors and the HTTPRoute weights
   belong to Argo Rollouts (warden-gitops `ignoreDifferences`). Someone who can write Services or HTTPRoutes in a
   `svc-*` namespace can move traffic between the stable and canary pods. Both run admitted images.
