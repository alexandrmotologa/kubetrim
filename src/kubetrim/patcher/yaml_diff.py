"""Unified YAML diff generator and Kustomize patch builder for Kubernetes manifests."""

from __future__ import annotations

import difflib
import json
from io import StringIO
from pathlib import Path
from typing import List, Optional, Tuple
from ruamel.yaml import YAML

from kubetrim.core.models import ContainerRecommendation, WorkloadRecommendation

yaml = YAML()
yaml.preserve_quotes = True
yaml.indent(mapping=2, sequence=4, offset=2)


def generate_unified_diff(
    original_yaml: str,
    modified_yaml: str,
    filename: str = "manifest.yaml",
) -> str:
    """Generates standard unified diff lines."""
    orig_lines = original_yaml.splitlines(keepends=True)
    mod_lines = modified_yaml.splitlines(keepends=True)

    diff = difflib.unified_diff(
        orig_lines,
        mod_lines,
        fromfile=f"a/{filename}",
        tofile=f"b/{filename}",
        n=3,
    )
    return "".join(diff)


def patch_manifest_yaml(
    yaml_content: str,
    recommendation: WorkloadRecommendation,
) -> Tuple[str, str]:
    """Applies rightsized requests and limits to a Kubernetes YAML manifest and returns (new_yaml, diff)."""
    # Build container recommendation lookup
    recs_by_name = {c.container_name: c for c in recommendation.containers}

    stream = StringIO(yaml_content)
    try:
        docs = list(yaml.load_all(stream))
    except Exception:
        # Fallback to plain string if parse fails
        return yaml_content, ""

    modified = False
    for doc in docs:
        if not isinstance(doc, dict):
            continue

        kind = doc.get("kind")
        metadata = doc.get("metadata", {})
        name = metadata.get("name")

        if kind != recommendation.workload_kind.value or name != recommendation.workload_name:
            continue

        spec = doc.get("spec", {})
        template_spec = spec.get("template", {}).get("spec", {})
        containers = template_spec.get("containers", [])

        for c in containers:
            c_name = c.get("name")
            rec = recs_by_name.get(c_name)
            if not rec:
                continue

            if "resources" not in c:
                c["resources"] = {}

            if "requests" not in c["resources"]:
                c["resources"]["requests"] = {}
            c["resources"]["requests"]["cpu"] = rec.recommended_request_cpu
            c["resources"]["requests"]["memory"] = rec.recommended_request_memory

            if "limits" not in c["resources"]:
                c["resources"]["limits"] = {}
            c["resources"]["limits"]["cpu"] = rec.recommended_limit_cpu
            c["resources"]["limits"]["memory"] = rec.recommended_limit_memory

            modified = True

    if not modified:
        return yaml_content, ""

    out_stream = StringIO()
    yaml.dump_all(docs, out_stream)
    new_yaml = out_stream.getvalue()

    filename = Path(recommendation.manifest_path).name if recommendation.manifest_path else f"{recommendation.workload_name}.yaml"
    diff = generate_unified_diff(yaml_content, new_yaml, filename=filename)
    return new_yaml, diff


def generate_kustomize_patch(recommendation: WorkloadRecommendation) -> str:
    """Generates a Kustomize Strategic Merge Patch or JSON 6902 patch."""
    containers_patch = []
    for c in recommendation.containers:
        containers_patch.append({
            "name": c.container_name,
            "resources": {
                "requests": {
                    "cpu": c.recommended_request_cpu,
                    "memory": c.recommended_request_memory,
                },
                "limits": {
                    "cpu": c.recommended_limit_cpu,
                    "memory": c.recommended_limit_memory,
                },
            },
        })

    patch_doc = {
        "apiVersion": "apps/v1",
        "kind": recommendation.workload_kind.value,
        "metadata": {
            "name": recommendation.workload_name,
            "namespace": recommendation.namespace,
        },
        "spec": {
            "template": {
                "spec": {
                    "containers": containers_patch,
                }
            }
        },
    }

    out_stream = StringIO()
    yaml.dump(patch_doc, out_stream)
    return out_stream.getvalue()


def generate_kubectl_patch_command(recommendation: WorkloadRecommendation) -> str:
    """Generates a one-line kubectl patch command to apply rightsized resources in cluster."""
    containers_patch = []
    for c in recommendation.containers:
        containers_patch.append({
            "name": c.container_name,
            "resources": {
                "requests": {
                    "cpu": c.recommended_request_cpu,
                    "memory": c.recommended_request_memory,
                },
                "limits": {
                    "cpu": c.recommended_limit_cpu,
                    "memory": c.recommended_limit_memory,
                },
            },
        })

    payload = {
        "spec": {
            "template": {
                "spec": {
                    "containers": containers_patch,
                }
            }
        }
    }

    json_payload = json.dumps(payload, separators=(",", ":"))
    kind_cmd = recommendation.workload_kind.value.lower()
    return f"kubectl patch {kind_cmd} {recommendation.workload_name} -n {recommendation.namespace} --type='strategic' -p='{json_payload}'"
