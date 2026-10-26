Same symptom here on Kyverno v1.19.2 (chart 3.9.2, kind, Kubernetes 1.37, public GHCR image, keyless cosign v3 bundles stored as OCI referrers), plus two details that may help.

**Request count.** One `kyverno apply` evaluation of an IVP with two attestations (SLSA provenance and CycloneDX SBOM, `ctlog.url` set) against one image made 95 sequential HTTPS requests (`GODEBUG=http2debug=2`) and took 25-36 s from a laptop. Every registry access repeated `GET /v2/` and `GET /token` (16 tokens for one image), which matches the missing `remote.Reuse(puller)` described above.

**TUF client.** The Sigstore TUF client was also initialised again for each cosign verification (`15/16/17.root.json` plus `timestamp.json`, 6 requests each). Setting `spec.attestors[].cosign.trustedRoot.value` to a verified `trusted_root.json` did not remove the TUF requests (still 18), although the field description says TUF is skipped then. #17883 looks related.

**Cost on a cluster.** About 7.5 s per attestation verification, so about 15 s per Pod warm with two attestations. The same figure on kind and on AKS (14-15 s), so it is not network distance. With the 30 s webhook limit, `failurePolicy: Fail` would refuse Pods whenever the network is slow.

Data: https://github.com/WARDEN-CCD/warden/blob/main/evidence/verification/2026-10-24T225231Z-root-cause.json
