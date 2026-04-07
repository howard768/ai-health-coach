import Foundation
import TelemetryDeck

// MARK: - Meld Analytics Service
// Thin wrapper around TelemetryDeck for product analytics.
// Hybrid architecture:
// - TelemetryDeck: product analytics (screen views, taps, funnels) — NO PHI
// - FastAPI backend: health-sensitive events (anything referencing user health data)
//
// TelemetryDeck double-hashes user IDs — neither we nor they can identify users.
// All signals are privacy-safe by design.

enum Analytics {

    // MARK: - Initialization

    static func initialize() {
        let config = TelemetryDeck.Config(appID: "8B229662-CCE8-4468-847E-6A097C4D0E1D")
        TelemetryDeck.initialize(config: config)
    }

    // MARK: - Core Signal

    static func signal(_ name: String, parameters: [String: String] = [:]) {
        TelemetryDeck.signal(name, parameters: parameters)
    }

    // MARK: - Onboarding Events

    enum Onboarding {
        static func welcomeViewed() {
            signal("onboarding.welcome.viewed")
        }

        static func appleSignInTapped() {
            signal("onboarding.apple_signin.tapped")
        }

        static func appleSignInCompleted() {
            signal("onboarding.apple_signin.completed")
        }

        static func appleSignInFailed() {
            signal("onboarding.apple_signin.failed")
        }

        static func goalsViewed() {
            signal("onboarding.goals.viewed")
        }

        static func goalsSelected(goals: [String]) {
            signal("onboarding.goals.selected", parameters: ["goals": goals.joined(separator: ",")])
        }

        static func goalsContinued() {
            signal("onboarding.goals.continued")
        }

        static func profileViewed() {
            signal("onboarding.profile.viewed")
        }

        static func profilePrefilledFields(count: Int) {
            signal("onboarding.profile.prefilled_fields", parameters: ["count": String(count)])
        }

        static func profileSkipped() {
            signal("onboarding.profile.skipped")
        }

        static func profileCompleted() {
            signal("onboarding.profile.completed")
        }

        static func connectViewed() {
            signal("onboarding.connect.viewed")
        }

        static func ouraConnectTapped() {
            signal("onboarding.connect.oura.tapped")
        }

        static func ouraConnected() {
            signal("onboarding.connect.oura.completed")
        }

        static func ouraFailed() {
            signal("onboarding.connect.oura.failed")
        }

        static func healthKitTapped() {
            signal("onboarding.connect.healthkit.tapped")
        }

        static func healthKitGranted() {
            signal("onboarding.connect.healthkit.granted")
        }

        static func healthKitDenied() {
            signal("onboarding.connect.healthkit.denied")
        }

        static func connectContinued() {
            signal("onboarding.connect.continued")
        }

        static func syncStarted() {
            signal("onboarding.sync.started")
        }

        static func syncCompleted() {
            signal("onboarding.sync.completed")
        }

        static func dashboardReached() {
            signal("onboarding.dashboard.reached")
        }
    }

    // MARK: - Dashboard Events

    enum Dashboard {
        static func viewed() {
            signal("dashboard.viewed")
        }

        static func insightCardTapped() {
            signal("dashboard.insight_card.tapped")
        }

        static func metricCardTapped(metric: String) {
            signal("dashboard.metric_card.tapped", parameters: ["metric": metric])
        }

        static func pullToRefresh() {
            signal("dashboard.pull_to_refresh")
        }
    }

    // MARK: - Tab Events

    enum Navigation {
        static func tabSwitched(to tab: String) {
            signal("navigation.tab_switched", parameters: ["tab": tab])
        }
    }

    // MARK: - Coach Events

    enum Coach {
        static func chatOpened() {
            signal("coach.chat.opened")
        }

        static func messageSent() {
            signal("coach.message.sent")
        }

        static func quickActionTapped(action: String) {
            signal("coach.quick_action.tapped", parameters: ["action": action])
        }
    }
}
