import UserNotifications
import UIKit

/// Manages push notification permissions and device token registration.
@MainActor
final class NotificationService {

    static let shared = NotificationService()
    private init() {}

    /// Request notification permission and register for remote notifications.
    /// Returns true if permission was granted.
    func requestPermission() async -> Bool {
        do {
            let granted = try await UNUserNotificationCenter.current()
                .requestAuthorization(options: [.alert, .badge, .sound])

            if granted {
                UIApplication.shared.registerForRemoteNotifications()
                Analytics.signal("Notifications.permissionGranted")
            } else {
                Analytics.signal("Notifications.permissionDenied")
            }

            return granted
        } catch {
            Log.notifications.error("Permission request failed: \(error.localizedDescription)")
            return false
        }
    }

    /// Check current notification authorization status.
    ///
    /// Uses the completion-handler form of `getNotificationSettings` and
    /// extracts the Sendable `authorizationStatus` inside the completion so
    /// the non-Sendable `UNNotificationSettings` never crosses an actor
    /// boundary. The async variant `notificationSettings()` returns
    /// `UNNotificationSettings` across a nonisolated context, which Swift 6
    /// rejects. See feedback_swift6_delegates.md for the general pattern.
    func getPermissionStatus() async -> UNAuthorizationStatus {
        await withCheckedContinuation { continuation in
            UNUserNotificationCenter.current().getNotificationSettings { settings in
                continuation.resume(returning: settings.authorizationStatus)
            }
        }
    }

    /// Send device token to the backend for APNs delivery.
    func registerToken(_ token: String) async {
        do {
            try await APIClient.shared.registerDeviceToken(token)
            Log.notifications.info("Token registered with backend")
        } catch {
            Log.notifications.error("Token registration failed: \(error.localizedDescription)")
        }
    }
}
