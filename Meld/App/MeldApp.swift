import SwiftUI

@main
struct MeldApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    @AppStorage("hasCompletedOnboarding") private var hasCompletedOnboarding = false
    @StateObject private var authState = AuthSessionState.shared

    #if DEBUG
    private static var isUITesting: Bool {
        UserDefaults.standard.bool(forKey: "uitesting-skip-auth")
    }
    private let skipAuth = MeldApp.isUITesting
    #endif

    init() {
        #if DEBUG
        DSFontDebug.verifyFonts()
        if MeldApp.isUITesting {
            UserDefaults.standard.set(true, forKey: "hasCompletedOnboarding")
            AuthSessionState.shared.isSignedIn = true
        }
        #endif

        Analytics.initialize()
    }

    var body: some Scene {
        WindowGroup {
            Group {
                #if DEBUG
                if skipAuth {
                    MainTabView()
                } else {
                    routedContent
                }
                #else
                routedContent
                #endif
            }
            .onOpenURL { url in
                NotificationNavigator.shared.handle(url: url)
            }
            .task {
                #if DEBUG
                guard !MeldApp.isUITesting else { return }
                #endif
                // First-launch Keychain wipe (prevents refurbished-device token inheritance)
                await KeychainStore.wipeKeychainOnFirstLaunchIfNeeded()
                // Bootstrap auth state — if a token is stored, mark session active
                await AuthManager.shared.bootstrapSession()
            }
        }
    }

    @ViewBuilder
    private var routedContent: some View {
        if !authState.isSignedIn {
            OnboardingFlow {
                Analytics.Onboarding.dashboardReached()
                withAnimation(DSMotion.emphasis) {
                    hasCompletedOnboarding = true
                }
            }
        } else if hasCompletedOnboarding {
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
