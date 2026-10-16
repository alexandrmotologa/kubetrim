"""Core data models, resource quantity parsers, HPA, Spot, and Bin-Packing schemas for KubeTrim."""

from __future__ import annotations

import re
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class WorkloadKind(str, Enum):
    DEPLOYMENT = "Deployment"
    STATEFULSET = "StatefulSet"
    DAEMONSET = "DaemonSet"
    JOB = "Job"
    CRONJOB = "CronJob"


class ResourceQuantity:
    """Parses and normalizes Kubernetes CPU and Memory string quantities."""

    @staticmethod
    def parse_cpu(val: Any) -> float:
        """Parses Kubernetes CPU quantity to float cores."""
        if val is None:
            return 0.0
        if isinstance(val, (int, float)):
            return float(val)
        val_str = str(val).strip()
        if not val_str:
            return 0.0
        if val_str.endswith("m"):
            return float(val_str[:-1]) / 1000.0
        if val_str.endswith("u"):
            return float(val_str[:-1]) / 1000000.0
        if val_str.endswith("n"):
            return float(val_str[:-1]) / 1000000000.0
        return float(val_str)

    @staticmethod
    def format_cpu(cores: float) -> str:
        """Formats CPU float cores into standard Kubernetes string."""
        if cores <= 0.0:
            return "10m"
        if cores < 1.0:
            milli = max(1, int(round(cores * 1000.0)))
            return f"{milli}m"
        if cores == int(cores):
            return f"{int(cores)}"
        return f"{int(round(cores * 1000.0))}m"

    @staticmethod
    def parse_memory_bytes(val: Any) -> int:
        """Parses Kubernetes memory quantity string to raw bytes."""
        if val is None:
            return 0
        if isinstance(val, (int, float)):
            return int(val)
        val_str = str(val).strip()
        if not val_str:
            return 0

        multipliers = {
            "Ki": 1024,
            "Mi": 1024**2,
            "Gi": 1024**3,
            "Ti": 1024**4,
            "Pi": 1024**5,
            "k": 1000,
            "M": 1000**2,
            "G": 1000**3,
            "T": 1000**4,
            "P": 1000**5,
            "m": 1,
        }

        match = re.match(r"^([0-9.]+)\s*([A-Za-z]+)?$", val_str)
        if not match:
            try:
                return int(float(val_str))
            except ValueError:
                return 0

        number = float(match.group(1))
        unit = match.group(2)
        if not unit:
            return int(number)
        mult = multipliers.get(unit, 1)
        return int(number * mult)

    @staticmethod
    def parse_memory_mb(val: Any) -> float:
        """Parses Kubernetes memory quantity to Megabytes (MB, 1 MB = 1024*1024 bytes)."""
        bytes_val = ResourceQuantity.parse_memory_bytes(val)
        return bytes_val / (1024.0 * 1024.0)

    @staticmethod
    def format_memory(mb: float) -> str:
        """Formats Megabytes into clean Kubernetes memory string (Mi or Gi)."""
        if mb <= 0:
            return "32Mi"
        if mb >= 1024:
            gi = mb / 1024.0
            if abs(gi - round(gi)) < 0.05:
                return f"{int(round(gi))}Gi"
            return f"{int(round(mb))}Mi"
        return f"{int(round(mb))}Mi"


class ResourceLimits(BaseModel):
    cpu: str = "0m"
    memory: str = "0Mi"

    @property
    def cpu_cores(self) -> float:
        return ResourceQuantity.parse_cpu(self.cpu)

    @property
    def memory_mb(self) -> float:
        return ResourceQuantity.parse_memory_mb(self.memory)


class ResourceRequests(BaseModel):
    cpu: str = "0m"
    memory: str = "0Mi"

    @property
    def cpu_cores(self) -> float:
        return ResourceQuantity.parse_cpu(self.cpu)

    @property
    def memory_mb(self) -> float:
        return ResourceQuantity.parse_memory_mb(self.memory)


class ContainerResources(BaseModel):
    requests: ResourceRequests = Field(default_factory=ResourceRequests)
    limits: ResourceLimits = Field(default_factory=ResourceLimits)


class ContainerSpec(BaseModel):
    name: str
    image: str = ""
    resources: ContainerResources = Field(default_factory=ContainerResources)


class HPAConfig(BaseModel):
    min_replicas: int = 1
    max_replicas: int = 10
    current_replicas: int = 1
    target_cpu_utilization_pct: Optional[int] = None
    target_memory_utilization_pct: Optional[int] = None


class WorkloadSpec(BaseModel):
    namespace: str
    name: str
    kind: WorkloadKind = WorkloadKind.DEPLOYMENT
    replicas: int = 1
    containers: List[ContainerSpec] = Field(default_factory=list)
    labels: Dict[str, str] = Field(default_factory=dict)
    manifest_path: Optional[str] = None
    hpa: Optional[HPAConfig] = None
    has_pdb: bool = False


class MetricPercentiles(BaseModel):
    p50: float = 0.0
    p90: float = 0.0
    p95: float = 0.0
    p99: float = 0.0
    max_peak: float = 0.0
    avg: float = 0.0
    sample_count: int = 0


class ContainerUsageMetrics(BaseModel):
    container_name: str
    cpu: MetricPercentiles = Field(default_factory=MetricPercentiles)
    memory_mb: MetricPercentiles = Field(default_factory=MetricPercentiles)
    oomkill_count: int = 0


class WorkloadMetrics(BaseModel):
    namespace: str
    workload_name: str
    workload_kind: WorkloadKind = WorkloadKind.DEPLOYMENT
    containers: List[ContainerUsageMetrics] = Field(default_factory=list)
    evaluation_window: str = "14d"
    source: str = "prometheus"


class HPAWarning(BaseModel):
    has_hpa: bool = False
    original_target_pct: Optional[int] = None
    original_trigger_cpu_cores: float = 0.0
    rightsized_trigger_cpu_cores: float = 0.0
    suggested_target_pct: Optional[int] = None
    warning_message: str = ""


class SpotRecommendation(BaseModel):
    eligible_for_spot: bool = False
    has_pdb: bool = False
    disruption_tolerance_score: int = 0  # 0 to 100
    current_on_demand_monthly_cost: float = 0.0
    potential_spot_monthly_cost: float = 0.0
    additional_spot_savings: float = 0.0
    reason: str = ""


class ContainerRecommendation(BaseModel):
    container_name: str
    current_request_cpu: str
    current_request_memory: str
    current_limit_cpu: str
    current_limit_memory: str

    recommended_request_cpu: str
    recommended_request_memory: str
    recommended_limit_cpu: str
    recommended_limit_memory: str

    delta_cpu_cores: float
    delta_memory_mb: float

    current_monthly_cost: float
    recommended_monthly_cost: float
    monthly_savings: float
    savings_pct: float

    oomkill_detected: bool = False
    action_note: str = ""


class WorkloadRecommendation(BaseModel):
    namespace: str
    workload_name: str
    workload_kind: WorkloadKind = WorkloadKind.DEPLOYMENT
    replicas: int = 1
    containers: List[ContainerRecommendation] = Field(default_factory=list)

    total_current_monthly_cost: float = 0.0
    total_recommended_monthly_cost: float = 0.0
    total_monthly_savings: float = 0.0
    savings_pct: float = 0.0

    oomkill_detected: bool = False
    manifest_path: Optional[str] = None

    hpa_warning: Optional[HPAWarning] = None
    spot_recommendation: Optional[SpotRecommendation] = None


class NodeSpec(BaseModel):
    name: str
    instance_type: str = "m6i.xlarge"
    allocatable_cpu_cores: float = 4.0
    allocatable_memory_mb: float = 16384.0
    zone: str = "us-east-1a"
    is_spot: bool = False
    hourly_cost: float = 0.192


class BinPackingResult(BaseModel):
    current_node_count: int = 0
    rightsized_node_count: int = 0
    removable_nodes_count: int = 0
    current_monthly_node_spend: float = 0.0
    rightsized_monthly_node_spend: float = 0.0
    net_node_monthly_savings: float = 0.0
    annual_node_savings: float = 0.0
    cpu_utilization_before_pct: float = 0.0
    cpu_utilization_after_pct: float = 0.0
    memory_utilization_before_pct: float = 0.0
    memory_utilization_after_pct: float = 0.0
    nodes_summary: List[Dict[str, Any]] = Field(default_factory=list)


class ClusterSummary(BaseModel):
    total_workloads: int = 0
    total_containers: int = 0
    total_replicas: int = 0
    total_current_monthly_cost: float = 0.0
    total_recommended_monthly_cost: float = 0.0
    total_monthly_savings: float = 0.0
    annual_savings: float = 0.0
    total_savings_pct: float = 0.0

    provider: str = "aws"
    region: str = "us-east-1"
    profile_name: str = "balanced"
    recommendations: List[WorkloadRecommendation] = Field(default_factory=list)

    bin_packing: Optional[BinPackingResult] = None
    total_spot_potential_savings: float = 0.0
