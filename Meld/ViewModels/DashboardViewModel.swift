import Foundation

// MARK: - Dashboard View Model
// Provides data for the Dashboard screen.
// Currently serves mock data. Will pull from backend API in Cycle 1.

@Observable @MainActor
final class DashboardViewModel {

    // MARK: - State

    enum ViewState {
        case loading
        case loaded
        case empty
        case error(DashboardError)
    }

    var viewState: ViewState = .loaded
    var dashboardData: DashboardData
    var isLoading: Bool = false
    var error: DashboardError? = nil

    enum DashboardError: Error, LocalizedError {
        case networkFailure
        case noData
        case staleData

        var errorDescription: String? {
            switch self {
            case .networkFailure: "Unable to connect. Check your connection."
            case .noData: "No health data available. Connect a wearable in Profile."
            case .staleData: "Data may be outdated. Pull to refresh."
            }
        }
    }

    init() {
        self.dashboardData = Self.mockData()
    }

    // MARK: - Actions

    /// Pull-to-refresh — tries backend first, falls back to mock data
    func refresh() async {
        isLoading = true
        error = nil

        do {
            let response = try await APIClient.shared.fetchDashboard()
            dashboardData = response.toDashboardData()
            viewState = .loaded
        } catch {
            // Backend not available — use mock data silently
            dashboardData = Self.mockData()
            viewState = .loaded
        }

        isLoading = false
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
        // TODO: Pull user name from profile/backend
        return "Good \(timeOfDay), Brock"
    }

    var dateString: String {
        let formatter = DateFormatter()
        formatter.dateFormat = "EEEE, MMMM d"
        return formatter.string(from: Date())
    }

    var lastSyncedString: String? {
        guard let lastSynced = dashboardData.lastSynced else { return nil }
        let formatter = RelativeDateTimeFormatter()
        formatter.unitsStyle = .abbreviated
        return "Synced \(formatter.localizedString(for: lastSynced, relativeTo: Date()))"
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
                timestamp: Date().addingTimeInterval(-300) // 5 min ago
            ),
            lastSynced: Date().addingTimeInterval(-120) // 2 min ago
        )
    }
}
