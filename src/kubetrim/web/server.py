"""FastAPI server providing REST endpoints, WebSockets, What-If simulator, and FinOps Web Studio UI."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from kubetrim.core.advisor import RightsizingAdvisor
from kubetrim.core.binpack import NodeBinPackingSimulator
from kubetrim.core.config import BUILTIN_PROFILES, RightsizingProfile, load_profile
from kubetrim.core.cost import BUILTIN_PRICING, PricingModel, load_pricing_model
from kubetrim.core.models import BinPackingResult, ClusterSummary, WorkloadRecommendation
from kubetrim.k8s.client import KubernetesClient
from kubetrim.k8s.synthetic import get_synthetic_cluster
from kubetrim.patcher.exporter import export_csv, export_html, export_json
from kubetrim.patcher.yaml_diff import (
    generate_kubectl_patch_command,
    generate_kustomize_patch,
    generate_unified_diff,
)

app = FastAPI(
    title="KubeTrim FinOps Web Studio",
    description="Zero-Agent Kubernetes FinOps, Pod Rightsizing, HPA & Bin-Packing API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).parent / "static"


class ScanRequest(BaseModel):
    provider: str = "aws"
    profile: str = "balanced"
    namespace: Optional[str] = None
    context: Optional[str] = None
    evaluation_window: str = "14d"
    custom_cpu_buffer: Optional[float] = None
    custom_memory_buffer: Optional[float] = None
    custom_percentile: Optional[float] = None


class WebStudioState:
    def __init__(self):
        self.provider = "aws"
        self.profile = "balanced"
        self.namespace = None
        self.context = None
        self.custom_cpu_buffer: Optional[float] = None
        self.custom_memory_buffer: Optional[float] = None
        self.custom_percentile: Optional[float] = None

        self.pricing = load_pricing_model("aws")
        self.rightsizer_profile = load_profile("balanced")
        self.summary: Optional[ClusterSummary] = None
        self.recommendations: List[WorkloadRecommendation] = []
        self._refresh()

    def _refresh(self):
        self.pricing = load_pricing_model(self.provider)

        if self.custom_cpu_buffer is not None or self.custom_memory_buffer is not None or self.custom_percentile is not None:
            base = load_profile(self.profile)
            self.rightsizer_profile = RightsizingProfile(
                name="custom",
                description="Interactive What-If Headroom Profile",
                target_percentile=self.custom_percentile if self.custom_percentile is not None else base.target_percentile,
                cpu_headroom_buffer=self.custom_cpu_buffer if self.custom_cpu_buffer is not None else base.cpu_headroom_buffer,
                memory_headroom_buffer=self.custom_memory_buffer if self.custom_memory_buffer is not None else base.memory_headroom_buffer,
                oomkill_extra_buffer=base.oomkill_extra_buffer,
                min_cpu_cores=base.min_cpu_cores,
                min_memory_mb=base.min_memory_mb,
                limit_cpu_multiplier=base.limit_cpu_multiplier,
                limit_memory_multiplier=base.limit_memory_multiplier,
            )
        else:
            self.rightsizer_profile = load_profile(self.profile)

        advisor = RightsizingAdvisor(self.rightsizer_profile, self.pricing)

        recs: List[WorkloadRecommendation] = []
        k8s = KubernetesClient(context=self.context)
        if k8s.connect():
            workloads = k8s.discover_cluster_workloads(namespace=self.namespace)
            for w in workloads:
                recs.append(advisor.advise_workload(w))

        if not recs:
            cluster = get_synthetic_cluster()
            for w_spec, w_metrics in cluster:
                if self.namespace and w_spec.namespace != self.namespace:
                    continue
                recs.append(advisor.advise_workload(w_spec, w_metrics))

        self.recommendations = recs
        self.summary = advisor.generate_cluster_summary(recs)


state = WebStudioState()


@app.get("/api/cluster/summary", response_model=ClusterSummary)
def get_cluster_summary():
    """Returns aggregated cluster FinOps metrics, node bin-packing, and recommendations."""
    if not state.summary:
        state._refresh()
    return state.summary


@app.get("/api/contexts")
def list_contexts():
    """Lists available Kubernetes cluster contexts."""
    k8s = KubernetesClient()
    return {"contexts": k8s.list_available_contexts(), "active_context": state.context}


@app.get("/api/binpack", response_model=Optional[BinPackingResult])
def get_binpack_simulation():
    """Returns Karpenter / Cluster Autoscaler node bin-packing simulation."""
    if not state.summary:
        state._refresh()
    return state.summary.bin_packing


@app.get("/api/profiles")
def get_profiles():
    """Lists available rightsizing profiles and their thresholds."""
    return {k: v.model_dump() for k, v in BUILTIN_PROFILES.items()}


@app.get("/api/pricing")
def get_pricing():
    """Lists available cloud provider pricing rate cards."""
    return {k: v.model_dump() for k, v in BUILTIN_PRICING.items()}


@app.post("/api/scan", response_model=ClusterSummary)
def trigger_scan(req: ScanRequest):
    """Triggers recalculation across cloud providers, profiles, What-If headroom sliders, and namespaces."""
    state.provider = req.provider
    state.profile = req.profile
    state.namespace = req.namespace
    state.context = req.context
    state.custom_cpu_buffer = req.custom_cpu_buffer
    state.custom_memory_buffer = req.custom_memory_buffer
    state.custom_percentile = req.custom_percentile
    state._refresh()
    return state.summary


@app.get("/api/patch/{namespace}/{workload_name}")
def get_workload_patch(namespace: str, workload_name: str):
    """Generates Kustomize strategic merge patch, kubectl one-liner, and HPA status."""
    rec = next(
        (r for r in state.recommendations if r.namespace == namespace and r.workload_name == workload_name),
        None,
    )
    if not rec:
        raise HTTPException(status_code=404, detail="Workload recommendation not found")

    kustomize = generate_kustomize_patch(rec)
    kubectl_cmd = generate_kubectl_patch_command(rec)
    return {
        "namespace": namespace,
        "workload_name": workload_name,
        "kustomize_patch": kustomize,
        "kubectl_command": kubectl_cmd,
        "hpa_warning": rec.hpa_warning.model_dump() if rec.hpa_warning else None,
        "spot_recommendation": rec.spot_recommendation.model_dump() if rec.spot_recommendation else None,
    }


@app.get("/api/export/csv")
def export_csv_report():
    """Downloads CSV report of all rightsizing recommendations."""
    if not state.summary:
        state._refresh()
    csv_content = export_csv(state.summary)
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=kubetrim_finops_audit.csv"},
    )


@app.get("/api/export/json")
def export_json_report():
    """Downloads JSON report."""
    if not state.summary:
        state._refresh()
    json_content = export_json(state.summary)
    return Response(
        content=json_content,
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=kubetrim_finops_audit.json"},
    )


@app.get("/api/export/html")
def export_html_report():
    """Downloads standalone interactive HTML report."""
    if not state.summary:
        state._refresh()
    html_content = export_html(state.summary)
    return HTMLResponse(content=html_content)


@app.websocket("/ws/status")
async def websocket_status(websocket: WebSocket):
    """Streams live FinOps status and real-time updates."""
    await websocket.accept()
    try:
        if state.summary:
            await websocket.send_json({
                "type": "summary_update",
                "current_monthly_spend": state.summary.total_current_monthly_cost,
                "rightsized_monthly_spend": state.summary.total_recommended_monthly_cost,
                "monthly_savings": state.summary.total_monthly_savings,
                "savings_pct": state.summary.total_savings_pct,
                "workload_count": state.summary.total_workloads,
            })
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass


@app.get("/", response_class=HTMLResponse)
def serve_dashboard():
    """Serves the FinOps Web Studio UI."""
    index_file = STATIC_DIR / "index.html"
    if index_file.is_file():
        return HTMLResponse(content=index_file.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>KubeTrim Web Studio</h1><p>Static index.html not found.</p>")


if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
