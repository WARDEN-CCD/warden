# Draft upstream issues for kyverno/kyverno

Not filed. Both come from Warden's E8 work on Kyverno **v1.19.2** (kind, Kubernetes 1.37, GHCR, cosign v3
bundles as OCI referrers). Evidence paths are in the hub repo.

---

## 1. ImageValidatingPolicy: ~30 sequential HTTPS requests per attestation verification (no token or TUF reuse)

**What happens.** One evaluation of an IVP with two attestations (SLSA provenance and CycloneDX SBOM, keyless,
`ctlog.url` Rekor) against a public GHCR image makes **95 sequential HTTPS requests** and takes 25–36 s from a
laptop (`kyverno apply`, `GODEBUG=http2debug=2`). Observed:

- every registry access repeats `GET /v2/` and `GET /token` (16 tokens for one image);
- the Sigstore TUF client is initialised again for each cosign verification (`15/16/17.root.json` + `timestamp.json`, 6 requests each);
- nothing is reused between the verifications of the same digest.

On the cluster this costs ~7.5 s per attestation verification, or ~15 s per Pod, warm. With the 30 s maximum
webhook timeout, enforcement (`failurePolicy: Fail`) refuses Pods whenever the network is slow.

**Also:** setting `spec.attestors[].cosign.trustedRoot.value` to a verified `trusted_root.json` did not remove
the TUF requests (still 18), although the field description says TUF is then skipped.

**Expected.** Reuse the registry transport/token and the TUF client within a request (and ideally cache
verification results per digest), so the cost is closer to one round trip per artifact.

Evidence: `evidence/verification/2026-10-24T225231Z-root-cause.json`, `...192711Z.json`, `...232000Z.json`.

---

## 2. ImageValidatingPolicy matching `apps/v1 replicasets` is not evaluated at admission

**What happens.** An IVP with `matchConstraints.resourceRules` for `apps/v1 replicasets`, an `images` extractor
`object.spec.template.spec.containers.map(c, c.image)`, `validationActions: [Deny]`, `failurePolicy: Fail` and
`validationConfigurations.required: true` **admits** a ReplicaSet whose template has an unsigned image, in
0.23 s, with no verification in the admission controller's log. The webhook is registered (rules:
`replicasets`, path `/ivpol/validate/<policy>`). The same policy and resource **fail** as expected with
`kyverno apply`. Removing `matchConditions` makes no difference.

The same holds for the autogen'd controller rules of a Pod-matching IVP: a dry-run ReplicaSet is admitted in
0.22 s, the equivalent Pod takes 16.7 s (verified).

**Expected.** ReplicaSets (and the other pod controllers the webhook is registered for) are verified at
admission, as `kyverno apply` does.

Evidence: hub `DECISIONS.md` ADR-031 (Result), `evidence/attacks/2026-10-25T024144Z-results.json` (A14 failing
against the prototype).

---

## 3. Transient fetch errors become policy failures (no retry), with a misleading message

**What happens.** During 40 admissions of legitimate, correctly signed Pods, two verifications failed because of
network errors:

- Downloading a 2 MB CycloneDX bundle layer ended in `unexpected EOF`. Kyverno logged `skipping referrer: not a
  usable sigstore bundle` (at trace level) and then failed the Pod with `required predicate type
  https://cyclonedx.org/bom not found`, although the attestation exists (cosign verifies it).
- `failed to initialize TUF client ... failed to download 17.root.json`.

Neither is retried, and the first one reads like a missing attestation, not a network error.

**Expected.** Retry transient registry and TUF fetch errors; report a fetch failure as an error, not as
"attestation not found", so `failurePolicy` (not the policy result) decides what happens.

Evidence: `evidence/m3/readiness-20261025T104356Z.json` (`ivp_fail_root_causes`).

