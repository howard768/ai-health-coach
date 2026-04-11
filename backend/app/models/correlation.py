from datetime import datetime
from sqlalchemy import String, Integer, Float, DateTime, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.core.time import utcnow_naive


class UserCorrelation(Base):
    """Discovered cross-domain correlations for a specific user.

    Populated by the correlation engine running weekly.
    Confidence tiers: emerging → developing → established → literature_supported.
    """
    __tablename__ = "user_correlations"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String(255), index=True)
    source_metric: Mapped[str] = mapped_column(String(100))
    target_metric: Mapped[str] = mapped_column(String(100))
    lag_days: Mapped[int] = mapped_column(Integer, default=0)
    direction: Mapped[str] = mapped_column(String(10))  # positive, negative
    pearson_r: Mapped[float] = mapped_column(Float)
    spearman_r: Mapped[float] = mapped_column(Float)
    p_value: Mapped[float] = mapped_column(Float)
    fdr_adjusted_p: Mapped[float] = mapped_column(Float)
    sample_size: Mapped[int] = mapped_column(Integer)
    strength: Mapped[float] = mapped_column(Float)  # abs(r), 0-1
    confidence_tier: Mapped[str] = mapped_column(String(30))  # emerging, developing, established, literature_supported
    literature_match: Mapped[bool] = mapped_column(Boolean, default=False)
    literature_ref: Mapped[str] = mapped_column(Text, nullable=True)
    effect_size_description: Mapped[str] = mapped_column(Text)
    discovered_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)
    last_validated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)
