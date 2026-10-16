"""Karpenter & Cluster Autoscaler node bin-packing simulator."""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple
from kubetrim.core.cost import HOURS_PER_MONTH, PricingModel
from kubetrim.core.models import (
    BinPackingResult,
    NodeSpec,
    ResourceQuantity,
    WorkloadRecommendation,
    WorkloadSpec,
)


class NodeBinPackingSimulator:
    """Simulates cluster bin-packing before and after pod rightsizing to calculate real infrastructure node savings."""

    def __init__(
        self,
        default_instance_type: str = "m6i.xlarge",
        node_cpu_cores: float = 4.0,
        node_memory_mb: float = 16384.0,
        node_hourly_cost: float = 0.192,
    ):
        # 10% system reservation buffer (kube-system, daemonsets, OS kernel)
        self.node_cpu_cores = node_cpu_cores * 0.90
        self.node_memory_mb = node_memory_mb * 0.90
        self.node_hourly_cost = node_hourly_cost
        self.instance_type = default_instance_type

    def _pack_items(
        self,
        items: List[Tuple[float, float]],  # List of (cpu_cores, mem_mb)
    ) -> List[Dict[str, float]]:
        """Multi-dimensional First-Fit Decreasing (FFD) bin packing."""
        # Sort items by dominant resource demand descending
        sorted_items = sorted(
            items,
            key=lambda x: max(x[0] / self.node_cpu_cores, x[1] / self.node_memory_mb),
            reverse=True,
        )

        nodes: List[Dict[str, float]] = []

        for cpu, mem in sorted_items:
            placed = False
            for node in nodes:
                if (node["cpu_used"] + cpu <= self.node_cpu_cores) and (
                    node["mem_used"] + mem <= self.node_memory_mb
                ):
                    node["cpu_used"] += cpu
                    node["mem_used"] += mem
                    node["pod_count"] += 1
                    placed = True
                    break

            if not placed:
                nodes.append({
                    "cpu_used": cpu,
                    "mem_used": mem,
                    "pod_count": 1,
                })

        return nodes

    def simulate(
        self,
        recommendations: List[WorkloadRecommendation],
        existing_nodes: Optional[List[NodeSpec]] = None,
    ) -> BinPackingResult:
        """Simulates node requirements and compute node savings."""
        original_pods: List[Tuple[float, float]] = []
        rightsized_pods: List[Tuple[float, float]] = []

        for w in recommendations:
            for _ in range(w.replicas):
                # Sum container requests per pod
                orig_pod_cpu = 0.0
                orig_pod_mem = 0.0
                rec_pod_cpu = 0.0
                rec_pod_mem = 0.0

                for c in w.containers:
                    orig_pod_cpu += ResourceQuantity.parse_cpu(c.current_request_cpu)
                    orig_pod_mem += ResourceQuantity.parse_memory_mb(c.current_request_memory)
                    rec_pod_cpu += ResourceQuantity.parse_cpu(c.recommended_request_cpu)
                    rec_pod_mem += ResourceQuantity.parse_memory_mb(c.recommended_request_memory)

                original_pods.append((orig_pod_cpu, orig_pod_mem))
                rightsized_pods.append((rec_pod_cpu, rec_pod_mem))

        if not original_pods:
            return BinPackingResult()

        nodes_before = self._pack_items(original_pods)
        nodes_after = self._pack_items(rightsized_pods)

        count_before = len(nodes_before)
        count_after = len(nodes_after)
        removable_count = max(0, count_before - count_after)

        cost_before = round(count_before * self.node_hourly_cost * HOURS_PER_MONTH, 2)
        cost_after = round(count_after * self.node_hourly_cost * HOURS_PER_MONTH, 2)
        net_savings = round(cost_before - cost_after, 2)
        annual_savings = round(net_savings * 12.0, 2)

        total_cpu_cap_before = count_before * self.node_cpu_cores
        total_mem_cap_before = count_before * self.node_memory_mb
        total_cpu_used_before = sum(n["cpu_used"] for n in nodes_before)
        total_mem_used_before = sum(n["mem_used"] for n in nodes_before)

        cpu_util_before = round((total_cpu_used_before / total_cpu_cap_before * 100.0) if total_cpu_cap_before > 0 else 0.0, 1)
        mem_util_before = round((total_mem_used_before / total_mem_cap_before * 100.0) if total_mem_cap_before > 0 else 0.0, 1)

        total_cpu_cap_after = count_after * self.node_cpu_cores
        total_mem_cap_after = count_after * self.node_memory_mb
        total_cpu_used_after = sum(n["cpu_used"] for n in nodes_after)
        total_mem_used_after = sum(n["mem_used"] for n in nodes_after)

        cpu_util_after = round((total_cpu_used_after / total_cpu_cap_after * 100.0) if total_cpu_cap_after > 0 else 0.0, 1)
        mem_util_after = round((total_mem_used_after / total_mem_cap_after * 100.0) if total_mem_cap_after > 0 else 0.0, 1)

        nodes_summary = []
        for idx, n in enumerate(nodes_after):
            nodes_summary.append({
                "node_index": idx + 1,
                "instance_type": self.instance_type,
                "cpu_utilization_pct": round(n["cpu_used"] / self.node_cpu_cores * 100.0, 1),
                "mem_utilization_pct": round(n["mem_used"] / self.node_memory_mb * 100.0, 1),
                "pods_scheduled": n["pod_count"],
            })

        return BinPackingResult(
            current_node_count=count_before,
            rightsized_node_count=count_after,
            removable_nodes_count=removable_count,
            current_monthly_node_spend=cost_before,
            rightsized_monthly_node_spend=cost_after,
            net_node_monthly_savings=net_savings,
            annual_node_savings=annual_savings,
            cpu_utilization_before_pct=cpu_util_before,
            cpu_utilization_after_pct=cpu_util_after,
            memory_utilization_before_pct=mem_util_before,
            memory_utilization_after_pct=mem_util_after,
            nodes_summary=nodes_summary,
        )
