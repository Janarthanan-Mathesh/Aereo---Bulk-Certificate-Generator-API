"""SQLAlchemy database configuration."""

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/certificates.db")
Path("data").mkdir(exist_ok=True)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def create_schema() -> None:
    # Import models so their tables are registered before create_all.
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def get_db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
