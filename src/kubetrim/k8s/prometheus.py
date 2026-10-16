"""Prometheus historical metrics client for PromQL quantile and peak evaluation."""

from __future__ import annotations

import logging
from typing import Dict, List, Optional
import httpx

from kubetrim.core.models import (
    ContainerUsageMetrics,
    MetricPercentiles,
    WorkloadKind,
    WorkloadMetrics,
    WorkloadSpec,
)

logger = logging.getLogger("kubetrim.prometheus")


class PrometheusClient:
    """Queries Prometheus or Thanos for historical container resource utilization."""

    def __init__(
        self,
        endpoint_url: str = "http://localhost:9090",
        timeout: float = 10.0,
        headers: Optional[Dict[str, str]] = None,
    ):
        self.endpoint_url = endpoint_url.rstrip("/")
        self.timeout = timeout
        self.headers = headers or {}

    def query_instant(self, query: str) -> Optional[List[Dict]]:
        """Executes an instant PromQL query against /api/v1/query."""
        url = f"{self.endpoint_url}/api/v1/query"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(url, params={"query": query}, headers=self.headers)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("status") == "success":
                        return data.get("data", {}).get("result", [])
                logger.debug(f"Prometheus query failed with code {resp.status_code}: {resp.text}")
                return None
        except Exception as e:
            logger.debug(f"Prometheus connection error for {url}: {e}")
            return None

    def check_health(self) -> bool:
        """Verifies if Prometheus endpoint is reachable."""
        try:
            with httpx.Client(timeout=3.0) as client:
                resp = client.get(f"{self.endpoint_url}/-/ready", headers=self.headers)
                return resp.status_code == 200
        except Exception:
            return False

    def get_workload_metrics(
        self,
        workload: WorkloadSpec,
        window: str = "14d",
    ) -> Optional[WorkloadMetrics]:
        """Queries historical p50, p90, p95, p99, peak CPU and memory for all workload containers."""
        ns = workload.namespace
        pod_prefix = workload.name
        container_metrics: List[ContainerUsageMetrics] = []

        for container in workload.containers:
            c_name = container.name

            # 1. CPU Quantiles & Peak (in cores)
            cpu_p50 = self._query_scalar(
                f'quantile_over_time(0.50, rate(container_cpu_usage_seconds_total{{container="{c_name}",namespace="{ns}",pod=~"{pod_prefix}.*"}}[5m])[{window}:5m])'
            )
            cpu_p90 = self._query_scalar(
                f'quantile_over_time(0.90, rate(container_cpu_usage_seconds_total{{container="{c_name}",namespace="{ns}",pod=~"{pod_prefix}.*"}}[5m])[{window}:5m])'
            )
            cpu_p95 = self._query_scalar(
                f'quantile_over_time(0.95, rate(container_cpu_usage_seconds_total{{container="{c_name}",namespace="{ns}",pod=~"{pod_prefix}.*"}}[5m])[{window}:5m])'
            )
            cpu_p99 = self._query_scalar(
                f'quantile_over_time(0.99, rate(container_cpu_usage_seconds_total{{container="{c_name}",namespace="{ns}",pod=~"{pod_prefix}.*"}}[5m])[{window}:5m])'
            )
            cpu_peak = self._query_scalar(
                f'max_over_time(rate(container_cpu_usage_seconds_total{{container="{c_name}",namespace="{ns}",pod=~"{pod_prefix}.*"}}[5m])[{window}:5m])'
            )
            cpu_avg = self._query_scalar(
                f'avg_over_time(rate(container_cpu_usage_seconds_total{{container="{c_name}",namespace="{ns}",pod=~"{pod_prefix}.*"}}[5m])[{window}:5m])'
            )

            # 2. Memory Working Set Bytes (converted to MB)
            mem_p50_bytes = self._query_scalar(
                f'quantile_over_time(0.50, container_memory_working_set_bytes{{container="{c_name}",namespace="{ns}",pod=~"{pod_prefix}.*"}}[{window}:5m])'
            )
            mem_p90_bytes = self._query_scalar(
                f'quantile_over_time(0.90, container_memory_working_set_bytes{{container="{c_name}",namespace="{ns}",pod=~"{pod_prefix}.*"}}[{window}:5m])'
            )
            mem_p95_bytes = self._query_scalar(
                f'quantile_over_time(0.95, container_memory_working_set_bytes{{container="{c_name}",namespace="{ns}",pod=~"{pod_prefix}.*"}}[{window}:5m])'
            )
            mem_p99_bytes = self._query_scalar(
                f'quantile_over_time(0.99, container_memory_working_set_bytes{{container="{c_name}",namespace="{ns}",pod=~"{pod_prefix}.*"}}[{window}:5m])'
            )
            mem_peak_bytes = self._query_scalar(
                f'max_over_time(container_memory_working_set_bytes{{container="{c_name}",namespace="{ns}",pod=~"{pod_prefix}.*"}}[{window}:5m])'
            )
            mem_avg_bytes = self._query_scalar(
                f'avg_over_time(container_memory_working_set_bytes{{container="{c_name}",namespace="{ns}",pod=~"{pod_prefix}.*"}}[{window}:5m])'
            )

            # 3. OOMKill Detection
            oom_count_val = self._query_scalar(
                f'sum(kube_pod_container_status_last_terminated_reason{{reason="OOMKilled",namespace="{ns}",container="{c_name}"}})'
            )
            oom_count = int(oom_count_val) if oom_count_val is not None else 0

            # If no data returned from Prometheus, return None to trigger fallback
            if cpu_p95 is None and mem_p95_bytes is None:
                return None

            to_mb = 1.0 / (1024.0 * 1024.0)

            container_metrics.append(
                ContainerUsageMetrics(
                    container_name=c_name,
                    cpu=MetricPercentiles(
                        p50=round(cpu_p50 or 0.0, 4),
                        p90=round(cpu_p90 or 0.0, 4),
                        p95=round(cpu_p95 or 0.0, 4),
                        p99=round(cpu_p99 or 0.0, 4),
                        max_peak=round(cpu_peak or 0.0, 4),
                        avg=round(cpu_avg or 0.0, 4),
                    ),
                    memory_mb=MetricPercentiles(
                        p50=round((mem_p50_bytes or 0.0) * to_mb, 1),
                        p90=round((mem_p90_bytes or 0.0) * to_mb, 1),
                        p95=round((mem_p95_bytes or 0.0) * to_mb, 1),
                        p99=round((mem_p99_bytes or 0.0) * to_mb, 1),
                        max_peak=round((mem_peak_bytes or 0.0) * to_mb, 1),
                        avg=round((mem_avg_bytes or 0.0) * to_mb, 1),
                    ),
                    oomkill_count=oom_count,
                )
            )

        return WorkloadMetrics(
            namespace=ns,
            workload_name=workload.name,
            workload_kind=workload.kind,
            containers=container_metrics,
            evaluation_window=window,
            source="prometheus",
        )

    def _query_scalar(self, query: str) -> Optional[float]:
        """Runs instant query and extracts first float value from results."""
        results = self.query_instant(query)
        if not results:
            return None
        try:
            val_str = results[0]["value"][1]
            return float(val_str)
        except (KeyError, IndexError, ValueError):
            return None
