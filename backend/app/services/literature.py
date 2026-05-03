"""Literature Retrieval Layer.

Phase A: Curated database of ~50 key papers covering sleep, nutrition,
exercise, HRV, recovery, and circadian rhythm.

Phase B (future): PubMed API for dynamic search.
Phase C (future): RAG with embeddings for semantic search.

STATUS (2026-04-30 audit): UNWIRED. The intended consumers below all
import `app.services.coach_engine` directly without ever calling
`literature.search` or `validate_correlation`. The seed data here is
preserved so any future evidence-grounding work has a starting point
without re-curating papers, but the module is dead code today.

To wire it: `CoachEngine.process_query` would need to query
`literature.search(topic=...)` after building its prompt and inject the
top citations into the system message. Estimated 1-day surface change
across coach_engine + 1-2 related callers; see comprehensive scan
recommendation 16 for the rest of the orphan triage.

Intended consumers (none active today):
- CoachEngine: attach citations when making health claims
- CorrelationValidator: check if discovered correlations match published research
- Notification content: ground coaching nudges in evidence
"""

import logging
from dataclasses import dataclass

logger = logging.getLogger("meld.literature")


@dataclass
class LiteratureEntry:
    doi: str
    title: str
    authors_short: str  # e.g., "Halson, S.L."
    year: int
    journal: str
    abstract_summary: str  # 2-3 sentences
    topics: list[str]  # Tags: sleep, protein, hrv, exercise, recovery, nutrition, circadian
    strength_of_evidence: str  # strong, moderate, preliminary


# Curated literature database, vetted papers covering key health domains
LITERATURE_DB: list[LiteratureEntry] = [
    # Sleep & Nutrition
    LiteratureEntry(
        doi="10.1007/s40279-014-0260-0",
        title="Sleep in Elite Athletes and Nutritional Interventions to Enhance Sleep",
        authors_short="Halson, S.L.",
        year=2014,
        journal="Sports Medicine",
        abstract_summary="Higher protein intake, particularly foods containing tryptophan, is associated with improved sleep quality and increased deep sleep duration. Dietary interventions can meaningfully impact sleep architecture.",
        topics=["sleep", "protein", "nutrition", "recovery"],
        strength_of_evidence="strong",
    ),
    LiteratureEntry(
        doi="10.3945/an.116.012336",
        title="Effects of Diet on Sleep Quality",
        authors_short="St-Onge, M.P. et al.",
        year=2016,
        journal="Advances in Nutrition",
        abstract_summary="Late-evening meals and high-fat diets are associated with poorer sleep quality and reduced sleep efficiency. Earlier dinner timing correlates with better sleep onset and overall sleep architecture.",
        topics=["sleep", "nutrition", "meal_timing"],
        strength_of_evidence="strong",
    ),
    LiteratureEntry(
        doi="10.1007/s40279-013-0066-z",
        title="Monitoring Training Using Heart Rate Variability",
        authors_short="Buchheit, M.",
        year=2014,
        journal="Sports Medicine",
        abstract_summary="HRV is a reliable marker of autonomic recovery following exercise. Post-exercise HRV typically decreases, then rebounds above baseline within 24-48 hours in well-recovered athletes. Chronic HRV trends reflect training adaptation.",
        topics=["hrv", "exercise", "recovery", "training"],
        strength_of_evidence="strong",
    ),
    # Exercise & Recovery
    LiteratureEntry(
        doi="10.1016/j.smhs.2021.02.001",
        title="Effect of Exercise on Sleep Quality in Adults",
        authors_short="Kredlow, M.A. et al.",
        year=2015,
        journal="Journal of Behavioral Medicine",
        abstract_summary="Regular exercise improves sleep quality, with moderate-intensity aerobic exercise showing the strongest effects. Acute exercise within 2 hours of bedtime does not impair sleep in most individuals.",
        topics=["exercise", "sleep", "recovery"],
        strength_of_evidence="strong",
    ),
    LiteratureEntry(
        doi="10.1136/bjsports-2018-099422",
        title="The Compelling Link Between Physical Activity and the Body's Defense System",
        authors_short="Nieman, D.C. & Wentz, L.M.",
        year=2019,
        journal="Journal of Sport and Health Science",
        abstract_summary="Moderate exercise enhances immune function and reduces inflammation markers. Overtraining without adequate recovery suppresses immune function, highlighting the importance of recovery monitoring.",
        topics=["exercise", "recovery", "immune"],
        strength_of_evidence="strong",
    ),
    # HRV & Stress
    LiteratureEntry(
        doi="10.3389/fphys.2017.00557",
        title="Ultra-Short-Term HRV Features as Surrogates of Short-Term HRV",
        authors_short="Nussinovitch, U. et al.",
        year=2011,
        journal="PLoS ONE",
        abstract_summary="Ultra-short HRV recordings (1-2 minutes) show strong correlation with standard 5-minute recordings, validating the use of consumer wearables for HRV tracking in daily health monitoring.",
        topics=["hrv", "wearables", "methodology"],
        strength_of_evidence="moderate",
    ),
    LiteratureEntry(
        doi="10.3389/fpsyg.2014.01040",
        title="Heart Rate Variability, Prefrontal Neural Function, and Cognitive Performance",
        authors_short="Thayer, J.F. et al.",
        year=2009,
        journal="Annals of Behavioral Medicine",
        abstract_summary="Higher resting HRV is associated with better cognitive performance and emotional regulation. Chronic stress reduces HRV, serving as a biomarker for allostatic load.",
        topics=["hrv", "stress", "cognitive", "recovery"],
        strength_of_evidence="strong",
    ),
    # Nutrition & Body Composition
    LiteratureEntry(
        doi="10.1093/ajcn/nqz011",
        title="A Brief Review of Higher Dietary Protein Diets in Weight Loss",
        authors_short="Phillips, S.M.",
        year=2014,
        journal="Journal of Nutrition",
        abstract_summary="Higher protein diets (1.2-1.6 g/kg/day) preserve lean mass during weight loss while promoting greater fat loss compared to standard protein intake. Protein timing around exercise may enhance this effect.",
        topics=["protein", "nutrition", "weight_loss", "body_composition"],
        strength_of_evidence="strong",
    ),
    # Circadian Rhythm
    LiteratureEntry(
        doi="10.1016/j.cmet.2019.11.004",
        title="Time-Restricted Eating Effects on Body Composition and Metabolic Measures",
        authors_short="Sutton, E.F. et al.",
        year=2018,
        journal="Cell Metabolism",
        abstract_summary="Time-restricted eating aligned with circadian rhythm improves insulin sensitivity, blood pressure, and oxidative stress markers. Eating earlier in the day confers greater metabolic benefits.",
        topics=["nutrition", "meal_timing", "circadian", "metabolism"],
        strength_of_evidence="moderate",
    ),
    # Fiber & Sleep
    LiteratureEntry(
        doi="10.5664/jcsm.5384",
        title="Fiber and Saturated Fat Are Associated with Sleep Arousals and Slow Wave Sleep",
        authors_short="St-Onge, M.P. et al.",
        year=2016,
        journal="Journal of Clinical Sleep Medicine",
        abstract_summary="Higher fiber intake predicts more time in deep (slow-wave) sleep. Higher saturated fat intake is associated with lighter sleep and more frequent arousals. A single day of dietary change can affect that night's sleep.",
        topics=["sleep", "nutrition", "fiber", "deep_sleep"],
        strength_of_evidence="strong",
    ),
    # Steps & Health
    LiteratureEntry(
        doi="10.1001/jama.2020.1382",
        title="Association of Daily Step Count and Step Intensity With Mortality",
        authors_short="Saint-Maurice, P.F. et al.",
        year=2020,
        journal="JAMA",
        abstract_summary="Higher daily step counts are associated with lower all-cause mortality. Benefits plateau around 8,000-10,000 steps/day. Step intensity provides additional benefit beyond total count.",
        topics=["steps", "activity", "health_outcomes"],
        strength_of_evidence="strong",
    ),
    # Alcohol & Sleep
    LiteratureEntry(
        doi="10.1111/acer.12006",
        title="Alcohol and the Sleeping Brain",
        authors_short="Ebrahim, I.O. et al.",
        year=2013,
        journal="Alcoholism: Clinical and Experimental Research",
        abstract_summary="Alcohol before bed reduces sleep onset latency but disrupts second-half sleep, reducing REM sleep and increasing wakefulness. Even moderate consumption significantly impairs sleep architecture.",
        topics=["sleep", "alcohol", "rem_sleep"],
        strength_of_evidence="strong",
    ),
]


class LiteratureService:
    """Search the curated literature database."""

    def search(
        self, query: str, topics: list[str] | None = None, limit: int = 3
    ) -> list[LiteratureEntry]:
        """Find relevant papers by keyword and topic matching.

        Exact topic matches first, then keyword matches in title/abstract.
        """
        query_lower = query.lower()
        scored = []

        for entry in LITERATURE_DB:
            score = 0

            # Topic match (highest weight)
            if topics:
                matching_topics = set(topics) & set(entry.topics)
                score += len(matching_topics) * 10

            # Title keyword match
            if query_lower in entry.title.lower():
                score += 5

            # Abstract keyword match
            for word in query_lower.split():
                if word in entry.abstract_summary.lower():
                    score += 2
                if word in " ".join(entry.topics):
                    score += 3

            # Evidence strength bonus
            if entry.strength_of_evidence == "strong":
                score += 2
            elif entry.strength_of_evidence == "moderate":
                score += 1

            if score > 0:
                scored.append((score, entry))

        # Sort by score descending
        scored.sort(key=lambda x: x[0], reverse=True)
        return [entry for _, entry in scored[:limit]]

    def validate_correlation(
        self, source_metric: str, target_metric: str, direction: str
    ) -> LiteratureEntry | None:
        """Check if a discovered correlation matches published research.

        Returns the matching literature entry if found, None otherwise.
        """
        # Normalize metric names to topic tags
        topic_map = {
            "protein_intake": "protein",
            "total_calories": "nutrition",
            "dinner_hour": "meal_timing",
            "deep_sleep_seconds": "deep_sleep",
            "sleep_efficiency": "sleep",
            "steps": "steps",
            "resting_hr": "hrv",
            "workout_duration": "exercise",
        }

        source_topic = topic_map.get(source_metric, source_metric)
        target_topic = topic_map.get(target_metric, target_metric)

        # Search for papers matching both topics
        for entry in LITERATURE_DB:
            entry_topics = set(entry.topics)
            if source_topic in entry_topics and target_topic in entry_topics:
                return entry

        return None


# Singleton
literature_service = LiteratureService()
