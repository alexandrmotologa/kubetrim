"""Unit tests for resource parsing and core models."""

import pytest
from kubetrim.core.models import (
    ContainerResources,
    ContainerSpec,
    ResourceLimits,
    ResourceQuantity,
    ResourceRequests,
    WorkloadKind,
    WorkloadSpec,
)


def test_parse_cpu():
    assert ResourceQuantity.parse_cpu("500m") == 0.5
    assert ResourceQuantity.parse_cpu("2000m") == 2.0
    assert ResourceQuantity.parse_cpu("1") == 1.0
    assert ResourceQuantity.parse_cpu("0.25") == 0.25
    assert ResourceQuantity.parse_cpu(1.5) == 1.5
    assert ResourceQuantity.parse_cpu(None) == 0.0
    assert ResourceQuantity.parse_cpu("") == 0.0


def test_format_cpu():
    assert ResourceQuantity.format_cpu(0.5) == "500m"
    assert ResourceQuantity.format_cpu(0.048) == "48m"
    assert ResourceQuantity.format_cpu(1.0) == "1"
    assert ResourceQuantity.format_cpu(2.0) == "2"
    assert ResourceQuantity.format_cpu(0.0) == "10m"


def test_parse_memory_bytes_and_mb():
    # 1024 bytes = 1 KiB
    assert ResourceQuantity.parse_memory_bytes("1Ki") == 1024
    assert ResourceQuantity.parse_memory_mb("1024Ki") == 1.0
    assert ResourceQuantity.parse_memory_mb("256Mi") == 256.0
    assert ResourceQuantity.parse_memory_mb("1Gi") == 1024.0
    assert ResourceQuantity.parse_memory_mb("2Gi") == 2048.0
    assert ResourceQuantity.parse_memory_mb(None) == 0.0
    assert ResourceQuantity.parse_memory_mb("") == 0.0


def test_format_memory():
    assert ResourceQuantity.format_memory(256.0) == "256Mi"
    assert ResourceQuantity.format_memory(1024.0) == "1Gi"
    assert ResourceQuantity.format_memory(2048.0) == "2Gi"
    assert ResourceQuantity.format_memory(1500.0) == "1500Mi"
    assert ResourceQuantity.format_memory(0.0) == "32Mi"


def test_workload_spec_creation():
    spec = WorkloadSpec(
        namespace="prod",
        name="web",
        kind=WorkloadKind.DEPLOYMENT,
        replicas=3,
        containers=[
            ContainerSpec(
                name="app",
                image="nginx:alpine",
                resources=ContainerResources(
                    requests=ResourceRequests(cpu="200m", memory="256Mi"),
                    limits=ResourceLimits(cpu="500m", memory="512Mi"),
                ),
            )
        ],
    )
    assert spec.replicas == 3
    assert spec.containers[0].resources.requests.cpu_cores == 0.2
    assert spec.containers[0].resources.requests.memory_mb == 256.0
    assert spec.containers[0].resources.limits.cpu_cores == 0.5
    assert spec.containers[0].resources.limits.memory_mb == 512.0
