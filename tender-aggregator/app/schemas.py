"""Pydantic schemas for API I/O."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict

from app.models import TenderCategory, TenderStatus


class TenderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str
    external_id: str
    title: str
    description: str
    organization: str
    url: str
    cpv_codes: List[str]
    keywords_matched: List[str]
    published_at: Optional[datetime]
    deadline: Optional[datetime]
    scraped_at: datetime
    status: TenderStatus
    category: TenderCategory
    notes: Optional[str]


class StatusUpdate(BaseModel):
    status: TenderStatus


class NotesUpdate(BaseModel):
    notes: str


class ScrapeRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    adapter: str
    started_at: datetime
    finished_at: Optional[datetime]
    found_count: int
    new_count: int
    status: str
    error_message: Optional[str]
