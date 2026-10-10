from io import BytesIO
from zipfile import ZipFile

from app.services import jobs


def test_creates_generation_job_and_processes_recipients(client, valid_payload):
    response = client.post("/api/v1/jobs", json=valid_payload)
    assert response.status_code == 202
    accepted = response.json()
    assert accepted["total"] == 2
    assert accepted["status"] == "queued"

    result = client.get(accepted["status_url"]).json()
    assert result["status"] == "completed"
    assert result["processed"] == result["total"] == 2
    assert result["succeeded"] == 2
    assert result["failed"] == 0
    assert all(item["status"] == "succeeded" for item in result["recipients"])


def test_input_validation_rejects_empty_and_duplicate_recipients(client, valid_payload):
    empty = {**valid_payload, "recipients": []}
    assert client.post("/api/v1/jobs", json=empty).status_code == 422

    duplicate = {**valid_payload, "recipients": [
        {"name": "A", "certificate_id": "same"},
        {"name": "B", "certificate_id": "SAME"},
    ]}
    assert client.post("/api/v1/jobs", json=duplicate).status_code == 422


def test_certificate_generation_returns_pdf():
    from datetime import date

    from app.services.certificates import generate_certificate

    pdf = generate_certificate("Arun Kumar", "Workshop", "Issuer", date(2026, 10, 10), "CERT-1")
    assert pdf.startswith(b"%PDF-")


def test_job_progress_and_status_endpoint(client, valid_payload):
    accepted = client.post("/api/v1/jobs", json=valid_payload).json()
    result = client.get(accepted["status_url"])
    assert result.status_code == 200
    data = result.json()
    assert data["processed"] == data["succeeded"] + data["failed"]
    assert data["total"] == 2
    assert data["completed_at"] is not None


def test_one_certificate_failure_does_not_stop_remaining_work(client, valid_payload, monkeypatch):
    original = jobs.generate_certificate

    def fail_one(name, *args, **kwargs):
        if name == "Arun Kumar":
            raise RuntimeError("simulated renderer error")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(jobs, "generate_certificate", fail_one)
    accepted = client.post("/api/v1/jobs", json=valid_payload).json()
    result = client.get(accepted["status_url"]).json()
    assert result["status"] == "partially_failed"
    assert result["succeeded"] == 1
    assert result["failed"] == 1
    assert result["recipients"][0]["status"] == "failed"
    assert result["recipients"][1]["status"] == "succeeded"


def test_retrieves_individual_pdf_and_job_archive(client, valid_payload):
    accepted = client.post("/api/v1/jobs", json=valid_payload).json()
    job = client.get(accepted["status_url"]).json()
    record_id = job["recipients"][0]["id"]

    pdf_response = client.get(f"/api/v1/jobs/{job['id']}/certificates/{record_id}/download")
    assert pdf_response.status_code == 200
    assert pdf_response.headers["content-type"] == "application/pdf"
    assert pdf_response.content.startswith(b"%PDF-")

    archive_response = client.get(f"/api/v1/jobs/{job['id']}/download")
    assert archive_response.status_code == 200
    with ZipFile(BytesIO(archive_response.content)) as archive:
        assert len([name for name in archive.namelist() if name.endswith(".pdf")]) == 2
        assert "manifest.json" in archive.namelist()
