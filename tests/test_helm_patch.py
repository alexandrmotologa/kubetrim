"""Unit tests for Helm values.yaml in-place patching."""

from kubetrim.core.models import (
    ContainerRecommendation,
    WorkloadKind,
    WorkloadRecommendation,
)
from kubetrim.patcher.helm_patch import apply_helm_file_patch, patch_helm_values


def test_patch_helm_values_top_level(tmp_path):
    values_content = """# Production web application chart
replicaCount: 2

image:
  repository: myapp
  tag: v1.0.0

resources:
  requests:
    cpu: 1000m
    memory: 2Gi
  limits:
    cpu: 2000m
    memory: 4Gi
"""
    rec = WorkloadRecommendation(
        namespace="default",
        workload_name="myapp",
        workload_kind=WorkloadKind.DEPLOYMENT,
        replicas=2,
        containers=[
            ContainerRecommendation(
                container_name="myapp",
                current_request_cpu="1000m",
                current_request_memory="2Gi",
                current_limit_cpu="2000m",
                current_limit_memory="4Gi",
                recommended_request_cpu="150m",
                recommended_request_memory="384Mi",
                recommended_limit_cpu="300m",
                recommended_limit_memory="512Mi",
                delta_cpu_cores=0.85,
                delta_memory_mb=1664.0,
                current_monthly_cost=50.0,
                recommended_monthly_cost=10.0,
                monthly_savings=40.0,
                savings_pct=80.0,
            )
        ],
    )

    new_yaml, diff = patch_helm_values(values_content, rec)
    assert "cpu: 150m" in new_yaml
    assert "memory: 384Mi" in new_yaml
    assert "# Production web application chart" in new_yaml  # Preserves comments!
    assert "-    cpu: 1000m" in diff
    assert "+    cpu: 150m" in diff

    # Test file application with backup
    file_path = tmp_path / "values.yaml"
    file_path.write_text(values_content, encoding="utf-8")

    apply_helm_file_patch(str(file_path), rec, write=True, backup=True)
    assert file_path.with_suffix(".yaml.bak").exists()
    assert "cpu: 150m" in file_path.read_text(encoding="utf-8")
