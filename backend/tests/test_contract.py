import json
import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from app import schemas
from app.main import app

CONTRACT = Path(__file__).resolve().parents[2] / "docs/plan/prompts/kontrak.md"
TEXT = CONTRACT.read_text(encoding="utf-8")
ENDPOINTS = re.findall(r"^### `(GET|POST) ([^`]+)`", TEXT, re.MULTILINE)
RESPONSE_MODELS = {
    ("GET", "/health"): schemas.HealthResponse,
    ("POST", "/quick-check"): schemas.QuickCheckResponse,
    ("POST", "/sites"): schemas.SiteCreateResponse,
    ("POST", "/sites/{site_id}/verify"): schemas.SiteVerifyResponse,
    ("POST", "/sites/{site_id}/scan"): schemas.ScanStartResponse,
    ("GET", "/scans/{scan_id}"): schemas.ScanResponse,
    ("GET", "/findings/{finding_id}"): schemas.FindingResponse,
    ("POST", "/findings/{finding_id}/remediation"): schemas.RemediationResponse,
    ("GET", "/audit-log"): schemas.AuditLogResponse,
}
REQUEST_MODELS = {
    ("POST", "/quick-check"): schemas.QuickCheckRequest,
    ("POST", "/sites"): schemas.SiteCreateRequest,
}


def contract_examples():
    examples = []
    for section in re.split(r"(?=^### )", TEXT, flags=re.MULTILINE):
        section = section.split("\n## ", 1)[0]
        header = re.match(r"### `(GET|POST) ([^`]+)`", section)
        if not header and not section.startswith("### Error"):
            continue
        endpoint = header.groups() if header else None
        for match in re.finditer(r"```json\s*([\s\S]*?)```|`(\{[^`]*\}|\[[^`]*\])`", section):
            raw = match.group(1) or match.group(2)
            line_prefix = section[:match.start()].rsplit("\n", 1)[-1]
            is_request = line_prefix.startswith("Request:")
            model = (
                REQUEST_MODELS[endpoint] if is_request
                else RESPONSE_MODELS[endpoint] if endpoint
                else schemas.ErrorResponse
            )
            examples.append((model, json.loads(raw)))
    return examples


EXAMPLES = contract_examples()


def test_all_contract_paths_and_methods_are_documented():
    assert set(ENDPOINTS) == set(RESPONSE_MODELS)
    actual = {
        (method.upper(), path)
        for path, operations in app.openapi()["paths"].items()
        for method in operations
    }
    assert actual == set(ENDPOINTS)


def test_every_json_example_is_covered():
    # Nine responses, two requests, and one error, including inline JSON.
    assert len(EXAMPLES) == 12
    assert {model for model, _ in EXAMPLES} == {
        *RESPONSE_MODELS.values(), *REQUEST_MODELS.values(), schemas.ErrorResponse,
    }


@pytest.mark.parametrize("model,payload", EXAMPLES, ids=[model.__name__ for model, _ in EXAMPLES])
def test_contract_example_validates_without_shape_changes(model, payload):
    assert model.model_validate(payload).model_dump(mode="json") == payload


@pytest.mark.parametrize("method,path", [entry for entry in ENDPOINTS if entry[1] not in {"/health", "/quick-check"}])
def test_unimplemented_endpoints_return_501(client, method, path):
    url = path.format(site_id="ste_01", scan_id="scn_01", finding_id="fnd_12")
    payload = {"domain": "kampus-a.example"} if path == "/sites" else None
    response = client.request(method, url, json=payload)
    assert response.status_code == 501
    assert response.json() == {"detail": "Belum diimplementasikan"}
    assert "501" in app.openapi()["paths"][path][method.lower()]["responses"]


@pytest.mark.parametrize("path,payload", [
    ("/quick-check", {"url": "file:///secret"}),
    ("/quick-check", {"url": "not-a-url"}),
    ("/sites", {"domain": "https://kampus-a.example/"}),
    ("/sites", {"domain": "kampus-a.example/path"}),
])
def test_request_validation_stays_enabled(client, path, payload):
    assert client.post(path, json=payload).status_code == 422


@pytest.mark.parametrize("field,value", [
    ("status", "terinfeksi"),
    ("reasons", ["unknown"]),
    ("pages_checked", -1),
    ("checked_at", "2026-10-31T15:00:00"),
    ("checked_at", "2026-10-31T15:00:00Z"),
    ("url", "https://kampus-a.example/"),
    ("snippet", "bukti privat"),
    ("affected_pages", 3),
])
def test_quick_check_rejects_invalid_codes_time_and_private_fields(field, value):
    payload = next(data for model, data in EXAMPLES if model is schemas.QuickCheckResponse)
    with pytest.raises(ValidationError):
        schemas.QuickCheckResponse.model_validate({**payload, field: value})


@pytest.mark.parametrize("field,value", [
    ("reason", "unknown"), ("link_count", -1),
])
def test_l2_evidence_validation(field, value):
    payload = {"selector": "a", "reason": "display_none", "link_count": 1, "snippet": "[DISENSOR]"}
    with pytest.raises(ValidationError):
        schemas.L2Evidence.model_validate({**payload, field: value})


@pytest.mark.parametrize("status", ["ok", "partial", "blocked", "skipped"])
def test_layer_statuses(status):
    assert schemas.LayerResult[schemas.L1Evidence](status=status, score=0, evidence=[]).status == status


@pytest.mark.parametrize("field,value", [("score", 1.1), ("score", -0.1), ("status", "unknown")])
def test_invalid_layer_values(field, value):
    payload = {"status": "ok", "score": 0.5, "evidence": []}
    with pytest.raises(ValidationError):
        schemas.LayerResult[schemas.L1Evidence].model_validate({**payload, field: value})


def test_safe_page_requires_null_finding():
    payload = next(data for model, data in EXAMPLES if model is schemas.ScanResponse)["pages"][0]
    with pytest.raises(ValidationError):
        schemas.ScanPage.model_validate({**payload, "label": "aman"})
    assert schemas.ScanPage.model_validate({**payload, "label": "aman", "finding_id": None}).finding_id is None


@pytest.mark.parametrize("status", ["running", "done", "failed"])
def test_scan_status_and_nullable_finish(status):
    payload = next(data for model, data in EXAMPLES if model is schemas.ScanResponse)
    assert schemas.ScanResponse.model_validate({**payload, "status": status, "finished_at": None}).status == status


def test_id_prefix_is_enforced(client):
    assert client.get("/scans/ste_01").status_code == 422


def test_docker_and_pip_playwright_versions_match():
    backend = Path(__file__).resolve().parents[1]
    requirements = (backend / "requirements.txt").read_text()
    dockerfile = (backend / "Dockerfile").read_text()
    version = re.search(r"^playwright==([^\s]+)$", requirements, re.MULTILINE).group(1)
    assert f"FROM mcr.microsoft.com/playwright/python:v{version}-noble" in dockerfile
    assert "${PORT:-8000}" in dockerfile
