"""Background bulk-generation worker with per-recipient failure isolation."""

import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from app import database
from app.models import CertificateRecord, GenerationJob
from app.services.certificates import generate_certificate

logger = logging.getLogger(__name__)
STORAGE_DIR = Path(os.getenv("CERTIFICATE_STORAGE_DIR", "generated"))


def process_job(job_id: str) -> None:
    """Generate every recipient independently and persist progress as each finishes."""
    session = database.SessionLocal()
    try:
        job = session.get(GenerationJob, job_id)
        if job is None or job.status != "queued":
            return
        job.status = "processing"
        job.started_at = datetime.now(timezone.utc)
        session.commit()

        records = session.query(CertificateRecord).filter_by(job_id=job_id).order_by(CertificateRecord.position).all()
        job_dir = STORAGE_DIR / job_id
        job_dir.mkdir(parents=True, exist_ok=True)

        for record in records:
            try:
                pdf_bytes = generate_certificate(
                    name=record.recipient_name,
                    event_name=job.event_name,
                    issuer=job.issuer,
                    issue_date=job.issue_date,
                    certificate_id=record.certificate_id,
                )
                path = job_dir / f"{record.id}.pdf"
                path.write_bytes(pdf_bytes)
                record.status = "succeeded"
                record.file_path = str(path.resolve())
                job.succeeded += 1
            except Exception as exc:  # one bad recipient must not cancel the rest of the batch
                logger.exception("Certificate generation failed for record %s in job %s", record.id, job_id)
                record.status = "failed"
                detail = str(exc).strip()
                record.error_message = f"{type(exc).__name__}: {detail[:300]}" if detail else type(exc).__name__
                job.failed += 1
            session.commit()

        job.completed_at = datetime.now(timezone.utc)
        if job.succeeded == job.total:
            job.status = "completed"
        elif job.succeeded:
            job.status = "partially_failed"
        else:
            job.status = "failed"
        session.commit()
    except Exception:
        logger.exception("Bulk generation worker failed for job %s", job_id)
        session.rollback()
        job = session.get(GenerationJob, job_id)
        if job:
            # If an unexpected batch-level problem occurs, retain already-created results.
            remaining = session.query(CertificateRecord).filter_by(job_id=job_id, status="pending").all()
            for record in remaining:
                record.status = "failed"
                record.error_message = "Job processing stopped unexpectedly."
            job.failed = session.query(CertificateRecord).filter_by(job_id=job_id, status="failed").count()
            job.succeeded = session.query(CertificateRecord).filter_by(job_id=job_id, status="succeeded").count()
            job.completed_at = datetime.now(timezone.utc)
            job.status = "partially_failed" if job.succeeded else "failed"
            session.commit()
    finally:
        session.close()
