import SwiftUI

@main
struct MeldApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    @AppStorage("hasCompletedOnboarding") private var hasCompletedOnboarding = false
    @StateObject private var authState = AuthSessionState.shared

    init() {
        #if DEBUG
        DSFontDebug.verifyFonts()
        #endif

        Analytics.initialize()
    }

    var body: some Scene {
        WindowGroup {
            Group {
                if !authState.isSignedIn {
                    // Not signed in → always show onboarding (Welcome → Sign in with Apple)
                    OnboardingFlow {
                        Analytics.Onboarding.dashboardReached()
                        withAnimation(DSMotion.emphasis) {
                            hasCompletedOnboarding = true
                        }
                    }
                } else if hasCompletedOnboarding {
                    // Signed in and past first-run → main app
                    MainTabView()
                } else {
                    // Signed in but still in onboarding (goals, profile, connect, etc.)
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
            .task {
                // First-launch Keychain wipe (prevents refurbished-device token inheritance)
                await KeychainStore.wipeKeychainOnFirstLaunchIfNeeded()
                // Bootstrap auth state — if a token is stored, mark session active
                await AuthManager.shared.bootstrapSession()
                // After reinstall, AppStorage resets to false. If the backend says the
                // user already completed onboarding, skip it without showing any UI.
                if authState.isSignedIn && !hasCompletedOnboarding {
                    if let profile = try? await APIClient.shared.fetchUserProfile(),
                       profile.onboarding_complete == true {
                        hasCompletedOnboarding = true
                    }
                }
            }
        }
    }
}
