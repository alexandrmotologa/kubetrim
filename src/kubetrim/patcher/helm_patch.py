"""Helm values.yaml in-place resource patcher with comment and structure preservation."""

from __future__ import annotations

import difflib
from io import StringIO
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from ruamel.yaml import YAML

from kubetrim.core.models import ContainerRecommendation, WorkloadRecommendation

yaml = YAML()
yaml.preserve_quotes = True
yaml.indent(mapping=2, sequence=4, offset=2)


def _update_resources_dict(res_node: Any, rec: ContainerRecommendation) -> bool:
    """Updates requests and limits inside a ruamel.yaml resources dictionary."""
    if not isinstance(res_node, dict):
        return False

    changed = False
    if "requests" not in res_node:
        res_node["requests"] = {}
    
    if res_node["requests"].get("cpu") != rec.recommended_request_cpu:
        res_node["requests"]["cpu"] = rec.recommended_request_cpu
        changed = True
    if res_node["requests"].get("memory") != rec.recommended_request_memory:
        res_node["requests"]["memory"] = rec.recommended_request_memory
        changed = True

    if "limits" not in res_node:
        res_node["limits"] = {}

    if res_node["limits"].get("cpu") != rec.recommended_limit_cpu:
        res_node["limits"]["cpu"] = rec.recommended_limit_cpu
        changed = True
    if res_node["limits"].get("memory") != rec.recommended_limit_memory:
        res_node["limits"]["memory"] = rec.recommended_limit_memory
        changed = True

    return changed


def patch_helm_values(
    values_yaml: str,
    recommendation: WorkloadRecommendation,
) -> Tuple[str, str]:
    """Updates resources in a Helm values.yaml file and returns (updated_yaml, unified_diff)."""
    stream = StringIO(values_yaml)
    try:
        data = yaml.load(stream)
    except Exception:
        return values_yaml, ""

    if not isinstance(data, dict):
        return values_yaml, ""

    recs_by_name = {c.container_name.lower(): c for c in recommendation.containers}
    first_rec = recommendation.containers[0] if recommendation.containers else None

    modified = False

    # 1. Direct top-level resources block
    if "resources" in data and isinstance(data["resources"], dict) and first_rec:
        if _update_resources_dict(data["resources"], first_rec):
            modified = True

    # 2. Check sub-dictionaries matching container names or workload name
    for key, val in data.items():
        if isinstance(val, dict):
            key_lower = str(key).lower().replace("-", "").replace("_", "")
            # Check if key matches a container
            matched_rec = None
            for c_name, c_rec in recs_by_name.items():
                clean_c = c_name.replace("-", "").replace("_", "")
                if clean_c in key_lower or key_lower in clean_c:
                    matched_rec = c_rec
                    break

            if matched_rec and "resources" in val and isinstance(val["resources"], dict):
                if _update_resources_dict(val["resources"], matched_rec):
                    modified = True
            elif "resources" in val and isinstance(val["resources"], dict) and not modified and first_rec:
                # If workload name matches section
                w_clean = recommendation.workload_name.lower().replace("-", "").replace("_", "")
                if w_clean in key_lower:
                    if _update_resources_dict(val["resources"], first_rec):
                        modified = True

    if not modified:
        return values_yaml, ""

    out_stream = StringIO()
    yaml.dump(data, out_stream)
    new_yaml = out_stream.getvalue()

    orig_lines = values_yaml.splitlines(keepends=True)
    mod_lines = new_yaml.splitlines(keepends=True)
    diff = "".join(
        difflib.unified_diff(
            orig_lines,
            mod_lines,
            fromfile="a/values.yaml",
            tofile="b/values.yaml",
            n=3,
        )
    )

    return new_yaml, diff


def apply_helm_file_patch(
    file_path: str,
    recommendation: WorkloadRecommendation,
    write: bool = False,
    backup: bool = True,
) -> Tuple[str, str]:
    """Reads a Helm values.yaml file, applies patch, and optionally writes back with backup."""
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Helm values file not found: {file_path}")

    content = path.read_text(encoding="utf-8")
    new_yaml, diff = patch_helm_values(content, recommendation)

    if write and new_yaml != content:
        if backup:
            backup_path = path.with_suffix(path.suffix + ".bak")
            backup_path.write_text(content, encoding="utf-8")
        path.write_text(new_yaml, encoding="utf-8")

    return new_yaml, diff
