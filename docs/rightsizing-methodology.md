# KubeTrim Rightsizing Methodology

This document outlines the statistical principles, formulas, and safety heuristics KubeTrim uses to recommend resource requests and limits.

## The Over-Provisioning Problem

In Kubernetes, the scheduler schedules pods onto nodes based on `resources.requests`, not on actual utilization. Node autoscalers (such as Cluster Autoscaler or Karpenter) provision additional EC2/Compute Engine instances when aggregate requests exceed node allocatable capacity.

When applications request 2000m CPU and 4Gi RAM but realistically operate at 250m CPU and 800Mi RAM:
1. Nodes fill up prematurely with phantom reservations.
2. Cloud bills reflect the provisioned instance sizes rather than consumed resources.
3. The cluster operates at 10%–20% average hardware efficiency.

## Percentile Evaluation

Instantaneous utilization metrics are noisy. A single batch routine or warm-up phase can skew point-in-time observations. KubeTrim aggregates time-series metrics over a sliding window (default: 14 days):

- **p90 (90th percentile)**: 90% of observed 5-minute sampling buckets fall below this value. Useful for dev/staging environments or fault-tolerant background workers.
- **p95 (95th percentile)**: Standard industry benchmark for rightsizing production web services. Filters out anomalous spikes while capturing regular peak traffic.
- **p99 (99th percentile)**: Captures extreme peak usage, reserved for mission-critical workloads with strict latency SLAs.
- **Max Peak**: The absolute recorded maximum utilization over the evaluation window.

## Calculation Formulas

### 1. Recommended Requests

Given target percentile metric $U_{\text{target}}$ and configured headroom buffer $B$:

$$\text{Request}_{\text{CPU}} = \max\left( U_{\text{CPU}} \times (1 + B_{\text{CPU}}), \text{Floor}_{\text{CPU}} \right)$$

$$\text{Request}_{\text{RAM}} = \max\left( U_{\text{RAM}} \times (1 + B_{\text{RAM}}), \text{Floor}_{\text{RAM}} \right)$$

### 2. OOMKill Crash Protection

If a container has recorded one or more OOMKilled events in its status history:

$$B_{\text{RAM, adjusted}} = B_{\text{RAM}} + B_{\text{OOMKill}}$$

Where $B_{\text{OOMKill}}$ defaults to 0.40 (+40% additional memory headroom). This guarantees that crash-prone services receive expanded memory allocation.

### 3. Recommended Limits

For CPU:
- Burstable profile: $\text{Limit}_{\text{CPU}} = \max\left(\text{Request}_{\text{CPU}} \times 1.5, \text{Peak}_{\text{CPU}} \times 1.1\right)$
- Guaranteed profile: $\text{Limit}_{\text{CPU}} = \text{Request}_{\text{CPU}}$

For Memory:
- Burstable profile: $\text{Limit}_{\text{RAM}} = \text{Request}_{\text{RAM}} \times 1.25$
- Guaranteed profile: $\text{Limit}_{\text{RAM}} = \text{Request}_{\text{RAM}}$

### 4. Dollar Waste & Financial Impact

For a workload with $R$ replicas, current request $Req$, recommended request $Rec$, and hourly rate $P$:

$$\Delta\text{CPU} = Req_{\text{CPU}} - Rec_{\text{CPU}}$$
$$\Delta\text{RAM} = Req_{\text{RAM}} - Rec_{\text{RAM}}$$

$$\text{Monthly Savings} = 730 \times R \times \left( \Delta\text{CPU} \times P_{\text{vCPU}} + \Delta\text{RAM} \times P_{\text{GB}} \right)$$

$$\text{Waste Percentage} = \frac{\text{Current Cost} - \text{Recommended Cost}}{\text{Current Cost}} \times 100\%$$
