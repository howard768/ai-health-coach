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

    /// Signal Engine Phase 4 card. Nil when the backend returned
    /// ``has_card=false`` (shadow mode, cap hit, or no candidates for
    /// today). DashboardView renders ``SignalInsightCard`` when non-nil
    /// and falls back to the legacy ``CoachInsightCard`` otherwise.
    var signalInsight: SignalInsight? = nil
    /// Surface reason when ``signalInsight`` is nil, for logging only.
    var signalInsightReason: String? = nil

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

        // Phase 4 Signal Engine card. Fetch in parallel semantics (sequential
        // is fine here — both are small). Failures of THIS fetch should NOT
        // break the dashboard; the legacy CoachInsightCard still renders
        // when signalInsight stays nil.
        await refreshSignalInsight()

        isLoading = false
    }

    /// Fetch today's ranked Signal Engine card, if any. Swallows errors
    /// so a broken signal endpoint does not degrade the rest of the
    /// dashboard. The fallback when ``signalInsight`` is nil is the
    /// legacy ``CoachInsightCard``.
    func refreshSignalInsight() async {
        do {
            let result = try await SignalRanker.shared.fetchTodayInsight()
            switch result {
            case .card(let insight):
                signalInsight = insight
                signalInsightReason = nil
            case .none(let reason):
                signalInsight = nil
                signalInsightReason = reason
            }
        } catch {
            // Defensive: never break the dashboard over the Signal surface.
            signalInsight = nil
            signalInsightReason = "fetch_failed"
        }
    }

    /// Submit feedback on the currently-shown signal insight card. No-op
    /// if ``signalInsight`` is nil (defensive). Does not mutate local
    /// state — the card view owns its own `submittedFeedback` marker.
    func submitInsightFeedback(_ feedback: SignalInsightFeedback) async {
        guard let insight = signalInsight else { return }
        do {
            try await SignalRanker.shared.submitFeedback(
                rankingID: insight.id,
                feedback: feedback
            )
        } catch {
            // Feedback failing is not a user-visible error; the backend will
            // accept a re-submission next session.
        }
    }

    // MARK: - Computed Properties

    var greeting: String {
        if !dashboardData.greeting.isEmpty {
            return dashboardData.greeting
        }
        let hour = Calendar.current.component(.hour, from: Date())
        let timeOfDay: String
        switch hour {
        case 5..<12: timeOfDay = "morning"
        case 12..<17: timeOfDay = "afternoon"
        case 17..<22: timeOfDay = "evening"
        default: timeOfDay = "night"
        }
        return "Good \(timeOfDay)"
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
