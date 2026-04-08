from datetime import datetime
from sqlalchemy import String, Float, Integer, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class OuraToken(Base):
    __tablename__ = "oura_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String(255), index=True)
    access_token: Mapped[str] = mapped_column(Text)
    refresh_token: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SleepRecord(Base):
    __tablename__ = "sleep_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String(255), index=True)
    date: Mapped[str] = mapped_column(String(10), index=True)  # YYYY-MM-DD
    efficiency: Mapped[float] = mapped_column(Float, nullable=True)
    total_sleep_seconds: Mapped[int] = mapped_column(Integer, nullable=True)
    deep_sleep_seconds: Mapped[int] = mapped_column(Integer, nullable=True)
    rem_sleep_seconds: Mapped[int] = mapped_column(Integer, nullable=True)
    light_sleep_seconds: Mapped[int] = mapped_column(Integer, nullable=True)
    hrv_average: Mapped[float] = mapped_column(Float, nullable=True)
    resting_hr: Mapped[float] = mapped_column(Float, nullable=True)
    readiness_score: Mapped[int] = mapped_column(Integer, nullable=True)
    raw_json: Mapped[str] = mapped_column(Text, nullable=True)
    synced_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
