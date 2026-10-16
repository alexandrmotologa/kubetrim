"""Unit tests for rightsizing advisor and headroom buffer heuristics."""

from kubetrim.core.advisor import RightsizingAdvisor
from kubetrim.core.config import load_profile
from kubetrim.core.cost import load_pricing_model
from kubetrim.core.models import (
    ContainerResources,
    ContainerSpec,
    ContainerUsageMetrics,
    MetricPercentiles,
    ResourceLimits,
    ResourceRequests,
    WorkloadKind,
    WorkloadMetrics,
    WorkloadSpec,
)


def test_advisor_balanced_profile():
    profile = load_profile("balanced")  # +20% buffer on p95
    pricing = load_pricing_model("aws")
    advisor = RightsizingAdvisor(profile, pricing)

    workload = WorkloadSpec(
        namespace="prod",
        name="checkout",
        kind=WorkloadKind.DEPLOYMENT,
        replicas=2,
        containers=[
            ContainerSpec(
                name="api",
                resources=ContainerResources(
                    requests=ResourceRequests(cpu="1000m", memory="2Gi"),
                    limits=ResourceLimits(cpu="2000m", memory="4Gi"),
                ),
            )
        ],
    )

    metrics = WorkloadMetrics(
        namespace="prod",
        workload_name="checkout",
        containers=[
            ContainerUsageMetrics(
                container_name="api",
                cpu=MetricPercentiles(p95=0.20, max_peak=0.35),
                memory_mb=MetricPercentiles(p95=500.0, max_peak=700.0),
                oomkill_count=0,
            )
        ],
    )

    rec = advisor.advise_workload(workload, metrics)
    assert rec.total_monthly_savings > 0
    assert rec.containers[0].recommended_request_cpu == "240m"  # 0.20 * 1.20 = 0.24 -> 240m
    assert rec.containers[0].recommended_request_memory == "600Mi"  # 500 * 1.20 = 600Mi
    assert not rec.oomkill_detected


def test_advisor_oomkill_guard():
    profile = load_profile("balanced")  # normal buffer 0.20, oomkill buffer +0.40 = 0.60
    pricing = load_pricing_model("aws")
    advisor = RightsizingAdvisor(profile, pricing)

    workload = WorkloadSpec(
        namespace="prod",
        name="indexer",
        kind=WorkloadKind.STATEFULSET,
        replicas=1,
        containers=[
            ContainerSpec(
                name="indexer",
                resources=ContainerResources(
                    requests=ResourceRequests(cpu="2000m", memory="4Gi"),
                    limits=ResourceLimits(cpu="4000m", memory="8Gi"),
                ),
            )
        ],
    )

    metrics = WorkloadMetrics(
        namespace="prod",
        workload_name="indexer",
        containers=[
            ContainerUsageMetrics(
                container_name="indexer",
                cpu=MetricPercentiles(p95=0.50, max_peak=0.80),
                memory_mb=MetricPercentiles(p95=1000.0, max_peak=1500.0),
                oomkill_count=3,  # OOMKills detected!
            )
        ],
    )

    rec = advisor.advise_workload(workload, metrics)
    assert rec.oomkill_detected
    assert rec.containers[0].oomkill_detected
    # Memory should have 60% buffer over 1000 MB = 1600 MB
    assert rec.containers[0].recommended_request_memory == "1600Mi"
    assert "OOMKill detected" in rec.containers[0].action_note


def test_advisor_min_floors():
    profile = load_profile("balanced")
    pricing = load_pricing_model("aws")
    advisor = RightsizingAdvisor(profile, pricing)

    workload = WorkloadSpec(
        namespace="test",
        name="tiny",
        kind=WorkloadKind.DEPLOYMENT,
        replicas=1,
        containers=[
            ContainerSpec(
                name="tiny",
                resources=ContainerResources(
                    requests=ResourceRequests(cpu="50m", memory="64Mi"),
                    limits=ResourceLimits(cpu="100m", memory="128Mi"),
                ),
            )
        ],
    )

    # Usage near zero
    metrics = WorkloadMetrics(
        namespace="test",
        workload_name="tiny",
        containers=[
            ContainerUsageMetrics(
                container_name="tiny",
                cpu=MetricPercentiles(p95=0.001, max_peak=0.002),
                memory_mb=MetricPercentiles(p95=5.0, max_peak=10.0),
                oomkill_count=0,
            )
        ],
    )

    rec = advisor.advise_workload(workload, metrics)
    c_rec = rec.containers[0]
    # Should enforce min_cpu_cores (0.02 -> 20m) and min_memory_mb (32Mi)
    assert c_rec.recommended_request_cpu == "20m"
    assert c_rec.recommended_request_memory == "32Mi"
