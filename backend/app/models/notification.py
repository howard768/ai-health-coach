from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Text, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.core.time import utcnow_naive


class DeviceToken(Base):
    __tablename__ = "device_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String(255), index=True)
    token: Mapped[str] = mapped_column(String(255), unique=True)
    platform: Mapped[str] = mapped_column(String(20), default="ios")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive, onupdate=utcnow_naive)


class NotificationRecord(Base):
    __tablename__ = "notification_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String(255), index=True)
    device_token_id: Mapped[int] = mapped_column(Integer, nullable=True)
    category: Mapped[str] = mapped_column(String(50), index=True)  # morning_brief, coaching_nudge, etc.
    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)
    opened_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    morning_brief: Mapped[bool] = mapped_column(Boolean, default=True)
    coaching_nudge: Mapped[bool] = mapped_column(Boolean, default=True)
    bedtime_coaching: Mapped[bool] = mapped_column(Boolean, default=True)
    streak_alerts: Mapped[bool] = mapped_column(Boolean, default=True)
    weekly_review: Mapped[bool] = mapped_column(Boolean, default=True)
    # P3-1: workout_reminders is plumbed end-to-end (model + API + iOS struct)
    # but no scheduler job emits them yet. Keeping the column so we don't have
    # to migrate twice when the feature ships. The iOS UI does not expose a
    # toggle, so this stays at the default `False` for now.
    workout_reminders: Mapped[bool] = mapped_column(Boolean, default=False)
    health_alerts: Mapped[bool] = mapped_column(Boolean, default=True)
    nudge_frequency: Mapped[str] = mapped_column(String(20), default="2x_week")  # daily, 2x_week, weekly
    quiet_hours_start: Mapped[str] = mapped_column(String(5), default="22:00")
    quiet_hours_end: Mapped[str] = mapped_column(String(5), default="07:00")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive, onupdate=utcnow_naive)


class NotificationTemplate(Base):
    """Pre-authored notification content variants.

    Templates use {variable} interpolation for personalization.
    Available variables: {user_name}, {streak_count}, {streak_goal},
    {recovery_level}, {week_sleep_delta}, {week_workout_days}.
    """
    __tablename__ = "notification_templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    category: Mapped[str] = mapped_column(String(50), index=True)
    context: Mapped[str] = mapped_column(String(50), index=True)
    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)
