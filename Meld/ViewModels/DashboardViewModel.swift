import Foundation

// MARK: - Dashboard View Model
// Provides data for the Dashboard screen.
// Currently serves mock data. Will pull from backend API in Cycle 1.

@Observable
final class DashboardViewModel {

    var dashboardData: DashboardData

    init() {
        self.dashboardData = Self.mockData()
    }

    // MARK: - Computed Properties

    var greeting: String {
        let hour = Calendar.current.component(.hour, from: Date())
        let timeOfDay: String
        switch hour {
        case 5..<12: timeOfDay = "morning"
        case 12..<17: timeOfDay = "afternoon"
        case 17..<22: timeOfDay = "evening"
        default: timeOfDay = "night"
        }
        return "Good \(timeOfDay), Brock"
    }

    var dateString: String {
        let formatter = DateFormatter()
        formatter.dateFormat = "EEEE, MMMM d"
        return formatter.string(from: Date())
    }

    // MARK: - Mock Data

    private static func mockData() -> DashboardData {
        DashboardData(
            date: Date(),
            greeting: "Good morning, Brock",
            metrics: [
                HealthMetric(
                    category: .sleepEfficiency,
                    label: "Sleep Efficiency",
                    value: "91",
                    unit: "%",
                    subtitle: "7h 12m total",
                    trend: .positive
                ),
                HealthMetric(
                    category: .hrv,
                    label: "HRV Status",
                    value: "68",
                    unit: "ms",
                    subtitle: "\u{2191} 14% vs baseline",
                    trend: .positive
                ),
                HealthMetric(
                    category: .restingHR,
                    label: "Resting HR",
                    value: "58",
                    unit: "bpm",
                    subtitle: "Stable this week",
                    trend: .neutral
                ),
                HealthMetric(
                    category: .consistency,
                    label: "Consistency",
                    value: "5/7",
                    unit: "days",
                    subtitle: "On track this week",
                    trend: .positive
                ),
            ],
            recoveryReadiness: RecoveryReadiness(
                level: .high,
                description: "Good for intensity today"
            ),
            coachInsight: CoachInsight(
                message: "Your HRV is 14% above your 7-day baseline and sleep efficiency hit 91%. Great recovery night. Today is ideal for progressive overload on your leg day. Prioritize compound lifts.",
                timestamp: Date()
            )
        )
    }
}
