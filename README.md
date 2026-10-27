# Warden

**A golden-path platform for Kubernetes with a verifiable software supply chain.**

One command ships a new service. Images are signed and checked against their commit and build pipeline at the
admission boundary. Digest, registry and pod-hygiene rules deny invalid workloads; cryptographic image verification
remains in Audit while its reliability is measured (ADR-032 and ADR-035). Faulty releases roll back on their own.
The whole environment is rebuilt from Git, routinely.

> CCD project · 5th semester · CSE C · School of Computer Engineering · 2026–27
> Team: Abhyuday Gupta, Aditya Chetan Thakur, Sankalp Arya, Shaurya Jain
> Supervisor: Mohandas Shenoy

## What makes it different

| Typical student DevOps project | Warden |
|--------------------------------|--------|
| CI pushes `:latest` to the cluster with a kubeconfig secret | CI has **no cluster credentials**; Argo CD pulls digests from Git |
| Image scanning that nobody enforces | Signature, SLSA provenance, SBOM and vulnerability attestations checked at admission; cryptographic checks currently report in Audit |
| "Signed" means signed by anyone | The verification policy checks for Warden's own build workflow and `main` of an org repo (SLSA Build L3); live enforcement is pending |
| Deployments succeed or fail | 5 % canaries judged by Prometheus, **auto-aborted** on SLO breach |
| Demo cluster built by hand once | Destroyed and rebuilt from Git, every rebuild **timed and logged** |
| Claims | 14 scripted attacks, DORA metrics from real history, a threat model with tests |

## Repository map

This folder is the **hub** (`warden`): design, decisions, threat model, evaluation evidence and workspace tooling.
The four platform repositories are cloned inside it (and ignored by the hub's Git):

| Path | Repo | Purpose |
|------|------|---------|
| `warden-infra/` | `WARDEN-CCD/warden-infra` | OpenTofu (Azure, AKS), kind, Crossplane APIs |
| `warden-gitops/` | `WARDEN-CCD/warden-gitops` | Desired cluster state for Argo CD |
| `warden-policy/` | `WARDEN-CCD/warden-policy` | Admission policies, policy tests, attack suite |
| `warden-platform/` | `WARDEN-CCD/warden-platform` | Reusable build workflow, `warden` CLI, service template, observability |

## Documents

| Doc | Read it for |
|-----|-------------|
| [DESIGN.md](DESIGN.md) | Architecture, trust model, every component and why it is there |
| [STATUS.md](STATUS.md) | **Start here when resuming**: where the project stands, what is left, traps to avoid |
| [docs/report/report.md](docs/report/report.md) | The technical design document (final report) |
| [docs/demo-script.md](docs/demo-script.md) | Demo scenes, commands and the presentation outline |
| [DECISIONS.md](DECISIONS.md) | 34 ADRs: what we chose, what we rejected, why |
| [THREAT_MODEL.md](THREAT_MODEL.md) | Threats → controls → tests |
| [EVALUATION.md](EVALUATION.md) | How each claim is measured (E1–E8) |
| [ROADMAP.md](ROADMAP.md) | Milestones, spikes, week plan, risks |
| [RESEARCH.md](RESEARCH.md) | Ecosystem facts verified 2026-10-21, with sources |
| [CONTRIBUTING.md](CONTRIBUTING.md) | How we work: branches, PRs, pinning, ADRs |

## Getting started (Windows, Git Bash)

```bash
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -r requirements-dev.txt
./.venv/Scripts/python.exe scripts/doctor.py
./.venv/Scripts/python.exe scripts/verify.py
```

`doctor.py` lists missing tools and the versions to install (from [versions.yaml](versions.yaml)). It also
checks `~/.warden/env`, where `WARDEN_JAVA_HOME` points at JDK 25 for Warden builds only
([CONTRIBUTING.md](CONTRIBUTING.md#local-setup-wardenenv)).
To get the four platform repos into this folder:

```bash
for r in warden-infra warden-gitops warden-policy warden-platform; do gh repo clone WARDEN-CCD/$r; done
```

With Task installed, `task doctor`, `task verify` and `task up:local` wrap the same steps.

## Status

The platform is built and evaluated (E1 to E8 have evidence under `evidence/`). Native admission policies and pod
hygiene deny; image verification stays in Audit until Kyverno improves. Open work and the order to do it in are in
[STATUS.md](STATUS.md); the plan and milestones are in [ROADMAP.md](ROADMAP.md).
