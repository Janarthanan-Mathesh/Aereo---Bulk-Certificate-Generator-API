from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class GenerationJob(Base):
    __tablename__ = "generation_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    event_name: Mapped[str] = mapped_column(String(200), nullable=False)
    issuer: Mapped[str] = mapped_column(String(150), nullable=False)
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued")
    total: Mapped[int] = mapped_column(Integer, nullable=False)
    succeeded: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    recipients: Mapped[list["CertificateRecord"]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )


class CertificateRecord(Base):
    __tablename__ = "certificate_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("generation_jobs.id", ondelete="CASCADE"), index=True)
    certificate_id: Mapped[str] = mapped_column(String(80), nullable=False)
    recipient_name: Mapped[str] = mapped_column(String(150), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    job: Mapped[GenerationJob] = relationship(back_populates="recipients")
