import SwiftUI

/// Handles deep link navigation from push notifications.
/// Uses ObservableObject + @Published so the value is retained for cold-launch
/// scenarios — when MainTabView subscribes via .onReceive after the delegate
/// has already set the value, it immediately receives the pending tab.
@MainActor
final class NotificationNavigator: ObservableObject {
    static let shared = NotificationNavigator()
    private init() {}

    @Published var pendingTab: Tab?

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
        default: break
        }
    }
}
