"""Synthetic cluster data generator for local demonstrations and testing."""

from __future__ import annotations

from typing import List, Tuple
from kubetrim.core.models import (
    ContainerResources,
    ContainerSpec,
    ContainerUsageMetrics,
    HPAConfig,
    MetricPercentiles,
    ResourceLimits,
    ResourceRequests,
    WorkloadKind,
    WorkloadMetrics,
    WorkloadSpec,
)


def get_synthetic_cluster() -> List[Tuple[WorkloadSpec, WorkloadMetrics]]:
    """Generates a realistic multi-namespace production cluster dataset with over-provisioned workloads."""
    data = [
        # 1. Critical E-Commerce Service (Heavily over-provisioned, with HPA active)
        {
            "namespace": "production",
            "name": "checkout-service",
            "kind": WorkloadKind.DEPLOYMENT,
            "replicas": 4,
            "container": "checkout-api",
            "req_cpu": "2000m",
            "req_mem": "4Gi",
            "lim_cpu": "4000m",
            "lim_mem": "8Gi",
            "p50_cpu": 0.08,
            "p90_cpu": 0.14,
            "p95_cpu": 0.18,
            "p99_cpu": 0.28,
            "peak_cpu": 0.45,
            "p50_mem": 420.0,
            "p90_mem": 560.0,
            "p95_mem": 620.0,
            "p99_mem": 780.0,
            "peak_mem": 950.0,
            "oomkill": 0,
            "hpa": HPAConfig(min_replicas=2, max_replicas=8, current_replicas=4, target_cpu_utilization_pct=80),
            "has_pdb": True,
        },
        # 2. Payment Gateway (Eligible for Spot Arbitrage, with PDB)
        {
            "namespace": "production",
            "name": "payment-gateway",
            "kind": WorkloadKind.DEPLOYMENT,
            "replicas": 3,
            "container": "gateway",
            "req_cpu": "1500m",
            "req_mem": "2Gi",
            "lim_cpu": "3000m",
            "lim_mem": "4Gi",
            "p50_cpu": 0.11,
            "p90_cpu": 0.18,
            "p95_cpu": 0.22,
            "p99_cpu": 0.35,
            "peak_cpu": 0.52,
            "p50_mem": 310.0,
            "p90_mem": 430.0,
            "p95_mem": 480.0,
            "p99_mem": 600.0,
            "peak_mem": 710.0,
            "oomkill": 0,
            "hpa": None,
            "has_pdb": True,
        },
        # 3. Search Indexer (With OOMKill history to test guard!)
        {
            "namespace": "production",
            "name": "search-indexer",
            "kind": WorkloadKind.STATEFULSET,
            "replicas": 2,
            "container": "indexer",
            "req_cpu": "3000m",
            "req_mem": "8Gi",
            "lim_cpu": "6000m",
            "lim_mem": "12Gi",
            "p50_cpu": 0.25,
            "p90_cpu": 0.38,
            "p95_cpu": 0.45,
            "p99_cpu": 0.85,
            "peak_cpu": 1.40,
            "p50_mem": 1200.0,
            "p90_mem": 1650.0,
            "p95_mem": 1850.0,
            "p99_mem": 2400.0,
            "peak_mem": 3200.0,
            "oomkill": 2,
            "hpa": None,
            "has_pdb": False,
        },
        # 4. User Authentication Service in Staging (Spot Eligible)
        {
            "namespace": "staging",
            "name": "auth-service",
            "kind": WorkloadKind.DEPLOYMENT,
            "replicas": 2,
            "container": "auth",
            "req_cpu": "1000m",
            "req_mem": "2Gi",
            "lim_cpu": "2000m",
            "lim_mem": "4Gi",
            "p50_cpu": 0.04,
            "p90_cpu": 0.07,
            "p95_cpu": 0.08,
            "p99_cpu": 0.12,
            "peak_cpu": 0.18,
            "p50_mem": 160.0,
            "p90_mem": 195.0,
            "p95_mem": 210.0,
            "p99_mem": 250.0,
            "peak_mem": 300.0,
            "oomkill": 0,
            "hpa": None,
            "has_pdb": True,
        },
        # 5. Notification Worker in Staging
        {
            "namespace": "staging",
            "name": "notification-worker",
            "kind": WorkloadKind.DEPLOYMENT,
            "replicas": 1,
            "container": "worker",
            "req_cpu": "500m",
            "req_mem": "1Gi",
            "lim_cpu": "1000m",
            "lim_mem": "2Gi",
            "p50_cpu": 0.02,
            "p90_cpu": 0.035,
            "p95_cpu": 0.04,
            "p99_cpu": 0.06,
            "peak_cpu": 0.09,
            "p50_mem": 110.0,
            "p90_mem": 135.0,
            "p95_mem": 150.0,
            "p99_mem": 180.0,
            "peak_mem": 220.0,
            "oomkill": 0,
            "hpa": None,
            "has_pdb": False,
        },
        # 6. Analytics Heavy Batch Engine
        {
            "namespace": "analytics",
            "name": "spark-streaming-worker",
            "kind": WorkloadKind.DEPLOYMENT,
            "replicas": 5,
            "container": "spark-worker",
            "req_cpu": "4000m",
            "req_mem": "16Gi",
            "lim_cpu": "8000m",
            "lim_mem": "24Gi",
            "p50_cpu": 0.65,
            "p90_cpu": 1.05,
            "p95_cpu": 1.25,
            "p99_cpu": 1.95,
            "peak_cpu": 2.80,
            "p50_mem": 4100.0,
            "p90_mem": 5800.0,
            "p95_mem": 6400.0,
            "p99_mem": 8200.0,
            "peak_mem": 10500.0,
            "oomkill": 0,
            "hpa": None,
            "has_pdb": True,
        },
    ]

    cluster: List[Tuple[WorkloadSpec, WorkloadMetrics]] = []
    for item in data:
        spec = WorkloadSpec(
            namespace=item["namespace"],
            name=item["name"],
            kind=item["kind"],
            replicas=item["replicas"],
            containers=[
                ContainerSpec(
                    name=item["container"],
                    image=f"registry.company.internal/{item['name']}:v1.4.2",
                    resources=ContainerResources(
                        requests=ResourceRequests(
                            cpu=item["req_cpu"],
                            memory=item["req_mem"],
                        ),
                        limits=ResourceLimits(
                            cpu=item["lim_cpu"],
                            memory=item["lim_mem"],
                        ),
                    ),
                )
            ],
            labels={"app": item["name"], "tier": item["namespace"]},
            hpa=item.get("hpa"),
            has_pdb=item.get("has_pdb", False),
        )

        metrics = WorkloadMetrics(
            namespace=item["namespace"],
            workload_name=item["name"],
            workload_kind=item["kind"],
            containers=[
                ContainerUsageMetrics(
                    container_name=item["container"],
                    cpu=MetricPercentiles(
                        p50=item["p50_cpu"],
                        p90=item["p90_cpu"],
                        p95=item["p95_cpu"],
                        p99=item["p99_cpu"],
                        max_peak=item["peak_cpu"],
                        avg=item["p50_cpu"] * 1.1,
                        sample_count=4032,
                    ),
                    memory_mb=MetricPercentiles(
                        p50=item["p50_mem"],
                        p90=item["p90_mem"],
                        p95=item["p95_mem"],
                        p99=item["p99_mem"],
                        max_peak=item["peak_mem"],
                        avg=item["p50_mem"] * 1.1,
                        sample_count=4032,
                    ),
                    oomkill_count=item["oomkill"],
                )
            ],
            evaluation_window="14d",
            source="simulation",
        )
        cluster.append((spec, metrics))

    return cluster
