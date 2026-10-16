"""Rightsizing advisor, HPA conflict detection, Spot arbitrage, and safety headroom engine."""

from __future__ import annotations

from typing import List, Optional
from kubetrim.core.binpack import NodeBinPackingSimulator
from kubetrim.core.config import RightsizingProfile
from kubetrim.core.cost import PricingModel, calculate_cost_breakdown
from kubetrim.core.models import (
    ClusterSummary,
    ContainerRecommendation,
    ContainerSpec,
    ContainerUsageMetrics,
    HPAWarning,
    ResourceQuantity,
    SpotRecommendation,
    WorkloadKind,
    WorkloadMetrics,
    WorkloadRecommendation,
    WorkloadSpec,
)


class RightsizingAdvisor:
    """Analyzes workload specifications, metrics, HPAs, and nodes to generate actionable FinOps guidance."""

    def __init__(self, profile: RightsizingProfile, pricing: PricingModel):
        self.profile = profile
        self.pricing = pricing

    def _get_percentile_value(self, metrics: ContainerUsageMetrics, resource: str) -> float:
        """Extracts the target percentile value for CPU or memory."""
        target_perc = self.profile.target_percentile
        percentiles = metrics.cpu if resource == "cpu" else metrics.memory_mb

        if target_perc >= 0.99:
            val = percentiles.p99 or percentiles.p95 or percentiles.max_peak
        elif target_perc >= 0.95:
            val = percentiles.p95 or percentiles.p90 or percentiles.p99
        elif target_perc >= 0.90:
            val = percentiles.p90 or percentiles.p50 or percentiles.p95
        else:
            val = percentiles.p50 or percentiles.avg
        return max(0.0, float(val))

    def advise_container(
        self,
        container_spec: ContainerSpec,
        container_metrics: Optional[ContainerUsageMetrics],
        replicas: int = 1,
    ) -> ContainerRecommendation:
        """Generates a rightsizing recommendation for a single container."""
        curr_req_cpu = container_spec.resources.requests.cpu_cores
        curr_req_mem = container_spec.resources.requests.memory_mb
        curr_lim_cpu = container_spec.resources.limits.cpu_cores
        curr_lim_mem = container_spec.resources.limits.memory_mb

        oomkill_detected = False
        action_notes = []

        if container_metrics is not None:
            observed_cpu = self._get_percentile_value(container_metrics, "cpu")
            rec_cpu_raw = observed_cpu * (1.0 + self.profile.cpu_headroom_buffer)
            rec_cpu = max(rec_cpu_raw, self.profile.min_cpu_cores)

            observed_mem = self._get_percentile_value(container_metrics, "memory")
            mem_buffer = self.profile.memory_headroom_buffer

            if container_metrics.oomkill_count > 0:
                oomkill_detected = True
                mem_buffer += self.profile.oomkill_extra_buffer
                action_notes.append(
                    f"OOMKill detected ({container_metrics.oomkill_count}x): memory buffer increased by +{int(self.profile.oomkill_extra_buffer * 100)}%"
                )

            rec_mem_raw = observed_mem * (1.0 + mem_buffer)
            rec_mem = max(rec_mem_raw, self.profile.min_memory_mb)

            if self.profile.qos_class_preference.lower() == "guaranteed":
                lim_cpu = rec_cpu
                lim_mem = rec_mem
            else:
                peak_cpu = container_metrics.cpu.max_peak or observed_cpu
                peak_mem = container_metrics.memory_mb.max_peak or observed_mem
                lim_cpu = max(rec_cpu * self.profile.limit_cpu_multiplier, peak_cpu * 1.10)
                lim_mem = max(rec_mem * self.profile.limit_memory_multiplier, peak_mem * 1.15)
        else:
            rec_cpu = max(curr_req_cpu, self.profile.min_cpu_cores) if curr_req_cpu > 0 else self.profile.min_cpu_cores
            rec_mem = max(curr_req_mem, self.profile.min_memory_mb) if curr_req_mem > 0 else self.profile.min_memory_mb
            lim_cpu = curr_lim_cpu if curr_lim_cpu > 0 else rec_cpu * self.profile.limit_cpu_multiplier
            lim_mem = curr_lim_mem if curr_lim_mem > 0 else rec_mem * self.profile.limit_memory_multiplier
            action_notes.append("No historical metrics found; using fallback safety floor")

        str_rec_req_cpu = ResourceQuantity.format_cpu(rec_cpu)
        str_rec_req_mem = ResourceQuantity.format_memory(rec_mem)
        str_rec_lim_cpu = ResourceQuantity.format_cpu(lim_cpu)
        str_rec_lim_mem = ResourceQuantity.format_memory(lim_mem)

        delta_cpu = max(0.0, curr_req_cpu - rec_cpu)
        delta_mem = max(0.0, curr_req_mem - rec_mem)

        curr_cost, rec_cost, savings, pct = calculate_cost_breakdown(
            curr_req_cpu, curr_req_mem, rec_cpu, rec_mem, self.pricing, replicas=replicas
        )

        if savings > 0.0:
            action_notes.append(f"Save ${savings:.2f}/mo ({pct:.1f}% reduction)")
        elif curr_req_cpu == 0 and curr_req_mem == 0:
            action_notes.append("Workload unconstrained; recommendations establish initial requests")

        return ContainerRecommendation(
            container_name=container_spec.name,
            current_request_cpu=ResourceQuantity.format_cpu(curr_req_cpu),
            current_request_memory=ResourceQuantity.format_memory(curr_req_mem),
            current_limit_cpu=ResourceQuantity.format_cpu(curr_lim_cpu) if curr_lim_cpu > 0 else "unlimited",
            current_limit_memory=ResourceQuantity.format_memory(curr_lim_mem) if curr_lim_mem > 0 else "unlimited",
            recommended_request_cpu=str_rec_req_cpu,
            recommended_request_memory=str_rec_req_mem,
            recommended_limit_cpu=str_rec_lim_cpu,
            recommended_limit_memory=str_rec_lim_mem,
            delta_cpu_cores=round(delta_cpu, 3),
            delta_memory_mb=round(delta_mem, 1),
            current_monthly_cost=curr_cost,
            recommended_monthly_cost=rec_cost,
            monthly_savings=savings,
            savings_pct=pct,
            oomkill_detected=oomkill_detected,
            action_note="; ".join(action_notes),
        )

    def _evaluate_hpa_conflict(
        self,
        workload: WorkloadSpec,
        container_recs: List[ContainerRecommendation],
    ) -> Optional[HPAWarning]:
        """Detects if rightsizing requests will alter HPA utilization trigger points."""
        if not workload.hpa:
            return None

        hpa = workload.hpa
        target_pct = hpa.target_cpu_utilization_pct or 80

        curr_cpu_sum = sum(ResourceQuantity.parse_cpu(c.current_request_cpu) for c in container_recs)
        rec_cpu_sum = sum(ResourceQuantity.parse_cpu(c.recommended_request_cpu) for c in container_recs)

        if curr_cpu_sum <= 0 or rec_cpu_sum <= 0:
            return None

        orig_trigger = curr_cpu_sum * (target_pct / 100.0)
        new_trigger = rec_cpu_sum * (target_pct / 100.0)

        if orig_trigger > new_trigger * 1.25:
            suggested_pct = min(95, int(round((orig_trigger / rec_cpu_sum) * 100.0)))
            msg = (
                f"HPA Conflict: lowering requests shifts trigger from {orig_trigger:.2f} cores to {new_trigger:.2f} cores. "
                f"Consider raising HPA target to {suggested_pct}% or adjusting minReplicas."
            )
            return HPAWarning(
                has_hpa=True,
                original_target_pct=target_pct,
                original_trigger_cpu_cores=round(orig_trigger, 3),
                rightsized_trigger_cpu_cores=round(new_trigger, 3),
                suggested_target_pct=suggested_pct,
                warning_message=msg,
            )

        return HPAWarning(
            has_hpa=True,
            original_target_pct=target_pct,
            original_trigger_cpu_cores=round(orig_trigger, 3),
            rightsized_trigger_cpu_cores=round(new_trigger, 3),
            suggested_target_pct=target_pct,
            warning_message="HPA scaling targets aligned.",
        )

    def _evaluate_spot_recommendation(
        self,
        workload: WorkloadSpec,
        rec_monthly_cost: float,
    ) -> Optional[SpotRecommendation]:
        """Assesses disruption tolerance for 65% Spot instance arbitrage."""
        if workload.kind != WorkloadKind.DEPLOYMENT:
            return SpotRecommendation(
                eligible_for_spot=False,
                has_pdb=workload.has_pdb,
                disruption_tolerance_score=10,
                reason=f"Stateful workloads ({workload.kind.value}) not recommended for Spot evictions.",
            )

        if workload.replicas < 2:
            return SpotRecommendation(
                eligible_for_spot=False,
                has_pdb=workload.has_pdb,
                disruption_tolerance_score=25,
                reason="Single-replica workloads risk downtime during node eviction.",
            )

        spot_cost = round(rec_monthly_cost * 0.35, 2)
        additional_savings = round(rec_monthly_cost - spot_cost, 2)
        score = 95 if workload.has_pdb else 75

        return SpotRecommendation(
            eligible_for_spot=True,
            has_pdb=workload.has_pdb,
            disruption_tolerance_score=score,
            current_on_demand_monthly_cost=rec_monthly_cost,
            potential_spot_monthly_cost=spot_cost,
            additional_spot_savings=additional_savings,
            reason=f"Multi-replica stateless deployment. Spot migration yields extra ${additional_savings:.2f}/mo (65% off).",
        )

    def advise_workload(
        self,
        workload: WorkloadSpec,
        metrics: Optional[WorkloadMetrics] = None,
    ) -> WorkloadRecommendation:
        """Generates rightsizing recommendations, HPA conflict checks, and Spot advice for a workload."""
        container_recs: List[ContainerRecommendation] = []
        metrics_by_container = {m.container_name: m for m in (metrics.containers if metrics else [])}

        total_curr_cost = 0.0
        total_rec_cost = 0.0
        total_savings = 0.0
        oomkill_flag = False

        for container in workload.containers:
            c_metrics = metrics_by_container.get(container.name)
            rec = self.advise_container(container, c_metrics, replicas=workload.replicas)
            container_recs.append(rec)
            total_curr_cost += rec.current_monthly_cost
            total_rec_cost += rec.recommended_monthly_cost
            total_savings += rec.monthly_savings
            if rec.oomkill_detected:
                oomkill_flag = True

        total_curr_cost = round(total_curr_cost, 2)
        total_rec_cost = round(total_rec_cost, 2)
        total_savings = round(total_savings, 2)
        savings_pct = round((total_savings / total_curr_cost * 100.0) if total_curr_cost > 0 else 0.0, 1)

        hpa_warn = self._evaluate_hpa_conflict(workload, container_recs)
        spot_rec = self._evaluate_spot_recommendation(workload, total_rec_cost)

        return WorkloadRecommendation(
            namespace=workload.namespace,
            workload_name=workload.name,
            workload_kind=workload.kind,
            replicas=workload.replicas,
            containers=container_recs,
            total_current_monthly_cost=total_curr_cost,
            total_recommended_monthly_cost=total_rec_cost,
            total_monthly_savings=total_savings,
            savings_pct=savings_pct,
            oomkill_detected=oomkill_flag,
            manifest_path=workload.manifest_path,
            hpa_warning=hpa_warn,
            spot_recommendation=spot_rec,
        )

    def generate_cluster_summary(
        self,
        recommendations: List[WorkloadRecommendation],
    ) -> ClusterSummary:
        """Aggregates workload recommendations, simulates node bin-packing, and computes cluster FinOps metrics."""
        total_workloads = len(recommendations)
        total_containers = sum(len(w.containers) for w in recommendations)
        total_replicas = sum(w.replicas for w in recommendations)

        total_current_cost = round(sum(w.total_current_monthly_cost for w in recommendations), 2)
        total_rec_cost = round(sum(w.total_recommended_monthly_cost for w in recommendations), 2)
        total_savings = round(sum(w.total_monthly_savings for w in recommendations), 2)
        savings_pct = round((total_savings / total_current_cost * 100.0) if total_current_cost > 0 else 0.0, 1)
        annual_savings = round(total_savings * 12.0, 2)

        # Total potential Spot savings
        total_spot_savings = round(
            sum(
                w.spot_recommendation.additional_spot_savings
                for w in recommendations
                if w.spot_recommendation and w.spot_recommendation.eligible_for_spot
            ),
            2,
        )

        # Run Node Bin-Packing Simulation
        binpack_sim = NodeBinPackingSimulator()
        binpack_res = binpack_sim.simulate(recommendations)

        return ClusterSummary(
            total_workloads=total_workloads,
            total_containers=total_containers,
            total_replicas=total_replicas,
            total_current_monthly_cost=total_current_cost,
            total_recommended_monthly_cost=total_rec_cost,
            total_monthly_savings=total_savings,
            annual_savings=annual_savings,
            total_savings_pct=savings_pct,
            provider=self.pricing.provider,
            region=self.pricing.region,
            profile_name=self.profile.name,
            recommendations=recommendations,
            bin_packing=binpack_res,
            total_spot_potential_savings=total_spot_savings,
        )
