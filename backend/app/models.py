from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Enum, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Site(Base):
    __tablename__ = "sites"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    domain: Mapped[str] = mapped_column(String)
    alias: Mapped[str] = mapped_column(String)
    site_alias: Mapped[str] = mapped_column(String)
    tier: Mapped[str] = mapped_column(
        Enum("public", "research", "verified", native_enum=False, create_constraint=True),
        default="public",
    )
    token: Mapped[str | None] = mapped_column(String)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Scan(Base):
    __tablename__ = "scans"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(
        Enum("running", "done", "failed", native_enum=False, create_constraint=True)
    )


class Page(Base):
    __tablename__ = "pages"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    scan_id: Mapped[str] = mapped_column(ForeignKey("scans.id"))
    url: Mapped[str] = mapped_column(Text)
    r_score: Mapped[float | None] = mapped_column(Float)
    label: Mapped[str | None] = mapped_column(
        Enum(
            "aman", "waspada", "terinfeksi", "tidak_dapat_diperiksa",
            native_enum=False, create_constraint=True,
        )
    )


class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    page_id: Mapped[str] = mapped_column(ForeignKey("pages.id"))
    layer: Mapped[str] = mapped_column(String)
    profile: Mapped[str | None] = mapped_column(String)
    evidence_html: Mapped[str | None] = mapped_column(Text)
    detail_json: Mapped[dict[str, Any]] = mapped_column(JSON)


class Snapshot(Base):
    __tablename__ = "snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    page_id: Mapped[str] = mapped_column(ForeignKey("pages.id"))
    profile: Mapped[str] = mapped_column(String)
    html_path: Mapped[str | None] = mapped_column(Text)
    screenshot_path: Mapped[str | None] = mapped_column(Text)
    headers_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    user: Mapped[str] = mapped_column(String)
    site_alias: Mapped[str] = mapped_column(String)
    action: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
