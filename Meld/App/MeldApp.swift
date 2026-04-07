import SwiftUI

@main
struct MeldApp: App {
    @State private var hasCompletedOnboarding = false

    init() {
        #if DEBUG
        DSFontDebug.verifyFonts()
        #endif

        // Check if onboarding was previously completed
        // For now, always show onboarding in development
        // In production, this would check UserDefaults or Keychain
    }

    var body: some Scene {
        WindowGroup {
            if hasCompletedOnboarding {
                MainTabView()
            } else {
                OnboardingFlow {
                    withAnimation(DSMotion.emphasis) {
                        hasCompletedOnboarding = true
                    }
                }
            }
        }
    }
}
