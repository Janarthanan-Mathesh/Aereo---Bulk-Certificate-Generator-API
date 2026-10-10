# Bulk Certificate Generator API

A Python API for submitting, tracking, and retrieving bulk certificate-generation jobs. Each accepted job is stored in SQLite, processed in the background, and tracked at both job and recipient level. Generated certificates use one predefined PDF design.

## Features

- FastAPI REST API with OpenAPI / Swagger documentation.
- SQLite relational persistence using SQLAlchemy.
- Background bulk processing with persisted progress.
- Per-recipient failure isolation: one rendering failure does not stop other recipients.
- Individual PDF retrieval or a ZIP of successful PDFs plus a job manifest.
- Request limit of 2,000 recipients per job and case-insensitive unique certificate IDs.
- Automated tests for job creation, validation, PDF generation, progress, individual failures, and retrieval.

## Requirements

- Python 3.12 or newer
- pip

## Setup and run

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
uvicorn app.main:app --reload
```

On macOS or Linux, activate with `source .venv/bin/activate`. The API is at `http://127.0.0.1:8000` and interactive docs are at `http://127.0.0.1:8000/docs`.

By default, SQLite is stored at `data/certificates.db` and PDF artifacts are stored in `generated/`. Override these locations using `DATABASE_URL` and `CERTIFICATE_STORAGE_DIR`. Keep both in persistent storage when deploying.

## Create a generation job

`POST /api/v1/jobs` accepts one event and a list of recipients. It returns `202 Accepted` with a job ID and status URL.

```json
{
  "event_name": "Geospatial AI Workshop",
  "issuer": "Aereo Learning Team",
  "issue_date": "2026-10-10",
  "recipients": [
    {"name": "Arun Kumar", "certificate_id": "AERO-2026-001"},
    {"name": "Priya S", "certificate_id": "AERO-2026-002"},
    {"name": "Rahul Menon", "certificate_id": "AERO-2026-003"}
  ]
}
```

Example response:

```json
{
  "id": "<job-id>",
  "status": "queued",
  "total": 3,
  "status_url": "/api/v1/jobs/<job-id>"
}
```

In PowerShell, save the request JSON as `request.json` and submit it with:

```powershell
$body = Get-Content .\request.json -Raw
$job = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v1/jobs -ContentType 'application/json' -Body $body
$job
```

Poll the returned status URL with `Invoke-RestMethod -Uri ("http://127.0.0.1:8000" + $job.status_url)`. When processing finishes, download the archive with `Invoke-WebRequest -Uri ("http://127.0.0.1:8000/api/v1/jobs/" + $job.id + "/download") -OutFile .\certificates.zip`. Individual successful PDFs have download URLs in the job response.

## Track progress and retrieve certificates

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/jobs/{job_id}` | Job status, counts, timestamps, recipient results and links |
| `GET` | `/api/v1/jobs/{job_id}/certificates` | List recipient generation outcomes |
| `GET` | `/api/v1/jobs/{job_id}/certificates/{record_id}/download` | Download one successful PDF |
| `GET` | `/api/v1/jobs/{job_id}/download` | Download successful PDFs and `manifest.json` as a ZIP |

Possible job states: `queued`, `processing`, `completed`, `partially_failed`, and `failed`. `processed` equals `succeeded + failed`; pending recipients are not counted. A partial job still allows successful certificates to be downloaded. The manifest contains every recipient outcome and failure message.

## Validation and failure behavior

The API rejects blank or oversized fields, an empty recipient list, batches over 2,000, duplicate certificate IDs (case-insensitive), unknown JSON fields, and malformed dates with `422 Unprocessable Entity`. Each recipient is rendered independently. A rendering or file-write failure is recorded for that recipient, then processing continues. Job status is `partially_failed` if some certificates succeed and some fail, or `failed` if all fail.

## Tests

```powershell
python -m pytest tests -v
```

Tests use an isolated in-memory SQLite database and temporary artifact directory.

## Design decisions and limitations

- **BackgroundTasks:** keeps the assignment self-contained without Redis. Work runs in the API process, so a process crash can interrupt a job. A production service with sustained workloads should use a durable queue and worker.
- **SQLite + SQLAlchemy:** meets the relational database requirement and runs locally. `DATABASE_URL` can point to PostgreSQL for multi-instance deployment.
- **Artifact storage:** PDFs live on the local filesystem, with paths stored in the database. Production deployments need a persistent shared volume or object storage.
- **Single predefined template:** ReportLab generates a landscape completion certificate with event, recipient, issuer, date, and certificate ID. Built-in Helvetica targets standard Latin text; multilingual output needs an embedded Unicode font.
- **Progress:** job states are persisted and counts update after each recipient, allowing clients to poll status.

## Project layout

```text
app/
  database.py                 SQLAlchemy engine and session dependency
  models.py                   Relational job and recipient records
  schemas.py                  API request/response validation
  main.py                     Routes and HTTP responses
  services/certificates.py    Predefined PDF template
  services/jobs.py            Background generation and failure isolation
tests/
  conftest.py
  test_api.py
```
