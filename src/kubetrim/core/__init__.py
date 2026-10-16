"""Core rightsizing models, cost estimation, bin-packing, and recommendation engine."""

from kubetrim.core.advisor import RightsizingAdvisor
from kubetrim.core.binpack import NodeBinPackingSimulator
from kubetrim.core.config import RightsizingProfile, load_profile
from kubetrim.core.cost import PricingModel, calculate_cost_breakdown, calculate_monthly_cost, load_pricing_model
from kubetrim.core.models import (
    BinPackingResult,
    ClusterSummary,
    ContainerRecommendation,
    ContainerSpec,
    ContainerUsageMetrics,
    HPAConfig,
    HPAWarning,
    MetricPercentiles,
    NodeSpec,
    ResourceQuantity,
    SpotRecommendation,
    WorkloadKind,
    WorkloadMetrics,
    WorkloadRecommendation,
    WorkloadSpec,
)

__all__ = [
    "BinPackingResult",
    "ClusterSummary",
    "ContainerRecommendation",
    "ContainerSpec",
    "ContainerUsageMetrics",
    "HPAConfig",
    "HPAWarning",
    "MetricPercentiles",
    "NodeBinPackingSimulator",
    "NodeSpec",
    "PricingModel",
    "ResourceQuantity",
    "RightsizingAdvisor",
    "RightsizingProfile",
    "SpotRecommendation",
    "WorkloadKind",
    "WorkloadMetrics",
    "WorkloadRecommendation",
    "WorkloadSpec",
    "calculate_cost_breakdown",
    "calculate_monthly_cost",
    "load_pricing_model",
    "load_profile",
]
