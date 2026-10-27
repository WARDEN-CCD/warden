# Warden presentation and demonstration guide

This guide pairs with the editable [final deck](Warden-CCD-Project-Presentation-FINAL.pptx) and its [PDF](Warden-CCD-Project-Presentation-FINAL.pdf). The spoken presentation is 10 minutes for four presenters. It is written for an audience meeting the project for the first time.

## The project in one sentence

Warden is a Kubernetes delivery platform that checks how software was built, controls which container images can enter a cluster, deploys approved changes gradually, and can stop a rollout when the new version behaves badly.

The four sample applications (Books, Loans, Members and Notify) are deliberately simple. They are test workloads used to exercise the platform. Warden itself—the build workflow, command-line tool, policies, GitOps setup, rollout controls and evidence—is the project.

## Before presenting

Do these checks before class, not while the 10-minute clock is running:

1. Open the deck and keep this guide available on a second screen or printed page.
2. In PowerShell at the repository root, run:

   ```powershell
   .\.venv\Scripts\python.exe scripts\doctor.py
   kubectl config current-context
   kubectl get applications -n argocd
   kubectl get rollouts -A
   ```

   The expected local context is `kind-warden`. At the 28 October rehearsal, all 23 listed Argo CD applications were Synced/Healthy. If the cluster is unavailable, use the saved evidence listed below and say it is recorded evidence.
3. Confirm the CLI exists at `warden-platform\cli\bin\warden.exe`. If it does not, build it from `warden-platform\cli` with `go build -o bin/warden.exe ./cmd/warden`.
4. Rehearse `warden.exe status books` and the four local HTTP checks in [the demo runbook](../demo-script.md). Rehearse `warden.exe verify <image>` on the same network you will use in class; it contacts public registry/transparency services and may take time.
5. Do not start a cold rebuild, new public service creation, Azure provisioning or a fresh canary release during the presentation. They can outlast the available time. Show recorded experiment results for those parts.
6. Keep a terminal open with a large font. If a live command takes more than about 10 seconds, switch to the matching saved JSON or screenshot and label it with its date and environment.

### Safe live-demo sequence

Use only these read-only checks during the presentation:

```powershell
kubectl get applications -n argocd
kubectl get rollouts -A
warden-platform\cli\bin\warden.exe status books
$image = kubectl get rollout books -n svc-books -o jsonpath='{.spec.template.spec.containers[0].image}'
$image
```

If time and network allow, run `warden-platform\cli\bin\warden.exe verify $image`. Do not paste a mutable tag; the command should show the deployed image digest. For the service check, use the four `curl.exe` commands in `docs/demo-script.md`. The expected response is HTTP 200 for each service.

For an offline fallback, show `evidence/attacks/`, `evidence/rollbacks/`, `evidence/databases/2026-10-27-azure-flexible-server-smoke.json`, `evidence/dora/`, or `evidence/rebuilds/rebuild-ledger.csv`. Evidence is part of the project: explain the test date, environment and exact result, not just the headline number.

## Ten-minute, four-presenter script

The goal is to explain the system and demonstrate evidence, not to read every slide. Keep each section to its time slot. The final references slide can remain on screen during questions.

### 0:00–2:30 — Abhyuday Gupta: purpose, architecture and trusted build

**Slides 1–5.**

“Good morning. Our project is Warden, a delivery platform for software running on Kubernetes. The four sample services are intentionally small; they let us test the platform without confusing application features with delivery controls.

The problem we address is that a successful build alone does not tell an operator whether the deployed image came from the expected source, whether it was changed after the build, or how the system will respond if a release fails.

This diagram shows our main pieces. A developer changes source code. A GitHub Actions workflow builds a container image and attaches evidence about the build. The image is identified by its digest, which is a content-based fingerprint. Our GitOps repository then records the desired version. Argo CD, running inside the cluster, reads that Git state and applies it. The cluster—not the CI job—performs the deployment.

That separation is deliberate. CI can publish a reviewed desired-state change, but it does not receive Kubernetes credentials. The deployed workload can therefore be traced back through Git to the image and its build evidence. Next, Sankalp will explain the policy checks and what we tested against them.”

**Plain-language cues:** A *container image* is the packaged application and its runtime. A *digest* is a fingerprint of that exact package; changing the contents changes the fingerprint. *GitOps* means Git stores the intended state and a cluster controller brings the real cluster toward it. *Argo CD* is that controller in our setup.

### 2:30–5:00 — Sankalp Arya: admission controls and attack results

**Slides 6–8 and 13.**

“A Kubernetes cluster can check a workload before allowing it to run. Warden uses these admission checks to examine image references and their supporting build evidence. For example, an image should be pinned to a digest, come from an allowed registry, and have evidence from an approved build identity.

We tested this with controlled attacks: cases such as using a tag instead of a digest, using an untrusted image, or removing required evidence. The saved final run passed all 15 test cases: 14 attacks were rejected for their expected reasons, and the legitimate control was admitted. These tests used temporary Deny-mode test policies so that we could verify the expected rejection behavior.

There is an important status distinction: the live image-verification policy is still in Audit mode. Audit records what would have been rejected; it does not block the workload. We have not claimed live Deny enforcement. Warm verification took about 14 to 15 seconds against a 30-second webhook timeout, and transient delays reduce the safety margin. We kept the Kyverno version pinned and left enforcement staged until reliability testing supports a change.

The result is a measured security boundary with a clear next gate, rather than an unsupported claim that every live deployment is already blocked.”

**Plain-language cues:** *Admission* is the cluster’s “check before entry.” *Audit* reports a policy violation; *Deny* blocks it. A *signature* links an image to a signing identity. *Provenance* describes where and how the image was built. An *SBOM* is a list of software components inside it. A controlled attack is a planned negative test, not an attempt to compromise an unrelated system.

### 5:00–7:30 — Shaurya Jain: deployment, canary and observability

**Slide 9, the live read-only cluster check, and slide 14.**

“Once GitOps applies a new version, Warden uses a canary rollout. A canary sends a small share of user traffic to the new version first. The system watches measurements such as request success and latency. If the new version crosses a failure threshold, the rollout stops and returns traffic to the stable version. If it stays healthy, it receives more traffic and is promoted.

We tested both faulty and healthy releases. In the recorded experiment, all four app-only injected faulty releases aborted automatically, and all 12 healthy canaries promoted. The median time from canary start to abort was about 147.6 seconds. These are results from a planned experiment, not a guarantee that every possible failure is caught.

Here is the live cluster view. This command lists GitOps applications and whether they are synchronized and healthy. This one lists rollouts. The CLI status command summarizes the Books service. [Run the read-only commands.] If the cluster is slow or unavailable, I’ll use the dated rehearsal output rather than wait.

Our engineering lessons include fixing an interaction between GitOps and the rollout controller, and correcting how deployment records are counted. The failures helped us improve both the platform and the measurement process.”

**Plain-language cues:** A *canary* is a limited release to a small amount of traffic. *Rollback* means returning to the previous healthy version. *Observability* means using metrics and system state to understand what the software is doing. “Synced” means GitOps has applied the desired configuration; “Healthy” means the component reports that it is operating normally.

### 7:30–10:00 — Aditya Chetan Thakur: database, results, limits and close

**Slides 10–12 and 15–16.**

“Warden also offers a declarative database request. A developer describes the database they need, and the platform provisions it through the selected backend. We measured the local CloudNativePG path and the AKS path. We also live-tested Azure Database for PostgreSQL Flexible Server: Crossplane provisioned PostgreSQL 18, created the application database and connection Secret, and a temporary `psql` Pod successfully queried it. We removed the test database and the temporary Azure cluster afterward.

We describe this carefully as a smoke test. The SQL client ran in the platform namespace. We have not yet run the Books service’s database migration against Azure or collected repeatable timing and cost measurements, so the full application-level database outcome remains partial.

The remaining slides summarize delivery measurements and rebuild results. Our 20-deployment DORA experiment was a short scripted sample with planned faults; it is not our normal team deployment rate. Rebuild results are recorded from local and Azure runs. Image-verification enforcement remains in Audit until repeated reliability and timeout checks pass.

To conclude, Warden connects build evidence, policy checks, GitOps delivery and automated recovery, and we evaluated those parts with saved experiments. We have merged the project changes, preserved the current Kyverno version, and documented what remains open. Thank you—we’re happy to take questions.”

**Plain-language cues:** *Crossplane* provisions infrastructure from Kubernetes-style resource requests. A *Secret* is a Kubernetes object used to provide connection details securely to workloads. A *smoke test* checks that a basic path works; it is not a load test or a full application migration. *DORA metrics* describe software delivery performance; a small scripted sample should not be generalized into a long-term team performance claim.

## If the teacher asks

**“What does the project actually do?”** Warden helps a team build, verify, deploy and monitor software on Kubernetes. The sample services are the test subjects; the delivery platform is the main product.

**“Does it block every unsafe image today?”** No. The controlled test suite rejected the tested cases, but live image verification remains in Audit. The team is keeping it there until reliability and timeout margins are demonstrated.

**“Is the Azure database finished?”** Provisioning, generated connection details, a basic SQL query and teardown were verified. The service migration, a service-namespace connection test, and representative repeat timing/cost measurements remain.

**“Why not upgrade Kyverno?”** The project keeps the pinned version and focuses on verifying the current implementation. A version change would need its own tested, reviewed change; it is not required for this presentation.

**“Can you show Grafana?”** If the local Grafana dashboard has already loaded, show the Warden rollout dashboard briefly as supporting observability evidence. Do not make it a dependency for the core demo; the CLI and saved rollout records prove the main story. If it is blank or slow, return to the deck.

**“Are the DORA numbers representative of normal work?”** No. They describe a 20-deployment scripted experiment with planned faults over a short window. The presentation labels that limit.

## Glossary

| Term | Meaning in this project |
|---|---|
| Kubernetes | System that runs and manages containers across a cluster of machines. |
| Cluster | The Kubernetes control plane and machines running the applications. |
| CI | Continuous integration: automated build and checks after a code change. |
| GitOps | Keeping desired deployment configuration in Git and reconciling the cluster to it. |
| Argo CD | Controller that applies Git-stored desired state to Kubernetes. |
| Digest | Content fingerprint that identifies one exact container image. |
| Signature | Cryptographic proof connecting an artifact to a signing identity. |
| Provenance | Verifiable record of the source and process used to build an artifact. |
| SBOM | Software Bill of Materials: inventory of components inside an image. |
| Admission policy | Rule checked by Kubernetes before a resource is accepted. |
| Canary | Gradual release that sends a small share of traffic to a new version first. |
| Audit / Deny | Audit records a policy violation; Deny rejects the resource. |
| Crossplane | Kubernetes extension used here to provision local or cloud infrastructure. |
| DORA | Delivery metrics used to discuss deployment lead time, recovery and failure rates. |

