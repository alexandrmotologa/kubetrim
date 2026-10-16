"""Cloud provider pricing catalogs and FinOps cost calculation engine."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Optional, Tuple
from pydantic import BaseModel, Field

HOURS_PER_MONTH: float = 730.0


class PricingRates(BaseModel):
    cpu_per_vcpu_hour: float = Field(ge=0.0)
    memory_per_gb_hour: float = Field(ge=0.0)
    cluster_base_hour: float = Field(default=0.0, ge=0.0)


class PricingModel(BaseModel):
    provider: str
    region: str
    currency: str = "USD"
    rates: PricingRates
    description: str = ""


BUILTIN_PRICING: Dict[str, PricingModel] = {
    "aws": PricingModel(
        provider="aws",
        region="us-east-1",
        currency="USD",
        rates=PricingRates(
            cpu_per_vcpu_hour=0.04048,
            memory_per_gb_hour=0.004445,
            cluster_base_hour=0.10,
        ),
        description="AWS EKS compute allocation rate based on general purpose m6i/c6i and Fargate.",
    ),
    "gcp": PricingModel(
        provider="gcp",
        region="us-central1",
        currency="USD",
        rates=PricingRates(
            cpu_per_vcpu_hour=0.03350,
            memory_per_gb_hour=0.004490,
            cluster_base_hour=0.10,
        ),
        description="GCP GKE compute allocation rate based on E2/N2 standard instances.",
    ),
    "azure": PricingModel(
        provider="azure",
        region="eastus",
        currency="USD",
        rates=PricingRates(
            cpu_per_vcpu_hour=0.03800,
            memory_per_gb_hour=0.005100,
            cluster_base_hour=0.10,
        ),
        description="Azure AKS compute allocation rate based on D-series v5 instances.",
    ),
    "baremetal": PricingModel(
        provider="baremetal",
        region="default",
        currency="USD",
        rates=PricingRates(
            cpu_per_vcpu_hour=0.02000,
            memory_per_gb_hour=0.002500,
            cluster_base_hour=0.0,
        ),
        description="On-premise or bare-metal internal compute amortization rate.",
    ),
}


def load_pricing_model(
    provider: str = "aws",
    region: Optional[str] = None,
    custom_path: Optional[str] = None,
) -> PricingModel:
    """Loads a cloud pricing model from file, configs/pricing/, or built-in catalog."""
    if custom_path:
        path = Path(custom_path)
        if path.is_file():
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return PricingModel(**data)

    clean_provider = provider.strip().lower()
    
    # Try looking in configs/pricing/
    config_dir = Path("configs") / "pricing"
    if config_dir.is_dir():
        for file in config_dir.glob("*.json"):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if data.get("provider", "").lower() == clean_provider:
                        if not region or data.get("region", "").lower() == region.strip().lower():
                            return PricingModel(**data)
            except Exception:
                continue

    if clean_provider in BUILTIN_PRICING:
        model = BUILTIN_PRICING[clean_provider]
        if region:
            return PricingModel(
                provider=model.provider,
                region=region,
                currency=model.currency,
                rates=model.rates,
                description=model.description,
            )
        return model

    # Fallback to AWS
    return BUILTIN_PRICING["aws"]


def calculate_monthly_cost(
    cpu_cores: float,
    memory_mb: float,
    pricing: PricingModel,
    replicas: int = 1,
) -> float:
    """Calculates monthly dollar cost for CPU and Memory allocation."""
    if replicas <= 0:
        return 0.0
    mem_gb = max(0.0, memory_mb) / 1024.0
    cpu = max(0.0, cpu_cores)
    
    hourly_cpu = cpu * pricing.rates.cpu_per_vcpu_hour
    hourly_mem = mem_gb * pricing.rates.memory_per_gb_hour
    total_hourly = (hourly_cpu + hourly_mem) * replicas
    return round(total_hourly * HOURS_PER_MONTH, 2)


def calculate_cost_breakdown(
    current_cpu_cores: float,
    current_memory_mb: float,
    recommended_cpu_cores: float,
    recommended_memory_mb: float,
    pricing: PricingModel,
    replicas: int = 1,
) -> Tuple[float, float, float, float]:
    """Calculates current monthly cost, recommended monthly cost, dollar savings, and percentage.
    
    Returns:
        (current_cost, recommended_cost, monthly_savings, savings_pct)
    """
    curr = calculate_monthly_cost(current_cpu_cores, current_memory_mb, pricing, replicas)
    recc = calculate_monthly_cost(recommended_cpu_cores, recommended_memory_mb, pricing, replicas)
    savings = round(max(0.0, curr - recc), 2)
    pct = round((savings / curr * 100.0) if curr > 0 else 0.0, 1)
    return curr, recc, savings, pct
