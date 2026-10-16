# KubeTrim: Master Implementation Plan

> **Zero-Agent Kubernetes FinOps & Pod Rightsizing Patch Generator**
>
> *Cut cloud Kubernetes spend by 30%–60% without installing invasive cluster agents. Compares CPU/memory resource allocations against actual p95 historical utilization, calculates dollar waste across AWS EKS, GCP GKE, and Azure AKS, and generates ready-to-apply Helm and YAML rightsizing patches.*

---

## 1. Project Overview & Architecture

Development teams routinely over-provision Kubernetes workloads out of caution, setting inflated `resources.requests` (e.g. requesting 4 CPU cores and 8GB RAM for a service that rarely peaks above 0.5 cores and 1.5GB RAM). Because cloud providers bill for *requested* node capacity rather than actual utilization, companies waste tens of thousands of dollars each month on idle compute.

Commercial FinOps platforms (Kubecost, Cast AI, Vantage) are expensive, require invasive agents with cluster-admin privileges, and push SaaS lock-in.

**KubeTrim** provides a lightweight, 100% read-only, agentless alternative:
1. **Agentless Connection**: Runs locally using your existing `~/.kube/config` and queries Kubernetes Metrics Server or Prometheus for historical p90/p95/p99 usage metrics.
2. **Cost Calculation Engine**: Ingests realistic pricing models across cloud providers (AWS, GCP, Azure, bare-metal per-vCPU and per-GB/hour rates) to calculate monthly dollar burn per namespace and deployment.
3. **Safety Buffer Heuristics**: Recommends rightsized request/limit values incorporating a configurable safety buffer (e.g. $+25\%$ headroom over p95 peak) to prevent throttling or OOMKills.
4. **Automated YAML / Helm Patch Generator**: Outputs exact `git diff` patches for `values.yaml` or Deployment manifests ready to commit into GitOps repositories (ArgoCD / Flux).
5. **Interactive TUI & Web Dashboard**: Real-time cluster financial overview with namespace breakdown, cluster waste heatmaps, and 1-click patch exports.

```
+-----------------------------------------------------------------------------------+
|                                     KUBETRIM                                      |
+-----------------------------------------+-----------------------------------------+
                                          |
        +---------------------------------+---------------------------------+
        |                                                                   |
+-------v-------------------------+                 +-----------------------v-------+
|    Kubernetes Cluster Client    |                 |   Historical Metrics Engine   |
|  * Read-Only ~/.kube/config     |                 |  * Kubernetes Metrics Server  |
|  * Pod Spec Requests & Limits   |                 |  * Prometheus p95 Querying    |
|  * Namespace & DaemonSet Filter |                 |  * Peak Spikes & OOM History  |
+-------+-------------------------+                 +-----------------------+-------+
        |                                                                   |
        +---------------------------------+---------------------------------+
                                          |
                        +-----------------v-----------------+
                        |      FinOps Rightsizing Engine    |
                        |  * Cloud Cost Calculator ($/mo)   |
                        |  * Safety Buffer Headroom (+25%)  |
                        |  * Potential Savings Projection   |
                        +-----------------+-----------------+
                                          |
                        +-----------------v-----------------+
                        |      Actionable Patch Output      |
                        |  * Git Diff Helm values.yaml      |
                        |  * K8s Deployment Manifest Patch  |
                        |  * Interactive TUI & Web Studio   |
                        +-----------------------------------+
```

---

## 2. Directory Structure

```
kubetrim/
├── pyproject.toml
├── README.md
├── LICENSE
├── configs/
│   ├── pricing/
│   │   ├── aws-us-east-1.json        # AWS EKS vCPU & RAM hourly rates
│   │   ├── gcp-us-central1.json      # GCP GKE compute pricing
│   │   └── azure-eastus.json         # Azure AKS pricing
│   └── profiles/
│       ├── conservative.yaml         # +40% buffer over p99 (zero risk)
│       └── balanced.yaml             # +20% buffer over p95 (optimal savings)
├── docs/
│   ├── architecture.md
│   ├── cli-reference.md
│   └── rightsizing-methodology.md
├── src/
│   └── kubetrim/
│       ├── __init__.py
│       ├── py.typed
│       ├── cli/
│       │   ├── __init__.py
│       │   └── main.py
│       ├── core/
│       │   ├── __init__.py
│       │   ├── config.py             # Rightsizing policy & threshold schemas
│       │   ├── models.py             # WorkloadMetrics, RightsizingRecommendation
│       │   ├── cost.py               # Cloud provider pricing matrix & cost calculator
│       │   └── advisor.py            # Headroom calculation & recommendation engine
│       ├── k8s/
│       │   ├── __init__.py
│       │   ├── client.py             # Read-only official Kubernetes Python client
│       │   ├── metrics_server.py     # Live kubectl top pod/node scraper
│       │   └── prometheus.py         # PromQL p95 historical utilization client
│       ├── patcher/
│       │   ├── __init__.py
│       │   ├── yaml_diff.py          # Generates clean unified diffs for K8s manifests
│       │   └── helm_patch.py         # Patches Helm values.yaml files in-place
│       ├── tui/
│       │   ├── __init__.py
│       │   └── app.py                # Rich / Textual terminal dashboard
│       └── web/
│           ├── __init__.py
│           ├── server.py             # FastAPI backend with WebSocket cluster status
│           └── static/               # Dark-mode dashboard with cost charts & 1-click diffs
└── tests/
    ├── test_cost.py
    ├── test_advisor.py
    ├── test_yaml_diff.py
    ├── test_metrics_server.py
    └── test_cli.py
```

---

## 3. Step-by-Step Implementation Roadmap

### Phase 1: Cluster Ingestion & Resource Discovery (`src/kubetrim/k8s/`)
- Connect via `kubernetes.config.load_kube_config()` with zero cluster mutations (read-only).
- Discover all Deployments, StatefulSets, and DaemonSets across namespaces.
- Extract configured requests and limits:
  - CPU: millicores (`m` or float).
  - Memory: mebibytes/gibibytes (`Mi`, `Gi`).

### Phase 2: Historical Utilization & Metrics Aggregation (`src/kubetrim/k8s/prometheus.py`)
- Query Prometheus for historical time-series metrics over the evaluation window (e.g. 14 days):
  - CPU: `quantile_over_time(0.95, rate(container_cpu_usage_seconds_total[5m])[14d:5m])`
  - Memory: `quantile_over_time(0.95, container_memory_working_set_bytes[14d:5m])`
  - Peak: `max_over_time(...)`
- Fallback: If Prometheus is unavailable, gracefully query the live Kubernetes Metrics Server API (`/apis/metrics.k8s.io/v1beta1`).

### Phase 3: Rightsizing Algorithm & Cost Calculations (`src/kubetrim/core/`)
- For each container:
  $$\text{Recommended CPU} = \max(\text{p95\_CPU} \times (1 + \text{Buffer}), \text{Min\_CPU})$$
  $$\text{Recommended RAM} = \max(\text{p95\_RAM} \times (1 + \text{Buffer}), \text{Min\_RAM})$$
- Calculate monthly dollar savings:
  $$\text{Savings} = (\Delta \text{CPU} \times \text{Rate}_{\text{CPU}} + \Delta \text{RAM} \times \text{Rate}_{\text{RAM}}) \times 730 \text{ hours} \times \text{Replicas}$$
- Flag high-risk workloads (e.g. pods that experienced recent OOMKills receive stricter memory headroom).

### Phase 4: Patch Generator (`src/kubetrim/patcher/`)
- `yaml_diff.py`: Generates standardized unified diffs:
  ```diff
  --- a/deployment.yaml
  +++ b/deployment.yaml
  @@ -24,8 +24,8 @@
             resources:
               requests:
  -              cpu: "2000m"
  -              memory: "4Gi"
  +              cpu: "400m"
  +              memory: "1280Mi"
  ```
- Support direct GitOps patch application: `kubetrim apply --manifest ./k8s/deployment.yaml`.

### Phase 5: CLI & Dual Dashboards
- CLI commands:
  - `kubetrim scan [--namespace <name>] [--provider aws]`: Terminal summary table.
  - `kubetrim diff ./manifests/`: Outputs patch files for all over-provisioned workloads.
  - `kubetrim tui`: Textual-based interactive cluster cost monitor.
  - `kubetrim web --port 8980`: Browser interface with savings meters and namespace treemaps.

---

## 4. Agent Kickoff Prompt (Copy-Paste Ready)

```markdown
You are building KubeTrim from scratch.

KubeTrim is a zero-agent Kubernetes FinOps and pod rightsizing patch generator.
It analyzes historical p95 CPU and memory utilization, projects dollar savings across AWS, GCP, and Azure, and synthesizes ready-to-commit Helm and YAML patches.

Follow these rules:
1. All code, comments, commit messages, and docs must be in English.
2. Zero mocks or placeholder implementations. Write authentic Kubernetes client interactions, PromQL queries, and YAML diff generation.
3. Keep test coverage high with pytest.
4. Provide a rich CLI with Typer and an interactive Web Studio with FastAPI.

Begin by setting up the repository in `B:\workgit\kubetrim`, initialize git, write the core schemas in `src/kubetrim/core/models.py`, and implement the Kubernetes resource discovery client and cost calculator.
```
