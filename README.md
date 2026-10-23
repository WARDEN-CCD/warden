# Warden

**A golden-path platform for Kubernetes with a verifiable software supply chain.**

One command ships a new service. No container runs unless it can prove — cryptographically, at the cluster's
admission boundary — which commit and which build pipeline produced it. Faulty releases roll back on their own.
The whole environment is rebuilt from Git, routinely.

> CCD project · 5th semester · CSE C · School of Computer Engineering · 2026–27
> Team: Abhyuday Gupta, Aditya Chetan Thakur, Sankalp Arya, Shaurya Jain
> Supervisor: Mohandas Shenoy

## What makes it different

| Typical student DevOps project | Warden |
|--------------------------------|--------|
| CI pushes `:latest` to the cluster with a kubeconfig secret | CI has **no cluster credentials**; Argo CD pulls digests from Git |
| Image scanning that nobody enforces | Signature, SLSA provenance, SBOM and vuln attestations **verified at admission** |
| "Signed" means signed by anyone | Only Warden's own build workflow, from `main` of an org repo, is trusted (SLSA Build L3) |
| Deployments succeed or fail | 5 % canaries judged by Prometheus, **auto-aborted** on SLO breach |
| Demo cluster built by hand once | Destroyed and rebuilt from Git, every rebuild **timed and logged** |
| Claims | 12 scripted attacks, DORA metrics from real history, a threat model with tests |

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
| [DECISIONS.md](DECISIONS.md) | 28 ADRs: what we chose, what we rejected, why |
| [THREAT_MODEL.md](THREAT_MODEL.md) | Threats → controls → tests |
| [EVALUATION.md](EVALUATION.md) | How each claim is measured (E1–E8) |
| [ROADMAP.md](ROADMAP.md) | Milestones, spikes, week plan, risks |
| [RESEARCH.md](RESEARCH.md) | Ecosystem facts verified 2026-10-21, with sources |
| [CONTRIBUTING.md](CONTRIBUTING.md) | How we work: branches, PRs, pinning, ADRs |
| [CLAUDE.md](CLAUDE.md) | Instructions for AI coding assistants working in this workspace |

## Getting started (Windows, Git Bash)

```bash
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -r requirements-dev.txt
./.venv/Scripts/python.exe scripts/doctor.py
./.venv/Scripts/python.exe scripts/verify.py
```

`doctor.py` lists missing tools and the versions to install (from [versions.yaml](versions.yaml)).
To get the four platform repos into this folder:

```bash
for r in warden-infra warden-gitops warden-policy warden-platform; do gh repo clone WARDEN-CCD/$r; done
```

With Task installed, `task doctor`, `task verify` and `task up:local` wrap the same steps.

## Status

Week 0 — design drafted, repositories scaffolded, spikes S1–S3 next. See [ROADMAP.md](ROADMAP.md).
