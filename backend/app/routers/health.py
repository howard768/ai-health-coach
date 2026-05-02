import logging
from datetime import datetime, date, timedelta

import anthropic
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func

from app.api.deps import CurrentUser
from app.core.constants import ReadinessThreshold
from app.core.time import utcnow_naive
from app.database import get_db
from app.models.health import OuraToken, SleepRecord
from app.models.meal import MealRecord, FoodItemRecord
from app.models.user import User
from app.schemas.health import DashboardResponse, MetricResponse, RecoveryResponse, CoachInsightResponse
from app.services.claude import ClaudeClient
from app.services.oura_sync import sync_user_data
from app.services.health_data import get_latest_health_data

logger = logging.getLogger("meld.health")

# On-demand sync throttle window. If OuraToken.last_synced_at is within
# this window, the dashboard endpoint skips its refresh pass. Chosen to
# balance: (1) "open app, see today's data" UX, (2) Oura's 5000 req/day
# quota, (3) Oura webhooks are eventual, not instant. 30 min means 48 max
# auto-syncs/day even with the app constantly reloaded.
_OURA_REFRESH_THRESHOLD = timedelta(minutes=30)


def _first_name_of(user: User) -> str:
    """Get the user's first name for greetings, or empty string if no name."""
    if user.name:
        return user.name.split()[0]
    return ""


async def _maybe_refresh_oura(db: AsyncSession, user_id: str) -> None:
    """Trigger an Oura sync if stored data is stale.

    Gated by `OuraToken.last_synced_at`, which sync_user_data bumps on
    every successful call. If it's within the refresh threshold, no-op.
    Otherwise do a foreground sync — the Oura API is fast enough (~1-2s)
    that blocking the dashboard response is imperceptible, and the user
    gets fresh data in the same round trip.

    NOTE: The staleness check was originally on `max(SleepRecord.synced_at)`,
    which was broken: `sync_user_data` skips existing rows during dedup, so
    that column only reflected the first successful pull of a given day.
    Every subsequent dashboard load >30 min later would keep re-hitting
    Oura forever. Fixed by adding `OuraToken.last_synced_at` which tracks
    "when did we last talk to Oura" instead.

    Silent on error: if Oura's API is down or the token is revoked, the
    dashboard still renders from cached data. Errors are logged but not
    surfaced to the user.
    """
    # Find the user's Oura token. No token → no sync possible → bail.
    result = await db.execute(
        select(OuraToken)
        .where(OuraToken.user_id == user_id)
        .order_by(desc(OuraToken.created_at))
        .limit(1)
    )
    token = result.scalar_one_or_none()
    if token is None:
        return

    # Throttle: if we synced within the threshold, no-op. NULL
    # last_synced_at (fresh schema migration, never synced) falls
    # through to the sync below, which is what we want.
    if token.last_synced_at is not None:
        age = utcnow_naive() - token.last_synced_at
        if age < _OURA_REFRESH_THRESHOLD:
            return

    # Stale or never synced — kick off a foreground sync.
    try:
        result = await sync_user_data(db, user_id)
        logger.info("On-demand Oura sync: %s", result)
    except Exception as e:  # noqa: BLE001  — intentionally broad
        # This is the dashboard endpoint — it MUST render from cached data
        # when Oura is broken, regardless of which exception sync_user_data
        # surfaces. P2-6 narrowed exceptions everywhere else; this single
        # call is kept broad because the safety net is the whole point.
        # Capture to Sentry: in the 2026-04-29 incident era, Oura sync was
        # broken for 10 days and only WARN logs surfaced it. Don't repeat.
        logger.warning("On-demand Oura sync failed, serving cached data: %s", e)
        try:
            import sentry_sdk
            with sentry_sdk.push_scope() as scope:
                scope.set_tag("oura_action", "on_demand_sync")
                scope.set_tag("user_id_prefix", (user_id or "")[:12])
                sentry_sdk.capture_exception(e)
        except Exception:  # noqa: BLE001 -- never let Sentry crash the request
            logger.debug("Sentry capture failed (non-fatal)", exc_info=True)


router = APIRouter(prefix="/api", tags=["health"])


@router.get("/trends")
async def get_trends(
    current_user: CurrentUser,
    range: int = 7,
    db: AsyncSession = Depends(get_db),
):
    """Historical health metric trends for a given number of days.

    Returns arrays of values, dates, baselines, and personal ranges per metric.
    """
    # range=7 means "7 days including today": today minus 6 = 7 days total
    start_date = (date.today() - timedelta(days=range - 1)).isoformat()

    result = await db.execute(
        select(SleepRecord)
        .where(SleepRecord.user_id == current_user.apple_user_id, SleepRecord.date >= start_date)
        .order_by(SleepRecord.date)
    )
    records = list(result.scalars().all())

    if not records:
        return {"range_days": range, "metrics": {}, "nutrition": None}

    def build_metric(values):
        clean = [v for v in values if v is not None]
        if not clean:
            return {"values": [], "dates": [], "baseline": 0, "personal_min": 0, "personal_max": 0, "personal_average": 0}
        return {
            "values": clean,
            "baseline": round(sum(clean) / len(clean), 1),
            "personal_min": round(min(clean), 1),
            "personal_max": round(max(clean), 1),
            "personal_average": round(sum(clean) / len(clean), 1),
        }

    dates = [r.date for r in records]
    sleep_eff = build_metric([r.efficiency for r in records])
    sleep_eff["dates"] = dates
    resting_hr = build_metric([r.resting_hr for r in records])
    resting_hr["dates"] = dates
    readiness = build_metric([r.readiness_score for r in records])
    readiness["dates"] = dates
    hrv = build_metric([r.hrv_average for r in records])
    hrv["dates"] = dates

    # Nutrition summary over the same window
    nutrition_result = await db.execute(
        select(
            MealRecord.date,
            func.sum(FoodItemRecord.protein).label("total_protein"),
            func.sum(FoodItemRecord.calories).label("total_calories"),
        )
        .join(FoodItemRecord, FoodItemRecord.meal_id == MealRecord.id)
        .where(MealRecord.user_id == current_user.apple_user_id, MealRecord.date >= start_date)
        .group_by(MealRecord.date)
    )
    nutrition_rows = list(nutrition_result)

    target_calories = 2000.0
    target_protein = 100.0
    if nutrition_rows:
        days_logged = len(nutrition_rows)
        avg_protein = round(sum(float(r.total_protein or 0) for r in nutrition_rows) / days_logged, 1)
        avg_calories = round(sum(float(r.total_calories or 0) for r in nutrition_rows) / days_logged, 1)
        days_in_range = sum(
            1 for r in nutrition_rows
            if r.total_calories and abs(float(r.total_calories) - target_calories) / target_calories <= 0.15
        )
        nutrition = {
            "avg_protein_g": avg_protein,
            "avg_calories": avg_calories,
            "target_protein_g": target_protein,
            "target_calories": target_calories,
            "days_logged": days_logged,
            "days_in_range": days_in_range,
        }
    else:
        nutrition = None

    return {
        "range_days": range,
        "metrics": {
            "sleep_efficiency": sleep_eff,
            "resting_hr": resting_hr,
            "readiness": readiness,
            "hrv": hrv,
        },
        "nutrition": nutrition,
    }


@router.get("/trends/patterns")
async def get_trend_patterns(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    days: int = 30,
):
    """Cross-domain pattern insights derived from sleep and nutrition data.

    `days` controls the lookback window. The Trends tab passes 7, 30, or 90
    based on the timeframe selector; without this param the coach insight
    card was pinned to a 30-day default regardless of the user's view.
    Clamped to [1, 365] so a malformed query can't run an unbounded scan.
    """
    days = max(1, min(days, 365))
    window_start = (date.today() - timedelta(days=days)).isoformat()

    sleep_result = await db.execute(
        select(SleepRecord)
        .where(SleepRecord.user_id == current_user.apple_user_id, SleepRecord.date >= window_start)
        .order_by(SleepRecord.date)
    )
    sleep_records = list(sleep_result.scalars().all())

    if not sleep_records:
        return {"patterns": []}

    days_total = len(sleep_records)

    # Load daily nutrition totals for the same window
    nutrition_result = await db.execute(
        select(
            MealRecord.date,
            func.sum(FoodItemRecord.protein).label("total_protein"),
            func.sum(FoodItemRecord.calories).label("total_calories"),
        )
        .join(FoodItemRecord, FoodItemRecord.meal_id == MealRecord.id)
        .where(MealRecord.user_id == current_user.apple_user_id, MealRecord.date >= window_start)
        .group_by(MealRecord.date)
    )
    nutrition_by_date = {
        row.date: {"protein": float(row.total_protein or 0), "calories": float(row.total_calories or 0)}
        for row in nutrition_result
    }

    patterns = []

    # Pattern 1: High sleep efficiency nights correlate with higher HRV
    high_eff = [r for r in sleep_records if r.efficiency is not None and r.efficiency >= 85 and r.hrv_average]
    low_eff = [r for r in sleep_records if r.efficiency is not None and r.efficiency < 75 and r.hrv_average]
    if len(high_eff) >= 3 and len(low_eff) >= 2:
        avg_high_hrv = sum(r.hrv_average for r in high_eff) / len(high_eff)
        avg_low_hrv = sum(r.hrv_average for r in low_eff) / len(low_eff)
        if avg_high_hrv > avg_low_hrv * 1.04:
            confidence = min(0.95, 0.55 + len(high_eff) / days_total)
            patterns.append({
                "pattern_text": (
                    f"Your HRV averages {int(avg_high_hrv)}ms on nights with >85% sleep efficiency, "
                    f"vs {int(avg_low_hrv)}ms on poor nights."
                ),
                "confidence": round(confidence, 2),
                "days_matched": len(high_eff),
                "days_total": days_total,
            })

    # Pattern 2: High protein intake correlates with better readiness
    if nutrition_by_date:
        paired = [
            (nutrition_by_date[r.date]["protein"], r.readiness_score)
            for r in sleep_records
            if r.date in nutrition_by_date and r.readiness_score is not None
        ]
        if len(paired) >= 4:
            high_p = [(p, r) for p, r in paired if p >= 120]
            low_p = [(p, r) for p, r in paired if p < 80]
            if len(high_p) >= 2 and len(low_p) >= 2:
                avg_r_high = sum(r for _, r in high_p) / len(high_p)
                avg_r_low = sum(r for _, r in low_p) / len(low_p)
                if avg_r_high > avg_r_low * 1.04:
                    confidence = min(0.90, 0.48 + len(high_p) / days_total)
                    patterns.append({
                        "pattern_text": (
                            f"On days you hit 120g+ protein, your readiness score averages "
                            f"{int(avg_r_high)} vs {int(avg_r_low)} on lower-protein days."
                        ),
                        "confidence": round(confidence, 2),
                        "days_matched": len(high_p),
                        "days_total": days_total,
                    })

    # Pattern 3: Resting HR trend vs period baseline (fitness improvement signal)
    rhr_records = [r for r in sleep_records if r.resting_hr is not None]
    if len(rhr_records) >= 7:
        half = len(rhr_records) // 2
        avg_first = sum(r.resting_hr for r in rhr_records[:half]) / half
        avg_second = sum(r.resting_hr for r in rhr_records[half:]) / (len(rhr_records) - half)
        if avg_second < avg_first * 0.97:
            drop = round(avg_first - avg_second, 1)
            patterns.append({
                "pattern_text": (
                    f"Your resting heart rate dropped {drop} bpm over the last 30 days — "
                    "a sign your cardiovascular fitness is improving."
                ),
                "confidence": 0.88,
                "days_matched": len(rhr_records),
                "days_total": days_total,
            })

    # Return top 3 by confidence
    patterns.sort(key=lambda p: p["confidence"], reverse=True)
    return {"patterns": patterns[:3]}


@router.post("/health/apple-health")
async def sync_apple_health(
    metrics: list[dict],
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Batch sync HealthKit data from iOS device.

    Each metric: {date, metric_type, value, unit, source}
    Writes to HealthMetricRecord for reconciliation.
    """
    from app.models.health import HealthMetricRecord

    # Cap at 1000 metrics per request to prevent DoS (P1-5 fix)
    if len(metrics) > 1000:
        raise HTTPException(status_code=413, detail="Max 1000 metrics per request")

    user_id = current_user.apple_user_id
    saved = 0
    for m in metrics:
        # Check for existing record (dedup by user+date+metric+source)
        existing = await db.execute(
            select(HealthMetricRecord).where(
                HealthMetricRecord.user_id == user_id,
                HealthMetricRecord.date == m.get("date", ""),
                HealthMetricRecord.metric_type == m.get("metric_type", ""),
                HealthMetricRecord.source == m.get("source", "apple_health"),
            )
        )
        if existing.scalar_one_or_none():
            continue

        record = HealthMetricRecord(
            user_id=user_id,
            date=m.get("date", ""),
            metric_type=m.get("metric_type", ""),
            value=float(m.get("value", 0)),
            unit=m.get("unit", ""),
            source=m.get("source", "apple_health"),
        )
        db.add(record)
        saved += 1

    if saved:
        await db.commit()
        # Run reconciliation for today
        from app.services.data_reconciliation import reconcile_day
        today = datetime.now().strftime("%Y-%m-%d")
        await reconcile_day(db, user_id, today)

    return {"status": "ok", "records_saved": saved}


@router.get("/health/canary")
async def health_canary(
    db: AsyncSession = Depends(get_db),
):
    """Synthetic health check: is the data pipeline producing fresh data?

    No auth required — designed for uptime monitoring and CI canary checks.

    MEL-45 part 2: returns AGGREGATE counts only, NEVER per-user data.
    Pre-PR-MEL-45 this endpoint returned the first active user's reconciled
    health metrics, which was a PHI leak in multi-user mode (any unauthed
    caller got an arbitrary user's sleep/HRV/RHR). Now the response is
    aggregate signals only:

      - users_with_data_24h: how many distinct users wrote a sleep record
        in the last 24h (proves the pipeline is producing data for someone)
      - active_oura_connections: how many OuraToken rows exist (proves the
        sync infrastructure has connected accounts)

    `status` is "ok" when fresh data is being written, "degraded" otherwise.
    """
    # Count active users. MEL-45 part 4: the 'default' placeholder row was
    # dropped in migration e9c3f7b285a1, so we no longer need to filter it out.
    user_count_result = await db.execute(
        select(func.count(User.id)).where(
            User.is_active == True,  # noqa: E712 -- SQLAlchemy boolean comparison
        )
    )
    active_user_count = user_count_result.scalar() or 0

    # Users who wrote a sleep record in the last 24h (cheap freshness check).
    # Pass a real datetime, not isoformat() — `synced_at` is a DateTime column
    # and Postgres rejects implicit string-to-timestamp coercion (SQLite is
    # lenient and would let a string compare slip through).
    twenty_four_hrs_ago = utcnow_naive() - timedelta(hours=24)
    fresh_users_result = await db.execute(
        select(func.count(func.distinct(SleepRecord.user_id))).where(
            SleepRecord.synced_at >= twenty_four_hrs_ago,
        )
    )
    users_with_data_24h = fresh_users_result.scalar() or 0

    # Connected Oura accounts
    oura_count_result = await db.execute(select(func.count(OuraToken.id)))
    active_oura_connections = oura_count_result.scalar() or 0

    pipeline_healthy = users_with_data_24h > 0
    return {
        "status": "ok" if pipeline_healthy else "degraded",
        "active_users": active_user_count,
        "users_with_data_24h": users_with_data_24h,
        "active_oura_connections": active_oura_connections,
    }


@router.post("/sync/oura")
async def sync_oura(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Pull latest data from Oura API and store in DB."""
    return await sync_user_data(db, current_user.apple_user_id)


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Dashboard data — reads from reconciled multi-source health data.

    On-demand sync: if OuraToken.last_synced_at is older than the refresh
    threshold (30 min), trigger a foreground Oura pull before rendering.
    Keeps the dashboard fresh without waiting for the background scheduler
    job. Throttled by last_synced_at so rapid reloads don't hammer Oura's
    API quota.
    """

    hour = datetime.now().hour
    time_of_day = "morning" if 5 <= hour < 12 else "afternoon" if 12 <= hour < 17 else "evening" if 17 <= hour < 22 else "night"

    first_name = _first_name_of(current_user)
    greeting = f"Good {time_of_day}, {first_name}" if first_name else f"Good {time_of_day}"

    # Auto-sync if data is stale. Staleness check uses the most recent
    # SleepRecord's synced_at; if older than 30 min (or no record at all),
    # pull fresh Oura data before rendering. This is the only place we do
    # on-demand sync — meals, workouts, etc. stay on the scheduler.
    await _maybe_refresh_oura(db, current_user.apple_user_id)

    # Load reconciled data (multi-source: Oura + Apple Health + Garmin + Peloton)
    health_data = await get_latest_health_data(db, current_user.apple_user_id)

    if not health_data:
        return DashboardResponse(
            greeting=greeting,
            date=datetime.now().strftime("%A, %B %-d"),
            metrics=[],
            recovery=RecoveryResponse(level="High", description="Connect a data source to start"),
            coach_insight=CoachInsightResponse(
                message="Connect your Oura Ring or Apple Health to see coaching insights based on your real data.",
                timestamp=datetime.now().isoformat(),
            ),
            last_synced=None,
        )

    # Extract values from reconciled data
    efficiency = health_data.get("sleep_efficiency", 0)
    sleep_hours = health_data.get("sleep_duration_hours", 0)
    hours = int(sleep_hours)
    mins = int((sleep_hours - hours) * 60)
    rhr = health_data.get("resting_hr", 0)
    hrv = health_data.get("hrv_average", 0)
    readiness = health_data.get("readiness_score", 0)
    steps = health_data.get("steps", 0)
    baseline_rhr = health_data.get("baseline_rhr", rhr)
    baseline_hrv = health_data.get("baseline_hrv", hrv)
    sources = health_data.get("data_sources", {})

    readiness_level = (
        "High" if readiness >= ReadinessThreshold.HIGH
        else "Moderate" if readiness >= ReadinessThreshold.MODERATE
        else "Low"
    )
    readiness_desc = {
        "High": "Good for hard training today",
        "Moderate": "Keep it easy today",
        "Low": "Your body needs rest today",
    }.get(readiness_level, "")

    # Trends
    eff_trend = "positive" if efficiency > 75 else "negative" if efficiency < 60 else "neutral"
    rhr_diff = baseline_rhr - rhr
    rhr_trend = "positive" if rhr_diff > 1 else "negative" if rhr_diff < -1 else "neutral"
    rhr_delta = (
        f"{'Down' if rhr_diff > 0 else 'Up'} {abs(int(rhr_diff))} bpm vs avg"
        if abs(rhr_diff) >= 1 else "Stable"
    )

    # Source attribution — pretty labels we reuse in every metric subtitle
    def _pretty_source(raw: str) -> str:
        return raw.replace("_", " ").title() if raw else ""

    sleep_source = _pretty_source(sources.get("sleep_efficiency", ""))
    rhr_source = _pretty_source(sources.get("resting_hr", ""))
    hrv_source = _pretty_source(sources.get("hrv", ""))
    steps_source = _pretty_source(sources.get("steps", "device"))

    def _with_source(primary: str, source: str) -> str:
        """Append ' · via Source' to a subtitle, skipping if source is empty."""
        if not source:
            return primary
        if not primary:
            return f"via {source}"
        return f"{primary} · via {source}"

    # Generate coaching insight
    insight_context = {
        "sleep_efficiency": f"{int(efficiency)}%",
        "sleep_duration": f"{hours}h {mins}m",
        "resting_hr": f"{int(rhr)} bpm",
        "readiness": readiness_level,
        "readiness_score": readiness,
    }
    try:
        import asyncio
        user_goals = current_user.goals or []
        claude = ClaudeClient()
        insight_text = await asyncio.to_thread(
            claude.generate_insight, insight_context, user_goals
        )
    except anthropic.APIError:
        insight_text = f"Your sleep efficiency was {int(efficiency)}% with {hours}h {mins}m of total sleep. Readiness is {readiness_level.lower()}."

    metrics = [
        MetricResponse(
            category="sleepEfficiency", label="Sleep Efficiency",
            value=str(int(efficiency)), unit="%",
            subtitle=_with_source(f"{hours}h {mins}m total", sleep_source), trend=eff_trend,
        ),
    ]
    if hrv:
        hrv_diff = hrv - baseline_hrv
        hrv_pct = int(abs(hrv_diff) / max(baseline_hrv, 1) * 100)
        hrv_trend = "positive" if hrv_diff > 0 else "negative" if hrv_diff < 0 else "neutral"
        hrv_delta = (
            f"{'Up' if hrv_diff > 0 else 'Down'} {hrv_pct}% vs baseline"
            if hrv_pct > 2 else "Stable"
        )
        metrics.append(MetricResponse(
            category="hrv", label="HRV Status",
            value=str(int(hrv)), unit="ms",
            subtitle=_with_source(hrv_delta, hrv_source), trend=hrv_trend,
        ))
    if rhr:
        metrics.append(MetricResponse(
            category="restingHR", label="Resting HR",
            value=str(int(rhr)), unit="bpm",
            subtitle=_with_source(rhr_delta, rhr_source), trend=rhr_trend,
        ))
    if steps:
        metrics.append(MetricResponse(
            category="consistency", label="Steps",
            value=f"{int(steps):,}", unit="steps",
            subtitle=f"via {steps_source}" if steps_source else "steps",
            trend="positive" if steps > 5000 else "neutral",
        ))

    return DashboardResponse(
        greeting=greeting,
        date=datetime.now().strftime("%A, %B %-d"),
        metrics=metrics,
        recovery=RecoveryResponse(level=readiness_level, description=readiness_desc),
        coach_insight=CoachInsightResponse(
            message=insight_text,
            timestamp=datetime.now().isoformat(),
        ),
        last_synced=datetime.now().isoformat(),
    )
