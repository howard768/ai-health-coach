from pydantic import BaseModel


class MetricResponse(BaseModel):
    category: str
    label: str
    value: str
    unit: str
    subtitle: str
    trend: str  # "positive", "neutral", "negative"


class RecoveryResponse(BaseModel):
    level: str  # "High", "Moderate", "Low"
    description: str


class CoachInsightResponse(BaseModel):
    message: str
    timestamp: str


class DashboardResponse(BaseModel):
    greeting: str
    date: str
    metrics: list[MetricResponse]
    recovery: RecoveryResponse
    coach_insight: CoachInsightResponse
    last_synced: str | None = None
