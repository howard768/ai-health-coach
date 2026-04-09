from datetime import datetime
from sqlalchemy import String, Integer, Float, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class GarminToken(Base):
    """Garmin session credentials. Stores serialized session blob."""
    __tablename__ = "garmin_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String(255), index=True)
    username: Mapped[str] = mapped_column(String(255))
    session_data: Mapped[str] = mapped_column(Text, nullable=True)  # Serialized session
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_used_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class GarminDailyRecord(Base):
    """Garmin-specific daily health data including unique metrics (body battery, stress)."""
    __tablename__ = "garmin_daily_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String(255), index=True)
    date: Mapped[str] = mapped_column(String(10), index=True)
    steps: Mapped[int] = mapped_column(Integer, nullable=True)
    avg_heart_rate: Mapped[float] = mapped_column(Float, nullable=True)
    max_heart_rate: Mapped[float] = mapped_column(Float, nullable=True)
    resting_heart_rate: Mapped[float] = mapped_column(Float, nullable=True)
    stress_avg: Mapped[float] = mapped_column(Float, nullable=True)
    body_battery_high: Mapped[int] = mapped_column(Integer, nullable=True)
    body_battery_low: Mapped[int] = mapped_column(Integer, nullable=True)
    active_minutes: Mapped[int] = mapped_column(Integer, nullable=True)
    raw_json: Mapped[str] = mapped_column(Text, nullable=True)
    synced_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
