"""Unit tests for Prometheus client and query parsing."""

from unittest.mock import MagicMock, patch
from kubetrim.core.models import (
    ContainerResources,
    ContainerSpec,
    ResourceLimits,
    ResourceRequests,
    WorkloadKind,
    WorkloadSpec,
)
from kubetrim.k8s.prometheus import PrometheusClient


def test_prometheus_check_health():
    client = PrometheusClient("http://fake-prom:9090")
    with patch("httpx.Client.get") as mock_get:
        mock_get.return_value = MagicMock(status_code=200)
        assert client.check_health() is True

        mock_get.return_value = MagicMock(status_code=500)
        assert client.check_health() is False


def test_prometheus_query_instant_success():
    client = PrometheusClient("http://fake-prom:9090")
    with patch("httpx.Client.get") as mock_get:
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "status": "success",
                "data": {"result": [{"value": [1600000000, "0.145"]}]},
            },
        )
        res = client.query_instant("up")
        assert res is not None
        assert len(res) == 1
        assert res[0]["value"][1] == "0.145"


def test_prometheus_get_workload_metrics():
    client = PrometheusClient("http://fake-prom:9090")
    workload = WorkloadSpec(
        namespace="prod",
        name="web",
        kind=WorkloadKind.DEPLOYMENT,
        replicas=2,
        containers=[
            ContainerSpec(
                name="web-app",
                resources=ContainerResources(
                    requests=ResourceRequests(cpu="1", memory="1Gi"),
                    limits=ResourceLimits(cpu="2", memory="2Gi"),
                ),
            )
        ],
    )

    with patch.object(client, "_query_scalar") as mock_scalar:
        # Mocking returns for cpu (p50, p90, p95, p99, peak, avg) and mem (p50, p90, p95, p99, peak, avg) and oom
        mock_scalar.side_effect = [
            0.05, 0.10, 0.12, 0.18, 0.25, 0.08,  # cpu
            200 * 1024 * 1024, 400 * 1024 * 1024, 450 * 1024 * 1024, 600 * 1024 * 1024, 800 * 1024 * 1024, 300 * 1024 * 1024,  # mem
            1,  # oomkill
        ]

        metrics = client.get_workload_metrics(workload)
        assert metrics is not None
        assert metrics.workload_name == "web"
        assert len(metrics.containers) == 1
        c = metrics.containers[0]
        assert c.cpu.p95 == 0.12
        assert c.memory_mb.p95 == 450.0
        assert c.oomkill_count == 1
