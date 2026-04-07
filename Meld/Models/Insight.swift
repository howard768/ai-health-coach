import Foundation

// MARK: - Coach Insight Models
// Represents AI-generated insights from the coaching pipeline.
// These are pre-computed by the backend (Sonnet/Opus) and served to the client.

/// A cross-domain insight connecting multiple health data points
struct CrossDomainInsight: Identifiable, Codable {
    let id: UUID
    let title: String
    let body: String
    let dataPoints: [InsightDataPoint]
    let confidence: InsightConfidence
    let literatureReference: String?
    let createdAt: Date
}

/// A single data point referenced in an insight
struct InsightDataPoint: Identifiable, Codable {
    let id: UUID
    let metric: String
    let value: String
    let unit: String
    let source: DataSource
}

/// Source of health data
enum DataSource: String, Codable {
    case oura
    case eightSleep
    case garmin
    case appleHealth
    case manual
}

/// How confident the AI is in this insight
enum InsightConfidence: String, Codable {
    /// Sonnet-generated, not yet reviewed by Opus
    case provisional
    /// Opus-validated
    case validated
    /// Literature-backed causal claim
    case evidenceBased
}
