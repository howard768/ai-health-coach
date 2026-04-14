import Foundation
import Testing
@testable import Meld

// MARK: - Signal Engine Phase 4 — iOS decode + conversion tests
//
// These pin the wire contract against the backend's
// ``app/routers/insights.py`` response shape and the conversion from
// ``APIDailyInsightCard`` to the domain ``SignalInsight`` the dashboard
// renders. Snapshot tests for the card view are a follow-up once
// xcodebuild can record baselines locally.

// MARK: - APIDailyInsightResponse decode

@Test func dailyInsightDecodesHasCardFalseShadowMode() async throws {
    // Backend returns has_card=false with a reason when shadow mode is on.
    let json = """
    { "has_card": false, "card": null, "reason": "shadow_mode" }
    """.data(using: .utf8)!
    let response = try JSONDecoder().decode(APIDailyInsightResponse.self, from: json)
    #expect(response.has_card == false)
    #expect(response.card == nil)
    #expect(response.reason == "shadow_mode")
}

@Test func dailyInsightDecodesHasCardFalseCapHit() async throws {
    // Cap-hit reason is a free-form string from the backend; just verify decode.
    let json = """
    { "has_card": false, "card": null, "reason": "daily cap hit (1/1)" }
    """.data(using: .utf8)!
    let response = try JSONDecoder().decode(APIDailyInsightResponse.self, from: json)
    #expect(response.has_card == false)
    #expect(response.reason == "daily cap hit (1/1)")
}

@Test func dailyInsightDecodesCorrelationCard() async throws {
    // Representative correlation payload — matches what run_daily_insights
    // would produce for a literature-supported UserCorrelation row.
    let json = """
    {
      "has_card": true,
      "card": {
        "ranking_id": 42,
        "candidate_id": "8b4cbc4e924dafbe94fe29df",
        "kind": "correlation",
        "subject_metrics": ["protein_intake", "deep_sleep_seconds"],
        "effect_size": 0.55,
        "confidence": 0.95,
        "score": 0.82,
        "ranker_version": "heuristic-1.0.0",
        "literature_support": true,
        "payload": {
          "source_metric": "protein_intake",
          "target_metric": "deep_sleep_seconds",
          "lag_days": 0,
          "direction": "positive",
          "pearson_r": 0.55,
          "spearman_r": 0.5,
          "sample_size": 60,
          "effect_description": "When your protein is higher, your deep sleep tends to be longer.",
          "confidence_tier": "literature_supported",
          "literature_ref": "10.1007/s40279-014-0260-0"
        }
      },
      "reason": null
    }
    """.data(using: .utf8)!
    let response = try JSONDecoder().decode(APIDailyInsightResponse.self, from: json)
    #expect(response.has_card == true)
    let card = try #require(response.card)
    #expect(card.ranking_id == 42)
    #expect(card.kind == "correlation")
    #expect(card.literature_support == true)
    #expect(card.payload.source_metric == "protein_intake")
    #expect(card.payload.confidence_tier == "literature_supported")
    // Anomaly-only fields are absent on a correlation card.
    #expect(card.payload.metric_key == nil)
    #expect(card.payload.z_score == nil)
}

@Test func dailyInsightDecodesAnomalyCard() async throws {
    // Anomaly cards omit the correlation-specific payload fields; decoder
    // must tolerate all correlation-kind fields being null.
    let json = """
    {
      "has_card": true,
      "card": {
        "ranking_id": 77,
        "candidate_id": "abc123def456",
        "kind": "anomaly",
        "subject_metrics": ["hrv"],
        "effect_size": 0.8,
        "confidence": 0.80,
        "score": 0.61,
        "ranker_version": "heuristic-1.0.0",
        "literature_support": false,
        "payload": {
          "metric_key": "hrv",
          "observation_date": "2026-04-13",
          "observed_value": 22.0,
          "forecasted_value": 42.0,
          "residual": -20.0,
          "z_score": -4.0,
          "direction": "low",
          "confirmed_by_bocpd": true
        }
      },
      "reason": null
    }
    """.data(using: .utf8)!
    let response = try JSONDecoder().decode(APIDailyInsightResponse.self, from: json)
    let card = try #require(response.card)
    #expect(card.kind == "anomaly")
    #expect(card.payload.metric_key == "hrv")
    #expect(card.payload.z_score == -4.0)
    #expect(card.payload.confirmed_by_bocpd == true)
    // Correlation-only fields are absent on an anomaly card.
    #expect(card.payload.pearson_r == nil)
    #expect(card.payload.literature_ref == nil)
}

// MARK: - SignalInsightKind decode fallback

@Test func signalInsightKindFallsBackToUnknownOnForwardCompat() async throws {
    // Forward-compat: if the backend ships a new kind later, iOS should not
    // crash — it should fall back to .unknown and still render a generic card.
    let json = "\"brand_new_kind\"".data(using: .utf8)!
    let kind = try JSONDecoder().decode(SignalInsightKind.self, from: json)
    #expect(kind == .unknown)
}

@Test func signalInsightKindDecodesKnownKinds() async throws {
    let cases: [(raw: String, expected: SignalInsightKind)] = [
        ("correlation", .correlation),
        ("anomaly", .anomaly),
        ("forecast_warning", .forecastWarning),
        ("experiment_result", .experimentResult),
        ("streak", .streak),
        ("regression", .regression),
    ]
    for c in cases {
        let data = "\"\(c.raw)\"".data(using: .utf8)!
        let kind = try JSONDecoder().decode(SignalInsightKind.self, from: data)
        #expect(kind == c.expected)
    }
}

// MARK: - SignalInsightFeedback wire values

@Test func signalInsightFeedbackRawValuesMatchBackend() async throws {
    // The backend Literal enforces exactly these strings. If this changes,
    // both sides need updating simultaneously.
    #expect(SignalInsightFeedback.thumbsUp.rawValue == "thumbs_up")
    #expect(SignalInsightFeedback.thumbsDown.rawValue == "thumbs_down")
    #expect(SignalInsightFeedback.dismissed.rawValue == "dismissed")
    #expect(SignalInsightFeedback.alreadyKnew.rawValue == "already_knew")
}

// MARK: - SignalRanker.convert — API -> domain mapping

@Test func signalRankerConvertPreservesAllFields() async throws {
    let card = APIDailyInsightCard(
        ranking_id: 7,
        candidate_id: "xyz",
        kind: "correlation",
        subject_metrics: ["steps", "sleep_efficiency"],
        effect_size: 0.62,
        confidence: 0.60,
        score: 0.55,
        ranker_version: "heuristic-1.0.0",
        literature_support: false,
        payload: APIDailyInsightPayload(
            source_metric: "steps",
            target_metric: "sleep_efficiency",
            lag_days: 0,
            direction: "positive",
            pearson_r: 0.62,
            spearman_r: 0.58,
            sample_size: 45,
            effect_description: "Higher step days tend to have better sleep efficiency.",
            confidence_tier: "developing",
            literature_ref: nil,
            metric_key: nil,
            observation_date: nil,
            observed_value: nil,
            forecasted_value: nil,
            residual: nil,
            z_score: nil,
            confirmed_by_bocpd: nil
        )
    )
    let insight = await SignalRanker.shared.convert(card)
    #expect(insight.id == 7)
    #expect(insight.candidateID == "xyz")
    #expect(insight.kind == .correlation)
    #expect(insight.subjectMetrics == ["steps", "sleep_efficiency"])
    #expect(insight.effectSize == 0.62)
    #expect(insight.literatureSupport == false)
    #expect(insight.payload.sampleSize == 45)
    #expect(insight.payload.effectDescription != nil)
}

// MARK: - SignalInsight.body

@Test func signalInsightBodyPrefersBackendDescription() async throws {
    let insight = SignalInsight(
        id: 1, candidateID: "x", kind: .correlation,
        subjectMetrics: ["a", "b"], effectSize: 0.5, confidence: 0.6,
        score: 0.5, rankerVersion: "heuristic-1.0.0", literatureSupport: false,
        payload: SignalInsightPayload(
            sourceMetric: "a", targetMetric: "b", lagDays: 0, direction: "positive",
            pearsonR: 0.5, spearmanR: 0.5, sampleSize: 30,
            effectDescription: "Server-generated sentence about your data.",
            confidenceTier: "developing", literatureRef: nil,
            metricKey: nil, observationDate: nil, observedValue: nil,
            forecastedValue: nil, residual: nil, zScore: nil, confirmedByBocpd: nil
        )
    )
    #expect(insight.body == "Server-generated sentence about your data.")
}

@Test func signalInsightBodyComposesCorrelationFallback() async throws {
    // No effect_description -> iOS generates a plain-language fallback.
    let insight = SignalInsight(
        id: 1, candidateID: "x", kind: .correlation,
        subjectMetrics: ["steps", "sleep_efficiency"],
        effectSize: 0.5, confidence: 0.6, score: 0.5,
        rankerVersion: "heuristic-1.0.0", literatureSupport: false,
        payload: SignalInsightPayload(
            sourceMetric: "steps", targetMetric: "sleep efficiency",
            lagDays: 0, direction: "positive",
            pearsonR: 0.5, spearmanR: 0.5, sampleSize: 30,
            effectDescription: nil, confidenceTier: "developing", literatureRef: nil,
            metricKey: nil, observationDate: nil, observedValue: nil,
            forecastedValue: nil, residual: nil, zScore: nil, confirmedByBocpd: nil
        )
    )
    #expect(insight.body.contains("steps"))
    #expect(insight.body.contains("sleep efficiency"))
}

@Test func signalInsightBodyNeverContainsEmDash() async throws {
    // Voice rule (feedback_no_em_dashes): no em dash anywhere in
    // iOS-generated strings. Regression test — a previous revision used
    // an em dash in the anomaly fallback copy.
    let cases: [SignalInsightKind] = [.correlation, .anomaly, .forecastWarning, .unknown]
    for kind in cases {
        let insight = SignalInsight(
            id: 1, candidateID: "x", kind: kind,
            subjectMetrics: ["hrv"], effectSize: 0.5, confidence: 0.6,
            score: 0.5, rankerVersion: "heuristic-1.0.0", literatureSupport: false,
            payload: SignalInsightPayload(
                sourceMetric: nil, targetMetric: nil, lagDays: nil, direction: "low",
                pearsonR: nil, spearmanR: nil, sampleSize: nil,
                effectDescription: nil, confidenceTier: nil, literatureRef: nil,
                metricKey: "hrv", observationDate: "2026-04-13", observedValue: 20,
                forecastedValue: 40, residual: -20, zScore: -4, confirmedByBocpd: true
            )
        )
        #expect(!insight.body.contains("\u{2014}"), "Em dash found in body for kind \\(kind)")
        #expect(!insight.headline.contains("\u{2014}"))
        #expect(!insight.confidenceLabel.contains("\u{2014}"))
    }
}

// MARK: - SignalInsight.confidenceLabel

@Test func confidenceLabelPrefersLiteratureBadge() async throws {
    let insight = SignalInsight(
        id: 1, candidateID: "x", kind: .correlation,
        subjectMetrics: ["a"], effectSize: 0.5, confidence: 0.95,
        score: 0.9, rankerVersion: "heuristic-1.0.0", literatureSupport: true,
        payload: SignalInsightPayload(
            sourceMetric: "a", targetMetric: "b", lagDays: 0, direction: "positive",
            pearsonR: 0.5, spearmanR: 0.5, sampleSize: 60,
            effectDescription: nil, confidenceTier: "literature_supported",
            literatureRef: "10.1/abc", metricKey: nil, observationDate: nil,
            observedValue: nil, forecastedValue: nil, residual: nil,
            zScore: nil, confirmedByBocpd: nil
        )
    )
    #expect(insight.confidenceLabel == "Research-backed")
}

@Test func confidenceLabelMapsTiersToPlainLanguage() async throws {
    let cases: [(tier: String, expected: String)] = [
        ("established", "Strong personal trend"),
        ("developing", "Consistent pattern"),
        ("causal_candidate", "Likely driver"),
        ("emerging", "Early sign"),
    ]
    for c in cases {
        let insight = SignalInsight(
            id: 1, candidateID: "x", kind: .correlation,
            subjectMetrics: ["a"], effectSize: 0.5, confidence: 0.6,
            score: 0.5, rankerVersion: "heuristic-1.0.0", literatureSupport: false,
            payload: SignalInsightPayload(
                sourceMetric: "a", targetMetric: "b", lagDays: 0, direction: "positive",
                pearsonR: 0.5, spearmanR: 0.5, sampleSize: 30,
                effectDescription: nil, confidenceTier: c.tier, literatureRef: nil,
                metricKey: nil, observationDate: nil, observedValue: nil,
                forecastedValue: nil, residual: nil, zScore: nil, confirmedByBocpd: nil
            )
        )
        #expect(insight.confidenceLabel == c.expected, "tier=\\(c.tier) should map to \\(c.expected)")
    }
}
