import SwiftUI

@main
struct MeldApp: App {
    @State private var hasCompletedOnboarding = false

    init() {
        #if DEBUG
        DSFontDebug.verifyFonts()
        #endif

        Analytics.initialize()
    }

    var body: some Scene {
        WindowGroup {
            if hasCompletedOnboarding {
                MainTabView()
            } else {
                OnboardingFlow {
                    Analytics.Onboarding.dashboardReached()
                    withAnimation(DSMotion.emphasis) {
                        hasCompletedOnboarding = true
                    }
                }
            }
        }
    }
}
