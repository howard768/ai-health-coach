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
        case offline
        case networkFailure
        case noData
        case staleData

        var errorDescription: String? {
            switch self {
            case .offline: "You're offline. We'll refresh when you're back."
            case .networkFailure: "Unable to connect. Check your connection."
            case .noData: "No health data available. Connect a wearable in Profile."
            case .staleData: "Data may be outdated. Pull to refresh."
            }
        }
    }

    init() {
        // Start with empty data — refresh() fills from API on appear
        self.dashboardData = DashboardData(
            date: Date(),
            greeting: "",
            metrics: [],
            recoveryReadiness: RecoveryReadiness(level: .high, description: ""),
            coachInsight: CoachInsight(message: "", timestamp: Date()),
            lastSynced: nil
        )
        self.viewState = .loading
    }

    // MARK: - Actions

    /// Load dashboard data from backend API
    func refresh() async {
        isLoading = true
        error = nil

        // P2-10: Check reachability before hitting the network. When we're
        // offline we surface a dedicated "offline" state instead of the
        // generic "network failure" so the banner can explain what the user
        // needs to do. URLSession.waitsForConnectivity will still queue the
        // request once they're back — we just don't block the UI on it.
        if !NetworkMonitor.shared.isOnline {
            if dashboardData.metrics.isEmpty {
                self.error = .offline
                viewState = .error(.offline)
            }
            isLoading = false
            return
        }

        do {
            let response = try await APIClient.shared.fetchDashboard()
            dashboardData = response.toDashboardData()
            viewState = dashboardData.metrics.isEmpty ? .empty : .loaded
        } catch APIError.networkError {
            // URLError from transport layer — likely transient offline.
            if dashboardData.metrics.isEmpty {
                self.error = .offline
                viewState = .error(.offline)
            }
        } catch {
            if dashboardData.metrics.isEmpty {
                // First load failed — show error state
                self.error = .networkFailure
                viewState = .error(.networkFailure)
            }
            // If we already have data, keep showing it (stale is better than empty)
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

    // Mock data deleted in P2-9 cleanup. The dashboard pulls from /api/dashboard
    // and shows a loading state while the request is in flight. There is no
    // longer any seeded fake data anywhere in the iOS app.
}
