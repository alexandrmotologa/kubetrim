"""Interactive Textual terminal dashboard for KubeTrim FinOps rightsizing."""

from __future__ import annotations

from typing import List, Optional
from rich.syntax import Syntax
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Label,
    Static,
)

from kubetrim.core.advisor import RightsizingAdvisor
from kubetrim.core.config import RightsizingProfile, load_profile
from kubetrim.core.cost import PricingModel, load_pricing_model
from kubetrim.core.models import ClusterSummary, WorkloadRecommendation
from kubetrim.k8s.client import KubernetesClient
from kubetrim.k8s.prometheus import PrometheusClient
from kubetrim.k8s.synthetic import get_synthetic_cluster
from kubetrim.patcher.yaml_diff import generate_kubectl_patch_command, generate_kustomize_patch


class DiffModal(ModalScreen):
    """Modal dialog displaying unified YAML diff and patch commands."""

    def __init__(self, workload_rec: WorkloadRecommendation):
        super().__init__()
        self.rec = workload_rec

    def compose(self) -> ComposeResult:
        with Vertical(id="modal-dialog"):
            yield Label(
                f"Patch Inspector: {self.rec.namespace}/{self.rec.workload_name}",
                id="modal-title",
            )
            kustomize_text = generate_kustomize_patch(self.rec)
            kubectl_text = generate_kubectl_patch_command(self.rec)

            details = (
                f"# Strategic Merge Patch (Kustomize / GitOps):\n{kustomize_text}\n"
                f"# Kubectl Direct Command:\n{kubectl_text}\n"
            )
            yield Static(Syntax(details, "yaml", theme="monokai", line_numbers=True), id="modal-content")
            with Horizontal(id="modal-buttons"):
                yield Button("Close (Esc)", variant="primary", id="close-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close-btn":
            self.app.pop_screen()

    def key_escape(self) -> None:
        self.app.pop_screen()


class KubeTrimTUI(App):
    """KubeTrim interactive terminal user interface."""

    CSS = """
    Screen {
        background: #090d16;
        color: #e5e7eb;
    }

    #kpi-bar {
        height: 6;
        layout: horizontal;
        margin: 1 1 0 1;
        background: #111827;
        border: solid #1f2937;
    }

    .kpi-box {
        width: 1fr;
        height: 100%;
        content-align: center middle;
        text-align: center;
        border-right: solid #1f2937;
        padding: 0 1;
    }

    .kpi-box:last-child {
        border-right: none;
    }

    .kpi-title {
        color: #9ca3af;
        text-style: bold;
    }

    .kpi-val {
        color: #10b981;
        text-style: bold;
    }

    .kpi-val-blue {
        color: #3b82f6;
        text-style: bold;
    }

    #main-container {
        height: 1fr;
        margin: 1;
        layout: horizontal;
    }

    #sidebar {
        width: 26;
        height: 100%;
        background: #111827;
        border: solid #1f2937;
        padding: 1;
    }

    .sidebar-section-title {
        color: #3b82f6;
        text-style: bold;
        margin-top: 1;
        margin-bottom: 1;
    }

    .sidebar-btn {
        width: 100%;
        margin-bottom: 1;
    }

    #table-container {
        width: 1fr;
        height: 100%;
        background: #111827;
        border: solid #1f2937;
        margin-left: 1;
    }

    DataTable {
        height: 100%;
    }

    DiffModal {
        align: center middle;
    }

    #modal-dialog {
        background: #111827;
        border: thick #3b82f6;
        width: 85%;
        height: 80%;
        padding: 1 2;
    }

    #modal-title {
        text-style: bold;
        color: #3b82f6;
        margin-bottom: 1;
    }

    #modal-content {
        height: 1fr;
        overflow-y: scroll;
        border: solid #1f2937;
        margin-bottom: 1;
    }

    #modal-buttons {
        height: 3;
        align-horizontal: right;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("d", "view_diff", "View Patch"),
        ("p", "cycle_profile", "Switch Profile"),
        ("r", "refresh_data", "Refresh"),
    ]

    def __init__(
        self,
        provider: str = "aws",
        profile_name: str = "balanced",
        namespace: Optional[str] = None,
        kubeconfig_path: Optional[str] = None,
    ):
        super().__init__()
        self.provider_name = provider
        self.profile_name = profile_name
        self.target_namespace = namespace
        self.kubeconfig_path = kubeconfig_path

        self.pricing: PricingModel = load_pricing_model(provider)
        self.profile: RightsizingProfile = load_profile(profile_name)
        self.summary: Optional[ClusterSummary] = None
        self.recommendations: List[WorkloadRecommendation] = []
        self.active_namespace_filter: str = "all"

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="kpi-bar"):
            with Vertical(classes="kpi-box"):
                yield Label("CURRENT SPEND", classes="kpi-title")
                yield Label("$0.00 / mo", id="kpi-current", classes="kpi-val-blue")
            with Vertical(classes="kpi-box"):
                yield Label("RIGHTSIZED SPEND", classes="kpi-title")
                yield Label("$0.00 / mo", id="kpi-rightsized", classes="kpi-val-blue")
            with Vertical(classes="kpi-box"):
                yield Label("MONTHLY RECOVERABLE", classes="kpi-title")
                yield Label("$0.00", id="kpi-savings", classes="kpi-val")
            with Vertical(classes="kpi-box"):
                yield Label("ANNUAL RUN-RATE", classes="kpi-title")
                yield Label("$0.00 / yr", id="kpi-annual", classes="kpi-val")
            with Vertical(classes="kpi-box"):
                yield Label("ACTIVE PROFILE", classes="kpi-title")
                yield Label(self.profile.name.upper(), id="kpi-profile", classes="kpi-val-blue")

        with Horizontal(id="main-container"):
            with Vertical(id="sidebar"):
                yield Label("PROFILES", classes="sidebar-section-title")
                yield Button("Conservative", id="btn-prof-conservative", classes="sidebar-btn")
                yield Button("Balanced", id="btn-prof-balanced", classes="sidebar-btn", variant="primary")
                yield Button("Aggressive", id="btn-prof-aggressive", classes="sidebar-btn")

                yield Label("NAMESPACES", classes="sidebar-section-title")
                yield Button("All Namespaces", id="btn-ns-all", classes="sidebar-btn", variant="success")
                yield Container(id="ns-buttons-container")

            with Vertical(id="table-container"):
                yield DataTable(id="workloads-table", cursor_type="row")

        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns(
            "Namespace",
            "Workload",
            "Kind",
            "Reps",
            "Container",
            "Current Req",
            "Recommended Req",
            "Current $/mo",
            "Rec $/mo",
            "Savings $/mo",
            "Savings %",
            "Flags",
        )
        self.load_data()

    def load_data(self) -> None:
        """Fetches workload data from live cluster or fallback synthetic cluster."""
        advisor = RightsizingAdvisor(self.profile, self.pricing)
        recs: List[WorkloadRecommendation] = []

        k8s_client = KubernetesClient(kubeconfig_path=self.kubeconfig_path)
        if k8s_client.connect():
            workloads = k8s_client.discover_cluster_workloads(namespace=self.target_namespace)
            for w in workloads:
                rec = advisor.advise_workload(w, metrics=None)
                recs.append(rec)

        if not recs:
            # Use synthetic realistic cluster dataset
            cluster_data = get_synthetic_cluster()
            for w_spec, w_metrics in cluster_data:
                rec = advisor.advise_workload(w_spec, metrics=w_metrics)
                recs.append(rec)

        self.recommendations = recs
        self.summary = advisor.generate_cluster_summary(recs)
        self.update_ui()

    def update_ui(self) -> None:
        if not self.summary:
            return

        self.query_one("#kpi-current", Label).update(f"${self.summary.total_current_monthly_cost:,.2f} / mo")
        self.query_one("#kpi-rightsized", Label).update(f"${self.summary.total_recommended_monthly_cost:,.2f} / mo")
        self.query_one("#kpi-savings", Label).update(f"${self.summary.total_monthly_savings:,.2f} ({self.summary.total_savings_pct}%)")
        self.query_one("#kpi-annual", Label).update(f"${self.summary.annual_savings:,.2f} / yr")
        self.query_one("#kpi-profile", Label).update(self.profile.name.upper())

        table = self.query_one(DataTable)
        table.clear()

        for w in self.recommendations:
            if self.active_namespace_filter != "all" and w.namespace != self.active_namespace_filter:
                continue

            for c in w.containers:
                flags = "OOMKill Guard" if c.oomkill_detected else "Normal"
                table.add_row(
                    w.namespace,
                    w.workload_name,
                    f"{w.workload_kind.value}",
                    str(w.replicas),
                    c.container_name,
                    f"{c.current_request_cpu} / {c.current_request_memory}",
                    f"{c.recommended_request_cpu} / {c.recommended_request_memory}",
                    f"${c.current_monthly_cost:.2f}",
                    f"${c.recommended_monthly_cost:.2f}",
                    f"${c.monthly_savings:.2f}",
                    f"{c.savings_pct:.1f}%",
                    flags,
                    key=f"{w.namespace}/{w.workload_name}/{c.container_name}",
                )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        b_id = event.button.id or ""
        if b_id.startswith("btn-prof-"):
            new_prof = b_id.replace("btn-prof-", "")
            self.profile = load_profile(new_prof)
            self.load_data()
        elif b_id == "btn-ns-all":
            self.active_namespace_filter = "all"
            self.update_ui()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self.action_view_diff()

    def action_view_diff(self) -> None:
        table = self.query_one(DataTable)
        if not self.recommendations:
            return

        cursor_row = table.cursor_row
        if cursor_row is not None and cursor_row < len(self.recommendations):
            rec = self.recommendations[cursor_row]
            self.push_screen(DiffModal(rec))

    def action_cycle_profile(self) -> None:
        profiles = ["conservative", "balanced", "aggressive"]
        curr_idx = profiles.index(self.profile.name) if self.profile.name in profiles else 1
        next_prof = profiles[(curr_idx + 1) % len(profiles)]
        self.profile = load_profile(next_prof)
        self.load_data()

    def action_refresh_data(self) -> None:
        self.load_data()
