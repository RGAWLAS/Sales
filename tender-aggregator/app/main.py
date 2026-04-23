"""FastAPI app: dashboard routes + mutation endpoints."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

from fastapi import Depends, FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.adapters.registry import ADAPTERS, get_adapter
from app.config import configure_logging, settings
from app.database import SessionLocal, get_session, init_db
from app.models import ScrapeRun, Tender, TenderStatus
from app.services import change_status, update_notes


logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="Tender Aggregator")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


# Register Polish status labels for templates.
STATUS_LABELS_PL = {
    TenderStatus.NEW: "Nowe",
    TenderStatus.INTERESTED: "Biorę udział",
    TenderStatus.NOT_INTERESTED: "Nie biorę",
    TenderStatus.APPLIED: "Złożono ofertę",
    TenderStatus.REJECTED: "Odrzucono",
    TenderStatus.WON: "Wygrane",
}

templates.env.globals["STATUS_LABELS_PL"] = STATUS_LABELS_PL
templates.env.globals["STATUSES"] = list(TenderStatus)


@app.on_event("startup")
def _on_startup() -> None:
    configure_logging()
    init_db()
    logger.info("FastAPI app starting; adapters registered: %d", len(ADAPTERS))


# ---- Dashboard ---------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def dashboard(
    request: Request,
    status: Optional[List[str]] = Query(default=None),
    source: Optional[List[str]] = Query(default=None),
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    q: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    page_size = 50

    filters = []
    if status:
        try:
            enums = [TenderStatus(s) for s in status]
        except ValueError:
            enums = []
        if enums:
            filters.append(Tender.status.in_(enums))
    else:
        filters.append(Tender.status == TenderStatus.NEW)

    if source:
        filters.append(Tender.source.in_(source))

    if date_from:
        try:
            filters.append(Tender.scraped_at >= datetime.fromisoformat(date_from))
        except ValueError:
            pass
    if date_to:
        try:
            filters.append(Tender.scraped_at <= datetime.fromisoformat(date_to))
        except ValueError:
            pass

    if q:
        like = f"%{q}%"
        filters.append(or_(Tender.title.ilike(like), Tender.organization.ilike(like)))

    where = and_(*filters) if filters else None

    total_stmt = select(func.count(Tender.id))
    if where is not None:
        total_stmt = total_stmt.where(where)
    total = session.execute(total_stmt).scalar_one()

    list_stmt = select(Tender)
    if where is not None:
        list_stmt = list_stmt.where(where)
    list_stmt = (
        list_stmt.order_by(Tender.scraped_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    tenders = list(session.execute(list_stmt).scalars().all())

    source_ids = [a.source_id for a in ADAPTERS]
    total_pages = max(1, (total + page_size - 1) // page_size)

    soon_threshold = datetime.utcnow() + timedelta(days=7)

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "tenders": tenders,
            "total": total,
            "page": page,
            "total_pages": total_pages,
            "source_ids": source_ids,
            "selected_status": status or [TenderStatus.NEW.value],
            "selected_source": source or [],
            "date_from": date_from or "",
            "date_to": date_to or "",
            "q": q or "",
            "soon_threshold": soon_threshold,
        },
    )


@app.get("/tender/{tender_id}", response_class=HTMLResponse)
def tender_detail(
    tender_id: int,
    request: Request,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    tender = session.get(Tender, tender_id)
    if tender is None:
        raise HTTPException(status_code=404, detail="Tender not found")

    return templates.TemplateResponse(
        "tender_detail.html",
        {"request": request, "tender": tender},
    )


@app.post("/tender/{tender_id}/status")
def post_status(
    tender_id: int,
    status: str = Form(...),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    try:
        target = TenderStatus(status)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid status")
    tender = change_status(session, tender_id, target)
    if tender is None:
        raise HTTPException(status_code=404, detail="Tender not found")
    return RedirectResponse(url=f"/tender/{tender_id}", status_code=303)


@app.post("/tender/{tender_id}/notes")
def post_notes(
    tender_id: int,
    notes: str = Form(""),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    tender = update_notes(session, tender_id, notes)
    if tender is None:
        raise HTTPException(status_code=404, detail="Tender not found")
    return RedirectResponse(url=f"/tender/{tender_id}", status_code=303)


@app.post("/tender/{tender_id}/quick-status")
def quick_status(
    tender_id: int,
    status: str = Form(...),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Inline list-view buttons that set status then return to dashboard."""
    try:
        target = TenderStatus(status)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid status")
    tender = change_status(session, tender_id, target)
    if tender is None:
        raise HTTPException(status_code=404, detail="Tender not found")
    return RedirectResponse(url="/", status_code=303)


# ---- Sources / adapter health ------------------------------------------------

@app.get("/sources", response_class=HTMLResponse)
def sources_page(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    stale_threshold = datetime.utcnow() - timedelta(days=7)
    rows = []
    for adapter in ADAPTERS:
        last_run = session.execute(
            select(ScrapeRun)
            .where(ScrapeRun.adapter == adapter.source_id)
            .order_by(ScrapeRun.started_at.desc())
            .limit(1)
        ).scalar_one_or_none()

        recent_new = session.execute(
            select(func.coalesce(func.sum(ScrapeRun.new_count), 0))
            .where(
                ScrapeRun.adapter == adapter.source_id,
                ScrapeRun.started_at >= stale_threshold,
            )
        ).scalar_one()

        rows.append({
            "adapter": adapter,
            "last_run": last_run,
            "recent_new": int(recent_new or 0),
            "stale": (recent_new or 0) == 0 and last_run is not None,
        })

    return templates.TemplateResponse(
        "sources.html",
        {"request": request, "rows": rows},
    )


@app.post("/sources/{source_id}/run")
def run_source_now(source_id: str) -> RedirectResponse:
    """Fire a one-off run of a single adapter in a background thread."""
    from threading import Thread
    from app.scheduler import run_adapter_once

    adapter = get_adapter(source_id)
    if adapter is None:
        raise HTTPException(status_code=404, detail="Unknown adapter")

    Thread(target=run_adapter_once, args=(adapter,), daemon=True).start()
    return RedirectResponse(url="/sources", status_code=303)
