import SwiftUI

// MARK: - Main Tab Navigation
// Custom tab bar with Phosphor + SquatBlob icons and glassmorphic background.
// Manages cross-tab navigation (e.g., "Continue in chat" → Coach tab).
// Content gets proper safe area inset to clear the custom tab bar.

struct MainTabView: View {
    @State private var selectedTab: Tab = .home
    @Environment(\.scenePhase) private var scenePhase

    var body: some View {
        ZStack(alignment: .bottom) {
            // Content area with safe area inset for tab bar
            Group {
                switch selectedTab {
                case .home:
                    NavigationStack {
                        DashboardView(switchToTab: switchToTab)
                    }
                case .coach:
                    CoachChatView()
                case .trends:
                    NavigationStack {
                        TrendsView()
                    }
                case .meals:
                    MealsView()
                case .profile:
                    NavigationStack {
                        ProfileSettingsView()
                    }
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            // Push content up so it clears the tab bar
            .safeAreaInset(edge: .bottom) {
                Color.clear.frame(height: 80)
            }

            // Custom tab bar — stays at bottom even when keyboard is shown
            MeldTabBar(selectedTab: $selectedTab)
                .ignoresSafeArea(.keyboard, edges: .bottom)
        }
        .onAppear { checkPendingTab() }
        .onChange(of: scenePhase) { _, phase in
            if phase == .active { checkPendingTab() }
        }
        .onReceive(NotificationCenter.default.publisher(for: .init("MeldSwitchTab"))) { notification in
            if let tabName = notification.userInfo?["tab"] as? String,
               let tab = Tab(rawValue: tabName) {
                switchToTab(tab)
            }
        }
    }

    /// Check if a notification action set a pending tab to navigate to.
    private func checkPendingTab() {
        guard let tabName = AppDelegate.pendingTab else { return }
        AppDelegate.pendingTab = nil
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
    case coach
    case trends
    case meals
    case profile

    var title: String {
        switch self {
        case .home: "Home"
        case .coach: "Coach"
        case .trends: "Trends"
        case .meals: "Meals"
        case .profile: "Profile"
        }
    }
}

#Preview {
    MainTabView()
}
