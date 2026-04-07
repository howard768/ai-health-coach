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
    let lastSynced: Date?
}

struct HealthMetric: Identifiable, Hashable {
    let id = UUID()
    let category: MetricCategory
    let label: String
    let value: String
    let unit: String
    let subtitle: String
    let trend: MetricTrend
}

enum MetricCategory: String, CaseIterable, Hashable {
    case sleepEfficiency
    case hrv
    case restingHR
    case consistency

    /// Human-readable name for VoiceOver
    var accessibilityName: String {
        switch self {
        case .sleepEfficiency: "Sleep Efficiency"
        case .hrv: "Heart Rate Variability"
        case .restingHR: "Resting Heart Rate"
        case .consistency: "Training Consistency"
        }
    }

    /// SF Symbol placeholder for category identification
    /// Will be replaced with custom icons from Figma
    var iconName: String {
        switch self {
        case .sleepEfficiency: "moon.fill"
        case .hrv: "waveform.path.ecg"
        case .restingHR: "heart.fill"
        case .consistency: "calendar"
        }
    }
}

enum MetricTrend: Hashable {
    case positive
    case neutral
    case negative

    var accessibilityLabel: String {
        switch self {
        case .positive: "trending up"
        case .neutral: "stable"
        case .negative: "trending down"
        }
    }
}

struct RecoveryReadiness: Hashable {
    let level: ReadinessLevel
    let description: String
}

enum ReadinessLevel: String, Hashable {
    case high = "High"
    case moderate = "Moderate"
    case low = "Low"
}

struct CoachInsight: Identifiable {
    let id = UUID()
    let message: String
    let timestamp: Date
}
