import SwiftUI

// MARK: - Main Tab Navigation
// Custom tab bar with Phosphor + SquatBlob icons and glassmorphic background.
// Manages cross-tab navigation (e.g., "Continue in chat" → Coach tab).
// Content gets proper safe area inset to clear the custom tab bar.

struct MainTabView: View {
    @State private var selectedTab: Tab = .home
    @State private var coachViewModel = CoachViewModel()
    @Environment(\.scenePhase) private var scenePhase

    var body: some View {
        // iOS 26 SDK: the previous ZStack(.bottom) + safeAreaInset(.bottom)
        // pattern caused the tab bar to render in the middle of the screen
        // (safe-area calculations changed under Liquid Glass). The blessed
        // SwiftUI pattern is `.safeAreaInset(edge: .bottom)` on the content
        // itself — that pins the tab bar to the bottom safe area on every
        // SDK from iOS 16 onward, including 26.
        Group {
            switch selectedTab {
            case .home:
                NavigationStack {
                    DashboardView(switchToTab: switchToTab)
                }
            case .trends:
                NavigationStack {
                    TrendsView()
                }
            case .coach:
                CoachChatView(viewModel: coachViewModel)
            case .log:
                MealsView()
            case .you:
                NavigationStack {
                    ProfileSettingsView()
                }
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .safeAreaInset(edge: .bottom, spacing: 0) {
            MeldTabBar(selectedTab: $selectedTab)
                .ignoresSafeArea(.keyboard, edges: .bottom)
        }
        .offlineBanner()  // P2-10: app-wide offline indicator
        .onAppear { checkPendingTab() }
        .onChange(of: scenePhase) { _, phase in
            if phase == .active { checkPendingTab() }
        }
        .onReceive(NotificationCenter.default.publisher(for: .meldSwitchTab)) { notification in
            if let tabName = notification.userInfo?["tab"] as? String,
               let tab = Tab(rawValue: tabName) {
                // If a message was passed (e.g. "Ask coach about this"), auto-send it
                if tab == .coach, let message = notification.userInfo?["message"] as? String {
                    coachViewModel.prefill(message)
                }
                switchToTab(tab)
            }
        }
    }

    /// Check if a notification action set a pending tab to navigate to.
    /// `consume()` is atomic (read + clear in one critical section) — a new
    /// notification arriving during the consume call waits and is preserved
    /// for the next checkPendingTab() invocation.
    private func checkPendingTab() {
        guard let tabName = AppDelegate.pendingTab.consume() else { return }
        if let tab = Tab(rawValue: tabName) {
            switchToTab(tab)
        }
    }

    // MARK: - Cross-tab Navigation

    private func switchToTab(_ tab: Tab) {
        withAnimation(DSMotion.snappy) {
            selectedTab = tab
        }
        DSHaptic.selection()
    }
}

// MARK: - Tab Definition

enum Tab: String, CaseIterable {
    case home
    case trends
    case coach
    case log
    case you

    var title: String {
        switch self {
        case .home: "Today"
        case .trends: "Trends"
        case .coach: "Coach"
        case .log: "Log"
        case .you: "You"
        }
    }
}

#Preview {
    MainTabView()
}
