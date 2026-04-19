import Foundation
import Testing
@testable import Meld

// MARK: - Tab enum
//
// The tab order is the user-facing IA contract. The titles are the labels
// shown in the tab bar. Pinning both here so a future rename of one case
// without updating the other doesn't slip through.

@Test func tabOrderMatchesDesignSystem() async throws {
    // Order from the Meld Design System UI kit (2026-04-19):
    // Today / Trends / Coach / Log / You. Coach sits in the middle.
    #expect(Tab.allCases == [.home, .trends, .coach, .log, .you])
}

@Test func tabTitlesAreSentenceCase() async throws {
    #expect(Tab.home.title == "Today")
    #expect(Tab.trends.title == "Trends")
    #expect(Tab.coach.title == "Coach")
    #expect(Tab.log.title == "Log")
    #expect(Tab.you.title == "You")
}

@Test func tabRawValuesAreStableForDeepLinks() async throws {
    // Raw values are consumed by AppDelegate.pendingTab and the
    // MeldSwitchTab NotificationCenter post in DashboardView.
    // Renaming a case without auditing those call sites would silently
    // break notification routing.
    #expect(Tab.home.rawValue == "home")
    #expect(Tab.trends.rawValue == "trends")
    #expect(Tab.coach.rawValue == "coach")
    #expect(Tab.log.rawValue == "log")
    #expect(Tab.you.rawValue == "you")
}

// MARK: - NotificationNavigator deep links
//
// Backend currently only sends meld://coach, meld://dashboard, meld://trends
// (see backend/app/services/notification_content.py). The shim still maps
// the legacy meals/profile hosts so any in-flight notification queued
// against an older app version still routes after the rename.

@MainActor
@Test func deepLinkRoutesNewHostsToRenamedTabs() async throws {
    let nav = NotificationNavigator.shared
    nav.pendingTab = nil

    nav.handle(url: URL(string: "meld://today")!)
    #expect(nav.pendingTab == .home)

    nav.handle(url: URL(string: "meld://trends")!)
    #expect(nav.pendingTab == .trends)

    nav.handle(url: URL(string: "meld://coach")!)
    #expect(nav.pendingTab == .coach)

    nav.handle(url: URL(string: "meld://log")!)
    #expect(nav.pendingTab == .log)

    nav.handle(url: URL(string: "meld://you")!)
    #expect(nav.pendingTab == .you)
}

@MainActor
@Test func deepLinkLegacyHostsStillRoute() async throws {
    let nav = NotificationNavigator.shared
    nav.pendingTab = nil

    nav.handle(url: URL(string: "meld://dashboard")!)
    #expect(nav.pendingTab == .home, "legacy 'dashboard' should still route to .home")

    nav.handle(url: URL(string: "meld://meals")!)
    #expect(nav.pendingTab == .log, "legacy 'meals' should route to .log post-rename")

    nav.handle(url: URL(string: "meld://profile")!)
    #expect(nav.pendingTab == .you, "legacy 'profile' should route to .you post-rename")
}

@MainActor
@Test func deepLinkUnknownHostIsNoop() async throws {
    let nav = NotificationNavigator.shared
    nav.pendingTab = .coach

    nav.handle(url: URL(string: "meld://nonsense")!)
    #expect(nav.pendingTab == .coach, "unknown host must not clobber pendingTab")
}
