<p align="center">
  <img src="docs/images/logo.png?raw=true" alt="KubeTrim Logo" width="130" style="border-radius: 24px;" />
</p>

<h1 align="center">KubeTrim</h1>

<p align="center">
  Zero-agent Kubernetes FinOps and pod rightsizing patch generator analyzing historical p95/p99 metrics and cloud costs
</p>

<p align="center">
  <a href="https://github.com/alexandrmotologa/kubetrim/actions"><img src="https://img.shields.io/badge/CI-passing-2ea44f.svg" alt="Build Status" /></a>
  <a href="https://pypi.org/project/kubetrim"><img src="https://img.shields.io/badge/pypi-v0.1.0-blue.svg" alt="PyPI version" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License" /></a>
  <a href="https://python.org"><img src="https://img.shields.io/badge/python-%3E%3D3.10-brightgreen.svg" alt="Python Version" /></a>
</p>

---

Kubernetes workloads are frequently over-provisioned during initial rollout. Teams configure generous CPU and memory requests to prevent out-of-memory crashes and CPU throttling. Because cloud managed clusters schedule worker nodes based on total resource requests, unused allocations generate significant recurring costs.

Existing cost management solutions often demand cluster-admin agents, privileged daemonsets, or external software-as-a-service subscriptions.

KubeTrim runs locally or in CI pipelines without installing cluster agents. It reads workload specifications via standard kubeconfig, queries Prometheus or Kubernetes Metrics Server for historical p90, p95, and p99 utilization metrics, applies safety buffer heuristics, computes dollar waste using real AWS, GCP, and Azure pricing models, and generates unified git diffs, Helm values overrides, and Kustomize patches.

## Demonstration

![KubeTrim Live Demo](docs/images/kubetrim_demo.gif)

### Interface Walkthrough

| Interactive Textual TUI Dashboard | Real-Time Cluster FinOps Web Studio |
| :---: | :---: |
| ![KubeTrim TUI](docs/images/tui_dashboard.png) | ![KubeTrim Web Studio](docs/images/web_dashboard.png) |

| Unified Diff and Helm Patch Inspector | Namespace Waste Analysis and Cost Breakdown |
| :---: | :---: |
| ![YAML Diff Viewer](docs/images/yaml_diff_viewer.png) | ![Cost Breakdown](docs/images/cost_breakdown.png) |

---

## Core Capabilities

- **Zero-agent architecture**: Operates in read-only mode using existing `~/.kube/config` credentials. No cluster controllers, webhooks, or node daemonsets required.
- **Historical metric aggregation**: Evaluates PromQL time-series data over customizable timeframes (7d, 14d, 30d) for p90, p95, and p99 percentiles, with fallback to Kubernetes Metrics Server (`metrics.k8s.io`).
- **Cloud cost calculation engine**: Ships with pricing catalogs for AWS EKS, GCP GKE, Azure AKS, and bare-metal infrastructure, tracking per-vCPU and per-gigabyte hourly rates.
- **Karpenter & Cluster Autoscaler bin-packing**: Simulates multi-dimensional First-Fit Decreasing (FFD) node scheduling to compute physical worker node reduction, removable node counts, and net infrastructure bill savings.
- **HPA conflict protection**: Detects when scaling down CPU requests alters absolute autoscaling thresholds, preventing flapping autoscaler loops by computing recalculated target utilization percentages.
- **Spot instance arbitrage**: Evaluates PodDisruptionBudgets, replica counts, and workload types to score disruption tolerance and highlight additional Spot savings opportunities.
- **Interactive What-If simulation**: Browser-based FinOps Web Studio provides live CPU/memory headroom sliders and quantile selectors for instant scenario modeling.
- **Safety headroom heuristics**: Configurable profiles (`conservative`, `balanced`, `aggressive`) add safety buffers to prevent OOMKills and throttling while lowering idle capacity.
- **OOMKill mitigation guard**: Detects historical container crash events and automatically applies elevated memory safety floors.
- **Actionable GitOps patches**: Emits ready-to-commit unified diffs for Kubernetes Deployment and StatefulSet manifests, in-place Helm `values.yaml` patches, and Kustomize overlays.
- **Automated CI budget gates**: Enforces maximum allowable waste thresholds in pull requests with exit code signaling (`kubetrim gate`) and generates GitHub PR markdown tables.
- **Automated GitOps branch exporter**: Creates dedicated Git branches with formatted commits ready for Pull Request creation (`kubetrim gitops-export`).
- **Multi-cluster context switching**: Seamlessly switches between clusters registered in kubeconfig via `--context` or `kubetrim contexts`.

---

## Architecture

```
                      +---------------------------------------+
                      |         KubeTrim CLI / TUI / Web      |
                      +-------------------+-------------------+
                                          |
                 +------------------------+------------------------+
                 |                                                 |
+----------------v----------------+               +----------------v---------------+
|    Kubernetes Client Engine     |               |    Metrics Ingestion Layer     |
|  * Read-only kubeconfig context |               |  * Prometheus PromQL Evaluator |
|  * Deployments, StatefulSets    |               |  * Metrics Server API fallback |
|  * HPA, PDB & Node discovery    |               |  * OOMKill historical detector |
+----------------+----------------+               +----------------+---------------+
                 |                                                 |
                 +------------------------+------------------------+
                                          |
                        +-----------------v-----------------+
                        |     FinOps Calculation Engine     |
                        |  * Cloud rate cards (AWS/GCP/AKS) |
                        |  * Headroom buffer heuristics     |
                        |  * HPA conflict recalculator      |
                        |  * Spot disruption analyzer       |
                        |  * Karpenter bin-pack simulator   |
                        +-----------------+-----------------+
                                          |
                        +-----------------v-----------------+
                        |      Patch & Export Generator     |
                        |  * Unified YAML git diffs         |
                        |  * Helm values.yaml updates       |
                        |  * Kustomize resource patches     |
                        |  * GitOps PR branch commits       |
                        |  * CI/CD budget gatekeeper        |
                        |  * JSON, CSV, and HTML reports    |
                        +-----------------------------------+
```

---

## Installation

### Via pip

```bash
pip install kubetrim
```

### From source

```bash
git clone https://github.com/alexandrmotologa/kubetrim.git
cd kubetrim
python -m venv .venv
source .venv/bin/activate  # On Windows: .\.venv\Scripts\activate
pip install -e ".[dev]"
```

---

## Quickstart

### 1. Scan a cluster or namespace

Scan all workloads in the default namespace using AWS us-east-1 pricing and the balanced profile:

```bash
kubetrim scan --namespace default --provider aws
```

### 2. Simulate Karpenter / Autoscaler node bin-packing

Calculate physical worker node reduction and direct cloud bill savings:

```bash
kubetrim binpack --provider aws --instance-type m6i.xlarge
```

### 3. Enforce CI/CD FinOps budget gates

Fail pull requests if newly committed manifests exceed allowable over-provisioning thresholds:

```bash
kubetrim gate --manifest ./manifests/deployment.yaml --max-waste-usd 50 --fail-on-waste --pr-comment-file comment.md
```

### 4. Export automated GitOps patch branch

Create a new Git branch with the rightsized resource specifications committed:

```bash
kubetrim gitops-export ./manifests/deployment.yaml --branch finops/rightsize-checkout
```

### 5. Generate unified YAML diffs

Generate patch diffs for local deployment manifests:

```bash
kubetrim diff ./manifests/deployment.yaml
```

### 6. Patch Helm values.yaml in-place

Update `resources` blocks in a Helm chart values file with rightsized recommendations:

```bash
kubetrim patch ./charts/my-app/values.yaml --write
```

### 7. Launch the Interactive Textual TUI

```bash
kubetrim tui
```

### 8. Launch the Web Studio Dashboard

```bash
kubetrim web --port 8980
```

Open `http://localhost:8980` in your browser.

---

## Rightsizing Profiles

KubeTrim provides pre-configured profiles under `configs/profiles/`:

| Profile | Target Percentile | CPU Buffer | Memory Buffer | Target Workload |
| :--- | :---: | :---: | :---: | :--- |
| `conservative` | p99 | +40% | +40% | Mission-critical core services |
| `balanced` | p95 | +20% | +20% | General production applications |
| `aggressive` | p90 | +10% | +10% | Development, staging, and batch jobs |

You can also pass custom parameters or use the interactive sliders in Web Studio:

```bash
kubetrim scan --buffer-cpu 0.25 --buffer-memory 0.30 --min-cpu 0.05
```

---

## Cloud Pricing Reference

Default hourly rates per vCPU and GB RAM are loaded from `configs/pricing/`:

- **AWS EKS (us-east-1)**: \$0.04048 / vCPU-hour, \$0.004445 / GB-hour
- **GCP GKE (us-central1)**: \$0.03350 / vCPU-hour, \$0.004490 / GB-hour
- **Azure AKS (eastus)**: \$0.03800 / vCPU-hour, \$0.005100 / GB-hour
- **Bare-metal / Custom**: User-specified rate cards

---

## Development & Testing

Run tests and verification:

```bash
pytest
```

Run test suite with coverage report:

```bash
pytest --cov=kubetrim --cov-report=term-missing
```

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
