import SwiftUI

// MARK: - Main Tab Navigation
// Custom tab bar with Phosphor + SquatBlob icons and glassmorphic background.
// Manages cross-tab navigation (e.g., "Continue in chat" → Coach tab).
// Content gets proper safe area inset to clear the custom tab bar.

struct MainTabView: View {
    @State private var selectedTab: Tab = .home

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

            // Custom tab bar
            MeldTabBar(selectedTab: $selectedTab)
        }
        .ignoresSafeArea(.keyboard, edges: .bottom)
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
