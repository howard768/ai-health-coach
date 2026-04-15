import UIKit
import UserNotifications

/// Bridges SwiftUI to UIKit's push notification lifecycle.
/// Handles device token registration, foreground notification display,
/// and notification tap actions.
final class AppDelegate: NSObject, UIApplicationDelegate, @preconcurrency UNUserNotificationCenterDelegate {

    func application(
        _ application: UIApplication,
        didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil
    ) -> Bool {
        UNUserNotificationCenter.current().delegate = self
        registerNotificationCategories()

        // Skip the side-effectful auto-runs (push registration + HealthKit
        // sync) when launched under a test bundle. CI runs the Meld.app
        // host unsigned (CODE_SIGNING_ALLOWED=NO for unit + snapshot tests),
        // which means entitled APIs like HealthKit fail hard enough to
        // signal-trap the app before tests execute.
        // `XCTestConfigurationFilePath` is set by Xcode whenever the process
        // is launched as a test host (XCTest or Swift Testing), so this
        // guard is production-inert. Fixes "Early unexpected exit" +
        // "Test crashed with signal trap before starting test execution"
        // on the iOS CI test step.
        let isRunningTests = ProcessInfo.processInfo
            .environment["XCTestConfigurationFilePath"] != nil

        if !isRunningTests {
            // Always re-register for remote notifications on launch
            // (token may have changed, or permission was granted in a previous install)
            Task {
                let status = await NotificationService.shared.getPermissionStatus()
                if status == .authorized {
                    await MainActor.run {
                        UIApplication.shared.registerForRemoteNotifications()
                    }
                    Log.notifications.info("Re-registering for remote notifications on launch")
                }
            }

            // Auto-sync HealthKit data on every launch
            Task {
                if HealthKitService.shared.isAvailable {
                    let steps = await HealthKitService.shared.queryTodaySteps()
                    if steps != nil {
                        // HealthKit is authorized — sync data to backend
                        HealthKitService.shared.isAuthorized = true
                        await HealthKitService.shared.syncToBackend()
                        Log.healthKit.info("Auto-synced on launch")
                    }
                }
            }
        }

        return true
    }

    // MARK: - Token Registration

    func application(
        _ application: UIApplication,
        didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data
    ) {
        let token = deviceToken.map { String(format: "%02x", $0) }.joined()
        Task {
            await NotificationService.shared.registerToken(token)
        }
    }

    func application(
        _ application: UIApplication,
        didFailToRegisterForRemoteNotificationsWithError error: Error
    ) {
        Log.notifications.error("Registration failed: \(error.localizedDescription)")
    }

    // MARK: - Foreground Notification Display
    // Uses completion handler variant — the async variant deadlocks in Swift 6.

    func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        willPresent notification: UNNotification,
        withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void
    ) {
        completionHandler([.banner, .sound, .badge])
    }

    // MARK: - Notification Tap Handling
    // Uses completion handler variant — the async variant deadlocks in Swift 6.

    func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        didReceive response: UNNotificationResponse,
        withCompletionHandler completionHandler: @escaping () -> Void
    ) {
        let userInfo = response.notification.request.content.userInfo

        // Determine which tab to open — action buttons take priority
        let tabName: String
        switch response.actionIdentifier {
        case "REVIEW":
            tabName = "home"
        case "ASK_COACH", "TELL_ME_MORE":
            tabName = "coach"
        case "WIND_DOWN", "LOG_NOW":
            tabName = "home"
        case "SEE_REVIEW":
            tabName = "trends"
        default:
            if let deepLink = userInfo["deep_link"] as? String,
               let url = URL(string: deepLink),
               let host = url.host {
                tabName = host == "dashboard" ? "home" : host
            } else {
                tabName = "home"
            }
        }

        AppDelegate.pendingTab = tabName
        Log.notifications.debug("Set pendingTab to: \(tabName)")
        completionHandler()
    }

    // Static storage for pending navigation — read by MainTabView
    nonisolated(unsafe) static var pendingTab: String?

    // MARK: - Notification Categories (Action Buttons)

    private func registerNotificationCategories() {
        let reviewAction = UNNotificationAction(
            identifier: "REVIEW",
            title: "Review",
            options: .foreground
        )
        let askCoachAction = UNNotificationAction(
            identifier: "ASK_COACH",
            title: "Ask Coach",
            options: .foreground
        )
        let tellMeMoreAction = UNNotificationAction(
            identifier: "TELL_ME_MORE",
            title: "Tell me more",
            options: .foreground
        )
        let windDownAction = UNNotificationAction(
            identifier: "WIND_DOWN",
            title: "Wind down",
            options: .foreground
        )

        let logNowAction = UNNotificationAction(
            identifier: "LOG_NOW",
            title: "Log now",
            options: .foreground
        )
        let seeReviewAction = UNNotificationAction(
            identifier: "SEE_REVIEW",
            title: "See full review",
            options: .foreground
        )

        let morningBrief = UNNotificationCategory(
            identifier: "MORNING_BRIEF",
            actions: [reviewAction, askCoachAction],
            intentIdentifiers: []
        )
        let coachingNudge = UNNotificationCategory(
            identifier: "COACHING_NUDGE",
            actions: [tellMeMoreAction],
            intentIdentifiers: []
        )
        let bedtimeCoaching = UNNotificationCategory(
            identifier: "BEDTIME_COACHING",
            actions: [windDownAction],
            intentIdentifiers: []
        )
        let streakSaver = UNNotificationCategory(
            identifier: "STREAK_SAVER",
            actions: [logNowAction],
            intentIdentifiers: []
        )
        let weeklyReview = UNNotificationCategory(
            identifier: "WEEKLY_REVIEW",
            actions: [seeReviewAction],
            intentIdentifiers: []
        )
        let healthAlert = UNNotificationCategory(
            identifier: "HEALTH_ALERT",
            actions: [reviewAction],
            intentIdentifiers: []
        )

        UNUserNotificationCenter.current().setNotificationCategories([
            morningBrief, coachingNudge, bedtimeCoaching,
            streakSaver, weeklyReview, healthAlert,
        ])
    }
}
