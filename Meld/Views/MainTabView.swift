import SwiftUI

// MARK: - Main Tab Navigation
// Custom tab bar with pillowy filled icons and glassmorphic background.
// Active state has depth: glow + scale + dot indicator.
// Haptic feedback on every tab change.

struct MainTabView: View {
    @State private var selectedTab: Tab = .home

    var body: some View {
        ZStack(alignment: .bottom) {
            // Content area
            Group {
                switch selectedTab {
                case .home:
                    DashboardView()
                case .coach:
                    PlaceholderTab(title: "Coach", subtitle: "Cycle 2")
                case .trends:
                    PlaceholderTab(title: "Trends", subtitle: "Cycle 3")
                case .meals:
                    PlaceholderTab(title: "Meals", subtitle: "Future")
                case .profile:
                    PlaceholderTab(title: "Profile", subtitle: "Future")
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)

            // Custom tab bar
            MeldTabBar(selectedTab: $selectedTab)
        }
        .ignoresSafeArea(.keyboard, edges: .bottom)
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
