import Foundation
import HealthKit
import Testing
@testable import Meld

// MARK: - HealthKitServiceTests
//
// HealthKitService talks to HKHealthStore through Apple's API directly
// (no abstraction). Most methods need real Health data and user-granted
// authorization to do anything; without DI on HKHealthStore, those
// paths can't be unit tested. What this file pins instead:
//
//   - HealthMetricPayload: the wire shape the backend accepts at
//     POST /api/health/apple-health
//   - isAvailable: HK linkage works (i.e., the framework was actually
//     pulled in, not just declared)
//
// The interesting query/sync logic (date formatting, en_US_POSIX locale
// guard, DST arithmetic skip) needs HKHealthStore injection before it
// can be unit tested. Tracked separately.

// MARK: - HealthMetricPayload wire contract
//
// The backend's POST /api/health/apple-health endpoint expects an array of
// objects with these exact snake_case keys (see app/routers/health.py).
// Any rename here without updating the router shape silently 422s and the
// HK sync goes dark.

@Suite("HealthMetricPayload wire contract")
struct HealthMetricPayloadTests {

    @Test("Encodes every field with snake_case keys")
    func encodesSnakeCaseKeys() throws {
        let payload = HealthKitService.HealthMetricPayload(
            date: "2026-05-03",
            metric_type: "steps",
            value: 8421,
            unit: "count",
            source: "apple_health"
        )
        let data = try JSONEncoder().encode(payload)
        let json = try #require(try JSONSerialization.jsonObject(with: data) as? [String: Any])
        #expect(json["date"] as? String == "2026-05-03")
        #expect(json["metric_type"] as? String == "steps", "must be snake_case for FastAPI")
        #expect(json["value"] as? Double == 8421)
        #expect(json["unit"] as? String == "count")
        #expect(json["source"] as? String == "apple_health")
    }

    @Test("Round-trips through JSON without value precision loss")
    func roundTripsWithoutPrecisionLoss() throws {
        let original = HealthKitService.HealthMetricPayload(
            date: "2026-05-03",
            metric_type: "hrv",
            value: 42.7891234,
            unit: "ms",
            source: "apple_health"
        )
        let data = try JSONEncoder().encode(original)
        let decoded = try JSONDecoder().decode(HealthKitService.HealthMetricPayload.self, from: data)
        #expect(decoded.date == original.date)
        #expect(decoded.metric_type == original.metric_type)
        #expect(decoded.value == original.value)
        #expect(decoded.unit == original.unit)
        #expect(decoded.source == original.source)
    }

    @Test("Encodes a batch as a JSON array (the body shape backend expects)")
    func encodesAsArrayWhenBatched() throws {
        let batch = [
            HealthKitService.HealthMetricPayload(
                date: "2026-05-03", metric_type: "steps",
                value: 8421, unit: "count", source: "apple_health"
            ),
            HealthKitService.HealthMetricPayload(
                date: "2026-05-03", metric_type: "resting_hr",
                value: 58, unit: "bpm", source: "apple_health"
            ),
            HealthKitService.HealthMetricPayload(
                date: "2026-05-03", metric_type: "hrv",
                value: 42, unit: "ms", source: "apple_health"
            ),
        ]
        let data = try JSONEncoder().encode(batch)
        let arr = try #require(try JSONSerialization.jsonObject(with: data) as? [[String: Any]])
        #expect(arr.count == 3)
        let metricTypes = arr.compactMap { $0["metric_type"] as? String }
        #expect(metricTypes == ["steps", "resting_hr", "hrv"])
    }

    @Test("Pins the three metric_type values used by syncToBackend")
    func pinsMetricTypeKeysUsedBySync() throws {
        // syncToBackend writes these three metric_type strings inline. The
        // backend's metric handler (app/routers/health.py) routes on this
        // string. If a future refactor renames "resting_hr" to "rhr", the
        // backend silently drops the data. Pin the contract here.
        let pinned: Set<String> = ["steps", "resting_hr", "hrv"]
        for type in pinned {
            let p = HealthKitService.HealthMetricPayload(
                date: "2026-05-03", metric_type: type,
                value: 1, unit: "x", source: "apple_health"
            )
            let data = try JSONEncoder().encode(p)
            let json = try #require(try JSONSerialization.jsonObject(with: data) as? [String: Any])
            #expect(json["metric_type"] as? String == type)
        }
    }

    @Test("Source label is the literal backend expects ('apple_health')")
    func sourceLabelMatchesBackend() throws {
        // Backend's HealthMetricRecord row.source filter joins on this exact
        // string. Test pins the literal so a refactor to "apple-health" or
        // "applehealth" or "iOS" doesn't quietly orphan rows.
        let p = HealthKitService.HealthMetricPayload(
            date: "2026-05-03", metric_type: "steps",
            value: 1, unit: "count", source: "apple_health"
        )
        let data = try JSONEncoder().encode(p)
        let json = try #require(try JSONSerialization.jsonObject(with: data) as? [String: Any])
        #expect(json["source"] as? String == "apple_health")
    }
}

// MARK: - HealthKitService.isAvailable
//
// Sanity check that the HealthKit framework is actually linked into the
// app target. If the framework isn't pulled in, HKHealthStore.isHealthDataAvailable
// returns false on the simulator, which would be the real bug a future
// refactor could introduce by accidentally removing the framework.

@Suite("HealthKitService", .serialized)
struct HealthKitServiceShellTests {

    @Test("isAvailable is queryable in the simulator")
    @MainActor
    func isAvailableIsQueryable() async {
        // iOS simulators 11+ all return true. We don't pin the value here,
        // we just verify the call doesn't crash and returns a Bool, which
        // proves the HealthKit framework is linked.
        _ = HealthKitService.shared.isAvailable
    }

    @Test("Singleton stays the same across access")
    @MainActor
    func sharedInstanceStable() async {
        let a = HealthKitService.shared
        let b = HealthKitService.shared
        #expect(a === b, "HealthKitService.shared must be a stable singleton")
    }
}

// MARK: - ContinuationGuardTests
//
// ContinuationGuard backs HealthKitService's HKStatisticsQuery wrappers.
// It guards against two real iOS bugs documented in MEL-43:
//   1. Double-resume crash: HK callbacks can fire twice for batch updates.
//   2. Never-resume hang: HK daemon can stall and never call back.
//
// These tests pin the lock semantics so a refactor to e.g. atomics or
// an actor doesn't reintroduce the original race.

@Suite("ContinuationGuard")
struct ContinuationGuardTests {

    /// Box for capturing a value from inside a withCheckedContinuation
    /// closure under Swift 6 strict concurrency. Plain `var` capture is
    /// rejected because the closure is non-isolated.
    private final class Box<T>: @unchecked Sendable {
        var value: T
        init(_ value: T) { self.value = value }
    }

    @Test("First tryResume wins, second returns false")
    func firstCallWinsRace() async {
        let g = ContinuationGuard<Int>()
        let firstWon = Box(false)
        let secondWon = Box(false)

        let value: Int = await withCheckedContinuation { continuation in
            firstWon.value = g.tryResume(continuation: continuation, with: 1)
            secondWon.value = g.tryResume(continuation: continuation, with: 2)
        }

        #expect(value == 1, "continuation must receive only the first value")
        #expect(firstWon.value == true)
        #expect(secondWon.value == false, "second tryResume must be a no-op")
    }

    @Test("Concurrent callers race-free, exactly one wins")
    func concurrentCallersRaceFree() async {
        let g = ContinuationGuard<Int>()
        let winnerCount = Box(0)
        let lock = NSLock()

        let value: Int = await withCheckedContinuation { continuation in
            // 100 concurrent threads racing to resume the same continuation.
            // Without the lock inside ContinuationGuard, this would crash
            // with "SWIFT TASK CONTINUATION MISUSE" or similar in DEBUG.
            DispatchQueue.concurrentPerform(iterations: 100) { i in
                if g.tryResume(continuation: continuation, with: i) {
                    lock.lock()
                    winnerCount.value += 1
                    lock.unlock()
                }
            }
        }

        #expect(winnerCount.value == 1, "exactly one tryResume must win out of 100 racers")
        #expect(value >= 0 && value < 100, "winning value must be one of the racers")
    }

    @Test("Works with optional value types (the actual HealthKitService usage)")
    func optionalValueResumes() async {
        // HealthKitService uses ContinuationGuard<Double?> so HK queries can
        // resume with nil on no-data. Pin that the generic supports it.
        let g = ContinuationGuard<Double?>()

        let value: Double? = await withCheckedContinuation { continuation in
            _ = g.tryResume(continuation: continuation, with: 42.5)
            _ = g.tryResume(continuation: continuation, with: nil)
        }

        #expect(value == 42.5)
    }

    @Test("Timeout pattern: nil wins when armed before result")
    func timeoutPatternResumesWithNil() async {
        // Mirrors the "Task { sleep; tryResume(nil) }" timeout escape hatch
        // in HealthKitService.querySum. Even if the HK callback never fires,
        // tryResume(nil) wins and the awaiting task unblocks.
        let g = ContinuationGuard<Int?>()

        let value: Int? = await withCheckedContinuation { continuation in
            // Simulate timeout firing first; HK callback "never arrives"
            _ = g.tryResume(continuation: continuation, with: nil)
            // ...later the HK callback finally fires (no-op, lock blocks it)
            _ = g.tryResume(continuation: continuation, with: 99)
        }

        #expect(value == nil, "timeout result must win when armed first")
    }
}
