import Foundation

/// Guards a `CheckedContinuation` against double-resume and provides a
/// timeout escape hatch.
///
/// Why this exists (followup #1 to MEL-43 audit):
///
/// `HealthKitService` wraps `HKStatisticsQuery` (an Objective-C callback
/// API) in `withCheckedContinuation` to expose a Swift `async` interface.
/// The audit flagged two real risks:
///
/// 1. **Double-resume crash**: if HealthKit calls the result handler twice
///    (rare but documented for some HK queries on iOS 17+ batch updates),
///    `continuation.resume(returning:)` is called twice → `withCheckedContinuation`
///    runtime-traps in DEBUG, undefined behavior in RELEASE.
///
/// 2. **Never-resume hang**: if HealthKit's daemon dies or returns no result,
///    the handler is never called and the awaiting Task hangs forever. No
///    timeout means scheduled syncs accumulate stuck tasks.
///
/// `ContinuationGuard` solves both:
///
/// - `tryResume(with:)` is lock-guarded; second call returns false silently.
/// - The caller arms a timeout Task that calls `tryResume(with: nil)` after
///   the budget expires. Whichever fires first wins; the other is a no-op.
///
/// Generic over the continuation's value type so both `Double?` and other
/// optional shapes work.
// T: Sendable so `value: T` can cross the actor boundary into
// `continuation.resume(returning:)` under Swift 6 strict concurrency.
final class ContinuationGuard<T: Sendable>: @unchecked Sendable {
    private let lock = NSLock()
    private var fired = false

    /// Resume the continuation with the given value, but only if it has
    /// not been resumed already. Returns true if this call won the race.
    @discardableResult
    func tryResume(continuation: CheckedContinuation<T, Never>, with value: T) -> Bool {
        lock.lock()
        let canFire = !fired
        if canFire { fired = true }
        lock.unlock()
        if canFire {
            continuation.resume(returning: value)
        }
        return canFire
    }
}
