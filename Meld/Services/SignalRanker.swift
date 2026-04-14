import Foundation

// MARK: - Signal Engine service wrapper
//
// In Phase 4 this is a thin shim around the backend API: fetch the pre-
// ranked daily card and submit feedback. Ranking itself runs on the
// backend in the nightly insight_candidate_job scheduler.
//
// Phase 7 promotes this to a real on-device ranker: it will load a
// CoreML model shipped from Cloudflare R2, run the learned XGBoost
// LambdaMART over a local candidate set, and fall back to the heuristic
// when the model is unavailable. The file exists now so the naming is
// stable across that transition and no dashboard code has to change.
//
// See ~/.claude/plans/golden-floating-creek.md Phase 4 / Phase 7 for the
// full roadmap.

actor SignalRanker {
    static let shared = SignalRanker()

    private init() {}

    /// Fetch today's top-ranked insight card, or nil when the backend has
    /// nothing to show (shadow mode, cap hit, no candidates). The dashboard
    /// falls back to the legacy CoachInsightCard when nil is returned.
    ///
    /// The `reason` string from the backend is surfaced for logging /
    /// analytics so we can tell whether shadow mode, a cap, or lack of
    /// candidates is responsible.
    func fetchTodayInsight() async throws -> FetchResult {
        let response = try await APIClient.shared.fetchDailyInsight()
        guard response.has_card, let card = response.card else {
            return .none(reason: response.reason ?? "unknown")
        }
        return .card(convert(card))
    }

    /// Submit user feedback on a shown card. Backend persists it to
    /// ml_rankings.feedback. Phase 7 learned ranker consumes this as
    /// training labels (positive: thumbs_up; negative: thumbs_down,
    /// dismissed, already_knew).
    func submitFeedback(rankingID: Int, feedback: SignalInsightFeedback) async throws {
        try await APIClient.shared.submitInsightFeedback(
            rankingID: rankingID,
            feedback: feedback
        )
    }

    // MARK: - API -> domain conversion

    nonisolated func convert(_ card: APIDailyInsightCard) -> SignalInsight {
        let kind = SignalInsightKind(rawValue: card.kind) ?? .unknown
        let payload = SignalInsightPayload(
            sourceMetric: card.payload.source_metric,
            targetMetric: card.payload.target_metric,
            lagDays: card.payload.lag_days,
            direction: card.payload.direction,
            pearsonR: card.payload.pearson_r,
            spearmanR: card.payload.spearman_r,
            sampleSize: card.payload.sample_size,
            effectDescription: card.payload.effect_description,
            confidenceTier: card.payload.confidence_tier,
            literatureRef: card.payload.literature_ref,
            metricKey: card.payload.metric_key,
            observationDate: card.payload.observation_date,
            observedValue: card.payload.observed_value,
            forecastedValue: card.payload.forecasted_value,
            residual: card.payload.residual,
            zScore: card.payload.z_score,
            confirmedByBocpd: card.payload.confirmed_by_bocpd
        )
        return SignalInsight(
            id: card.ranking_id,
            candidateID: card.candidate_id,
            kind: kind,
            subjectMetrics: card.subject_metrics,
            effectSize: card.effect_size,
            confidence: card.confidence,
            score: card.score,
            rankerVersion: card.ranker_version,
            literatureSupport: card.literature_support,
            payload: payload
        )
    }

    /// Result type from the fetch path. Using an enum (rather than
    /// `SignalInsight?`) keeps the "no card" branch explicit about WHY —
    /// shadow mode vs cap vs no candidates — which the dashboard logs.
    enum FetchResult {
        case card(SignalInsight)
        case none(reason: String)
    }
}
