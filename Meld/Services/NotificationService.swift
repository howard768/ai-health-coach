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
    func getPermissionStatus() async -> UNAuthorizationStatus {
        let settings = await UNUserNotificationCenter.current().notificationSettings()
        return settings.authorizationStatus
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
