import Foundation

// MARK: - Phase 7B CoreML ranker model types
//
// Wire types for GET /api/ranker/metadata and GET /api/insights/candidates.
// The metadata drives conditional model downloads from R2. The candidate
// features drive on-device CoreML inference when offline.

/// Metadata for the latest active CoreML ranker model.
/// Used to decide whether to download a new model from R2.
struct RankerModelMetadata: Codable, Equatable {
    let modelVersion: String
    let fileHash: String
    let fileSizeBytes: Int
    let downloadUrl: String

    enum CodingKeys: String, CodingKey {
        case modelVersion = "model_version"
        case fileHash = "file_hash"
        case fileSizeBytes = "file_size_bytes"
        case downloadUrl = "download_url"
    }
}

/// Feature vector for one insight candidate, as returned by the backend.
/// Mirrors the 8 ranker features used by both the heuristic and learned models.
struct CandidateFeatures: Codable, Equatable, Identifiable {
    let candidateId: String
    let kind: String
    let subjectMetrics: [String]
    let effectSize: Double
    let confidence: Double
    let novelty: Double
    let recencyDays: Int
    let actionabilityScore: Double
    let literatureSupport: Bool
    let directionalSupport: Bool
    let causalSupport: Bool
    let payload: [String: AnyCodableValue]?

    var id: String { candidateId }

    enum CodingKeys: String, CodingKey {
        case candidateId = "candidate_id"
        case kind
        case subjectMetrics = "subject_metrics"
        case effectSize = "effect_size"
        case confidence
        case novelty
        case recencyDays = "recency_days"
        case actionabilityScore = "actionability_score"
        case literatureSupport = "literature_support"
        case directionalSupport = "directional_support"
        case causalSupport = "causal_support"
        case payload
    }
}

/// Response wrapper for GET /api/insights/candidates.
struct CandidatesResponse: Codable {
    let candidates: [CandidateFeatures]
}

/// Type-erased JSON value for the heterogeneous payload dict.
/// Supports String, Int, Double, Bool, and null.
enum AnyCodableValue: Codable, Equatable {
    case string(String)
    case int(Int)
    case double(Double)
    case bool(Bool)
    case null

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if container.decodeNil() {
            self = .null
        } else if let v = try? container.decode(Bool.self) {
            self = .bool(v)
        } else if let v = try? container.decode(Int.self) {
            self = .int(v)
        } else if let v = try? container.decode(Double.self) {
            self = .double(v)
        } else if let v = try? container.decode(String.self) {
            self = .string(v)
        } else {
            self = .null
        }
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch self {
        case .string(let v): try container.encode(v)
        case .int(let v): try container.encode(v)
        case .double(let v): try container.encode(v)
        case .bool(let v): try container.encode(v)
        case .null: try container.encodeNil()
        }
    }
}
