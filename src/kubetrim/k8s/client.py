"""Kubernetes workload discovery client for live clusters and local manifests."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml

from kubetrim.core.models import (
    ContainerResources,
    ContainerSpec,
    ResourceLimits,
    ResourceQuantity,
    ResourceRequests,
    WorkloadKind,
    WorkloadSpec,
)

logger = logging.getLogger("kubetrim.k8s")

SYSTEM_NAMESPACES = {
    "kube-system",
    "kube-public",
    "kube-node-lease",
    "local-path-storage",
}


class KubernetesClient:
    """Read-only client for discovering workloads and resource configurations."""

    def __init__(
        self,
        kubeconfig_path: Optional[str] = None,
        context: Optional[str] = None,
    ):
        self.kubeconfig_path = kubeconfig_path
        self.context = context
        self._apps_v1 = None
        self._core_v1 = None
        self._custom_api = None
        self._connected = False

    def connect(self) -> bool:
        """Initializes connection to Kubernetes API using kubeconfig or in-cluster credentials."""
        try:
            from kubernetes import client, config

            try:
                config.load_incluster_config()
                self._connected = True
            except config.ConfigException:
                config.load_kube_config(
                    config_file=self.kubeconfig_path,
                    context=self.context,
                )
                self._connected = True

            self._apps_v1 = client.AppsV1Api()
            self._core_v1 = client.CoreV1Api()
            self._custom_api = client.CustomObjectsApi()
            return True
        except Exception as e:
            logger.debug(f"Could not connect to live Kubernetes cluster: {e}")
            self._connected = False
            return False

    @property
    def is_connected(self) -> bool:
        return self._connected

    def discover_cluster_workloads(
        self,
        namespace: Optional[str] = None,
        exclude_system: bool = True,
    ) -> List[WorkloadSpec]:
        """Discovers Deployments, StatefulSets, and DaemonSets from the live cluster."""
        if not self._connected and not self.connect():
            return []

        workloads: List[WorkloadSpec] = []

        try:
            # 1. Deployments
            if namespace:
                dep_list = self._apps_v1.list_namespaced_deployment(namespace=namespace).items
            else:
                dep_list = self._apps_v1.list_deployment_for_all_namespaces().items

            for item in dep_list:
                ns = item.metadata.namespace
                if exclude_system and ns in SYSTEM_NAMESPACES:
                    continue
                spec = self._parse_k8s_workload(item, WorkloadKind.DEPLOYMENT)
                if spec:
                    workloads.append(spec)

            # 2. StatefulSets
            if namespace:
                sts_list = self._apps_v1.list_namespaced_stateful_set(namespace=namespace).items
            else:
                sts_list = self._apps_v1.list_stateful_set_for_all_namespaces().items

            for item in sts_list:
                ns = item.metadata.namespace
                if exclude_system and ns in SYSTEM_NAMESPACES:
                    continue
                spec = self._parse_k8s_workload(item, WorkloadKind.STATEFULSET)
                if spec:
                    workloads.append(spec)

            # 3. DaemonSets
            if namespace:
                ds_list = self._apps_v1.list_namespaced_daemon_set(namespace=namespace).items
            else:
                ds_list = self._apps_v1.list_daemon_set_for_all_namespaces().items

            for item in ds_list:
                ns = item.metadata.namespace
                if exclude_system and ns in SYSTEM_NAMESPACES:
                    continue
                spec = self._parse_k8s_workload(item, WorkloadKind.DAEMONSET)
                if spec:
                    workloads.append(spec)

        except Exception as e:
            logger.error(f"Error listing workloads from cluster: {e}")

        return workloads

    def _parse_k8s_workload(self, item: Any, kind: WorkloadKind) -> Optional[WorkloadSpec]:
        """Parses a kubernetes client object into a normalized WorkloadSpec."""
        try:
            ns = item.metadata.namespace or "default"
            name = item.metadata.name
            replicas = 1
            if hasattr(item.spec, "replicas") and item.spec.replicas is not None:
                replicas = max(1, int(item.spec.replicas))

            labels = item.metadata.labels or {}
            pod_spec = item.spec.template.spec
            containers: List[ContainerSpec] = []

            for c in pod_spec.containers:
                req_cpu = "0m"
                req_mem = "0Mi"
                lim_cpu = "0m"
                lim_mem = "0Mi"

                if c.resources:
                    if c.resources.requests:
                        req_cpu = str(c.resources.requests.get("cpu", "0m"))
                        req_mem = str(c.resources.requests.get("memory", "0Mi"))
                    if c.resources.limits:
                        lim_cpu = str(c.resources.limits.get("cpu", "0m"))
                        lim_mem = str(c.resources.limits.get("memory", "0Mi"))

                containers.append(
                    ContainerSpec(
                        name=c.name,
                        image=c.image or "",
                        resources=ContainerResources(
                            requests=ResourceRequests(cpu=req_cpu, memory=req_mem),
                            limits=ResourceLimits(cpu=lim_cpu, memory=lim_mem),
                        ),
                    )
                )

            return WorkloadSpec(
                namespace=ns,
                name=name,
                kind=kind,
                replicas=replicas,
                containers=containers,
                labels=labels,
            )
        except Exception as e:
            logger.warning(f"Failed to parse workload item {item}: {e}")
            return None

    @staticmethod
    def parse_manifest_file(file_path: str) -> List[WorkloadSpec]:
        """Parses local Kubernetes YAML manifest file(s) into WorkloadSpec models."""
        path = Path(file_path)
        if not path.is_file():
            return []

        workloads: List[WorkloadSpec] = []
        try:
            with open(path, "r", encoding="utf-8") as f:
                docs = yaml.safe_load_all(f)
                for doc in docs:
                    if not isinstance(doc, dict):
                        continue
                    kind_str = doc.get("kind", "")
                    if kind_str not in {"Deployment", "StatefulSet", "DaemonSet"}:
                        continue

                    kind = WorkloadKind(kind_str)
                    metadata = doc.get("metadata", {})
                    name = metadata.get("name", "unnamed")
                    namespace = metadata.get("namespace", "default")
                    labels = metadata.get("labels", {})

                    spec = doc.get("spec", {})
                    replicas = max(1, int(spec.get("replicas", 1))) if kind != WorkloadKind.DAEMONSET else 1

                    template_spec = spec.get("template", {}).get("spec", {})
                    containers_raw = template_spec.get("containers", [])
                    containers: List[ContainerSpec] = []

                    for c in containers_raw:
                        res = c.get("resources", {})
                        reqs = res.get("requests", {})
                        lims = res.get("limits", {})

                        containers.append(
                            ContainerSpec(
                                name=c.get("name", "app"),
                                image=c.get("image", ""),
                                resources=ContainerResources(
                                    requests=ResourceRequests(
                                        cpu=str(reqs.get("cpu", "0m")),
                                        memory=str(reqs.get("memory", "0Mi")),
                                    ),
                                    limits=ResourceLimits(
                                        cpu=str(lims.get("cpu", "0m")),
                                        memory=str(lims.get("memory", "0Mi")),
                                    ),
                                ),
                            )
                        )

                    workloads.append(
                        WorkloadSpec(
                            namespace=namespace,
                            name=name,
                            kind=kind,
                            replicas=replicas,
                            containers=containers,
                            labels=labels,
                            manifest_path=str(path.resolve()),
                        )
                    )
        except Exception as e:
            logger.error(f"Error parsing manifest {file_path}: {e}")

        return workloads

    @classmethod
    def scan_manifest_directory(cls, dir_path: str) -> List[WorkloadSpec]:
        """Scans a directory recursively for Kubernetes YAML files and extracts workloads."""
        path = Path(dir_path)
        if not path.is_dir():
            return []

        workloads: List[WorkloadSpec] = []
        for file in path.rglob("*"):
            if file.suffix.lower() in {".yaml", ".yml"}:
                workloads.extend(cls.parse_manifest_file(str(file)))
        return workloads
