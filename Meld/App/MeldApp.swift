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
                    // Auth bypass: get a real API token via dev-login so live data works.
                    // MainTabView is gated on devLoginReady to prevent a race with dashboard fetch.
                    print("[MELD-DEBUG] .task: calling dev-login")
                    do {
                        let pair = try await APIClient.shared.devLogin()
                        print("[MELD-DEBUG] .task: dev-login success, token=\(pair.accessToken.prefix(20))...")
                        // Store in-memory for unsigned builds (Keychain may not work
                        // without code signing entitlements).
                        await APIClient.shared.setTestToken(pair.accessToken)
                        // Also try Keychain as fallback for signed debug builds.
                        try? await KeychainStore.shared.saveAccessToken(pair.accessToken)
                        try? await KeychainStore.shared.saveRefreshToken(pair.refreshToken)
                    } catch {
                        print("[MELD-DEBUG] .task: dev-login FAILED: \(error)")
                    }
                    devLoginReady = true
                    return
                }
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
