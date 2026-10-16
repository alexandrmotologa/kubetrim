"""Unit tests for YAML unified diff, Kustomize patch, and kubectl patch generation."""

from kubetrim.core.models import (
    ContainerRecommendation,
    WorkloadKind,
    WorkloadRecommendation,
)
from kubetrim.patcher.yaml_diff import (
    generate_kubectl_patch_command,
    generate_kustomize_patch,
    generate_unified_diff,
    patch_manifest_yaml,
)


def test_generate_unified_diff():
    orig = "line1\nline2\nline3\n"
    mod = "line1\nline2_modified\nline3\n"
    diff = generate_unified_diff(orig, mod, filename="test.yaml")
    assert "--- a/test.yaml" in diff
    assert "+++ b/test.yaml" in diff
    assert "-line2" in diff
    assert "+line2_modified" in diff


def test_patch_manifest_yaml():
    manifest = """apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-server
  namespace: prod
spec:
  replicas: 2
  template:
    spec:
      containers:
        - name: app
          resources:
            requests:
              cpu: 1000m
              memory: 2Gi
            limits:
              cpu: 2000m
              memory: 4Gi
"""
    rec = WorkloadRecommendation(
        namespace="prod",
        workload_name="api-server",
        workload_kind=WorkloadKind.DEPLOYMENT,
        replicas=2,
        containers=[
            ContainerRecommendation(
                container_name="app",
                current_request_cpu="1000m",
                current_request_memory="2Gi",
                current_limit_cpu="2000m",
                current_limit_memory="4Gi",
                recommended_request_cpu="250m",
                recommended_request_memory="512Mi",
                recommended_limit_cpu="500m",
                recommended_limit_memory="1Gi",
                delta_cpu_cores=0.75,
                delta_memory_mb=1536.0,
                current_monthly_cost=60.0,
                recommended_monthly_cost=15.0,
                monthly_savings=45.0,
                savings_pct=75.0,
            )
        ],
    )

    new_yaml, diff = patch_manifest_yaml(manifest, rec)
    assert "-              cpu: 1000m" in diff or "-              cpu: \"1000m\"" in diff
    assert "+              cpu: 250m" in diff or "+              cpu: \"250m\"" in diff
    assert "512Mi" in new_yaml
    assert "250m" in new_yaml


def test_generate_kustomize_and_kubectl():
    rec = WorkloadRecommendation(
        namespace="prod",
        workload_name="api-server",
        workload_kind=WorkloadKind.DEPLOYMENT,
        replicas=1,
        containers=[
            ContainerRecommendation(
                container_name="app",
                current_request_cpu="1",
                current_request_memory="1Gi",
                current_limit_cpu="2",
                current_limit_memory="2Gi",
                recommended_request_cpu="200m",
                recommended_request_memory="256Mi",
                recommended_limit_cpu="400m",
                recommended_limit_memory="512Mi",
                delta_cpu_cores=0.8,
                delta_memory_mb=768.0,
                current_monthly_cost=30.0,
                recommended_monthly_cost=7.0,
                monthly_savings=23.0,
                savings_pct=76.7,
            )
        ],
    )

    kustomize = generate_kustomize_patch(rec)
    assert "kind: Deployment" in kustomize
    assert "cpu: 200m" in kustomize
    assert "memory: 256Mi" in kustomize

    cmd = generate_kubectl_patch_command(rec)
    assert "kubectl patch deployment api-server -n prod" in cmd
    assert "200m" in cmd
    assert "256Mi" in cmd
