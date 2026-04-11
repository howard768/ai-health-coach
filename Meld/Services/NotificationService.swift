import UserNotifications
import UIKit

/// Manages push notification permissions and device token registration.
@MainActor
final class NotificationService {

    static let shared = NotificationService()
    private init() {}

    private let lastTokenKey = "meld_last_push_token"

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
    func getPermissionStatus() async -> UNAuthorizationStatus {
        let settings = await UNUserNotificationCenter.current().notificationSettings()
        return settings.authorizationStatus
    }

    /// Send device token to the backend for APNs delivery.
    /// Skips the network call if the token hasn't changed since the last successful registration.
    func registerToken(_ token: String) async {
        let stored = UserDefaults.standard.string(forKey: lastTokenKey)
        guard token != stored else {
            Log.notifications.debug("Push token unchanged — skipping registration")
            return
        }
        do {
            try await APIClient.shared.registerDeviceToken(token)
            UserDefaults.standard.set(token, forKey: lastTokenKey)
            Log.notifications.info("Token registered with backend")
        } catch {
            Log.notifications.error("Token registration failed: \(error.localizedDescription)")
        }
    }
}
