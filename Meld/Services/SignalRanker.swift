import CoreML
import Foundation

// MARK: - Signal Engine ranker (Phase 4 + 7B)
//
// Phase 4: thin shim around the backend API (fetch pre-ranked daily card).
// Phase 7B: on-device CoreML ranking for offline use. Online path stays
// unchanged (backend API returns pre-ranked card). Offline path fetches
// candidates from the backend, ranks locally with the cached CoreML model,
// and falls back to heuristic scoring when no model is available.
//
// Fallback chain: CoreML model -> heuristic score -> backend API.
// DashboardViewModel calls fetchTodayInsight() exactly as before.

actor SignalRanker {
    static let shared = SignalRanker()

    /// Cached CoreML model for on-device ranking. Nil until a model is
    /// downloaded from R2 and compiled.
    private var compiledModel: MLModel?

    /// Last-fetched candidates, cached for offline use.
    private var cachedCandidates: [CandidateFeatures] = []

    private init() {}

    // MARK: - Model lifecycle

    /// Load the cached CoreML model from disk (Application Support).
    /// Called on app launch and after background model updates.
    /// Loads within this actor to avoid sending non-Sendable MLModel
    /// across actor boundaries.
    func loadCachedModel() async {
        guard let url = await RankerModelManager.shared.cachedModelURLForLoading() else {
            compiledModel = nil
            return
        }
        do {
            let config = MLModelConfiguration()
            config.computeUnits = .cpuOnly
            compiledModel = try MLModel(contentsOf: url, configuration: config)
        } catch {
            compiledModel = nil
        }
    }

    /// Check for model updates and download if available.
    func refreshModel() async {
        let updated = await RankerModelManager.shared.updateIfNeeded()
        if updated {
            await loadCachedModel()
        }
    }

    // MARK: - Fetch (online-first, offline fallback)

    /// Fetch today's top-ranked insight card. Online: uses backend API.
    /// Offline: ranks cached candidates locally with CoreML or heuristic.
    ///
    /// The `reason` string from the backend is surfaced for logging /
    /// analytics so we can tell whether shadow mode, a cap, or lack of
    /// candidates is responsible.
    func fetchTodayInsight() async throws -> FetchResult {
        // Try online path first.
        do {
            let response = try await APIClient.shared.fetchDailyInsight()

            // Also refresh candidates cache for potential offline use.
            Task { await refreshCandidatesCache() }

            guard response.has_card, let card = response.card else {
                return .none(reason: response.reason ?? "unknown")
            }
            return .card(convert(card))
        } catch {
            // Network failure: try offline ranking.
            return await rankOffline()
        }
    }

    /// Submit user feedback on a shown card.
    func submitFeedback(rankingID: Int, feedback: SignalInsightFeedback) async throws {
        try await APIClient.shared.submitInsightFeedback(
            rankingID: rankingID,
            feedback: feedback
        )
    }

    // MARK: - Offline ranking

    /// Rank cached candidates locally. Uses CoreML model if available,
    /// otherwise falls back to heuristic scoring.
    private func rankOffline() async -> FetchResult {
        guard !cachedCandidates.isEmpty else {
            return .none(reason: "offline_no_candidates")
        }

        // Ensure model is loaded.
        if compiledModel == nil {
            await loadCachedModel()
        }

        if let model = compiledModel {
            if let insight = rankWithModel(model, candidates: cachedCandidates) {
                return .card(insight)
            }
        }

        // Heuristic fallback.
        if let insight = rankWithHeuristic(cachedCandidates) {
            return .card(insight)
        }

        return .none(reason: "offline_ranking_failed")
    }

    /// Rank candidates using the CoreML model. Returns the top-1 as a
    /// SignalInsight, or nil if prediction fails.
    private func rankWithModel(
        _ model: MLModel,
        candidates: [CandidateFeatures]
    ) -> SignalInsight? {
        var scored: [(CandidateFeatures, Double)] = []

        for candidate in candidates {
            let provider = CandidateFeatureProvider(candidate: candidate)
            guard let prediction = try? model.prediction(from: provider) else {
                continue
            }
            // CoreML regressor output: look for "prediction" or first feature.
            let score = prediction.featureValue(for: "prediction")?.doubleValue
                ?? prediction.featureValue(for: "target")?.doubleValue
                ?? 0.0
            scored.append((candidate, score))
        }

        guard let top = scored.max(by: { $0.1 < $1.1 }) else { return nil }
        return candidateToInsight(top.0, score: top.1, rankerVersion: "coreml")
    }

    /// Rank candidates using the heuristic weighted sum.
    /// Weights match the backend: 0.35 effect + 0.25 confidence +
    /// 0.15 actionability + 0.15 novelty + 0.10 literature.
    private func rankWithHeuristic(
        _ candidates: [CandidateFeatures]
    ) -> SignalInsight? {
        guard let top = candidates.max(by: {
            heuristicScore($0) < heuristicScore($1)
        }) else { return nil }
        return candidateToInsight(
            top,
            score: heuristicScore(top),
            rankerVersion: "heuristic-ios-1.0.0"
        )
    }

    /// Heuristic score matching backend weights.
    nonisolated func heuristicScore(_ c: CandidateFeatures) -> Double {
        0.35 * c.effectSize
            + 0.25 * c.confidence
            + 0.15 * c.actionabilityScore
            + 0.15 * c.novelty
            + 0.10 * (c.literatureSupport ? 1.0 : 0.0)
    }

    // MARK: - Candidates cache

    private func refreshCandidatesCache() async {
        do {
            let response = try await APIClient.shared.fetchCandidates()
            cachedCandidates = response.candidates
        } catch {
            // Non-fatal: keep whatever was cached before.
        }
    }

    // MARK: - Conversion helpers

    /// Convert an API card to a domain SignalInsight (online path).
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

    /// Convert a CandidateFeatures to a SignalInsight (offline path).
    private nonisolated func candidateToInsight(
        _ c: CandidateFeatures,
        score: Double,
        rankerVersion: String
    ) -> SignalInsight {
        let kind = SignalInsightKind(rawValue: c.kind) ?? .unknown
        return SignalInsight(
            id: 0,  // no ranking_id for locally-ranked cards
            candidateID: c.candidateId,
            kind: kind,
            subjectMetrics: c.subjectMetrics,
            effectSize: c.effectSize,
            confidence: c.confidence,
            score: score,
            rankerVersion: rankerVersion,
            literatureSupport: c.literatureSupport,
            payload: SignalInsightPayload(
                sourceMetric: nil, targetMetric: nil, lagDays: nil,
                direction: nil, pearsonR: nil, spearmanR: nil,
                sampleSize: nil, effectDescription: nil, confidenceTier: nil,
                literatureRef: nil, metricKey: nil, observationDate: nil,
                observedValue: nil, forecastedValue: nil, residual: nil,
                zScore: nil, confirmedByBocpd: nil
            )
        )
    }

    /// Result type from the fetch path.
    enum FetchResult {
        case card(SignalInsight)
        case none(reason: String)
    }
}

// MARK: - CoreML Feature Provider

/// Bridges CandidateFeatures to MLFeatureProvider for CoreML inference.
private class CandidateFeatureProvider: MLFeatureProvider {
    let candidate: CandidateFeatures

    var featureNames: Set<String> {
        [
            "effect_size", "confidence", "novelty", "recency_days",
            "actionability_score", "literature_support",
            "directional_support", "causal_support",
        ]
    }

    init(candidate: CandidateFeatures) {
        self.candidate = candidate
    }

    func featureValue(for featureName: String) -> MLFeatureValue? {
        switch featureName {
        case "effect_size":
            MLFeatureValue(double: candidate.effectSize)
        case "confidence":
            MLFeatureValue(double: candidate.confidence)
        case "novelty":
            MLFeatureValue(double: candidate.novelty)
        case "recency_days":
            MLFeatureValue(double: Double(candidate.recencyDays) / 30.0)
        case "actionability_score":
            MLFeatureValue(double: candidate.actionabilityScore)
        case "literature_support":
            MLFeatureValue(double: candidate.literatureSupport ? 1.0 : 0.0)
        case "directional_support":
            MLFeatureValue(double: candidate.directionalSupport ? 1.0 : 0.0)
        case "causal_support":
            MLFeatureValue(double: candidate.causalSupport ? 1.0 : 0.0)
        default:
            nil
        }
    }
}
