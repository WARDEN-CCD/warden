### Kyverno Version

1.19.2 (Helm chart 3.9.2)

### Kubernetes Version

1.37.0 (kind)

### Description

Transient network errors during `ImageValidatingPolicy` verification are not retried and surface as policy failures with a misleading message.

In 40 admissions of legitimate, correctly signed Pods (public GHCR, cosign v3 bundles as OCI referrers), two verifications failed because of network errors:

1. Downloading a 2 MB CycloneDX bundle layer ended in `unexpected EOF`. Kyverno logged `skipping referrer: not a usable sigstore bundle` (at trace level) and then failed the Pod with `required predicate type https://cyclonedx.org/bom not found`, although the attestation exists and `cosign verify-attestation` accepts it.
2. `failed to initialize TUF client ... failed to download 17.root.json`.

Neither was retried. The first message reads like a missing attestation, not a network error, so it points an operator at the wrong thing.

### Expected

- Retry transient registry and TUF fetch errors with a short backoff.
- Report a fetch failure as an error rather than as "attestation not found", so that `failurePolicy` (not the policy result) decides what happens.

### Notes

Related but different: #18185 (`failurePolicy: Ignore` still denies on runtime verification errors). Data: https://github.com/WARDEN-CCD/warden/blob/main/evidence/m3/readiness-20261025T104356Z.json (`ivp_fail_root_causes`).
