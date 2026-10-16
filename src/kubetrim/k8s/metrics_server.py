"""Kubernetes Metrics Server API client for live pod resource usage scraping."""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from kubetrim.core.models import (
    ContainerUsageMetrics,
    MetricPercentiles,
    ResourceQuantity,
    WorkloadMetrics,
    WorkloadSpec,
)

logger = logging.getLogger("kubetrim.metrics_server")


class MetricsServerClient:
    """Queries live container CPU and Memory utilization from Kubernetes Metrics Server API."""

    def __init__(self, k8s_client=None):
        self._k8s = k8s_client

    def get_workload_metrics(self, workload: WorkloadSpec) -> Optional[WorkloadMetrics]:
        """Scrapes live pods associated with the workload from /apis/metrics.k8s.io/v1beta1."""
        if not self._k8s or not self._k8s.is_connected:
            return None

        ns = workload.namespace
        name_prefix = workload.name
        pod_samples: Dict[str, Dict[str, List[float]]] = {}  # container -> {"cpu": [...], "mem": [...]}

        for c in workload.containers:
            pod_samples[c.name] = {"cpu": [], "mem": []}

        try:
            custom_api = self._k8s._custom_api
            resp = custom_api.list_namespaced_custom_object(
                group="metrics.k8s.io",
                version="v1beta1",
                namespace=ns,
                plural="pods",
            )
            items = resp.get("items", [])

            matching_pods = 0
            for item in items:
                pod_name = item.get("metadata", {}).get("name", "")
                if not pod_name.startswith(name_prefix):
                    continue

                matching_pods += 1
                for c in item.get("containers", []):
                    c_name = c.get("name")
                    if c_name not in pod_samples:
                        pod_samples[c_name] = {"cpu": [], "mem": []}

                    usage = c.get("usage", {})
                    cpu_str = usage.get("cpu", "0m")
                    mem_str = usage.get("memory", "0Mi")

                    cpu_cores = ResourceQuantity.parse_cpu(cpu_str)
                    mem_mb = ResourceQuantity.parse_memory_mb(mem_str)

                    pod_samples[c_name]["cpu"].append(cpu_cores)
                    pod_samples[c_name]["mem"].append(mem_mb)

            if matching_pods == 0:
                logger.debug(f"No active metrics pods found for {ns}/{name_prefix}")
                return None

            container_metrics: List[ContainerUsageMetrics] = []
            for container in workload.containers:
                c_name = container.name
                samples = pod_samples.get(c_name, {"cpu": [], "mem": []})
                cpu_vals = samples["cpu"] or [0.0]
                mem_vals = samples["mem"] or [0.0]

                cpu_sorted = sorted(cpu_vals)
                mem_sorted = sorted(mem_vals)

                def percentile(arr: List[float], p: float) -> float:
                    idx = int(round(p * (len(arr) - 1)))
                    return arr[idx]

                container_metrics.append(
                    ContainerUsageMetrics(
                        container_name=c_name,
                        cpu=MetricPercentiles(
                            p50=round(percentile(cpu_sorted, 0.50), 4),
                            p90=round(percentile(cpu_sorted, 0.90), 4),
                            p95=round(percentile(cpu_sorted, 0.95), 4),
                            p99=round(percentile(cpu_sorted, 0.99), 4),
                            max_peak=round(max(cpu_sorted), 4),
                            avg=round(sum(cpu_sorted) / len(cpu_sorted), 4),
                            sample_count=len(cpu_sorted),
                        ),
                        memory_mb=MetricPercentiles(
                            p50=round(percentile(mem_sorted, 0.50), 1),
                            p90=round(percentile(mem_sorted, 0.90), 1),
                            p95=round(percentile(mem_sorted, 0.95), 1),
                            p99=round(percentile(mem_sorted, 0.99), 1),
                            max_peak=round(max(mem_sorted), 1),
                            avg=round(sum(mem_sorted) / len(mem_sorted), 1),
                            sample_count=len(mem_sorted),
                        ),
                        oomkill_count=0,
                    )
                )

            return WorkloadMetrics(
                namespace=ns,
                workload_name=workload.name,
                workload_kind=workload.kind,
                containers=container_metrics,
                evaluation_window="live_metrics_server",
                source="metrics_server",
            )
        except Exception as e:
            logger.debug(f"Metrics server query error: {e}")
            return None
