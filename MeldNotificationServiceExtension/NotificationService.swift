import UserNotifications

/// Attaches rich media (recovery badge images) to push notifications.
/// Uses bundled images keyed by recovery level — no network download needed.
@preconcurrency
class NotificationService: UNNotificationServiceExtension {

    var contentHandler: ((UNNotificationContent) -> Void)?
    var bestAttemptContent: UNMutableNotificationContent?

    override func didReceive(
        _ request: UNNotificationRequest,
        withContentHandler contentHandler: @escaping (UNNotificationContent) -> Void
    ) {
        self.contentHandler = contentHandler
        bestAttemptContent = (request.content.mutableCopy() as? UNMutableNotificationContent)

        guard let content = bestAttemptContent else {
            contentHandler(request.content)
            return
        }

        // Check for recovery_level in payload to pick the right badge
        let userInfo = request.content.userInfo
        guard userInfo["media_url"] != nil else {
            // No rich media requested
            contentHandler(content)
            return
        }

        // Determine which badge to show from the media_url filename
        let mediaURL = (userInfo["media_url"] as? String) ?? ""
        let badgeName: String
        if mediaURL.contains("high") {
            badgeName = "recovery-high"
        } else if mediaURL.contains("low") {
            badgeName = "recovery-low"
        } else {
            badgeName = "recovery-moderate"
        }

        // Load from extension bundle
        if let imageURL = Bundle.main.url(forResource: badgeName, withExtension: "png") {
            // Copy to temp location (UNNotificationAttachment needs a file it can move)
            let tmpFile = FileManager.default.temporaryDirectory
                .appendingPathComponent(UUID().uuidString + ".png")
            do {
                try FileManager.default.copyItem(at: imageURL, to: tmpFile)
                let attachment = try UNNotificationAttachment(
                    identifier: "recovery-badge",
                    url: tmpFile
                )
                content.attachments = [attachment]
            } catch {
                // Graceful degradation — deliver without image
            }
        }

        contentHandler(content)
    }

    override func serviceExtensionTimeWillExpire() {
        if let contentHandler, let bestAttemptContent {
            contentHandler(bestAttemptContent)
        }
    }
}
