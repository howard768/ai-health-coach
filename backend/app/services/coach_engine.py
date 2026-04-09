"""
Meld Coach Engine — Research-Informed AI Architecture

Implements 7 architectural principles from the AI research corpus:
1. Evidence-bound coaching (EviBound: 0% hallucination)
2. Deliberation-first routing (DOVA: 40-60% cost reduction)
3. Hierarchical memory (MAPLE/Memoria/HiMem)
4. Knowledge graph for cross-domain connections (GAAMA)
5. Multi-agent sub-tasks (memory, analysis, coaching)
6. Safety routing for concerning data (Health-ORSC-Bench, ILION)
7. Explainable model routing (Topaz)
"""

import json
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum

import anthropic
from app.config import settings

logger = logging.getLogger("meld.coach")


# ============================================================
# 7. EXPLAINABLE MODEL ROUTING (Topaz)
# Every routing decision is logged with reasoning.
# ============================================================

class ModelTier(Enum):
    RULES = "rules"          # No AI needed — deterministic answer
    HAIKU = "haiku"          # Simple formatting/summarization
    SONNET = "sonnet"        # Routine coaching, daily insights
    OPUS = "opus"            # Deep analysis, safety-critical, cross-domain


@dataclass
class RoutingDecision:
    tier: ModelTier
    reason: str
    confidence: float  # 0-1
    safety_flag: bool = False
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict:
        return {
            "tier": self.tier.value,
            "reason": self.reason,
            "confidence": self.confidence,
            "safety_flag": self.safety_flag,
            "timestamp": self.timestamp,
        }


# ============================================================
# 6. SAFETY ROUTING (Health-ORSC-Bench, ILION, MHDash)
# Pre-execution safety gates for concerning health data.
# ============================================================

@dataclass
class SafetyCheck:
    is_concerning: bool
    reasons: list[str]
    requires_disclaimer: bool
    requires_opus: bool

    @staticmethod
    def check_health_data(data: dict) -> "SafetyCheck":
        """Deterministic safety gates applied BEFORE any AI processing."""
        reasons = []
        concerning = False

        # HRV critically low (< 20ms suggests autonomic dysfunction)
        hrv = data.get("hrv_average")
        if hrv and hrv < 20:
            reasons.append(f"HRV critically low ({hrv}ms)")
            concerning = True

        # Resting HR elevated (> 100 bpm at rest is tachycardia)
        rhr = data.get("resting_hr")
        if rhr and rhr > 100:
            reasons.append(f"Resting HR elevated ({rhr} bpm)")
            concerning = True

        # Sleep efficiency critically low (< 50%)
        efficiency = data.get("sleep_efficiency")
        if efficiency and efficiency < 50:
            reasons.append(f"Sleep efficiency very low ({efficiency}%)")
            concerning = True

        # Readiness critically low
        readiness = data.get("readiness_score")
        if readiness and readiness < 20:
            reasons.append(f"Readiness critically low ({readiness})")
            concerning = True

        # Sudden large changes (> 30% deviation from baseline)
        baseline_hrv = data.get("baseline_hrv")
        if hrv and baseline_hrv and abs(hrv - baseline_hrv) / baseline_hrv > 0.3:
            reasons.append(f"HRV deviated {abs(hrv - baseline_hrv):.0f}ms from baseline")
            concerning = True

        return SafetyCheck(
            is_concerning=concerning,
            reasons=reasons,
            requires_disclaimer=concerning,
            requires_opus=concerning,
        )


# ============================================================
# 3. HIERARCHICAL MEMORY (MAPLE, Memoria, HiMem)
# Track what works for THIS user. Weight by recency.
# ============================================================

@dataclass
class UserMemory:
    """Persistent memory about what works for this specific user."""

    # What coaching advice they've engaged with
    effective_topics: dict[str, float] = field(default_factory=dict)  # topic → engagement score

    # What they tend to ask about
    frequent_queries: list[str] = field(default_factory=list)

    # Coaching style preferences (learned over time)
    prefers_detailed: bool = False  # vs concise
    prefers_actionable: bool = True  # vs explanatory
    responds_to_data: bool = True   # references specific numbers

    # Health patterns observed
    patterns: list[dict] = field(default_factory=list)

    def add_pattern(self, pattern: dict):
        """Add a cross-domain pattern with recency weighting."""
        pattern["discovered_at"] = datetime.utcnow().isoformat()
        pattern["weight"] = 1.0  # Decays over time (Memoria: exponential decay)
        self.patterns.append(pattern)

    def get_weighted_patterns(self, max_age_days: int = 30) -> list[dict]:
        """Return patterns weighted by recency (Memoria: exponential decay)."""
        cutoff = datetime.utcnow() - timedelta(days=max_age_days)
        active = []
        for p in self.patterns:
            discovered = datetime.fromisoformat(p["discovered_at"])
            if discovered > cutoff:
                age_days = (datetime.utcnow() - discovered).days
                p["weight"] = 0.95 ** age_days  # Exponential decay
                active.append(p)
        return sorted(active, key=lambda x: x["weight"], reverse=True)

    def to_context(self) -> str:
        """Convert memory to system prompt context."""
        lines = []
        if self.effective_topics:
            top_topics = sorted(self.effective_topics.items(), key=lambda x: x[1], reverse=True)[:3]
            lines.append(f"User responds well to: {', '.join(t[0] for t in top_topics)}")
        if self.patterns:
            recent = self.get_weighted_patterns(max_age_days=14)[:3]
            for p in recent:
                lines.append(f"Pattern found: {p.get('description', '')}")
        if self.prefers_actionable:
            lines.append("User prefers actionable advice over explanations.")
        return "\n".join(lines)


# ============================================================
# 4. KNOWLEDGE GRAPH (GAAMA)
# Structured relationships: food→sleep, protein→recovery
# ============================================================

@dataclass
class HealthConnection:
    """A discovered cross-domain relationship."""
    source_metric: str    # e.g., "protein_intake"
    target_metric: str    # e.g., "deep_sleep_duration"
    direction: str        # "positive" or "negative"
    strength: float       # 0-1 correlation strength
    evidence_days: int    # How many days of data support this
    literature_ref: str | None = None  # Published research citation

    def to_natural_language(self) -> str:
        """4th grade reading level description."""
        direction_word = "goes up" if self.direction == "positive" else "goes down"
        return f"When your {self.source_metric.replace('_', ' ')} is higher, your {self.target_metric.replace('_', ' ')} tends to {direction_word}."


class KnowledgeGraph:
    """Cross-domain health connections for this user."""

    def __init__(self):
        self.connections: list[HealthConnection] = []

        # Seed with literature-backed connections
        self._seed_literature_connections()

    def _seed_literature_connections(self):
        """Pre-populate with research-backed connections."""
        self.connections = [
            HealthConnection(
                source_metric="protein_intake",
                target_metric="deep_sleep_duration",
                direction="positive",
                strength=0.6,
                evidence_days=0,
                literature_ref="Halson, S.L. (2014). Sleep in Elite Athletes. Sports Medicine.",
            ),
            HealthConnection(
                source_metric="dinner_time",
                target_metric="sleep_efficiency",
                direction="negative",  # Later dinner → worse sleep
                strength=0.5,
                evidence_days=0,
                literature_ref="St-Onge et al. (2016). Effects of Diet on Sleep Quality. Advances in Nutrition.",
            ),
            HealthConnection(
                source_metric="exercise_intensity",
                target_metric="hrv_next_day",
                direction="positive",  # Hard training → higher HRV next day (if recovered)
                strength=0.4,
                evidence_days=0,
                literature_ref="Buchheit, M. (2014). Monitoring training status with HR measures.",
            ),
        ]

    def find_relevant_connections(self, metrics: list[str], min_strength: float = 0.3) -> list[HealthConnection]:
        """Find connections relevant to the given metrics."""
        relevant = []
        for conn in self.connections:
            if conn.strength >= min_strength:
                if conn.source_metric in metrics or conn.target_metric in metrics:
                    relevant.append(conn)
        return relevant


# ============================================================
# 2. DELIBERATION-FIRST ROUTING (DOVA, The Plausibility Trap)
# Check DB/rules before calling AI. 40-60% cost reduction.
# ============================================================

class Deliberator:
    """Decides whether a query needs AI or can be answered from rules/data."""

    # Deterministic rules that don't need AI
    RULES = {
        "readiness_high": "Your readiness is high. Today is good for a hard workout.",
        "readiness_moderate": "Your readiness is moderate. Keep it easy today.",
        "readiness_low": "Your body needs rest. Take it easy today.",
        "hrv_above_baseline": "Your HRV is above your average. Your body is handling stress well.",
        "hrv_below_baseline": "Your HRV is below your average. Your body may need more recovery.",
        "rhr_stable": "Your resting heart rate is stable. Your fitness level is consistent.",
        "rhr_dropping": "Your resting heart rate is dropping. Your fitness is improving.",
        "rhr_rising": "Your resting heart rate is going up. Watch your recovery and stress.",
    }

    @staticmethod
    def can_answer_from_rules(query: str, health_data: dict) -> tuple[bool, str | None]:
        """Check if the query can be answered deterministically."""

        query_lower = query.lower()

        # Readiness queries
        readiness = health_data.get("readiness_score", 0)
        if any(w in query_lower for w in ["readiness", "recovery", "ready", "push hard", "rest"]):
            if readiness >= 67:
                return True, Deliberator.RULES["readiness_high"]
            elif readiness >= 34:
                return True, Deliberator.RULES["readiness_moderate"]
            else:
                return True, Deliberator.RULES["readiness_low"]

        # HRV queries with clear baseline comparison
        hrv = health_data.get("hrv_average")
        baseline_hrv = health_data.get("baseline_hrv")
        if hrv and baseline_hrv and any(w in query_lower for w in ["hrv", "heart rate variability"]):
            if hrv > baseline_hrv * 1.05:
                return True, Deliberator.RULES["hrv_above_baseline"]
            elif hrv < baseline_hrv * 0.95:
                return True, Deliberator.RULES["hrv_below_baseline"]

        # Can't answer from rules — needs AI
        return False, None

    @staticmethod
    def route(query: str, health_data: dict, safety: SafetyCheck) -> RoutingDecision:
        """Determine the optimal model tier for this query.

        Priority order:
        1. Safety-critical → Opus (non-negotiable)
        2. Cross-domain / deep reasoning → Opus (needs synthesis)
        3. Simple factual → Rules (no AI cost)
        4. Everything else → Sonnet (routine coaching)
        """

        # 1. Safety-critical → always Opus
        if safety.requires_opus:
            return RoutingDecision(
                tier=ModelTier.OPUS,
                reason=f"Safety flag: {', '.join(safety.reasons)}",
                confidence=1.0,
                safety_flag=True,
            )

        # 2. Complex cross-domain queries → Opus (check BEFORE rules)
        query_lower = query.lower()
        cross_domain_keywords = ["why", "connect", "pattern", "correlation", "cause", "affect", "relationship", "correlate"]
        if any(w in query_lower for w in cross_domain_keywords):
            return RoutingDecision(
                tier=ModelTier.OPUS,
                reason="Cross-domain analysis requires deep reasoning",
                confidence=0.8,
            )

        # 3. Can answer from rules → no AI needed
        can_rule, _ = Deliberator.can_answer_from_rules(query, health_data)
        if can_rule:
            return RoutingDecision(
                tier=ModelTier.RULES,
                reason="Deterministic rule match",
                confidence=1.0,
            )

        # 4. Everything else → Sonnet
        return RoutingDecision(
            tier=ModelTier.SONNET,
            reason="Routine coaching query",
            confidence=0.9,
        )


# ============================================================
# 1. EVIDENCE-BOUND COACHING (EviBound: 0% hallucination)
# Every claim must cite specific data points.
# ============================================================

EVIDENCE_BOUND_SYSTEM_PROMPT = """You are a personal health coach for {user_name}. You provide evidence-based coaching.

CRITICAL RULES:
1. EVERY claim you make MUST reference a specific data point from the user's data below.
   - GOOD: "Your sleep efficiency was 91% last night, which is above your 7-day average of 85%."
   - BAD: "You had a great night of sleep." (no specific data cited)

2. If you don't have data to support a claim, say "I don't have enough data for that yet."

3. NEVER make up numbers. Only use the exact values provided below.

4. Write at a 4th grade reading level. Short sentences. Simple words.

5. Be warm but direct. Tell them what the data means and what to do.

6. You are a wellness coach, NOT a doctor. Never diagnose conditions.

{safety_disclaimer}

USER'S HEALTH DATA (cite these values):
{health_data}

USER'S GOALS: {goals}

{memory_context}

{knowledge_graph_context}
"""

SAFETY_DISCLAIMER = """
⚠️ IMPORTANT: Some of this user's health metrics are outside normal ranges.
Concerning values: {concerns}
Include a note suggesting they consult their healthcare provider if these patterns persist.
Do NOT diagnose or alarm — just gently suggest professional follow-up.
"""


# ============================================================
# 5. MULTI-AGENT PIPELINE (MAPLE, DOVA)
# Memory → Analysis → Coaching, each as a distinct step.
# ============================================================

class CoachEngine:
    """Research-informed AI coaching engine."""

    def __init__(self):
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.memory = UserMemory()  # TODO: persist to DB
        self.knowledge_graph = KnowledgeGraph()

    def process_query(
        self,
        query: str,
        health_data: dict,
        user_name: str = "Brock",
        user_goals: list[str] | None = None,
        history: list[dict] | None = None,
    ) -> dict:
        """Full multi-agent pipeline for processing a coaching query.

        Returns dict with: response, routing_decision, safety_check, evidence_citations
        """

        # Step 1: Safety check (ILION: deterministic pre-execution gates)
        safety = SafetyCheck.check_health_data(health_data)
        logger.info(f"Safety check: concerning={safety.is_concerning}, reasons={safety.reasons}")

        # Step 2: Deliberation-first routing (DOVA: decide before computing)
        routing = Deliberator.route(query, health_data, safety)
        logger.info(f"Routing: tier={routing.tier.value}, reason={routing.reason}")

        # Step 3: If rules can answer, return immediately (no AI cost)
        if routing.tier == ModelTier.RULES:
            _, rule_answer = Deliberator.can_answer_from_rules(query, health_data)
            return {
                "response": rule_answer,
                "routing": routing.to_dict(),
                "safety": {"is_concerning": False},
                "evidence_citations": [],
                "model_used": "rules",
            }

        # Step 4: Build evidence-bound prompt with memory + knowledge graph
        memory_context = self.memory.to_context()
        kg_connections = self.knowledge_graph.find_relevant_connections(
            list(health_data.keys())
        )
        kg_context = ""
        if kg_connections:
            kg_context = "KNOWN HEALTH CONNECTIONS (cite if relevant):\n"
            for conn in kg_connections:
                kg_context += f"- {conn.to_natural_language()}"
                if conn.literature_ref:
                    kg_context += f" (Source: {conn.literature_ref})"
                kg_context += "\n"

        safety_disclaimer = ""
        if safety.requires_disclaimer:
            safety_disclaimer = SAFETY_DISCLAIMER.format(
                concerns=", ".join(safety.reasons)
            )

        system_prompt = EVIDENCE_BOUND_SYSTEM_PROMPT.format(
            user_name=user_name,
            health_data=json.dumps(health_data, indent=2),
            goals=", ".join(user_goals or ["general wellness"]),
            memory_context=f"USER PREFERENCES (learned over time):\n{memory_context}" if memory_context else "",
            knowledge_graph_context=kg_context,
            safety_disclaimer=safety_disclaimer,
        )

        # Step 5: Call the appropriate model tier
        model = self._get_model(routing.tier)

        messages = []
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": query})

        try:
            response = self.client.messages.create(
                model=model,
                max_tokens=500,
                system=system_prompt,
                messages=messages,
            )
            response_text = response.content[0].text if response.content else "I'm having trouble right now. Please try again."
        except Exception as e:
            logger.error("Claude API call failed: %s", e)
            return {
                "response": "I'm having trouble connecting right now. Please try again in a moment.",
                "routing": routing.to_dict(),
                "safety": {"is_concerning": False},
                "model_used": model,
                "tokens": {"input": 0, "output": 0},
            }

        # Step 6: Log for explainability (Topaz)
        logger.info(f"Model used: {model}, tokens: {response.usage.input_tokens}+{response.usage.output_tokens}")

        return {
            "response": response_text,
            "routing": routing.to_dict(),
            "safety": {
                "is_concerning": safety.is_concerning,
                "reasons": safety.reasons,
                "disclaimer_included": safety.requires_disclaimer,
            },
            "model_used": model,
            "tokens": {
                "input": response.usage.input_tokens,
                "output": response.usage.output_tokens,
            },
        }

    def generate_daily_insight(self, health_data: dict, user_goals: list[str] | None = None) -> dict:
        """Generate the daily coaching insight for the dashboard."""
        return self.process_query(
            query="Generate a brief daily coaching insight based on my latest health data. Be specific about the numbers.",
            health_data=health_data,
            user_goals=user_goals,
        )

    def _get_model(self, tier: ModelTier) -> str:
        """Map tier to Anthropic model ID."""
        return {
            ModelTier.HAIKU: "claude-haiku-4-5-20251001",
            ModelTier.SONNET: "claude-sonnet-4-20250514",
            ModelTier.OPUS: "claude-opus-4-20250514",
        }.get(tier, "claude-sonnet-4-20250514")
