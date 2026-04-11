"""Waitlist signup model — captures pre-launch email signups from heymeld.com.

Unlike User (which is scoped to authenticated iOS app users), a WaitlistSignup
is a cold lead: just an email + the campaign it came from. No PII beyond that.

Dedupe key: lowercased email. Re-submissions touch `updated_at` rather than
creating a duplicate row, so we can track when someone re-engaged with the site.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utcnow_naive
from app.database import Base


class WaitlistSignup(Base):
    __tablename__ = "waitlist_signups"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Lowercased email is the natural dedupe key.
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)

    # Where on the site the submission came from — "hero", "final_cta", etc.
    # Used to A/B which section converts best.
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # UTM parameters preserved from the submission URL, for campaign attribution.
    utm_source: Mapped[str | None] = mapped_column(String(128), nullable=True)
    utm_medium: Mapped[str | None] = mapped_column(String(128), nullable=True)
    utm_campaign: Mapped[str | None] = mapped_column(String(128), nullable=True)
    utm_term: Mapped[str | None] = mapped_column(String(128), nullable=True)
    utm_content: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # Referer domain if the visitor came from an inbound link (not the submission URL).
    referer: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # IP address hash (never the raw IP) for bot-detection / dedup heuristics.
    # We hash server-side to avoid storing raw PII unnecessarily.
    ip_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # User-agent string, truncated. Helps diagnose cases where a phone browser
    # submission looks different from a desktop one.
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Whether we've sent a launch email to this address yet.
    notified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Number of times this email has been submitted (re-submissions bump this).
    submissions: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow_naive, onupdate=utcnow_naive, nullable=False
    )
