"""Unit tests for pricing loaders and FinOps cost calculations."""

from kubetrim.core.cost import (
    calculate_cost_breakdown,
    calculate_monthly_cost,
    load_pricing_model,
)


def test_load_builtin_pricing():
    aws = load_pricing_model("aws")
    assert aws.provider == "aws"
    assert aws.rates.cpu_per_vcpu_hour > 0
    assert aws.rates.memory_per_gb_hour > 0

    gcp = load_pricing_model("gcp")
    assert gcp.provider == "gcp"

    azure = load_pricing_model("azure")
    assert azure.provider == "azure"

    baremetal = load_pricing_model("baremetal")
    assert baremetal.provider == "baremetal"


def test_calculate_monthly_cost():
    aws = load_pricing_model("aws")
    # 1 vCPU, 1 GB RAM (1024 MB), 1 replica for 730 hours
    cost = calculate_monthly_cost(cpu_cores=1.0, memory_mb=1024.0, pricing=aws, replicas=1)
    # (0.04048 + 0.004445) * 730 = 0.044925 * 730 ~= 32.80
    assert 30.0 < cost < 35.0

    # 4 replicas
    cost_4x = calculate_monthly_cost(cpu_cores=1.0, memory_mb=1024.0, pricing=aws, replicas=4)
    assert abs(cost_4x - (cost * 4)) < 0.05

    # Zero replicas
    assert calculate_monthly_cost(1.0, 1024.0, aws, replicas=0) == 0.0


def test_calculate_cost_breakdown():
    aws = load_pricing_model("aws")
    # Current: 2 cores, 4096 MB (4 GB)
    # Rec: 0.5 cores, 1024 MB (1 GB)
    curr, recc, savings, pct = calculate_cost_breakdown(
        current_cpu_cores=2.0,
        current_memory_mb=4096.0,
        recommended_cpu_cores=0.5,
        recommended_memory_mb=1024.0,
        pricing=aws,
        replicas=2,
    )
    assert curr > recc
    assert savings > 0.0
    assert 60.0 < pct < 85.0
