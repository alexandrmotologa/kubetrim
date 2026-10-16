# KubeTrim Architecture Guide

This document details the internal design and data flow of KubeTrim.

## Architectural Objectives

KubeTrim is designed as a standalone, non-intrusive FinOps tool with four constraints:
1. Zero cluster mutations by default (read-only queries).
2. Zero required daemonsets or cluster-level agent deployments.
3. Strict separation of metrics collection, cost estimation, recommendation generation, and patch serialization.
4. Independent execution via command line interface, interactive terminal interface (TUI), and web dashboard.

## System Components

```
+---------------------------------------------------------------------------------+
|                                 User Interfaces                                 |
|          CLI (Typer/Rich)    |    TUI (Textual)    |    Web Studio (FastAPI)    |
+----------------------------------------+----------------------------------------+
                                         |
                       +-----------------v-----------------+
                       |         KubeTrim Engine           |
                       +-----------------+-----------------+
                                         |
     +-----------------------------------+-----------------------------------+
     |                                   |                                   |
+----v--------------------+     +--------v---------------+     +-------------v----+
|   Kubernetes Client     |     |   Historical Metrics   |     |   Pricing Engine |
| - Workload discovery    |     | - Prometheus PromQL    |     | - AWS/GCP/Azure  |
| - Requests & limits     |     | - Metrics Server API   |     | - Custom rates   |
| - Replicas & QoS        |     | - OOMKill event query  |     | - $/vCPU, $/GB   |
+----+--------------------+     +--------+---------------+     +-------------+----+
     |                                   |                                   |
     +-----------------------------------+-----------------------------------+
                                         |
                       +-----------------v-----------------+
                       |     Advisor & Rightsizer          |
                       | - Headroom calculation            |
                       | - Buffer heuristics & floors      |
                       | - OOMKill safety adjustment       |
                       +-----------------+-----------------+
                                         |
                       +-----------------v-----------------+
                       |       Patch Serialization         |
                       | - Unified YAML Diffs              |
                       | - Helm values.yaml in-place       |
                       | - Kustomize resource patches      |
                       | - JSON / CSV / HTML exports       |
                       +-----------------------------------+
```

### 1. Workload Ingestion (`kubetrim.k8s.client`)

The Kubernetes client utilizes standard authentication via `~/.kube/config` or service account tokens when running as an in-cluster job.

It queries the `apps/v1` and `core/v1` APIs for:
- Deployments, StatefulSets, and DaemonSets.
- Active replica counts and pod template specs.
- Configured container `resources.requests` and `resources.limits`.
- Associated namespaces and labels.

### 2. Historical Metrics Layer (`kubetrim.k8s.prometheus` and `metrics_server`)

Resource consumption must be evaluated over time rather than from a single instantaneous sample. KubeTrim employs a dual-tier strategy:

- **Prometheus / Thanos / Cortex (Preferred)**:
  Executes targeted PromQL quantile queries over an evaluation window (e.g., 7 days or 14 days) to calculate p90, p95, p99, and peak values for both CPU cores and memory working set bytes.
  Also queries `kube_pod_container_status_last_terminated_reason{reason="OOMKilled"}` to count recent memory crashes.
- **Metrics Server Fallback**:
  If Prometheus endpoint is unreachable or unspecified, queries `/apis/metrics.k8s.io/v1beta1` to extract live container usage metrics across pods.

### 3. FinOps Cost Model (`kubetrim.core.cost`)

Cloud providers bill compute by allocated instances. To accurately quantify pod-level waste, KubeTrim translates container requests into amortized hourly and monthly dollar amounts:

$$\text{Monthly Cost} = \left( \text{CPU Cores} \times \text{Rate}_{\text{CPU}} + \text{RAM GB} \times \text{Rate}_{\text{RAM}} \right) \times 730 \times \text{Replicas}$$

Pricing profiles under `configs/pricing/` model AWS EKS, GCP GKE, Azure AKS, and Bare-Metal hardware rates.

### 4. Rightsizing Advisor (`kubetrim.core.advisor`)

Calculates recommended resource requests by applying safety buffers to observed percentiles:

$$\text{Recommended CPU} = \max\left(\text{Percentile CPU} \times (1 + \text{Buffer}_{\text{CPU}}), \text{Floor}_{\text{CPU}}\right)$$
$$\text{Recommended RAM} = \max\left(\text{Percentile RAM} \times (1 + \text{Buffer}_{\text{RAM}}), \text{Floor}_{\text{RAM}}\right)$$

When an OOMKill event is detected for a workload, the memory safety headroom is automatically expanded by `oomkill_extra_buffer` to eliminate crash loops.

### 5. Patch & Diff Generator (`kubetrim.patcher`)

Emits clean, reproducible configuration artifacts:
- **Unified YAML Diff**: Standard Git-compatible diff against original manifests.
- **Helm In-Place Patch**: Updates `resources` dictionaries in `values.yaml` while preserving comments and layout using `ruamel.yaml`.
- **Kustomize Overlays**: Generates standard JSON 6902 or Strategic Merge Patch snippets.
