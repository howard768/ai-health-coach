import SwiftUI

@main
struct MeldApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    @AppStorage("hasCompletedOnboarding") private var hasCompletedOnboarding = false

    init() {
        #if DEBUG
        DSFontDebug.verifyFonts()
        #endif

        Analytics.initialize()
    }

    var body: some Scene {
        WindowGroup {
            Group {
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
            .onOpenURL { url in
                NotificationNavigator.shared.handle(url: url)
            }
        }
    }
}
