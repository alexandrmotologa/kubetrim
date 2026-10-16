"""Unit tests for Kubernetes Metrics Server API client."""

from unittest.mock import MagicMock
from kubetrim.core.models import (
    ContainerResources,
    ContainerSpec,
    ResourceLimits,
    ResourceRequests,
    WorkloadKind,
    WorkloadSpec,
)
from kubetrim.k8s.metrics_server import MetricsServerClient


def test_metrics_server_unconnected():
    client = MetricsServerClient(k8s_client=None)
    workload = WorkloadSpec(
        namespace="default",
        name="test-app",
        kind=WorkloadKind.DEPLOYMENT,
        containers=[ContainerSpec(name="app")],
    )
    assert client.get_workload_metrics(workload) is None


def test_metrics_server_scraping():
    mock_k8s = MagicMock()
    mock_k8s.is_connected = True
    mock_custom_api = MagicMock()
    mock_k8s._custom_api = mock_custom_api

    mock_custom_api.list_namespaced_custom_object.return_value = {
        "items": [
            {
                "metadata": {"name": "test-app-7b89f-abcde", "namespace": "prod"},
                "containers": [
                    {"name": "app", "usage": {"cpu": "120m", "memory": "350Mi"}},
                ],
            },
            {
                "metadata": {"name": "test-app-7b89f-vwxyz", "namespace": "prod"},
                "containers": [
                    {"name": "app", "usage": {"cpu": "180m", "memory": "450Mi"}},
                ],
            },
        ]
    }

    client = MetricsServerClient(k8s_client=mock_k8s)
    workload = WorkloadSpec(
        namespace="prod",
        name="test-app",
        kind=WorkloadKind.DEPLOYMENT,
        replicas=2,
        containers=[
            ContainerSpec(
                name="app",
                resources=ContainerResources(
                    requests=ResourceRequests(cpu="1", memory="1Gi"),
                    limits=ResourceLimits(cpu="2", memory="2Gi"),
                ),
            )
        ],
    )

    metrics = client.get_workload_metrics(workload)
    assert metrics is not None
    assert metrics.source == "metrics_server"
    assert len(metrics.containers) == 1
    c = metrics.containers[0]
    assert c.cpu.max_peak == 0.18
    assert c.memory_mb.max_peak == 450.0
    assert c.cpu.sample_count == 2
