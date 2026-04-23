"""Email digest sender."""
from __future__ import annotations

import logging
import smtplib
from datetime import datetime, timedelta
from email.message import EmailMessage
from pathlib import Path
from typing import List, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Tender
from app.services import fetch_new_since


logger = logging.getLogger(__name__)


_TEMPLATES_DIR = Path(__file__).parent / "templates"
_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)


def render_digest_html(tenders: List[Tender], dashboard_base_url: str) -> str:
    template = _env.get_template("email_digest.html")
    return template.render(
        tenders=tenders,
        dashboard_base_url=dashboard_base_url.rstrip("/"),
        generated_at=datetime.now(),
    )


def send_email(*, subject: str, html: str, to_addr: Optional[str] = None) -> None:
    """Send a single HTML email via the configured SMTP server."""
    to_addr = to_addr or settings.notification_email
    if not to_addr:
        logger.warning("No NOTIFICATION_EMAIL configured; skipping email send")
        return
    if not settings.smtp_host or not settings.smtp_user:
        logger.warning("SMTP not fully configured; skipping email send")
        return

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from or settings.smtp_user
    msg["To"] = to_addr
    msg.set_content("Twój klient pocztowy nie obsługuje HTML. Otwórz wiadomość w przeglądarce.")
    msg.add_alternative(html, subtype="html")

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as client:
        client.ehlo()
        client.starttls()
        client.login(settings.smtp_user, settings.smtp_password)
        client.send_message(msg)
    logger.info("Digest sent to %s (%d chars)", to_addr, len(html))


def send_daily_digest(session: Session, *, lookback_hours: int = 24) -> int:
    """Collect NEW tenders from the last N hours and mail them.

    Returns the number of tenders included (0 means no mail sent unless
    ``SEND_EMPTY_DIGEST`` is true).
    """
    since = datetime.utcnow() - timedelta(hours=lookback_hours)
    tenders = fetch_new_since(session, since)

    dashboard_url = f"http://{settings.dashboard_host}:{settings.dashboard_port}"

    if not tenders and not settings.send_empty_digest:
        logger.info("Digest: no new tenders since %s; not sending mail", since.isoformat())
        return 0

    html = render_digest_html(tenders, dashboard_url)
    today = datetime.now().strftime("%Y-%m-%d")
    subject = f"[Tender Aggregator] Nowości {today}: {len(tenders)} ogłoszeń"
    send_email(subject=subject, html=html)
    return len(tenders)
