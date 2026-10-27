# Warden: technical design document

Cloud Computing and DevOps mini project. Status on 2026-10-27: final draft. Every number links to the file in the
repository that produced it, and section 8 lists what is not done.

## 1. Introduction

Warden is an internal delivery platform for Kubernetes. A developer runs one command, `warden new <name>`, and gets a
repository, a build pipeline, deployment manifests, a catalog entry and a service running behind a canary. Every
release is built by one trusted workflow, signed, and checked again when the cluster admits the Pod. If a canary fails
its metrics, it rolls back without anyone touching it.

The four sample services (books, loans, members, notify) are deliberately trivial. The platform is the product, and the
project is judged on whether its claims can be tested. Eight experiments (E1 to E8) test them, and
[section 6](#6-evaluation) reports what they found.

The project uses these managed services and tools, which covers the course requirement of at least four:

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

Delivery platforms usually answer how a team ships a service and leave the question of what is running to someone
else. Several incidents show why that gap matters. SolarWinds (2020) shipped malicious code inside signed releases.
In the tj-actions incident (2025), version tags were repointed to a malicious commit and secrets reached build logs.
In March 2026, 76 of the 77 version tags of the trivy-action were poisoned, so every pipeline pinned by tag ran
attacker code ([THREAT_MODEL §6](../../THREAT_MODEL.md#6-real-incidents-and-how-warden-relates)).

A valid signature does not close the gap. Any GitHub Actions job can obtain a real Sigstore certificate, and any public
repository can call a public reusable workflow. A signature therefore proves that someone with a GitHub token signed
the image. It does not say which workflow ran, which repository it ran for, or which branch ([THREAT_MODEL
§7](../../THREAT_MODEL.md#7-what-a-valid-signature-does-not-prove)).

Warden's goals, each tied to an experiment ([DESIGN §2](../../DESIGN.md#2-goals-and-non-goals)):

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

The cluster pulls from Git. CI never pushes to it and holds no cluster credentials of any kind (T09).

### 3.1 Repositories

The platform is split into five repositories so each is its own trust boundary with its own reviewers and token scopes
([ADR-001](../../DECISIONS.md#adr-001-polyrepo-four-platform-repositories-plus-a-docs-hub)).

| Repository | Holds | Design |
|------------|-------|--------|
| `warden` (hub) | Design, 34 decision records, threat model T01 to T21, evaluation plan, `versions.yaml` (every pinned version), `scripts/verify.py`, experiment runners, evidence | |
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
| Database | CloudNativePG | CloudNativePG (an Azure Flexible Server composition was designed, not written) |
| Lifetime | as needed | ephemeral: created for a session and destroyed afterwards |

Two B2ms nodes cost about US$0.21 an hour, so a four-hour session is about US$1 against the US$100 student credit
([DESIGN §15](../../DESIGN.md#15-cost-guardrails-azure-for-students)). OpenTofu creates a subscription budget with alerts
at 25, 50 and 75 percent together with the cluster, and `task down:azure` removes both. The Taskfile writes a row to
`evidence/rebuilds/rebuild-ledger.csv` for every environment operation.

## 4. Application architecture

### 4.1 The sample services

Each service is a Spring Boot 4.1 application on Java 25 with Actuator, a Micrometer Prometheus endpoint and
OpenTelemetry instrumentation. The image is built with Jib, without a Docker daemon. `warden.yaml` holds the owner, the
tier and the service-level objective, and every deployment manifest is rendered from it. The books service uses a
`Database`. Two demo switches, `WARDEN_DEMO_ERROR_RATE` and `WARDEN_DEMO_LATENCY_MS`, are compiled in, so a faulty
release is a real, signed release that went through the whole pipeline.

### 4.2 Request path and rollout

Traffic enters through Envoy Gateway and the Gateway API (`HTTPRoute`); Ingress is not used. Each service runs as an
Argo Rollouts `Rollout`. A new version receives 5 percent of traffic, then 25, then 50, then 100, with a two-minute
Prometheus analysis after the first two steps ([DESIGN §9](../../DESIGN.md#9-progressive-delivery)). The analysis passes at a
success rate of at least 99 percent and a p95 latency under 300 ms, and fails below 95 percent or at 500 ms and above.
A window with too few requests ends as inconclusive and pauses the rollout, so silence never promotes a release. A k6
scenario sends about 40 requests per second to each service so the canary sees enough traffic.

### 4.3 Database

A developer asks for a database with a short manifest (kind `Database`, size and PostgreSQL version). Crossplane v2
renders it through a composition into a CloudNativePG cluster and creates a Secret named `<name>-conn` with six keys:
host, port, dbname, username, password and uri. The manifest and the Secret keep the same shape on every cluster.

### 4.4 Observability

kube-prometheus-stack provides Prometheus, Alertmanager and Grafana. Dashboards cover the golden signals, the rollout
timeline, admission decisions and the delivery metrics. Argo CD Notifications write a GitHub Deployment and a status
for every sync of a service, which gives the DORA ledger described in section 5.7.

## 5. Technical design

### 5.1 Trust chain and identity

A commit on a service's `main` branch calls the platform's reusable workflow, pinned by a semver tag. Three jobs matter.

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

Admission works in three layers, so the cheap checks survive a Kyverno outage
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
are prepared in [docs/upstream](../upstream/README.md) and have not been filed.

### 5.3 GitOps and promotion

Argo CD syncs from `warden-gitops`, which is the desired state of the cluster. After a signed build, the promote job
opens a pull request that changes one thing: the image digest of one service. A required status check, `digest-only`,
rejects any other change. The check sits in a ruleset with no bypass actors. A GitHub App, `warden-promoter`, opens the
pull request with a token limited to that repository. Each source repository has its own Argo CD AppProject that limits
which namespaces and kinds it can deploy, and the `default` project is locked (ADR-029). `selfHeal` and `prune` revert
a manual edit to a policy within one reconcile (attack A12).

### 5.4 Progressive delivery

The analysis template queries Prometheus for the canary pods only. Injected faults showed two traps (section 7): the
first analysis ran 9 seconds after the canary started and returned nothing, and Argo CD kept reverting the traffic
weights that Argo Rollouts had set. The analysis now waits two minutes before measuring, and the Service selector and
route weights are excluded from Argo CD's drift repair.

### 5.5 Self-service database

The `Database` API is a Crossplane v2 namespaced composite resource. The composition runs in pipeline mode with
`function-go-templating` and `function-auto-ready`, and composes a CloudNativePG `Cluster` and the `<name>-conn`
Secret. Admission has a narrow exception for the database operator: pods created by its service account, and pods the
Job controller creates for the operator's initialization Jobs, may run three exact upstream image references. A second
policy stops anyone else from creating Jobs that name those images ([ADR-033](../../DECISIONS.md#adr-033-cloudnativepg-carve-out-covers-the-job-controller-and-the-operator-image-jobs-are-gated-at-creation)).

### 5.6 Infrastructure as code and rebuild

OpenTofu creates the resource group, the AKS cluster, the budget and the GitHub-to-Azure federation. The cluster has
local accounts disabled, so the kubeconfig contains only an Entra ID exec plugin and no static credential. State is
encrypted by OpenTofu with a passphrase kept outside Git, in `~/.warden/env`. `task up:azure` creates everything from an
empty subscription, installs Argo CD and applies the root application. Everything else comes from Git. The only inputs
outside Git are the two GitHub App private keys.

### 5.7 CLI and delivery metrics

`warden` is a single Go binary with these commands: `new`, `render`, `verify`, `status`, `dora` and `setup-apps`.
`warden verify` runs the admission checks locally and reads its constants from the policy files, so the CLI and the
cluster cannot drift apart. `warden dora` reads the GitHub Deployments ledger and computes the five DORA metrics
(deployment frequency, change lead time, change fail rate, failed deployment recovery time, rework rate). The ledger
lives in GitHub, so the metrics survive a cluster rebuild.

### 5.8 Threat model coverage

[THREAT_MODEL §5](../../THREAT_MODEL.md#5-threats-controls-and-tests) maps 21 threats to a control and a test. The
attack suite covers T01 to T09 and T11 to T13 on a live cluster. Some risks are accepted and written down, including
that a compromised maintainer's merge is not prevented (T17) and that image verification does not yet fail closed
([§8 of the threat model](../../THREAT_MODEL.md#8-residual-risks-accepted)).

## 6. Evaluation

| ID | Claim | Result | Evidence |
|----|-------|--------|----------|
| E1 | One command creates and deploys a service | Median 8.6 min over three full runs on kind, 0 manual steps. Not run on Azure. | [timings](../../evidence/scaffold-timings/) |
| E2 | Unverifiable artifacts are refused | 15 of 15 on kind and on AKS: one legitimate deployment admitted, A01 to A14 refused for the expected reason | [kind](../../evidence/attacks/2026-10-25T024642Z-results.json), [AKS](../../evidence/attacks/2026-10-26T102953Z-results.json) |
| E3 | Faulty releases roll back without a human | 10 of 10 faulty releases aborted (median 147 s), 10 of 10 healthy releases promoted, median blast radius 0.40 percent of requests against a predicted 0.50, recovery median 12.7 min | [summary](../../evidence/rollbacks/summary-2026-10-25T09.json) |
| E4 | A database from a short request | The same manifest was ready on kind in 804 s cold and 21 s warm, and on AKS in 138 s; `psql` connects with the generated URI | [kind](../../evidence/databases/2026-10-24T152723Z-books-db.json), [AKS](../../evidence/databases/2026-10-26T102407Z-orders-db-azure.json) |
| E5 | DORA metrics from real history | 20 releases with 4 injected faults: lead time 12.6 min, change fail rate 20 percent, recovery 12.6 min, rework 20 percent | [data](../../evidence/dora/2026-10-26-e5-kind.json) |
| E6 | The environment rebuilds from Git | Local: 11 of 12 rebuilds ok, median 14.9 min, p90 24.2 min. Azure: four successful runs from nothing (median 22 min, range 20 to 24) with 20 of 20 applications healthy | [ledger](../../evidence/rebuilds/rebuild-ledger.csv) |
| E7 | Comparison with CNOE idpbuilder | idpbuilder reached GitOps and a first app in 8.5 min using 2.2 GiB and has no admission control. Warden used 8.8 GiB and adds verified admission, canaries and a self-service database. One run each. | [run](../../evidence/comparison/2026-10-25T000834Z-idpbuilder.json) |
| E8 | Cost of verification | Image verification adds 14 to 15 s per Pod when warm, the same on kind and on AKS, so network distance does not explain it | [kind](../../evidence/verification/2026-10-24T192711Z.json), [AKS](../../evidence/verification/2026-10-26T103002Z.json) |

[EVALUATION.md](../../EVALUATION.md) has the procedure and pass criteria for each. The attack suite runs against Deny-mode
clones of the policies, because the live image policy is in Audit.

E5 needs a careful reading. A script drove all 20 releases, with one injected fault in five, so the 20 percent failure
rate comes from the plan. Every promotion pull request was merged with the owner's review bypass, because the bot cannot
merge itself yet (ADR-034). The lead time therefore contains no human review. The figures agree with the experiment
runner's own records: 20 deployments for 20 releases, 4 failures for 4 faults, and a recovery median that equals the
runner's median of 758 seconds. The first computation had given 8 deployments and a 50 percent failure rate, which was
two counting bugs in the CLI.

## 7. Lessons learned

Each item below was found by running the system.

1. A policy tested only in Audit mode has not been tested. A carve-out for database pods passed in Audit, where denials
   are only warnings, and would have stopped every database under Deny. We now run each legitimate pod class, including
   operator-managed pods and Jobs, under a policy before enforcing it (ADR-033).
2. A default can undo a control. The vulnerability policy's default `mutateDigest: true` rewrote a tag to a digest, so
   a tag reference was admitted. We set it to false, and `verify.py` rejects any image policy without that setting.
3. Failing closed needs a latency budget. A policy set to `Fail` in Audit mode denied a legitimate Pod on a webhook
   timeout. Verification takes 14 to 15 seconds per Pod and the limit is 30, so the audit phase uses `Ignore`.
4. Two tools disagreed about who owns a field. Argo CD reverted the traffic weights that Argo Rollouts set, and the
   canary took one third of traffic instead of 5 percent. The fix was `ignoreDifferences` with
   `RespectIgnoreDifferences` (warden-gitops#16).
5. A bypass is not honoured everywhere, and a fix needs a live test. GitHub's auto-merge ignores a ruleset bypass, so the
   bot's pull requests waited for a review nobody would give. Our first fix called `gh pr merge`, which refuses a blocked
   pull request on the client before GitHub is asked, and it failed in its first live run. The second calls the REST
   endpoint. The `digest-only` check stays the guard in both.
6. Measure the measurer. The CLI counted 8 of 20 deployments because GitHub marks superseded deployments inactive and
   Argo CD announces each Git revision for every application. Comparing against the runner's records exposed both.
7. Injected faults need their own queries. Injected 500 responses carry `uri="UNKNOWN"`, so a blast-radius query on `/api`
   counted none.
8. Secrets need a recovery plan. The OpenTofu state passphrase in `~/.warden/env` changed after the first Azure run, and
   the stored state could no longer be decrypted. The old state described an environment that was already destroyed, so
   we pointed OpenTofu at a new state file.
9. Some causes stay unknown. The Kyverno reports controller entered a crash loop that a fresh pod cleared. We could not
   establish why, and the evaluation says so.

Smaller defects came out the same way. The scan gate blocked the first build over Tomcat CVEs until Spring Boot 4.1.2.
GHCR packages created by Actions start private, and the organization first forbade public ones. The Kyverno CRDs stayed
out of sync until a chart value fixed their empty labels. The database Secret's name depended on the backend until the
composition took ownership of `<name>-conn`. The policy test directory was empty until 57 cases were added.
[EVALUATION.md](../../EVALUATION.md) records each with its fix.

## 8. Limitations and open work

- Image verification is not enforcing. The registry, digest and hygiene policies deny. The signature and provenance
  policy is in Audit, so a slow or failing check admits the Pod. It needs Kyverno to retry transient errors and to
  cut the per-Pod latency (ADR-020, ADR-032).
- Azure coverage is thin. E1 and E3 were not run on Azure, and the Azure-native database composition (Flexible
  Server) is not written. Both clusters use CloudNativePG, so only the manifest and the Secret shape are shown to be
  identical across clusters. Two B2ms nodes are enough, with CPU requests at 80 and 94 percent of allocatable.
- Samples are small. E1 has three full runs where five per cluster were planned, E4 has two runs, and E8 has one run
  plus a spot check. The hand-timed baseline for E1 is not done.
- E5 describes an experiment, as section 6 explains.
- A trusted maintainer is not stopped. A signature proves origin, not safety (T17). The owner account can merge
  without review and relies on two-factor sign-in.
- The bot's self-merge is not verified. Version 0.1.1 of the workflow failed its first live run because the `gh` client
  refuses to merge a blocked pull request without `--admin`. Pull request 4 calls the REST endpoint instead and is the
  next release; until a run succeeds, the owner's bypass merges promotion pull requests (ADR-034).
- Repositories and images are public by decision (ADR-002, ADR-028), and platform namespaces are exempt from
  verification.

## 9. Individual contributions

The table is for the team to complete. The repository history alone cannot show who did what.

| Member | Area | Contribution |
|--------|------|--------------|
| Abhyuday Gupta | [area] | [to be written by the member] |
| Aditya Chetan Thakur | [area] | [to be written by the member] |
| Sankalp Arya | [area] | [to be written by the member] |
| Shaurya Jain | [area] | [to be written by the member] |

AI assistance: the repositories were developed with Claude Code (Anthropic). Commits it helped write carry a
`Co-Authored-By: Claude` trailer in the hub repository. Adjust this paragraph to the course's rules on tool use.

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
python scripts/experiments/canary.py <svc> error --admin-merge    # E3, E5 (owner-approved merges only)
python scripts/experiments/verification_cost.py --n 50            # E8
task -d warden-infra up:azure && task -d warden-infra down:azure  # E6 on Azure; always destroy afterwards
```

The demonstration script and the slide outline are in [docs/demo-script.md](../demo-script.md).
