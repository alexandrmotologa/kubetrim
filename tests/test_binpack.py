"""Unit tests for Karpenter and Cluster Autoscaler Node Bin-Packing Simulator."""

from kubetrim.core.binpack import NodeBinPackingSimulator
from kubetrim.core.models import (
    ContainerRecommendation,
    WorkloadKind,
    WorkloadRecommendation,
)


def _make_dummy_rec(
    name: str,
    replicas: int,
    curr_cpu: str,
    curr_mem: str,
    rec_cpu: str,
    rec_mem: str,
) -> WorkloadRecommendation:
    c = ContainerRecommendation(
        container_name=name,
        current_request_cpu=curr_cpu,
        current_request_memory=curr_mem,
        current_limit_cpu=curr_cpu,
        current_limit_memory=curr_mem,
        recommended_request_cpu=rec_cpu,
        recommended_request_memory=rec_mem,
        recommended_limit_cpu=rec_cpu,
        recommended_limit_memory=rec_mem,
        delta_cpu_cores=0.0,
        delta_memory_mb=0.0,
        current_monthly_cost=10.0,
        recommended_monthly_cost=5.0,
        monthly_savings=5.0,
        savings_pct=50.0,
    )
    return WorkloadRecommendation(
        namespace="default",
        workload_name=name,
        workload_kind=WorkloadKind.DEPLOYMENT,
        replicas=replicas,
        containers=[c],
        total_current_monthly_cost=10.0 * replicas,
        total_recommended_monthly_cost=5.0 * replicas,
        total_monthly_savings=5.0 * replicas,
        savings_pct=50.0,
    )


def test_binpack_empty_workloads():
    sim = NodeBinPackingSimulator()
    result = sim.simulate([])
    assert result.current_node_count == 0
    assert result.rightsized_node_count == 0
    assert result.removable_nodes_count == 0
    assert result.net_node_monthly_savings == 0.0


def test_binpack_simulation_savings():
    # Node allocatable is 4 cores * 0.90 = 3.6 cores, 16384 MB * 0.90 = 14745.6 MB
    # 12 replicas of 1000m CPU (1.0 core) each -> 12 cores -> requires at least 4 nodes
    # Rightsized to 200m CPU (0.2 core) each -> 2.4 cores -> fits in 1 node!
    recs = [
        _make_dummy_rec(
            name="checkout-worker",
            replicas=12,
            curr_cpu="1000m",
            curr_mem="2048Mi",
            rec_cpu="200m",
            rec_mem="512Mi",
        )
    ]

    sim = NodeBinPackingSimulator(
        default_instance_type="m6i.xlarge",
        node_cpu_cores=4.0,
        node_memory_mb=16384.0,
        node_hourly_cost=0.192,
    )
    result = sim.simulate(recs)

    assert result.current_node_count >= 4
    assert result.rightsized_node_count <= 2
    assert result.removable_nodes_count >= 2
    assert result.net_node_monthly_savings > 0
    assert result.annual_node_savings > 0
    assert result.cpu_utilization_after_pct > 0
    assert len(result.nodes_summary) == result.rightsized_node_count
    assert result.nodes_summary[0]["instance_type"] == "m6i.xlarge"


def test_binpack_custom_node_spec():
    # Test smaller 2-core node
    recs = [
        _make_dummy_rec(
            name="frontend",
            replicas=4,
            curr_cpu="500m",
            curr_mem="1024Mi",
            rec_cpu="100m",
            rec_mem="256Mi",
        )
    ]
    sim = NodeBinPackingSimulator(
        default_instance_type="t3.medium",
        node_cpu_cores=2.0,
        node_memory_mb=4096.0,
        node_hourly_cost=0.0416,
    )
    result = sim.simulate(recs)
    assert result.rightsized_node_count >= 1
    assert result.nodes_summary[0]["instance_type"] == "t3.medium"
