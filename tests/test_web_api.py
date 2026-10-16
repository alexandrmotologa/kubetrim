"""Integration tests for FastAPI FinOps Web Studio endpoints."""

from fastapi.testclient import TestClient
from kubetrim.web.server import app

client = TestClient(app)


def test_api_cluster_summary():
    resp = client.get("/api/cluster/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_workloads"] > 0
    assert data["total_monthly_savings"] > 0
    assert "recommendations" in data


def test_api_profiles():
    resp = client.get("/api/profiles")
    assert resp.status_code == 200
    data = resp.json()
    assert "conservative" in data
    assert "balanced" in data
    assert "aggressive" in data


def test_api_pricing():
    resp = client.get("/api/pricing")
    assert resp.status_code == 200
    data = resp.json()
    assert "aws" in data
    assert "gcp" in data
    assert "azure" in data


def test_api_scan():
    resp = client.post("/api/scan", json={"provider": "gcp", "profile": "conservative"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["provider"] == "gcp"
    assert data["profile_name"] == "conservative"


def test_api_patch():
    resp = client.get("/api/patch/production/checkout-service")
    assert resp.status_code == 200
    data = resp.json()
    assert "kustomize_patch" in data
    assert "kubectl_command" in data
    assert "checkout-service" in data["kustomize_patch"]


def test_api_exports():
    csv_resp = client.get("/api/export/csv")
    assert csv_resp.status_code == 200
    assert "namespace,workload_name" in csv_resp.text

    json_resp = client.get("/api/export/json")
    assert json_resp.status_code == 200
    assert "total_monthly_savings" in json_resp.text

    html_resp = client.get("/api/export/html")
    assert html_resp.status_code == 200
    assert "<!DOCTYPE html>" in html_resp.text
    assert "KubeTrim FinOps Audit" in html_resp.text


def test_web_ui_dashboard():
    resp = client.get("/")
    assert resp.status_code == 200
    assert "KubeTrim" in resp.text
