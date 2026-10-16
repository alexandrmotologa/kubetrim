"""Unit tests for Kubernetes manifest scanning and parsing."""

from kubetrim.core.models import WorkloadKind
from kubetrim.k8s.client import KubernetesClient


def test_parse_manifest_file(tmp_path):
    manifest_path = tmp_path / "deploy.yaml"
    manifest_path.write_text(
        """apiVersion: apps/v1
kind: Deployment
metadata:
  name: cart-service
  namespace: shop
spec:
  replicas: 3
  template:
    spec:
      containers:
        - name: cart
          image: cart:v2
          resources:
            requests:
              cpu: 500m
              memory: 1Gi
            limits:
              cpu: 1000m
              memory: 2Gi
""",
        encoding="utf-8",
    )

    workloads = KubernetesClient.parse_manifest_file(str(manifest_path))
    assert len(workloads) == 1
    w = workloads[0]
    assert w.name == "cart-service"
    assert w.namespace == "shop"
    assert w.kind == WorkloadKind.DEPLOYMENT
    assert w.replicas == 3
    assert len(w.containers) == 1
    assert w.containers[0].name == "cart"
    assert w.containers[0].resources.requests.cpu_cores == 0.5
    assert w.containers[0].resources.requests.memory_mb == 1024.0


def test_scan_manifest_directory(tmp_path):
    sub = tmp_path / "charts" / "templates"
    sub.mkdir(parents=True)
    (sub / "dep.yaml").write_text(
        """apiVersion: apps/v1
kind: Deployment
metadata:
  name: dep1
spec:
  replicas: 1
  template:
    spec:
      containers:
        - name: app
""",
        encoding="utf-8",
    )
    (sub / "sts.yaml").write_text(
        """apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: sts1
spec:
  replicas: 2
  template:
    spec:
      containers:
        - name: db
""",
        encoding="utf-8",
    )
    (sub / "ignore.txt").write_text("not a manifest", encoding="utf-8")

    workloads = KubernetesClient.scan_manifest_directory(str(tmp_path))
    assert len(workloads) == 2
    names = {w.name for w in workloads}
    assert "dep1" in names
    assert "sts1" in names
