from datetime import datetime
from sqlalchemy import String, Integer, Float, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.encryption import EncryptedString
from app.database import Base
from app.core.time import utcnow_naive


class PelotonToken(Base):
    """Peloton session credentials. NOT OAuth — stores session cookie."""
    __tablename__ = "peloton_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String(255), index=True)
    peloton_user_id: Mapped[str] = mapped_column(String(255))
    # Encrypted at rest with Fernet (P1-1)
    session_id: Mapped[str] = mapped_column(EncryptedString(2000))
    username: Mapped[str] = mapped_column(String(255))  # For display only, not auth
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)
    last_used_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)


class WorkoutRecord(Base):
    """Workout data from any source (Peloton, Garmin, Apple Health)."""
    __tablename__ = "workout_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String(255), index=True)
    date: Mapped[str] = mapped_column(String(10), index=True)
    source: Mapped[str] = mapped_column(String(30))  # peloton, garmin, apple_health
    external_id: Mapped[str] = mapped_column(String(255), nullable=True)  # Source-specific workout ID
    workout_type: Mapped[str] = mapped_column(String(50))  # cycling, running, strength, yoga, etc.
    duration_seconds: Mapped[int] = mapped_column(Integer)
    calories: Mapped[int] = mapped_column(Integer, nullable=True)
    avg_heart_rate: Mapped[float] = mapped_column(Float, nullable=True)
    max_heart_rate: Mapped[float] = mapped_column(Float, nullable=True)
    avg_output: Mapped[float] = mapped_column(Float, nullable=True)  # Watts (Peloton-specific)
    instructor: Mapped[str] = mapped_column(String(100), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=True)
    raw_json: Mapped[str] = mapped_column(Text, nullable=True)
    synced_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)
