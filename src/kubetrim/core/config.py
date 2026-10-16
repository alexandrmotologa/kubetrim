"""Configuration schemas and profile loaders for KubeTrim."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Optional
import yaml
from pydantic import BaseModel, Field


class RightsizingProfile(BaseModel):
    name: str = "balanced"
    description: str = "Default balanced profile targeting p95 historical utilization with 20% safety buffer."
    target_percentile: float = Field(default=0.95, ge=0.50, le=0.999)
    cpu_headroom_buffer: float = Field(default=0.20, ge=0.0, le=2.0)
    memory_headroom_buffer: float = Field(default=0.20, ge=0.0, le=2.0)
    oomkill_extra_buffer: float = Field(default=0.40, ge=0.0, le=2.0)
    min_cpu_cores: float = Field(default=0.02, ge=0.001)
    min_memory_mb: float = Field(default=32.0, ge=4.0)
    limit_cpu_multiplier: float = Field(default=1.50, ge=1.0)
    limit_memory_multiplier: float = Field(default=1.25, ge=1.0)
    qos_class_preference: str = Field(default="burstable")  # burstable | guaranteed


BUILTIN_PROFILES: Dict[str, RightsizingProfile] = {
    "conservative": RightsizingProfile(
        name="conservative",
        description="High-safety profile with 40% headroom buffer over p99 historical utilization, designed for critical production workloads.",
        target_percentile=0.99,
        cpu_headroom_buffer=0.40,
        memory_headroom_buffer=0.40,
        oomkill_extra_buffer=0.50,
        min_cpu_cores=0.05,
        min_memory_mb=64.0,
        limit_cpu_multiplier=1.50,
        limit_memory_multiplier=1.25,
        qos_class_preference="burstable",
    ),
    "balanced": RightsizingProfile(
        name="balanced",
        description="Standard production profile targeting p95 historical utilization with a 20% safety headroom buffer.",
        target_percentile=0.95,
        cpu_headroom_buffer=0.20,
        memory_headroom_buffer=0.20,
        oomkill_extra_buffer=0.40,
        min_cpu_cores=0.02,
        min_memory_mb=32.0,
        limit_cpu_multiplier=1.50,
        limit_memory_multiplier=1.25,
        qos_class_preference="burstable",
    ),
    "aggressive": RightsizingProfile(
        name="aggressive",
        description="Cost-optimized profile targeting p90 utilization with a 10% safety headroom buffer, suited for non-production environments and batch jobs.",
        target_percentile=0.90,
        cpu_headroom_buffer=0.10,
        memory_headroom_buffer=0.10,
        oomkill_extra_buffer=0.30,
        min_cpu_cores=0.01,
        min_memory_mb=16.0,
        limit_cpu_multiplier=1.25,
        limit_memory_multiplier=1.15,
        qos_class_preference="burstable",
    ),
}


def load_profile(name_or_path: str = "balanced") -> RightsizingProfile:
    """Loads a rightsizing profile from file path, configs/profiles/, or built-in defaults."""
    clean_name = name_or_path.strip().lower()
    if clean_name in BUILTIN_PROFILES:
        # Check if local configs/profiles/ override exists
        config_path = Path("configs") / "profiles" / f"{clean_name}.yaml"
        if config_path.is_file():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    if isinstance(data, dict):
                        return RightsizingProfile(**data)
            except Exception:
                pass
        return BUILTIN_PROFILES[clean_name]

    # Try as direct path
    direct_path = Path(name_or_path)
    if direct_path.is_file():
        with open(direct_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            if isinstance(data, dict):
                return RightsizingProfile(**data)

    # Check in configs/profiles/<name>.yaml
    profile_path = Path("configs") / "profiles" / f"{name_or_path}.yaml"
    if profile_path.is_file():
        with open(profile_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            if isinstance(data, dict):
                return RightsizingProfile(**data)

    # Default fallback
    return BUILTIN_PROFILES["balanced"]
