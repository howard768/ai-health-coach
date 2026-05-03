import Foundation

/// Thread-safe holder for the "next tab to switch to" hint set by the
/// notification-tap handler and read on the next view-cycle by `MainTabView`.
///
/// Why this exists (followup #1 to MEL-43 audit):
///
/// The previous implementation was `nonisolated(unsafe) static var pendingTab:
/// String?` on `AppDelegate`. The `unsafe` opt-out silenced Swift 6's data-race
/// warnings without actually fixing the race:
///
/// 1. The writer is the `UNUserNotificationCenterDelegate` callback. UN
///    invokes it on an internal queue, NOT on MainActor.
/// 2. The reader is `MainTabView.checkPendingTab()`, which runs on MainActor
///    (it's invoked from SwiftUI `.onAppear` and `.onChange(of: scenePhase)`).
/// 3. Concurrent `set` and `read+clear` calls had no memory-order guarantees;
///    the reader could see stale values, partially-written strings (in theory),
///    or miss a notification entirely.
///
/// `NSLock` is used (not `OSAllocatedUnfairLock`, which is iOS 16+ only and
/// the project supports older targets) for cross-version safety. `consume()`
/// is the read-and-clear primitive, atomic: a writer that fires *during*
/// consume waits for the lock, then sets the new value, and the next reader
/// sees it cleanly.
///
/// `@unchecked Sendable` is correct here because every accessor takes the
/// lock; the unchecked annotation is the standard pattern for hand-rolled
/// thread-safe types under Swift 6 strict concurrency.
final class PendingTabHolder: @unchecked Sendable {
    private let lock = NSLock()
    private var value: String?

    /// Set the pending tab. Subsequent `consume()` returns this value once,
    /// then the holder is empty again. If `set` is called multiple times
    /// before `consume`, only the latest wins (overwrite semantics, the
    /// most-recent tap takes priority).
    func set(_ tab: String) {
        lock.lock()
        defer { lock.unlock() }
        value = tab
    }

    /// Atomically read the pending tab and clear it. Returns nil when empty.
    /// Replaces the prior `read AppDelegate.pendingTab; AppDelegate.pendingTab = nil`
    /// pair which had a window where another `set` could be lost.
    func consume() -> String? {
        lock.lock()
        defer { lock.unlock() }
        let result = value
        value = nil
        return result
    }
}
