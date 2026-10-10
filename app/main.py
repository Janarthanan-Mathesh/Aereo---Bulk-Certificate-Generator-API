from __future__ import annotations

import logging
import json
import re
import uuid
from contextlib import asynccontextmanager
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, status
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from app import database
from app.models import CertificateRecord, GenerationJob
from app.schemas import CreateJobRequest, JobAccepted, JobResult, RecipientResult
from app.services.jobs import process_job

logger = logging.getLogger(__name__)


def _safe_archive_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", value).strip("_-")[:80] or "certificate"


@asynccontextmanager
async def lifespan(application: FastAPI):
    database.create_schema()
    yield


app = FastAPI(
    title="Bulk Certificate Generator API",
    summary="Create, track, and retrieve certificates generated in bulk.",
    description=(
        "Creates a persistent generation job, processes recipients in the background, "
        "tracks per-recipient outcomes in a relational database, and provides individual "
        "PDF and ZIP download endpoints."
    ),
    version="2.0.0",
    lifespan=lifespan,
)


@app.get("/", tags=["Service"])
def home():
    return {"name": app.title, "version": app.version, "docs": "/docs"}


@app.get("/health", tags=["Service"])
def health():
    return {"status": "healthy"}


def _job_result(job: GenerationJob) -> JobResult:
    recipients = [
        RecipientResult(
            id=record.id,
            certificate_id=record.certificate_id,
            name=record.recipient_name,
            status=record.status,
            error=record.error_message,
            download_url=(
                f"/api/v1/jobs/{job.id}/certificates/{record.id}/download"
                if record.status == "succeeded" else None
            ),
        )
        for record in sorted(job.recipients, key=lambda item: item.position)
    ]
    return JobResult(
        id=job.id,
        status=job.status,
        event_name=job.event_name,
        total=job.total,
        processed=job.succeeded + job.failed,
        succeeded=job.succeeded,
        failed=job.failed,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        certificates_url=f"/api/v1/jobs/{job.id}/certificates",
        archive_url=(
            f"/api/v1/jobs/{job.id}/download"
            if job.succeeded > 0 else None
        ),
        recipients=recipients,
    )


@app.post(
    "/api/v1/jobs",
    response_model=JobAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Generation jobs"],
    summary="Create a bulk certificate generation job",
)
def create_job(
    payload: CreateJobRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(database.get_db),
):
    job_id = str(uuid.uuid4())
    job = GenerationJob(
        id=job_id,
        event_name=payload.event_name,
        issuer=payload.issuer,
        issue_date=payload.issue_date,
        status="queued",
        total=len(payload.recipients),
    )
    job.recipients = [
        CertificateRecord(
            id=str(uuid.uuid4()),
            certificate_id=recipient.certificate_id,
            recipient_name=recipient.name,
            position=position,
            status="pending",
        )
        for position, recipient in enumerate(payload.recipients)
    ]
    db.add(job)
    db.commit()
    background_tasks.add_task(process_job, job_id)
    return JobAccepted(id=job_id, status="queued", total=job.total, status_url=f"/api/v1/jobs/{job_id}")


@app.get("/api/v1/jobs/{job_id}", response_model=JobResult, tags=["Generation jobs"], summary="Get job status and results")
def get_job(job_id: str, db: Session = Depends(database.get_db)):
    job = db.get(GenerationJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Generation job not found")
    return _job_result(job)


@app.get("/api/v1/jobs/{job_id}/certificates", tags=["Certificates"], summary="List certificates and outcomes for a job")
def list_certificates(job_id: str, db: Session = Depends(database.get_db)):
    job = db.get(GenerationJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Generation job not found")
    result = _job_result(job)
    return {"job_id": job_id, "status": result.status, "total": result.total, "succeeded": result.succeeded,
            "failed": result.failed, "certificates": [item.model_dump() for item in result.recipients]}


@app.get("/api/v1/jobs/{job_id}/certificates/{record_id}/download", tags=["Certificates"], summary="Download one generated PDF")
def download_certificate(job_id: str, record_id: str, db: Session = Depends(database.get_db)):
    record = db.get(CertificateRecord, record_id)
    if record is None or record.job_id != job_id:
        raise HTTPException(status_code=404, detail="Certificate not found")
    if record.status != "succeeded" or not record.file_path:
        raise HTTPException(status_code=409, detail=f"Certificate is {record.status}")
    path = Path(record.file_path)
    if not path.is_file():
        logger.error("Certificate artifact is missing: %s", path)
        raise HTTPException(status_code=410, detail="Certificate file is no longer available")
    return FileResponse(path, media_type="application/pdf", filename=f"{_safe_archive_name(record.certificate_id)}.pdf")


@app.get("/api/v1/jobs/{job_id}/download", tags=["Certificates"], summary="Download all successful PDFs as a ZIP")
def download_job_archive(job_id: str, db: Session = Depends(database.get_db)):
    job = db.get(GenerationJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Generation job not found")
    records = [record for record in job.recipients if record.status == "succeeded" and record.file_path]
    if not records:
        raise HTTPException(status_code=409, detail="No certificates have been generated successfully")
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for record in records:
            path = Path(record.file_path)
            if path.is_file():
                archive.write(path, arcname=f"certificates/{record.id[:8]}_{_safe_archive_name(record.certificate_id)}.pdf")
        archive.writestr("manifest.json", json.dumps({
            "job_id": job.id,
            "status": job.status,
            "total": job.total,
            "succeeded": job.succeeded,
            "failed": job.failed,
            "certificates": [
                {
                    "certificate_id": record.certificate_id,
                    "recipient": record.recipient_name,
                    "status": record.status,
                    "error": record.error_message,
                }
                for record in job.recipients
            ],
        }, ensure_ascii=False, indent=2))
    return Response(
        content=output.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="certificates-{job_id}.zip"', "Cache-Control": "no-store"},
    )
