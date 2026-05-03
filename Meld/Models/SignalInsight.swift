import Foundation

// MARK: - Signal Engine Phase 4 domain model
//
// The SignalInsight is the per-day ranked card surfaced by the backend's
// Phase 4 ranker. It comes from GET /api/insights/daily, which is shadow-
// gated server-side via `ml_shadow_insight_card`. When the backend reports
// `has_card=false`, the dashboard falls back to the legacy CoachInsightCard.
//
// The iOS side does NOT rank anything in Phase 4. Ranking happens in the
// nightly `insight_candidate_job` scheduler (backend). Phase 7 adds an on-
// device CoreML ranker, that is when `SignalRanker.swift` grows real
// scoring logic. For now the service file exists to keep the naming stable
// across phases.
//
// Feedback flow: user taps thumbs up / down / "already knew" on the card
// -> POST /api/insights/{ranking_id}/feedback -> ml_rankings.feedback set
// -> Phase 7 ranker training signal.

/// What kind of finding a card is showing. Decoded from the backend's
/// `kind` string, falls back to `.unknown` so a forward-compatible kind
/// added by the server does not crash decoding.
enum SignalInsightKind: String, Codable {
    case correlation
    case anomaly
    case forecastWarning = "forecast_warning"
    case experimentResult = "experiment_result"
    case streak
    case regression
    case unknown

    init(from decoder: Decoder) throws {
        let raw = try decoder.singleValueContainer().decode(String.self)
        self = SignalInsightKind(rawValue: raw) ?? .unknown
    }
}

/// Feedback values the card buttons can submit. Matches the backend's
/// `FeedbackRequest.feedback` Literal exactly; any drift is caught by the
/// end-to-end API contract test.
enum SignalInsightFeedback: String, Codable {
    case thumbsUp = "thumbs_up"
    case thumbsDown = "thumbs_down"
    case dismissed
    case alreadyKnew = "already_knew"
}

/// Card payload, heterogeneous by kind but rendered through a single view.
/// All fields are optional because the backend's payload shape is kind-
/// specific: correlations carry source/target/pearson_r, anomalies carry
/// observation_date/z_score, etc.
struct SignalInsightPayload: Codable, Equatable {
    // Correlation-kind fields
    let sourceMetric: String?
    let targetMetric: String?
    let lagDays: Int?
    let direction: String?
    let pearsonR: Double?
    let spearmanR: Double?
    let sampleSize: Int?
    let effectDescription: String?
    let confidenceTier: String?
    let literatureRef: String?

    // Anomaly-kind fields
    let metricKey: String?
    let observationDate: String?
    let observedValue: Double?
    let forecastedValue: Double?
    let residual: Double?
    let zScore: Double?
    let confirmedByBocpd: Bool?

    enum CodingKeys: String, CodingKey {
        case sourceMetric = "source_metric"
        case targetMetric = "target_metric"
        case lagDays = "lag_days"
        case direction
        case pearsonR = "pearson_r"
        case spearmanR = "spearman_r"
        case sampleSize = "sample_size"
        case effectDescription = "effect_description"
        case confidenceTier = "confidence_tier"
        case literatureRef = "literature_ref"
        case metricKey = "metric_key"
        case observationDate = "observation_date"
        case observedValue = "observed_value"
        case forecastedValue = "forecasted_value"
        case residual
        case zScore = "z_score"
        case confirmedByBocpd = "confirmed_by_bocpd"
    }
}

/// The full card shape as seen by the dashboard. Built from
/// `APIDailyInsightResponse` in APIClient.
struct SignalInsight: Identifiable, Equatable {
    /// Stable across decode runs so SwiftUI `ForEach` does not reshuffle.
    let id: Int // the ml_rankings.id
    let candidateID: String
    let kind: SignalInsightKind
    let subjectMetrics: [String]
    let effectSize: Double
    let confidence: Double
    let score: Double
    let rankerVersion: String
    let literatureSupport: Bool
    let payload: SignalInsightPayload

    /// Plain-language headline for the card. Picks the right phrasing based
    /// on kind so the narrator does not have to be re-implemented iOS-side.
    /// If/when the backend ships server-generated narration (Phase 5), this
    /// switches to the server's string.
    var headline: String {
        switch kind {
        case .correlation: return "Pattern noticed"
        case .anomaly: return "Recent change"
        case .forecastWarning: return "Looking ahead"
        case .experimentResult: return "Your experiment"
        case .streak: return "Streak update"
        case .regression: return "Heads up"
        case .unknown: return "New insight"
        }
    }

    /// Main body copy. For correlations the backend already wrote a plain-
    /// language description in `payload.effect_description`. For anomalies
    /// we compose a short sentence from z-score + metric. Voice-compliant
    /// per feedback_no_em_dashes memory (no em dashes, no emoji).
    var body: String {
        if let description = payload.effectDescription, !description.isEmpty {
            return description
        }

        switch kind {
        case .anomaly:
            let metric = payload.metricKey ?? subjectMetrics.first ?? "a metric"
            let direction = payload.direction ?? "changed"
            return "Your \(prettifyMetric(metric)) is \(direction) by more than usual today."
        case .correlation:
            guard let source = payload.sourceMetric, let target = payload.targetMetric else {
                return "A new pattern appeared in your data."
            }
            return "When your \(prettifyMetric(source)) moves, your \(prettifyMetric(target)) tends to move with it."
        default:
            return "A new signal appeared in your data. Tap to learn more."
        }
    }

    /// Short confidence badge text shown in the card footer.
    var confidenceLabel: String {
        if literatureSupport {
            return "Research-backed"
        }
        switch payload.confidenceTier {
        case "established":
            return "Strong personal trend"
        case "developing":
            return "Consistent pattern"
        case "causal_candidate":
            return "Likely driver"
        default:
            return "Early sign"
        }
    }

    private func prettifyMetric(_ key: String) -> String {
        key.replacingOccurrences(of: "_", with: " ")
    }
}
