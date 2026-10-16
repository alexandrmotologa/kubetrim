"""Patch generation, unified diffs, Helm updates, and report exports."""

from kubetrim.patcher.exporter import export_csv, export_html, export_json, export_markdown
from kubetrim.patcher.helm_patch import apply_helm_file_patch, patch_helm_values
from kubetrim.patcher.yaml_diff import (
    generate_kubectl_patch_command,
    generate_kustomize_patch,
    generate_unified_diff,
    patch_manifest_yaml,
)

__all__ = [
    "apply_helm_file_patch",
    "export_csv",
    "export_html",
    "export_json",
    "export_markdown",
    "generate_kubectl_patch_command",
    "generate_kustomize_patch",
    "generate_unified_diff",
    "patch_helm_values",
    "patch_manifest_yaml",
]
