# Warden — Research Notes (verified 2026-10-21)

What changed in the ecosystem between the synopsis and the start of implementation, and what it means for
Warden. Version numbers come from each project's GitHub "latest release" API on 2026-10-21; pins live in
[versions.yaml](versions.yaml). Re-run this check before each milestone.

## Findings that changed the design

| # | Finding | Impact | ADR |
|---|---------|--------|-----|
| 1 | **Kyverno 1.19 deprecated `ClusterPolicy`/`Policy`; removal planned for 1.20 (est. Nov 2026).** CEL types (`ImageValidatingPolicy` etc.) are GA since 1.17. | All policies written as CEL types; plan the 1.20 upgrade | 006 |
| 2 | **ingress-nginx retired in March 2026** (no more releases or security fixes). | Gateway API + Envoy Gateway; Rollouts Gateway API plugin | 012 |
| 3 | **cosign v3 defaults to Sigstore bundles as OCI referrers and Rekor v2.** GHCR exposes an empty referrers list → fallback tag. 2026 Kyverno issues (#16678, #17363, #16435) hit this combination; fixes landed through 1.19.2 (2026-10-20). | Spike S1 before building on it; Kyverno ≥ 1.19.2 | 008 |
| 4 | **GitHub documents SLSA v1 Build L3 via artifact attestations + reusable workflows.** | Platform-owned reusable workflow as the trusted builder; identity pinning | 009 |
| 5 | **Tag-repoint attacks on GitHub Actions in 2026** (trivy-action in March: 76/77 tags poisoned; others in May–Sept). | SHA-pin everything; install Trivy/Syft as cosign-verified binaries | 011 |
| 6 | **Crossplane v2:** claims removed, XRs namespaced, native XR connection secrets and native patch-and-transform removed; can compose any Kubernetes resource. | `Database` XR design; compose CNPG `Cluster` directly; compose a connection Secret | 016 |
| 7 | **DORA now has five metrics** (rework rate added 2024; "time to restore" → "failed deployment recovery time"). | Report five, headline the synopsis' four | 019 |
| 8 | **Spring Boot 3.5 OSS support ended June 2026**; 4.1.1 current. | Spring Boot 4.1 + Java 25 | 018 |
| 9 | **`slsa-github-generator` last released Feb 2025**; GitHub's `actions/attest-build-provenance` is actively maintained (v4.2.2). | Use GitHub native attestations | 008 |
| 10 | **Azure for Students subscription is region- and quota-restricted** (see below). | Region, VM size, ephemeral clusters | 004 |
| 11 | **Measured in spike S1:** GHCR has no referrers API (fallback tag used); cosign 3.1.4 writes even the signature as a DSSE bundle; all entries were Rekor v1; Kyverno 1.19.2 verifies all of it. | Formats confirmed | 008 |
| 12 | **Measured in spike S1:** GHCR packages pushed by Actions from a public repo are **private** (anonymous pull 403). | Visibility decision (DESIGN Q7) | — |

## Verified component versions

| Component | Latest | Released | Notes |
|-----------|--------|----------|-------|
| Kubernetes | v1.37.1 | 2026-09-23 | 1.37.0 released 2026-08-26 |
| kind | v0.33.0 | 2026-08-26 | default node `kindest/node:v1.37.0@sha256:a1ed56cf…` |
| Kyverno | v1.19.2 | 2026-10-20 | Helm chart 3.9.2 |
| Argo CD | v3.5.6 | 2026-10-20 | Helm chart `argo/argo-cd` 10.10.5 (app 3.5.5) |
| Argo Rollouts | v1.10.1 | 2026-10-12 | Helm chart 2.43.8 |
| Rollouts Gateway API plugin | v0.17.0 | 2026-09-01 | `maxTrafficWeight` semantics changed in this release |
| Envoy Gateway | v1.9.2 | 2026-09-28 | |
| Gateway API | v1.6.3 | 2026-10-06 | |
| Crossplane | v2.4.2 | 2026-09-22 | |
| provider-upjet-azure (crossplane-contrib) | v2.8.0 | 2026-10-08 | |
| function-go-templating | v0.13.1 | 2026-10-16 | |
| function-auto-ready | v0.7.2 | 2026-10-20 | |
| CloudNativePG | v1.30.1 | 2026-09-23 | |
| cosign | v3.1.4 | 2026-10-20 | |
| Syft | v1.55.0 | 2026-10-19 | checksums signed (`.sigstore.json`) |
| Trivy | v0.76.0 | 2026-10-14 | checksums signed (`.sigstore.json`) |
| Semgrep | v1.182.0 | 2026-10-20 | Opengrep v1.31.0 as alternative |
| zizmor | v1.31.1 | 2026-10-15 | |
| OpenTofu | v1.13.1 | 2026-10-01 | |
| kube-prometheus-stack | chart 92.11.0 | 2026-10-20 | |
| Prometheus | v3.15.0 | 2026-09-25 | |
| Grafana | v13.2.4 | 2026-10-13 | |
| OTel Collector | v0.163.1 | 2026-10-16 | |
| OTel Java instrumentation | v2.32.0 | 2026-10-03 | |
| k6 / k6-operator | v2.3.0 / v1.7.0 | 2026-09 / 2026-10 | k6-operator chart 4.7.0 |
| Spring Boot | v4.1.1 | 2026-08-20 | |
| Jib Maven plugin | 3.5.2 | 2026-07-14 | |
| Helm | v4.3.1 | 2026-10-15 | Helm 4 |
| Task | v3.54.0 | 2026-10-01 | |
| CNOE idpbuilder | v0.10.2 | 2026-04-13 | comparison target |
| Backstage | v1.56.0 | 2026-10-20 | stretch only |

## Azure for Students subscription facts

Observed with `az` on one team member's subscription on 2026-10-21. **Each member must re-check their own.**

```bash
az policy assignment list --query "[].{n:displayName,p:parameters}" -o json
az vm list-usage -l indiasouthcentral -o table
az aks get-versions -l indiasouthcentral -o table
```

- Policy "Allowed resource deployment regions": `indonesiacentral`, `eastasia`, `indiasouthcentral`, `uaenorth`,
  `koreacentral`. (`centralindia` is **not** allowed.)
- Quota per region: Total Regional vCPUs **6**; Standard BS Family vCPUs **4**; DSv5 / DASv5 / DDSv5 families **0**.
- AKS versions available in all three regions checked: 1.31 → **1.37**.
- PostgreSQL Flexible Server Burstable SKUs available in `indiasouthcentral`: `Standard_B1ms`, `Standard_B2s`.
- Linux PAYG prices (koreacentral reference): B2s US$0.052/h, B2ms US$0.104/h, B4ms US$0.208/h.
- Offer: US$100 credit, renewed yearly while a student; Microsoft's student page lists 750 h/month of PostgreSQL
  Flexible Server B1ms for 12 months — confirm applicability in spike S3.

## Sources

- Kubernetes 1.37 release page — <https://kubernetes.io/releases/1.37/>
- kind v0.33.0 release notes — <https://github.com/kubernetes-sigs/kind/releases>
- Kyverno 1.19 announcement (deprecations, timeline) — <https://kyverno.io/blog/2026/08/20/announcing-kyverno-release-1.19>
- Kyverno 1.17 announcement (CEL types GA) — <https://www.cncf.io/blog/2026/02/18/announcing-kyverno-1-17/>
- Kyverno ImageValidatingPolicy docs — <https://kyverno.io/docs/policy-types/image-validating-policy/>
- Kyverno issue #16678 (cosign v3 attestations via GHCR fallback tag) — <https://github.com/kyverno/kyverno/issues/16678>
- Kyverno issue #17363 (bundle-only referrers regression) — <https://github.com/kyverno/kyverno/issues/17363>
- Kyverno sample IVP for SLSA provenance — <https://github.com/kyverno/policies/tree/main/other-ivpol/verify-image-slsa>
- Ingress NGINX retirement — <https://kubernetes.io/blog/2025/11/11/ingress-nginx-retirement/>
- Steering/SRC statement on Ingress NGINX — <https://www.kubernetes.io/blog/2026/01/29/ingress-nginx-statement/>
- AKS and Ingress-NGINX — <https://blog.aks.azure.com/2025/11/13/ingress-nginx-update>
- Rollouts Gateway API plugin — <https://rollouts-plugin-trafficrouter-gatewayapi.readthedocs.io/>
- GitHub: artifact attestations + reusable workflows → SLSA Build L3 — <https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations>
- Rekor v2 GA — <https://blog.sigstore.dev/rekor-v2-ga/>
- Crossplane v2 what's new — <https://docs.crossplane.io/latest/whats-new/>
- DORA metrics history — <https://dora.dev/guides/dora-metrics/history/>
- Spring Boot 4.1.1 — <https://spring.io/blog/2026/08/20/spring-boot-4-1-1-available-now/>
- trivy-action tag poisoning (CSA research note) — <https://labs.cloudsecurityalliance.org/wp-content/uploads/2026/04/CSA_research_note_teamPCP-cicd-supply-chain_20260403-csa-styled.pdf>
- Re-enabled compromised actions (Sept 2026) — <https://thehackernews.com/2026/09/compromised-github-actions-came-back.html>
- OpenTofu azurerm backend — <https://opentofu.org/docs/language/settings/backends/azurerm/>
- AKS pricing tiers — <https://azure.microsoft.com/updates/generally-available-azure-kubernetes-service-introduces-two-pricing-tiers-free-and-standard>
- Azure for Students — <https://azure.microsoft.com/en-us/free/students>
- Azure Retail Prices API — <https://prices.azure.com/api/retail/prices>
