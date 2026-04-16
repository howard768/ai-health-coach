import SwiftUI

@main
struct MeldApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    @AppStorage("hasCompletedOnboarding") private var hasCompletedOnboarding = false
    @StateObject private var authState = AuthSessionState.shared

    #if DEBUG
    private static var isUITesting: Bool {
        ProcessInfo.processInfo.arguments.contains("-uitesting-skip-auth")
            || UserDefaults.standard.bool(forKey: "uitesting-skip-auth")
            // Env-var fallback for XCUITest targets where launchArguments
            // are sometimes dropped or prefixed unexpectedly on CI runners.
            || ProcessInfo.processInfo.environment["MELD_UI_TESTING"] == "1"
    }
    private let skipAuth = MeldApp.isUITesting
    @State private var devLoginReady = false
    #endif

    init() {
        #if DEBUG
        DSFontDebug.verifyFonts()
        // Debug file for tracing auth bypass in simulator
        let debugMsg = """
        isUITesting=\(MeldApp.isUITesting)
        skipAuth=\(skipAuth)
        args=\(ProcessInfo.processInfo.arguments)
        defaults=\(UserDefaults.standard.dictionaryRepresentation().filter { $0.key.contains("uitesting") })
        """
        if let docs = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first {
            try? debugMsg.write(to: docs.appendingPathComponent("auth-debug.txt"), atomically: true, encoding: .utf8)
        }
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
                    if devLoginReady {
                        MainTabView()
                    } else {
                        Color(DSColor.Background.primary)
                    }
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
                if MeldApp.isUITesting {
                    // Auth bypass: show the tab bar immediately, then try to
                    // get a real API token in the background. Blocking on
                    // dev-login makes CI tests hang because the runner has
                    // no backend at 127.0.0.1:8000 — URLSession takes up to
                    // 45s to time out, and XCUITest times out first.
                    // Unblocking devLoginReady lets the tab bar render for
                    // the UI smoke test; API calls that need a token will
                    // fail gracefully if dev-login never completes.
                    devLoginReady = true
                    print("[MELD-DEBUG] .task: UI-testing dev-login fire-and-forget")
                    Task {
                        do {
                            let pair = try await APIClient.shared.devLogin()
                            print("[MELD-DEBUG] .task: dev-login success, token=\(pair.accessToken.prefix(20))...")
                            await APIClient.shared.setTestToken(pair.accessToken)
                            try? await KeychainStore.shared.saveAccessToken(pair.accessToken)
                            try? await KeychainStore.shared.saveRefreshToken(pair.refreshToken)
                        } catch {
                            print("[MELD-DEBUG] .task: dev-login FAILED (UI test; non-fatal): \(error)")
                        }
                    }
                    return
                }
                #endif
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

    @ViewBuilder
    private var routedContent: some View {
        // Single OnboardingFlow instance. Do NOT branch on authState.isSignedIn
        // here: doing so destroys the path-A OnboardingFlow (and its @State
        // OnboardingViewModel) the moment sign-in flips isSignedIn, resetting
        // the flow back to `.welcome` after the user just finished the sign-in
        // step. That was the "had to tap Sign in with Apple twice" bug in
        // build 3: the first tap succeeded and called viewModel.next(), but
        // the viewModel was immediately thrown away because isSignedIn flipped
        // and SwiftUI created a brand-new OnboardingFlow on the signed-in path.
        //
        // OnboardingFlow itself handles the signed-out to signed-in transition
        // internally (WelcomeView shows the Sign in with Apple button, then
        // viewModel.next() moves past it on success). We only swap to
        // MainTabView once hasCompletedOnboarding flips true at the end of
        // FirstSync.
        if hasCompletedOnboarding && authState.isSignedIn {
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
