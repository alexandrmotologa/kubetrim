"""Multi-format report exporter supporting JSON, CSV, Markdown, and self-contained HTML."""

from __future__ import annotations

import csv
from io import StringIO
import json
from typing import Optional
from jinja2 import Template

from kubetrim.core.models import ClusterSummary

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>KubeTrim FinOps Audit Report</title>
  <style>
    :root {
      --bg: #090d16;
      --card-bg: #111827;
      --card-border: #1f2937;
      --text: #f3f4f6;
      --text-muted: #9ca3af;
      --accent: #3b82f6;
      --success: #10b981;
      --warning: #f59e0b;
      --danger: #ef4444;
      --font: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
      --mono: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background-color: var(--bg);
      color: var(--text);
      font-family: var(--font);
      line-height: 1.5;
      padding: 2.5rem 1.5rem;
    }
    .container {
      max-width: 1200px;
      margin: 0 auto;
    }
    header {
      margin-bottom: 2.5rem;
      border-bottom: 1px solid var(--card-border);
      padding-bottom: 1.5rem;
    }
    .header-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 1rem;
    }
    h1 {
      font-size: 1.85rem;
      font-weight: 700;
      color: #fff;
      display: flex;
      align-items: center;
      gap: 0.75rem;
    }
    .badge {
      background: rgba(59, 130, 246, 0.15);
      color: var(--accent);
      border: 1px solid rgba(59, 130, 246, 0.3);
      padding: 0.25rem 0.65rem;
      border-radius: 9999px;
      font-size: 0.8rem;
      font-weight: 600;
    }
    .subtitle {
      color: var(--text-muted);
      margin-top: 0.5rem;
      font-size: 0.95rem;
    }
    .grid-kpi {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 1.25rem;
      margin-bottom: 2.5rem;
    }
    .kpi-card {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 12px;
      padding: 1.25rem 1.5rem;
    }
    .kpi-title {
      font-size: 0.85rem;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 0.5rem;
    }
    .kpi-value {
      font-size: 2rem;
      font-weight: 700;
    }
    .kpi-value.green { color: var(--success); }
    .kpi-value.blue { color: var(--accent); }
    .kpi-sub {
      font-size: 0.85rem;
      color: var(--text-muted);
      margin-top: 0.35rem;
    }
    .section-title {
      font-size: 1.25rem;
      font-weight: 600;
      margin-bottom: 1rem;
    }
    .table-container {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 12px;
      overflow-x: auto;
      margin-bottom: 2.5rem;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      text-align: left;
      font-size: 0.9rem;
    }
    th {
      background: rgba(255, 255, 255, 0.03);
      padding: 0.85rem 1rem;
      font-weight: 600;
      color: var(--text-muted);
      border-bottom: 1px solid var(--card-border);
    }
    td {
      padding: 0.85rem 1rem;
      border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    }
    tr:last-child td { border-bottom: none; }
    .mono { font-family: var(--mono); font-size: 0.85rem; }
    .text-green { color: var(--success); font-weight: 600; }
    .tag {
      display: inline-block;
      padding: 0.15rem 0.5rem;
      border-radius: 4px;
      font-size: 0.75rem;
      font-weight: 600;
    }
    .tag-danger { background: rgba(239, 68, 68, 0.2); color: var(--danger); }
    .tag-neutral { background: rgba(255, 255, 255, 0.1); color: var(--text); }
    footer {
      text-align: center;
      color: var(--text-muted);
      font-size: 0.85rem;
      margin-top: 3rem;
    }
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div class="header-row">
        <div>
          <h1>KubeTrim FinOps Audit <span class="badge">Zero-Agent</span></h1>
          <p class="subtitle">Cloud Provider: {{ summary.provider|upper }} ({{ summary.region }}) | Profile: {{ summary.profile_name }}</p>
        </div>
      </div>
    </header>

    <div class="grid-kpi">
      <div class="kpi-card">
        <div class="kpi-title">Current Monthly Spend</div>
        <div class="kpi-value">${{ "%.2f"|format(summary.total_current_monthly_cost) }}</div>
        <div class="kpi-sub">Across {{ summary.total_workloads }} workloads ({{ summary.total_replicas }} replicas)</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-title">Right-sized Monthly Cost</div>
        <div class="kpi-value blue">${{ "%.2f"|format(summary.total_recommended_monthly_cost) }}</div>
        <div class="kpi-sub">With safety buffer headroom</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-title">Monthly Waste Recoverable</div>
        <div class="kpi-value green">${{ "%.2f"|format(summary.total_monthly_savings) }}</div>
        <div class="kpi-sub">{{ summary.total_savings_pct }}% total reduction</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-title">Projected Annual Savings</div>
        <div class="kpi-value green">${{ "%.2f"|format(summary.annual_savings) }}</div>
        <div class="kpi-sub">Run-rate financial reduction</div>
      </div>
    </div>

    <h2 class="section-title">Workload Rightsizing Recommendations</h2>
    <div class="table-container">
      <table>
        <thead>
          <tr>
            <th>Workload</th>
            <th>Kind / Rep</th>
            <th>Container</th>
            <th>Current Req</th>
            <th>Recommended Req</th>
            <th>Current $/mo</th>
            <th>Rec $/mo</th>
            <th>Savings</th>
            <th>Flags</th>
          </tr>
        </thead>
        <tbody>
          {% for w in summary.recommendations %}
            {% for c in w.containers %}
            <tr>
              <td><strong>{{ w.namespace }}</strong>/{{ w.workload_name }}</td>
              <td><span class="tag tag-neutral">{{ w.workload_kind.value }} &times;{{ w.replicas }}</span></td>
              <td class="mono">{{ c.container_name }}</td>
              <td class="mono">{{ c.current_request_cpu }} / {{ c.current_request_memory }}</td>
              <td class="mono text-green">{{ c.recommended_request_cpu }} / {{ c.recommended_request_memory }}</td>
              <td>${{ "%.2f"|format(c.current_monthly_cost) }}</td>
              <td>${{ "%.2f"|format(c.recommended_monthly_cost) }}</td>
              <td class="text-green">+${{ "%.2f"|format(c.monthly_savings) }} ({{ c.savings_pct }}%)</td>
              <td>
                {% if c.oomkill_detected %}
                  <span class="tag tag-danger">OOMKill Guard</span>
                {% else %}
                  -
                {% endif %}
              </td>
            </tr>
            {% endfor %}
          {% endfor %}
        </tbody>
      </table>
    </div>

    <footer>
      Generated by KubeTrim &bull; Zero-Agent Kubernetes FinOps &bull; Author: Alexandr Motologa
    </footer>
  </div>
</body>
</html>
"""


def export_json(summary: ClusterSummary) -> str:
    """Exports cluster summary to formatted JSON string."""
    return json.dumps(summary.model_dump(), indent=2)


def export_csv(summary: ClusterSummary) -> str:
    """Exports workload recommendations to standard CSV format."""
    out = StringIO()
    writer = csv.writer(out)
    writer.writerow([
        "namespace",
        "workload_name",
        "kind",
        "replicas",
        "container_name",
        "current_req_cpu",
        "current_req_mem",
        "current_lim_cpu",
        "current_lim_mem",
        "recommended_req_cpu",
        "recommended_req_mem",
        "recommended_lim_cpu",
        "recommended_lim_mem",
        "delta_cpu_cores",
        "delta_mem_mb",
        "current_monthly_cost_usd",
        "recommended_monthly_cost_usd",
        "monthly_savings_usd",
        "savings_pct",
        "oomkill_detected",
        "action_note",
    ])

    for w in summary.recommendations:
        for c in w.containers:
            writer.writerow([
                w.namespace,
                w.workload_name,
                w.workload_kind.value,
                w.replicas,
                c.container_name,
                c.current_request_cpu,
                c.current_request_memory,
                c.current_limit_cpu,
                c.current_limit_memory,
                c.recommended_request_cpu,
                c.recommended_request_memory,
                c.recommended_limit_cpu,
                c.recommended_limit_memory,
                c.delta_cpu_cores,
                c.delta_memory_mb,
                c.current_monthly_cost,
                c.recommended_monthly_cost,
                c.monthly_savings,
                c.savings_pct,
                c.oomkill_detected,
                c.action_note,
            ])

    return out.getvalue()


def export_markdown(summary: ClusterSummary) -> str:
    """Exports cluster summary to formatted GitHub Markdown."""
    lines = [
        f"# KubeTrim FinOps Audit Report",
        "",
        f"**Cloud Provider:** {summary.provider.upper()} ({summary.region}) | **Profile:** `{summary.profile_name}`",
        "",
        "## Summary Metrics",
        "",
        f"- **Current Monthly Spend:** ${summary.total_current_monthly_cost:.2f}",
        f"- **Recommended Monthly Spend:** ${summary.total_recommended_monthly_cost:.2f}",
        f"- **Potential Monthly Savings:** **${summary.total_monthly_savings:.2f}** ({summary.total_savings_pct}%)",
        f"- **Projected Annual Run-Rate Savings:** **${summary.annual_savings:.2f}**",
        f"- **Total Workloads Analyzed:** {summary.total_workloads} ({summary.total_replicas} total pod replicas)",
        "",
        "## Rightsizing Recommendations",
        "",
        "| Workload | Replicas | Container | Current Requests | Recommended Requests | Monthly Savings | Flags |",
        "| :--- | :---: | :--- | :--- | :--- | :--- | :--- |",
    ]

    for w in summary.recommendations:
        for c in w.containers:
            flags = "OOMKill Guard" if c.oomkill_detected else "Normal"
            lines.append(
                f"| `{w.namespace}/{w.workload_name}` | {w.replicas} | `{c.container_name}` | "
                f"`{c.current_request_cpu}` / `{c.current_request_memory}` | "
                f"**`{c.recommended_request_cpu}` / `{c.recommended_request_memory}`** | "
                f"+${c.monthly_savings:.2f} ({c.savings_pct}%) | {flags} |"
            )

    lines.append("")
    lines.append("---")
    lines.append("*Generated by KubeTrim - Zero-Agent Kubernetes FinOps*")
    return "\n".join(lines)


def export_html(summary: ClusterSummary) -> str:
    """Exports cluster summary to a self-contained responsive HTML report."""
    template = Template(HTML_TEMPLATE)
    return template.render(summary=summary)
