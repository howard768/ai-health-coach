import Foundation

// MARK: - Normalized Health Metrics
// These models represent health data from any source (Oura, Eight Sleep, etc.)
// in a normalized format that the app and AI coach can consume.

struct DashboardData: Identifiable {
    let id = UUID()
    let date: Date
    let greeting: String
    let metrics: [HealthMetric]
    let recoveryReadiness: RecoveryReadiness
    let coachInsight: CoachInsight
}

struct HealthMetric: Identifiable {
    let id = UUID()
    let category: MetricCategory
    let label: String
    let value: String
    let unit: String
    let subtitle: String
    let trend: MetricTrend
}

enum MetricCategory: String, CaseIterable {
    case sleepEfficiency
    case hrv
    case restingHR
    case consistency
}

enum MetricTrend {
    case positive
    case neutral
    case negative
}

struct RecoveryReadiness {
    let level: ReadinessLevel
    let description: String
}

enum ReadinessLevel: String {
    case high = "High"
    case moderate = "Moderate"
    case low = "Low"
}

struct CoachInsight: Identifiable {
    let id = UUID()
    let message: String
    let timestamp: Date
}
