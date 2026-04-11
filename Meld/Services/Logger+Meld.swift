import Foundation
import OSLog

// MARK: - Meld Logger
//
// P3-2: Centralized os.Logger replacement for the ad-hoc print() calls
// scattered across the iOS codebase. Using os.Logger gives us:
//
// - Structured filterable logs in Console.app and the Xcode console
// - Per-subsystem categories so you can grep for [HealthKit] vs [Auth]
// - Privacy redaction by default in Release builds
// - No string formatting overhead when the log level is filtered out
// - Centralized configuration if we ever want to ship logs to a service
//
// Usage:
//   Log.healthKit.info("Synced \(metrics.count) metrics to backend")
//   Log.notifications.error("Permission request failed: \(error.localizedDescription)")
//   Log.auth.debug("Refresh token rotated")
//
// All categories share the bundle identifier as their subsystem so they
// roll up under one app entry in Console.app.

enum Log {
    private static let subsystem = Bundle.main.bundleIdentifier ?? "com.heymeld.app"

    /// HealthKit reads, authorization, and backend sync
    static let healthKit = Logger(subsystem: subsystem, category: "HealthKit")

    /// Push notifications: APNs registration, permission, delivery
    static let notifications = Logger(subsystem: subsystem, category: "Notifications")

    /// API client: requests, responses, retries
    static let api = Logger(subsystem: subsystem, category: "API")

    /// Sign in with Apple, JWT, refresh, Keychain
    static let auth = Logger(subsystem: subsystem, category: "Auth")

    /// Onboarding flow
    static let onboarding = Logger(subsystem: subsystem, category: "Onboarding")

    /// Meals & food logging
    static let meals = Logger(subsystem: subsystem, category: "Meals")

    /// Coach chat
    static let coach = Logger(subsystem: subsystem, category: "Coach")

    /// Design system: font registration, etc. (rarely used)
    static let designSystem = Logger(subsystem: subsystem, category: "DesignSystem")

    /// Generic app lifecycle: launch, scene phase, deep links
    static let app = Logger(subsystem: subsystem, category: "App")
}
