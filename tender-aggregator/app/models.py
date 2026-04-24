"""SQLAlchemy ORM models."""
from __future__ import annotations

import enum
from datetime import datetime
from typing import List, Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TenderStatus(str, enum.Enum):
    NEW = "NEW"
    INTERESTED = "INTERESTED"
    NOT_INTERESTED = "NOT_INTERESTED"
    APPLIED = "APPLIED"
    REJECTED = "REJECTED"
    WON = "WON"


class TenderCategory(str, enum.Enum):
    """What kind of signal this row represents.

    - TENDER:        a classical tender / RFP with a formal procedure
    - EARLY_SIGNAL:  weak signal culled from a news feed or editorial page;
                     useful as a radar blip but not a procurement process
    """
    TENDER = "TENDER"
    EARLY_SIGNAL = "EARLY_SIGNAL"


class Tender(Base):
    __tablename__ = "tenders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(1000), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    organization: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    url: Mapped[str] = mapped_column(String(2000), nullable=False, default="")
    cpv_codes: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    keywords_matched: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    deadline: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    scraped_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    status: Mapped[TenderStatus] = mapped_column(
        Enum(TenderStatus, native_enum=False, length=20),
        default=TenderStatus.NEW,
        nullable=False,
    )
    category: Mapped[TenderCategory] = mapped_column(
        Enum(TenderCategory, native_enum=False, length=20),
        default=TenderCategory.TENDER,
        nullable=False,
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)

    status_history: Mapped[List["StatusChange"]] = relationship(
        back_populates="tender",
        cascade="all, delete-orphan",
        order_by="StatusChange.changed_at.desc()",
    )

    __table_args__ = (
        Index("ix_tenders_status", "status"),
        Index("ix_tenders_scraped_at", "scraped_at"),
        Index("ix_tenders_source", "source"),
        Index("ix_tenders_category", "category"),
    )


class StatusChange(Base):
    __tablename__ = "status_changes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tender_id: Mapped[int] = mapped_column(ForeignKey("tenders.id", ondelete="CASCADE"), nullable=False)
    from_status: Mapped[Optional[TenderStatus]] = mapped_column(
        Enum(TenderStatus, native_enum=False, length=20), nullable=True
    )
    to_status: Mapped[TenderStatus] = mapped_column(
        Enum(TenderStatus, native_enum=False, length=20), nullable=False
    )
    changed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    tender: Mapped[Tender] = relationship(back_populates="status_history")


class ScrapeRun(Base):
    __tablename__ = "scrape_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    adapter: Mapped[str] = mapped_column(String(100), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    found_count: Mapped[int] = mapped_column(Integer, default=0)
    new_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="OK")  # OK | ERROR
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_scrape_runs_adapter", "adapter"),
        Index("ix_scrape_runs_started_at", "started_at"),
    )
