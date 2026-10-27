# Warden: A Verifiable Kubernetes Delivery Platform

Cloud Computing and DevOps mini project report. We reviewed the evidence on 2026-10-28 and linked each result to its
record. In section 8, we identify the claims that still need implementation or further measurement.

## 1. Introduction

We built Warden as an internal delivery platform for Kubernetes. With one command, `warden new <name>`, a developer gets
a repository, a build pipeline, deployment manifests, a catalog entry and a service running behind a canary. One trusted
workflow builds and signs each release, and admission checks the image again before a Pod runs. If the canary fails its
metrics, the rollout returns to the stable version without manual intervention. Our trust chain draws on established
software supply-chain integrity work, including in-toto and SLSA provenance [2, 4].

Our live digest, registry and Pod-hygiene rules deny invalid workloads. Signature and attestation verification still
runs in Audit because the transient errors and timeouts we measured prevent reliable Deny mode. We also provisioned
Azure PostgreSQL Flexible Server from the `Database` API and connected to it from an AKS Pod using the generated
Secret. That smoke test exposed composition defects which are fixed in the current infrastructure working copy and
still need review and merge. We have not yet tested a service migration against the managed database. We discuss
these limits below and record them in ADR-035 and ADR-036.

We kept the four sample services (books, loans, members and notify) deliberately small because the platform is the
product. We evaluated its claims in eight experiments (E1 to E8); [section 6](#6-evaluation) reports the results.

We used the following managed services and tools, meeting the course requirement of at least four:

| Area | Used |
|------|------|
| Managed Kubernetes | Azure Kubernetes Service (AKS, Free tier, two Standard_B2ms nodes) and kind for local work |
| Infrastructure as code | OpenTofu with native state encryption; the state lives in an Azure storage account that accepts only Entra ID sign-in |
| CI/CD | GitHub Actions (one reusable workflow), Argo CD for deployment, Argo Rollouts for canaries |
| Registry | GitHub Container Registry (GHCR) |
| Identity | Microsoft Entra ID for cluster access and for CI federation, GitHub OIDC tokens for signing |
| Signing and transparency | Sigstore public good instance (Fulcio, Rekor) through cosign |
| Cost control | An Azure subscription budget with alerts, created by OpenTofu with the cluster |
| Data | Crossplane v2 with CloudNativePG for PostgreSQL |

## 2. Problem statement

We focused on a gap in delivery platforms: they can explain how a service ships without establishing what is running.
Incidents such as SolarWinds (2020) show why that gap matters: malicious code shipped inside signed releases.
In the tj-actions incident (2025), version tags were repointed to a malicious commit and secrets reached build logs.
In March 2026, 76 of the 77 version tags of the trivy-action were poisoned, so every pipeline pinned by tag ran
attacker code ([THREAT_MODEL §6](../../THREAT_MODEL.md#6-real-incidents-and-how-warden-relates)).

A valid signature alone does not close the gap. Any GitHub Actions job can obtain a real Sigstore certificate, and any
public repository can call a public reusable workflow. We therefore check which workflow ran, which repository it ran
for, and which branch, in addition to verifying the signature ([THREAT_MODEL
§7](../../THREAT_MODEL.md#7-what-a-valid-signature-does-not-prove)).

We tied each Warden goal to an experiment ([DESIGN §2](../../DESIGN.md#2-goals-and-non-goals)):

| Goal | Statement | Experiment |
|------|-----------|-----------|
| G1 | One command creates a service and deploys it | E1 |
| G2 | Artifacts that cannot be verified never run | E2 |
| G3 | Faulty releases revert without a human | E3 |
| G4 | A database comes from a short declarative request | E4 |
| G5 | Delivery performance is measured from real history | E5 |
| G6 | The environment can be rebuilt from Git with no manual state | E6 |

Out of scope: multi-tenancy, secrets management beyond Kubernetes Secrets, a service mesh, multiple regions, cost
chargeback, production-grade availability, private repositories and runtime threat detection.

## 3. Solution architecture

```mermaid
flowchart LR
  dev([Developer]) -->|warden new, git push| svc[svc-* repo]
  subgraph GH[GitHub]
    svc -->|uses @vX.Y.Z| rw[[warden-platform<br/>reusable build workflow]]
    rw -->|push by digest| ghcr[(GHCR<br/>image@sha256 + referrers)]
    rw -->|bot PR: new digest| gitops[(warden-gitops)]
    policy[(warden-policy)]
    infra[(warden-infra)]
  end
  rw -->|keyless sign + attest| sig[Sigstore<br/>Fulcio, Rekor]
  subgraph K8S[Cluster: kind locally, AKS in Azure]
    argocd[Argo CD] --> adm{Admission<br/>VAP + Kyverno}
    adm -->|deny| refused[Pod refused]
    adm -->|admit| ro[Argo Rollouts<br/>canary via Gateway API]
    k6[k6 load] --> gw[Envoy Gateway] --> ro
    ro --> prom[Prometheus]
    prom -->|AnalysisRun| ro
    xp[Crossplane v2] --> cnpg[CloudNativePG]
  end
  gitops -->|pull| argocd
  policy -->|pull| argocd
  infra -->|pull: XRDs, compositions| argocd
  adm -. fetch signatures .-> ghcr
  adm -. trusted root .-> sig
  tofu[OpenTofu] -->|creates AKS, budget, OIDC| K8S
```

We designed the cluster to pull desired state from Git. CI never pushes to it and holds no cluster credentials of any
kind (T09).

### 3.1 Repositories

We split the platform across five repositories so each has its own trust boundary, reviewers and token scopes
([ADR-001](../../DECISIONS.md#adr-001-polyrepo-four-platform-repositories-plus-a-docs-hub)).

| Repository | Holds | Design |
|------------|-------|--------|
| `warden` (hub) | Design, 36 decision records, threat model T01 to T21, evaluation plan, `versions.yaml` (every pinned version), `scripts/verify.py`, experiment runners, evidence | |
| `warden-platform` | The reusable workflow `build-sign-attest.yml`, the `warden` CLI (Go), the service template, canary analysis templates, dashboards, k6 load profiles | [DESIGN §5](../../DESIGN.md#5-delivery-path), [§11](../../DESIGN.md#11-scaffolding--the-warden-cli) |
| `warden-policy` | Validating admission policies, Kyverno image and pod policies, 57 `kyverno test` cases, the attack suite A01 to A14 | [DESIGN §7](../../DESIGN.md#7-admission-control) |
| `warden-gitops` | The Argo CD app-of-apps for both clusters, the platform charts (pinned), `apps/<svc>/` desired state, the `digest-only` promotion check | [DESIGN §8](../../DESIGN.md#8-gitops-layout) |
| `warden-infra` | kind config, OpenTofu for AKS (budget, Entra-only access, GitHub OIDC), the Crossplane `Database` API, a Taskfile that writes a rebuild ledger | [DESIGN §10](../../DESIGN.md#10-self-service-database-crossplane-v2), [§14](../../DESIGN.md#14-bootstrap-and-rebuild) |
| `svc-*` | One repository per generated service: application code and a caller workflow of about 15 lines | |

### 3.2 Environments and cost

| | local (kind) | azure (AKS) |
|---|--------------|-------------|
| Kubernetes | 1.37, one control plane and one worker | 1.37, two Standard_B2ms nodes (the student quota allows 4 B-series vCPUs) |
| Gateway | NodePort mapped to the host | LoadBalancer with one public IP |
| Database | CloudNativePG | Azure Flexible Server composition (implementation staged; live path not verified) |
| Lifetime | as needed | ephemeral: created for a session and destroyed afterwards |

Two B2ms nodes cost about US$0.21 an hour, so our four-hour session costs about US$1 against the US$100 student credit
([DESIGN §15](../../DESIGN.md#15-cost-guardrails-azure-for-students)). OpenTofu creates a subscription budget with alerts
at 25, 50 and 75 percent together with the cluster, and `task down:azure` removes both. The Taskfile writes a row to
`evidence/rebuilds/rebuild-ledger.csv` for every environment operation.

## 4. Application architecture

### 4.1 The sample services

We implemented each service as a Spring Boot 4.1 application on Java 25 with Actuator, a Micrometer Prometheus endpoint
and OpenTelemetry instrumentation. We build images with Jib, without a Docker daemon. `warden.yaml` holds the owner, tier
and service-level objective, and we render every deployment manifest from it. The books service uses a `Database`. We
included two demo switches, `WARDEN_DEMO_ERROR_RATE` and `WARDEN_DEMO_LATENCY_MS`, so a faulty release is still a real,
signed release that follows the full pipeline.

### 4.2 Request path and rollout

We route traffic through Envoy Gateway and the Gateway API (`HTTPRoute`); we do not use Ingress. Each service runs as an
Argo Rollouts `Rollout`. A new version receives 5 percent of traffic, then 25, then 50, then 100, with a two-minute
Prometheus analysis after the first two steps ([DESIGN §9](../../DESIGN.md#9-progressive-delivery)). Our analysis passes at a
success rate of at least 99 percent and a p95 latency under 300 ms, and fails below 95 percent or at 500 ms and above.
A window with too few requests ends as inconclusive and pauses the rollout, so silence never promotes a release. A k6
scenario sends about 40 requests per second to each service so the canary sees enough traffic.

### 4.3 Database

In our service template, a developer requests a database with a short manifest (kind `Database`, size and PostgreSQL
version). Crossplane v2 renders it through the cluster's `database-default` composition and creates a Secret named
`<name>-conn` with six keys: host, port, dbname, username, password and uri. Kind uses CloudNativePG; the Azure
composition uses Flexible Server and requires the AKS egress IPv4 address in `spec.network.allowedSourceIp`. In our
Azure smoke test, the composition created the server, `app` database, egress firewall rule and six-key Secret. A
temporary `psql` Pod connected successfully and returned `wardenadmin|app`. The test did not run a service migration.

### 4.4 Observability

We use kube-prometheus-stack for Prometheus, Alertmanager and Grafana. Our dashboards cover the golden signals, rollout
timeline, admission decisions and delivery metrics. Argo CD Notifications write a GitHub Deployment and a status for
every service sync, which feeds the DORA ledger described in section 5.7.

## 5. Technical design

### 5.1 Trust chain and identity

When a commit lands on a service's `main` branch, it calls our reusable platform workflow, pinned by a semver tag. We
separate the work into three jobs.

- The build job compiles and tests with project code. It has no `id-token` permission, so it cannot obtain a signing
  certificate.
- The scan job creates a CycloneDX SBOM with Syft and a vulnerability report with Trivy. Both tools are installed as
  binaries whose checksums are verified with cosign. The job fails on a fixable critical vulnerability.
- The sign job is the only one with `id-token: write`. It checks out no code. It signs the image keylessly and attaches
  three attestations (SLSA v1 provenance, SBOM, vulnerabilities) as OCI referrers.

A Fulcio certificate issued to a reusable workflow names the workflow's own ref as its subject, so the caller cannot
change it. Admission pins that subject to the platform workflow at a release tag and also reads the provenance, which
the workflow generates from OIDC claims. The provenance has to name a repository under `WARDEN-CCD/svc-` and the ref
`refs/heads/main` ([DESIGN §6](../../DESIGN.md#6-identity-and-trust-model), ADR-009, ADR-010).

### 5.2 Admission control

We split admission into three layers so that inexpensive checks survive a Kyverno outage
([ADR-007](../../DECISIONS.md#adr-007-layered-admission-native-vap-for-invariants-kyverno-for-cryptography)).

| Layer | Engine | Checks | State on 2026-10-27 |
|-------|--------|--------|---------------------|
| Invariants | Kubernetes ValidatingAdmissionPolicy | Registry is `ghcr.io/warden-ccd/`; the reference is pinned by digest; also applies to Rollout templates and Jobs | Deny and Audit |
| Cryptography | Kyverno ImageValidatingPolicy | Signature, certificate subject and issuer, transparency log proof, provenance (builder, repository, ref), SBOM and vulnerability attestations | Audit, with `failurePolicy: Ignore` |
| Hygiene | Kyverno ValidatingPolicy | Probes, privileged containers and related rules | Deny and Audit |

Platform namespaces such as `kube-system` and `argocd` are exempt, so the cluster can always recover. Only Kyverno's CEL
policy types are used, because `ClusterPolicy` is removed in Kyverno 1.20 (ADR-006).

The image-verification layer stays in Audit on purpose. Kyverno 1.19.2 takes 14 to 15 seconds per Pod to verify, does
not retry transient fetch errors and does not evaluate ReplicaSets. With a 30 second webhook limit, a slow check would
either fail open or block the cluster. ADR-020 and ADR-032 set the exit criteria for turning it on. Reports for the Kyverno project
were filed on 2026-10-27: the [request-count comment](https://github.com/kyverno/kyverno/issues/17832#issuecomment-6441526018), [ReplicaSet issue](https://github.com/kyverno/kyverno/issues/18314), and [transient-fetch issue](https://github.com/kyverno/kyverno/issues/18315).

### 5.3 GitOps and promotion

We use Argo CD to sync `warden-gitops`, the cluster's desired state, following declarative, versioned, pull-based
reconciliation principles [5]. After a signed build, our promote job
opens a pull request that changes one thing: the image digest of one service. A required status check, `digest-only`,
rejects any other change. The check sits in a ruleset with no bypass actors. A GitHub App, `warden-promoter`, opens the
pull request with a token limited to that repository. Each source repository has its own Argo CD AppProject that limits
which namespaces and kinds it can deploy, and the `default` project is locked (ADR-029). `selfHeal` and `prune` revert
a manual edit to a policy within one reconcile (attack A12).

### 5.4 Progressive delivery

Our analysis template queries Prometheus for canary Pods only and uses observed behavior to decide whether to promote
or abort the canary [6]. Injected faults showed two traps (section 7): the
first analysis ran 9 seconds after the canary started and returned nothing, and Argo CD kept reverting the traffic
weights that Argo Rollouts had set. The analysis now waits two minutes before measuring, and the Service selector and
route weights are excluded from Argo CD's drift repair.

### 5.5 Self-service database

We defined `Database` as a Crossplane v2 namespaced composite resource. Our local composition runs in pipeline mode with
`function-go-templating` and `function-auto-ready`, and composes a CloudNativePG `Cluster` and the `<name>-conn`
Secret. The AKS overlay now contains a provider-backed composition for Azure Flexible Server, its database, a firewall
rule limited to one supplied egress address, and the same Secret contract. OpenTofu grants the AKS kubelet managed
identity a PostgreSQL-only role; bootstrap creates its ProviderConfig after installing the provider. That overlay is
staged but still needs a live connection and deletion test. Admission has a narrow exception for the database operator: pods created by its service account, and pods the
Job controller creates for the operator's initialization Jobs, may run three exact upstream image references. A second
policy stops anyone else from creating Jobs that name those images ([ADR-033](../../DECISIONS.md#adr-033-cloudnativepg-carve-out-covers-the-job-controller-and-the-operator-image-jobs-are-gated-at-creation)).

### 5.6 Infrastructure as code and rebuild

We use OpenTofu to create the resource group, AKS cluster, budget and GitHub-to-Azure federation. The cluster has
local accounts disabled, so the kubeconfig contains only an Entra ID exec plugin and no static credential. State is
encrypted by OpenTofu with a passphrase kept outside Git, in `~/.warden/env`. `task up:azure` creates everything from an
empty subscription, installs Argo CD and applies the root application. Everything else comes from Git. The inputs
outside Git are the two GitHub App private keys and non-secret Azure account IDs; the PostgreSQL provider uses the
AKS managed identity.

### 5.7 CLI and delivery metrics

We packaged the CLI as one Go binary with these commands: `new`, `render`, `verify`, `status`, `dora` and `setup-apps`.
`warden verify` runs admission checks locally and reads its constants from the policy files, so the CLI and cluster
cannot drift apart. `warden dora` reads the GitHub Deployments ledger and computes the five DORA metrics
(deployment frequency, change lead time, change fail rate, failed deployment recovery time, rework rate). The ledger
lives in GitHub, so the metrics survive a cluster rebuild. The metric definitions follow DORA's published guidance [7].

### 5.8 Threat model coverage

[Our threat model](../../THREAT_MODEL.md#5-threats-controls-and-tests) maps 21 threats to a control and a test. Our
attack suite covers T01 to T09 and T11 to T13 on a live cluster. We accept and document some risks, including that a
compromised maintainer's merge is not prevented (T17) and that image verification does not yet fail closed
([§8 of the threat model](../../THREAT_MODEL.md#8-residual-risks-accepted)).

## 6. Evaluation

| ID | Claim | Result | Evidence |
|----|-------|--------|----------|
| E1 | One command creates and deploys a service | Five full kind runs: median 8.6 min, range 7.6–9.6 min, and 0 manual steps. Azure runs and the hand-timed baseline remain open. | [timings](../../evidence/scaffold-timings/) |
| E2 | Unverifiable artifacts are refused | 15 of 15 under Deny-mode test policies on kind and AKS: one legitimate deployment admitted, A01 to A14 refused for the expected reason. The live image policy remains in Audit. | [kind](../../evidence/attacks/2026-10-25T024642Z-results.json), [AKS](../../evidence/attacks/2026-10-26T102953Z-results.json) |
| E3 | Faulty releases roll back without a human | Historical series: 10/10 faults aborted and 10/10 healthy promoted. App-only repeat: 4/4 faults aborted and 12/12 healthy releases promoted; abort median 147.6 s and median blast radius 0.39 percent of requests. | [historical summary](../../evidence/rollbacks/summary-2026-10-25T09.json), [app-only summary](../../evidence/rollbacks/summary-2026-10-27T13.json) |
| E4 | A database from a short request | The measured CloudNativePG request was ready on kind in 804 s cold and 21 s warm, and on AKS in 138 s. A separate Azure Flexible Server smoke test provisioned PostgreSQL 18 and `app`; an in-cluster `psql` query succeeded. That first smoke test is not a timing benchmark, and it did not exercise a service migration. | [kind](../../evidence/databases/2026-10-24T152723Z-books-db.json), [AKS / CloudNativePG](../../evidence/databases/2026-10-26T102407Z-orders-db-azure.json), [AKS / Flexible Server](../../evidence/databases/2026-10-27-azure-flexible-server-smoke.json) |
| E5 | DORA metrics from real history | App-only batch: 20 deployments, 16 successful and 4 injected failures; median lead time 12.5 min, recovery 12.6 min, change fail and rework 20 percent | [app-only data](../../evidence/dora/2026-10-27-e5-app-only.json) |
| E6 | The environment rebuilds from Git | Local: 12 of 13 rebuilds ok, median 14.8 min, p90 24.2 min. The latest fresh rebuild took 869 s; 23/23 apps were Synced/Healthy and all four services returned HTTP 200. Azure: five successful runs from nothing (median 22 min, range 20 to 24), plus four recorded and explained failures. | [ledger](../../evidence/rebuilds/rebuild-ledger.csv), [smoke checks](../../evidence/rebuilds/smoke.jsonl) |
| E7 | Comparison with CNOE idpbuilder | idpbuilder reached GitOps and a first app in 8.5 min using 2.2 GiB and has no admission control. Warden used 8.8 GiB and adds digest/registry enforcement, audited cryptographic checks, canaries and a self-service database. One run each. | [run](../../evidence/comparison/2026-10-25T000834Z-idpbuilder.json) |
| E8 | Cost of verification | Image verification adds 14 to 15 s per Pod when warm, the same on kind and on AKS, so network distance does not explain it | [kind](../../evidence/verification/2026-10-24T192711Z.json), [AKS](../../evidence/verification/2026-10-26T103002Z.json) |

Our latest local rebuild used the current worktrees, whose ledger entries are marked dirty because untracked local
instruction files were present. We report that fresh-cluster rehearsal separately from the earlier clean-commit rebuild
series.

[EVALUATION.md](../../EVALUATION.md) has the procedure and pass criteria for each. The attack suite runs against Deny-mode
clones of the policies, because the live image policy is in Audit.

We ran two separate E5 batches. In the original 2026-10-26 batch, we used owner merges after the required `digest-only`
check; we planned its 20 percent change fail rate (one injected fault per five releases), and its lead time excludes
review. In the 2026-10-27 repeat, we used only the promoter app. Its ledger records 20 deployments, five per service,
with 16 successful deployments and four injected faults. Median lead time was 12.5 minutes, change fail and rework rates
were 20 percent, and failed-deployment recovery was 12.6 minutes. The canary evidence records 12 healthy promotions
(median 471.2 seconds), four fault aborts and four recovered fixes. All required digest-only checks passed, and the app
merged the promotion pull requests. This short synthetic window reflects our experiment schedule, not normal team
practice. The lead-time metric excludes human review because the app performed the merges automatically.

| Service | Deployments | Median lead time | Change fail rate | Median recovery |
|---------|-------------|------------------|------------------|-----------------|
| Books | 5 | 12.8 min | 20% | 14.1 min |
| Loans | 5 | 13.1 min | 20% | 11.8 min |
| Members | 5 | 12.3 min | 20% | 12.6 min |
| Notify | 5 | 12.5 min | 20% | 12.6 min |

Our deployment-frequency calculation is about 250 per day over the 92-minute experiment window. We do not interpret this
scripted rate as routine team cadence.

We cross-checked the independent canary summary against the deployment ledger: both show 20 measured releases, four
injected failures, and a recovery median of about 12.6 minutes. We retained two incomplete members measurements as
excluded evidence: one CI capture timed out, and one healthy rollout was superseded by the overlapping fault trial.
Neither is counted in the canary summary. We corrected an earlier calculation that counted eight deployments and a
50 percent failure rate because the CLI treated superseded GitHub deployments as final and duplicated Argo CD
notifications.

## 7. Lessons learned

We found each of the issues below by running the system.

1. We learned that a policy tested only in Audit mode has not been tested. A carve-out for database Pods passed in Audit, where denials
   are only warnings, and would have stopped every database under Deny. We now run each legitimate pod class, including
   operator-managed pods and Jobs, under a policy before enforcing it (ADR-033).
2. We found that a default can undo a control. The vulnerability policy's default `mutateDigest: true` rewrote a tag to a digest, so
   a tag reference was admitted. We set it to false, and `verify.py` rejects any image policy without that setting.
3. We found that failing closed needs a latency budget. A policy set to `Fail` in Audit mode denied a legitimate Pod on a webhook
   timeout. Verification takes 14 to 15 seconds per Pod and the limit is 30, so the audit phase uses `Ignore`.
4. We found that two tools disagreed about field ownership. Argo CD reverted the traffic weights that Argo Rollouts set, and the
   canary took one third of traffic instead of 5 percent. The fix was `ignoreDifferences` with
   `RespectIgnoreDifferences` (warden-gitops#16).
5. We learned that a bypass is not honoured everywhere and a fix needs a live test. GitHub's auto-merge ignores a ruleset bypass, so the
   bot's pull requests waited for a review nobody would give. Our first fix called `gh pr merge`, which refuses a blocked
   pull request on the client before GitHub is asked, and it failed in its first live run. The second calls the REST
   endpoint. The `digest-only` check stays the guard in both.
6. We had to measure the measurer. Our CLI counted 8 of 20 deployments because GitHub marks superseded deployments inactive and
   Argo CD announces each Git revision for every application. Comparing against the runner's records exposed both.
7. We found that injected faults need their own queries. Injected 500 responses carry `uri="UNKNOWN"`, so our blast-radius query on `/api`
   counted none.
8. We learned that secrets need a recovery plan. The OpenTofu state passphrase in `~/.warden/env` changed after our first Azure run, and
   the stored state could no longer be decrypted. The old state described an environment that was already destroyed, so
   we pointed OpenTofu at a new state file.
9. We could not establish every cause. A fresh Pod cleared the Kyverno reports-controller crash loop, but we could not
   determine why it happened; we preserve that uncertainty in the evaluation.

We found smaller defects through the same process. The scan gate blocked our first build over Tomcat CVEs until Spring
Boot 4.1.2. GHCR packages created by Actions started private, and our organization initially forbade public ones. The
Kyverno CRDs stayed out of sync until we changed a chart value to fix their empty labels. The database Secret's name
depended on its backend until we made the composition own `<name>-conn`. We also added 57 cases to the empty policy test
directory.
[EVALUATION.md](../../EVALUATION.md) records each with its fix.

## 8. Limitations and open work

- We have not enabled cryptographic image verification in Deny mode. Our registry, digest and hygiene policies deny,
  but the signature and provenance policy remains in Audit, so a slow or failing check can admit a Pod. Kyverno needs to
  retry transient errors and reduce per-Pod latency before we can change that (ADR-020, ADR-032).
- Our Azure coverage is thin. We did not run E1 or E3 on Azure. The Flexible Server smoke test used a temporary
  `psql` Pod in `crossplane-system`; it did not test a service migration or repeated provisioning. The earlier E4
  timing results use CloudNativePG on both clusters. The two B2ms nodes used 80 and 94 percent of allocatable CPU in
  the recorded runs.
- Our samples are small. E1 has five full kind runs, but no Azure runs or hand-timed baseline. E4 has two runs, and E8
  has one run plus a spot check.
- Our E5 results describe the experiment schedule, as section 6 explains.
- Our controls do not prevent a trusted maintainer from merging unsafe code (T17). A signature proves origin, not safety;
  the owner account can merge without review and relies on two-factor sign-in.
- We report the original owner-merge E5 batch separately from the later app-only batch. Its short synthetic schedule
  does not represent our ordinary delivery behavior.
- We chose to keep repositories and images public (ADR-002, ADR-028), and we exempt platform namespaces from
  verification.

## 9. Team contributions

We completed Warden as a four-person team. Our main contribution areas were:

| Member | Contribution area |
|--------|-------------------|
| Abhyuday Gupta | System architecture, trusted build workflow and CLI, cross-repository integration, and final evidence review |
| Aditya Chetan Thakur | Azure and local infrastructure, Crossplane database path, and rebuild evaluation |
| Sankalp Arya | Admission policy design and readiness, attack suite, threat model, and upstream policy reports |
| Shaurya Jain | GitOps delivery configuration, rollout and observability validation, and presentation/demo preparation |


## 10. Source repositories and reproduction

| Repository | Address |
|------------|---------|
| Hub: design, decisions, evidence | <https://github.com/WARDEN-CCD/warden> |
| Application template, CLI, pipeline | <https://github.com/WARDEN-CCD/warden-platform> |
| Policies and attack suite | <https://github.com/WARDEN-CCD/warden-policy> |
| Cluster desired state | <https://github.com/WARDEN-CCD/warden-gitops> |
| Infrastructure as code | <https://github.com/WARDEN-CCD/warden-infra> |
| Services | <https://github.com/WARDEN-CCD/svc-books>, `svc-loans`, `svc-members`, `svc-notify` |

The pipeline configuration is `warden-platform/.github/workflows/build-sign-attest.yml`. The infrastructure scripts are in
`warden-infra/tofu`.

```bash
./.venv/Scripts/python.exe scripts/doctor.py                      # tools against versions.yaml
task -d warden-infra up:local                                     # kind, Argo CD, everything from Git
python warden-policy/attacks/run_attacks.py                       # E2
python scripts/experiments/canary.py <svc> error                    # E3, E5 (promoter app merges after digest-only)
python scripts/experiments/verification_cost.py --n 50            # E8
task -d warden-infra up:azure && task -d warden-infra down:azure  # E6 on Azure; always destroy afterwards
```

The demonstration script and the slide outline are in [docs/demo-script.md](../demo-script.md).

## 11. References

These papers and technical articles informed the platform's design. Repository links above are provided separately for
reproduction; they are not part of this references list.

1. A. Verma, L. Pedrosa, M. R. Korupolu, D. Oppenheimer, E. Tune, and J. Wilkes, “Large-scale cluster management at Google with Borg,” *Proceedings of EuroSys*, 2015. [Paper](https://research.google/pubs/large-scale-cluster-management-at-google-with-borg/).
2. S. Torres-Arias, H. Afzali, T. K. Kuppusamy, R. Curtmola, and J. Cappos, “in-toto: Providing farm-to-table guarantees for bits and bytes,” *28th USENIX Security Symposium*, 2019, pp. 1393–1410. [Paper](https://www.usenix.org/conference/usenixsecurity19/presentation/torres-arias).
3. Z. Newman, J. S. Meyers, and S. Torres-Arias, “Sigstore: Software Signing for Everybody,” *ACM SIGSAC Conference on Computer and Communications Security*, 2022, pp. 2353–2367. [Paper](https://doi.org/10.1145/3548606.3560596).
4. OpenSSF, “SLSA v1.0: Provenance.” [Specification](https://slsa.dev/spec/v1.0/provenance).
5. OpenGitOps, “GitOps Principles v1.0.0.” [Principles](https://opengitops.dev/).
6. A. Warner and Š. Davidovič, “Canarying Releases,” *The Site Reliability Workbook*, O'Reilly Media, 2018, ch. 16. [Article](https://sre.google/workbook/canarying-releases/).
7. DORA, “A history of DORA's software delivery metrics,” Jan. 2, 2026. [Article](https://dora.dev/insights/dora-metrics-history/).
