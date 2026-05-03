import SwiftUI

/// Outcome of the most recent Oura OAuth round-trip.
/// `ConnectDataView` (and any future settings screen) observes
/// `NotificationNavigator.shared.lastOuraOutcome` to surface success or
/// the error reason to the user.
enum OuraConnectOutcome: Equatable {
    case connected
    case error(reason: String)
}

/// Handles deep link navigation from push notifications.
/// Uses ObservableObject + @Published so the value is retained for cold-launch
/// scenarios, when MainTabView subscribes via .onReceive after the delegate
/// has already set the value, it immediately receives the pending tab.
@MainActor
final class NotificationNavigator: ObservableObject {
    static let shared = NotificationNavigator()
    private init() {}

    @Published var pendingTab: Tab?

    /// Most recent Oura OAuth outcome from a `meld://oura/connected` or
    /// `meld://oura/error?reason=...` deep link. Views consume this and clear it.
    @Published var lastOuraOutcome: OuraConnectOutcome?

    func navigate(to tab: Tab) {
        pendingTab = tab
    }

    /// Handle a meld:// URL scheme deep link.
    func handle(url: URL) {
        guard url.scheme == "meld", let host = url.host else { return }
        switch host {
        case "dashboard", "home", "today": navigate(to: .home)
        case "trends": navigate(to: .trends)
        case "coach": navigate(to: .coach)
        case "log", "meals": navigate(to: .log)
        case "you", "profile": navigate(to: .you)
        case "oura":
            // OAuth round-trip return path. Backend redirects here so Safari
            // closes and the user is back in the app (instead of stranded on
            // a JSON response).
            //   meld://oura/connected            -> success
            //   meld://oura/error?reason=<code>  -> failure (state mismatch,
            //                                       exchange_failed, etc.)
            if url.path == "/error" {
                let reason = URLComponents(url: url, resolvingAgainstBaseURL: false)?
                    .queryItems?
                    .first(where: { $0.name == "reason" })?
                    .value ?? "unknown"
                lastOuraOutcome = .error(reason: reason)
            } else {
                lastOuraOutcome = .connected
            }
        default: break
        }
    }
}
