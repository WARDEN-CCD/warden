# Demo recordings and presentation outline (M5)

Runbook for the recordings in `evidence/recordings/` and the final presentation. Every scene shows something the
evidence folder already proves; the recording is a view of the evidence, never a replacement for it. Link large video
files from `evidence/recordings/README.md` instead of committing them.

Before the demo: run `./.venv/Scripts/python.exe scripts/doctor.py`, confirm Docker Desktop is running, and check the
kind cluster with `kubectl get applications -n argocd`. The 28 Oct rehearsal found 23 applications, all
Synced/Healthy. A cold local rebuild takes about 15 minutes, so do not start `task rebuild:local` during a short
presentation. Run `task up:local` only if `kind get clusters` does not list `warden`; it creates a new cluster and
does not reuse one that already exists. Build the CLI once from `warden-platform/cli` with
`go build -o bin/warden.exe ./cmd/warden`.

## Suggested 10-minute teacher walkthrough

1. **Problem and design (2 minutes):** use slides 1–6. Explain that Warden is the platform; the four sample services
   are intentionally small. Trace one change from a signed build, through a digest-only Git PR, to Argo CD and a
   canary rollout.
2. **Live deployment (1 minute):** run `kubectl get applications -n argocd` and `kubectl get rollouts -A`. Point out
   the four services and the healthy rollout state. Run `warden status books` to show its current digest and rollout.
3. **Supply-chain proof (2 minutes):** get the current image from the books Rollout, then run `warden verify` on that
   digest. Show the signature, provenance, SBOM and vulnerability result. This command contacts public registry and
   transparency services, so rehearse it on the same network before class.
4. **Security and recovery (2 minutes):** show the E2 attack summary and one E3 rollback record from `evidence/`.
   Explain that the attack harness uses Deny-mode test policies while the live supply-chain policy remains in Audit.
   Avoid starting a new canary release in class unless you have rehearsed the full GitHub-to-cluster path; it creates
   a real release and can take several minutes.
5. **Database and measurements (2 minutes):** explain the same declarative `Database` request, then show the saved
   Azure Flexible Server smoke-test record: PostgreSQL 18 was provisioned, a temporary `psql` Pod queried it using
   the generated Secret, and the database, AKS cluster and resource group were removed. Be precise: the query ran in
   `crossplane-system`; no books service migration, repeat timing or representative cost benchmark was run.
6. **Limits and close (1 minute):** cover the remaining service-level database test and benchmark, open evaluation
   comparisons, and why live image verification remains in Audit. The team kept the Kyverno version pinned.

Useful commands from the repository root:

```powershell
kubectl get applications -n argocd
kubectl get rollouts -A
warden-platform\cli\bin\warden.exe status books
$image = kubectl get rollout books -n svc-books -o jsonpath='{.spec.template.spec.containers[0].image}'
warden-platform\cli\bin\warden.exe verify $image
$hosts = @('books','loans','members','notify'); foreach ($hostName in $hosts) { $url = "http://${hostName}.warden.localhost:18080/api/info"; $code = & curl.exe -sS -o NUL -w '%{http_code}' --resolve "${hostName}.warden.localhost:18080:127.0.0.1" $url; Write-Output "$hostName $code" }
warden-platform\cli\bin\warden.exe dora --since 2026-10-27T13:38:00Z --until 2026-10-27T15:10:00Z --by-service
```

If a live network check is slow, use the committed evidence files linked below and label them as recorded results.
The demo is a walkthrough of measured evidence; it should not depend on completing a fresh environment rebuild in front
of the class.

## Scenes

| # | Scene | What to run/show | What the viewer must see | Backing evidence |
|---|-------|-------------|--------------------------|------------------|
| 1 | One-command service creation | Show the E1 timings and a service's generated repo/workflow; don't create a new public repo during the presentation | Five completed kind runs, median 8.6 min, zero manual steps | E1, [scaffold timings](../evidence/scaffold-timings/) |
| 2 | Pipeline proof | `warden verify <current-image@sha256:...>` | Signature, provenance, SBOM and vulnerability result for the exact deployed digest | E2, THREAT_MODEL T02/T08 |
| 3 | Admission tests | Show the saved A01–A14 results; run the attack harness only if rehearsed | 15/15 cases passed: 14 attacks refused for their expected threat IDs and one legitimate control admitted | E2, [attacks](../evidence/attacks/) |
| 4 | Automatic rollback | Show a recorded E3 error run and the matching Rollout/analysis result | Canary abort and recovery without a person changing traffic | E3, [rollbacks](../evidence/rollbacks/) |
| 5 | Declarative database | Show the recorded `Database` request and Azure smoke-test JSON | Azure PostgreSQL provisioning and a temporary `psql` query passed; service migration, repeat timings and cost remain open | E4, [databases](../evidence/databases/) |
| 6 | Delivery metrics | Run the DORA command above or show the saved JSON | 20 app-only deployments, including the planned injected failures; discuss the short synthetic window | E5, [DORA evidence](../evidence/dora/) |
| 7 | Rebuild from Git | Show the latest rebuild ledger and current `kubectl get applications` result; do not run a 15-minute rebuild live | The recorded fresh rebuild completed in 869 seconds, with 23/23 apps Synced/Healthy at that time and all four services returning HTTP 200 | E6, [ledger](../evidence/rebuilds/rebuild-ledger.csv) |

Show the evidence's date and environment whenever you use a recorded result. The DORA values are real pipeline
measurements from a short, planned experiment, not a claim about routine team deployment frequency.

## Presentation deck

The submission-ready deck is [Warden-CCD-Project-Presentation-FINAL.pptx](submission/Warden-CCD-Project-Presentation-FINAL.pptx), with a
matching PDF in the same folder. It has 17 slides and uses the measured E5 results. Slide 15 lists the open submission
gates; review it on presentation day. Regenerate both files with `node scripts/build_presentation.cjs` after editing the
source, then render and inspect the exported pages.

The deck covers the project outcomes, architecture, build trust boundary, admission layers, attack results, rollback,
database evaluation, DORA metrics, rebuild evidence, verification latency, engineering lessons, remaining gates and
technical references. Azure Flexible Server is marked as a passed smoke test, with the untested service migration and
benchmark stated as remaining work.

## Checks before presenting

- Every number on a slide is copied from `EVALUATION.md` or the linked evidence file, not retyped from memory.
- No slide calls a policy "enforced" that is still in `Audit` (rule 11; check `evidence/m3/` for the current state).
- Anything not yet run is labelled as such, including the service-level Azure migration and benchmark.

