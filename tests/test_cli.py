"""Integration tests for Typer CLI commands."""

from pathlib import Path
from typer.testing import CliRunner
from kubetrim.cli.main import app

runner = CliRunner(env={"COLUMNS": "160"})


def test_cli_version():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "KubeTrim version" in result.output


def test_cli_pricing():
    result = runner.invoke(app, ["pricing"])
    assert result.exit_code == 0
    assert "Cloud Compute Pricing Catalog" in result.output
    assert "AWS" in result.output
    assert "GCP" in result.output
    assert "AZURE" in result.output


def test_cli_scan_table():
    result = runner.invoke(app, ["scan"])
    assert result.exit_code == 0
    assert "KubeTrim FinOps Summary" in result.output
    assert "Recoverable Waste" in result.output
    assert "checkout" in result.output
    assert "OOMKill" in result.output


def test_cli_scan_json(tmp_path):
    out_file = tmp_path / "report.json"
    result = runner.invoke(app, ["scan", "--output", "json", "--export-file", str(out_file)])
    assert result.exit_code == 0
    assert out_file.exists()
    assert '"total_monthly_savings"' in out_file.read_text(encoding="utf-8")


def test_cli_scan_csv(tmp_path):
    out_file = tmp_path / "report.csv"
    result = runner.invoke(app, ["scan", "--output", "csv", "--export-file", str(out_file)])
    assert result.exit_code == 0
    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8")
    assert "namespace,workload_name" in content
    assert "checkout-service" in content


def test_cli_scan_html(tmp_path):
    out_file = tmp_path / "report.html"
    result = runner.invoke(app, ["scan", "--output", "html", "--export-file", str(out_file)])
    assert result.exit_code == 0
    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in content
    assert "KubeTrim FinOps Audit" in content


def test_cli_diff_manifest():
    manifest_path = Path("examples/manifests/deployment.yaml")
    result = runner.invoke(app, ["diff", str(manifest_path)])
    assert result.exit_code == 0
    assert "--- a/deployment.yaml" in result.output
    assert "+++ b/deployment.yaml" in result.output
    assert "-              cpu: \"2000m\"" in result.output or "-              cpu: 2000m" in result.output


def test_cli_diff_kustomize():
    manifest_path = Path("examples/manifests/deployment.yaml")
    result = runner.invoke(app, ["diff", str(manifest_path), "--kustomize"])
    assert result.exit_code == 0
    assert "kind: Deployment" in result.output
    assert "checkout-service" in result.output


def test_cli_patch_dry_run():
    values_path = Path("examples/helm/values.yaml")
    result = runner.invoke(app, ["patch", str(values_path)])
    assert result.exit_code == 0
    assert "--- a/values.yaml" in result.output
    assert "Dry run complete" in result.output


def test_cli_gate_pass():
    result = runner.invoke(app, ["gate", "--max-waste-usd", "50000", "--max-waste-pct", "99"])
    assert result.exit_code == 0
    assert "PASSED" in result.output


def test_cli_gate_fail(tmp_path):
    pr_comment = tmp_path / "pr_comment.md"
    result = runner.invoke(
        app,
        [
            "gate",
            "--max-waste-usd",
            "10",
            "--fail-on-waste",
            "--pr-comment-file",
            str(pr_comment),
        ],
    )
    assert result.exit_code == 1
    assert "FAILED" in result.output
    assert pr_comment.exists()
    assert "KubeTrim FinOps Budget Gate" in pr_comment.read_text(encoding="utf-8")


def test_cli_binpack():
    result = runner.invoke(app, ["binpack"])
    assert result.exit_code == 0
    assert "Node Bin-Packing" in result.output
    assert "Current Nodes Needed" in result.output
    assert "Simulated Node Allocation" in result.output


def test_cli_gitops_export_dry_run():
    manifest_path = Path("examples/manifests/deployment.yaml")
    result = runner.invoke(app, ["gitops-export", str(manifest_path), "--dry-run"])
    assert result.exit_code == 0
    assert "GitOps Export Target" in result.output
    assert "Dry run complete" in result.output


def test_cli_contexts():
    result = runner.invoke(app, ["contexts"])
    # Contexts list command exits 0 whether local contexts exist or not
    assert result.exit_code == 0

