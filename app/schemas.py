from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class RecipientInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    name: str = Field(min_length=1, max_length=150, examples=["Arun Kumar"])
    certificate_id: str = Field(min_length=1, max_length=80, examples=["AERO-2026-001"])

    @field_validator("name", "certificate_id")
    @classmethod
    def reject_blank(cls, value: str) -> str:
        if not value:
            raise ValueError("must contain non-whitespace characters")
        return value


class CreateJobRequest(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
        json_schema_extra={
            "examples": [{
                "event_name": "Geospatial AI Workshop",
                "issuer": "Aereo Learning Team",
                "issue_date": "2026-10-10",
                "recipients": [
                    {"name": "Arun Kumar", "certificate_id": "AERO-2026-001"},
                    {"name": "Priya S", "certificate_id": "AERO-2026-002"},
                    {"name": "Rahul Menon", "certificate_id": "AERO-2026-003"},
                ],
            }]
        },
    )

    event_name: str = Field(min_length=1, max_length=200)
    issuer: str = Field(min_length=1, max_length=150)
    issue_date: date
    recipients: list[RecipientInput] = Field(min_length=1, max_length=2000)

    @field_validator("event_name", "issuer")
    @classmethod
    def reject_blank_text(cls, value: str) -> str:
        if not value:
            raise ValueError("must contain non-whitespace characters")
        return value

    @model_validator(mode="after")
    def unique_certificate_ids(self):
        ids = [recipient.certificate_id.casefold() for recipient in self.recipients]
        if len(ids) != len(set(ids)):
            raise ValueError("certificate_id values must be unique within a job")
        return self


class RecipientResult(BaseModel):
    id: str
    certificate_id: str
    name: str
    status: Literal["pending", "succeeded", "failed"]
    error: str | None = None
    download_url: str | None = None


class JobResult(BaseModel):
    id: str
    status: Literal["queued", "processing", "completed", "partially_failed", "failed"]
    event_name: str
    total: int
    processed: int
    succeeded: int
    failed: int
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    certificates_url: str
    archive_url: str | None
    recipients: list[RecipientResult]


class JobAccepted(BaseModel):
    id: str
    status: Literal["queued"]
    total: int
    status_url: str
