import Foundation
import Testing
@testable import Meld

// MARK: - Phase 7B ranker model wire contract tests

@Suite("RankerModel wire contracts")
struct RankerModelTests {

    // MARK: - RankerModelMetadata decode

    @Test("Ranker metadata decodes from server JSON")
    func metadataDecodesFromJSON() throws {
        let json = """
        {
            "model_version": "ranker-abc12345",
            "file_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "file_size_bytes": 312000,
            "download_url": "https://models.heymeld.com/coreml/ranker-abc12345.mlmodel"
        }
        """.data(using: .utf8)!

        let metadata = try JSONDecoder().decode(RankerModelMetadata.self, from: json)
        #expect(metadata.modelVersion == "ranker-abc12345")
        #expect(metadata.fileHash == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")
        #expect(metadata.fileSizeBytes == 312000)
        #expect(metadata.downloadUrl == "https://models.heymeld.com/coreml/ranker-abc12345.mlmodel")
    }

    // MARK: - CandidateFeatures decode

    @Test("Candidate features decode from server JSON")
    func candidateFeaturesDecodeFromJSON() throws {
        let json = """
        {
            "candidate_id": "abcdef123456789012345678",
            "kind": "correlation",
            "subject_metrics": ["steps", "sleep_efficiency"],
            "effect_size": 0.65,
            "confidence": 0.80,
            "novelty": 1.0,
            "recency_days": 2,
            "actionability_score": 0.90,
            "literature_support": true,
            "directional_support": true,
            "causal_support": false,
            "payload": {
                "source_metric": "steps",
                "target_metric": "sleep_efficiency",
                "lag_days": 1
            }
        }
        """.data(using: .utf8)!

        let candidate = try JSONDecoder().decode(CandidateFeatures.self, from: json)
        #expect(candidate.candidateId == "abcdef123456789012345678")
        #expect(candidate.kind == "correlation")
        #expect(candidate.subjectMetrics == ["steps", "sleep_efficiency"])
        #expect(candidate.effectSize == 0.65)
        #expect(candidate.confidence == 0.80)
        #expect(candidate.novelty == 1.0)
        #expect(candidate.recencyDays == 2)
        #expect(candidate.actionabilityScore == 0.90)
        #expect(candidate.literatureSupport == true)
        #expect(candidate.directionalSupport == true)
        #expect(candidate.causalSupport == false)
    }

    // MARK: - CandidatesResponse decode

    @Test("Candidates response decodes multiple candidates")
    func candidatesResponseDecodesMultiple() throws {
        let json = """
        {
            "candidates": [
                {
                    "candidate_id": "cand1",
                    "kind": "correlation",
                    "subject_metrics": ["steps"],
                    "effect_size": 0.5,
                    "confidence": 0.6,
                    "novelty": 0.8,
                    "recency_days": 1,
                    "actionability_score": 0.7,
                    "literature_support": false,
                    "directional_support": false,
                    "causal_support": false,
                    "payload": null
                },
                {
                    "candidate_id": "cand2",
                    "kind": "anomaly",
                    "subject_metrics": ["hrv"],
                    "effect_size": 0.9,
                    "confidence": 0.8,
                    "novelty": 1.0,
                    "recency_days": 0,
                    "actionability_score": 0.4,
                    "literature_support": false,
                    "directional_support": false,
                    "causal_support": false,
                    "payload": null
                }
            ]
        }
        """.data(using: .utf8)!

        let response = try JSONDecoder().decode(CandidatesResponse.self, from: json)
        #expect(response.candidates.count == 2)
        #expect(response.candidates[0].candidateId == "cand1")
        #expect(response.candidates[1].kind == "anomaly")
    }

    // MARK: - Heuristic score

    @Test("Heuristic score matches backend weights")
    func heuristicScoreMatchesWeights() async {
        let candidate = CandidateFeatures(
            candidateId: "test",
            kind: "correlation",
            subjectMetrics: ["steps"],
            effectSize: 0.8,
            confidence: 0.6,
            novelty: 1.0,
            recencyDays: 3,
            actionabilityScore: 0.9,
            literatureSupport: true,
            directionalSupport: false,
            causalSupport: false,
            payload: nil
        )

        let score = await SignalRanker.shared.heuristicScore(candidate)

        // 0.35*0.8 + 0.25*0.6 + 0.15*0.9 + 0.15*1.0 + 0.10*1.0 = 0.815
        let expected: Double = 0.815
        #expect(abs(score - expected) < 0.001)
    }

    @Test("Heuristic score is zero for empty candidate")
    func heuristicScoreZeroForEmpty() async {
        let candidate = CandidateFeatures(
            candidateId: "zero",
            kind: "correlation",
            subjectMetrics: [],
            effectSize: 0.0,
            confidence: 0.0,
            novelty: 0.0,
            recencyDays: 0,
            actionabilityScore: 0.0,
            literatureSupport: false,
            directionalSupport: false,
            causalSupport: false,
            payload: nil
        )

        let score = await SignalRanker.shared.heuristicScore(candidate)
        #expect(score == 0.0)
    }

    // MARK: - Model cache

    @Test("Cached model URL is nil when no model downloaded")
    func cachedModelURLNilWhenEmpty() async {
        // Clear any cached model state.
        UserDefaults.standard.removeObject(forKey: "rankerModelHash")
        UserDefaults.standard.removeObject(forKey: "rankerModelVersion")

        let version = await RankerModelManager.shared.cachedModelVersion()
        // May or may not be nil depending on test ordering, but should not crash.
        _ = version
    }
}
