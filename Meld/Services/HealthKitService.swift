import HealthKit
import Foundation

/// Manages all HealthKit interactions — authorization, queries, background delivery, and backend sync.
/// Uses iOS 17+ async/await query descriptors for Swift 6 concurrency safety.
@Observable @MainActor
final class HealthKitService {

    static let shared = HealthKitService()
    private init() {}

    private let store = HKHealthStore()

    var isAuthorized = false

    // MARK: - Availability

    var isAvailable: Bool {
        HKHealthStore.isHealthDataAvailable()
    }

    // MARK: - Data Types

    private let readTypes: Set<HKObjectType> = {
        var types: Set<HKObjectType> = [
            HKQuantityType(.stepCount),
            HKQuantityType(.heartRate),
            HKQuantityType(.restingHeartRate),
            HKQuantityType(.heartRateVariabilitySDNN),
            HKQuantityType(.activeEnergyBurned),
            HKQuantityType(.bodyMass),
            HKQuantityType(.height),
            HKCategoryType(.sleepAnalysis),
            HKObjectType.workoutType(),
        ]
        // Characteristics for onboarding prefill
        if let dob = HKCharacteristicType.characteristicType(forIdentifier: .dateOfBirth) {
            types.insert(dob)
        }
        return types
    }()

    // MARK: - Authorization

    func requestAuthorization() async -> Bool {
        guard isAvailable else { return false }
        do {
            try await store.requestAuthorization(toShare: [], read: readTypes)
            isAuthorized = true
            return true
        } catch {
            print("[HealthKit] Authorization failed: \(error)")
            return false
        }
    }

    // MARK: - Onboarding Prefill

    func getAge() -> Int? {
        guard let components = try? store.dateOfBirthComponents() else { return nil }
        guard let year = components.year else { return nil }
        return Calendar.current.component(.year, from: Date()) - year
    }

    func getLatestWeight() async -> Double? {
        await queryLatestQuantity(.bodyMass, unit: .pound())
    }

    func getLatestHeight() async -> Double? {
        // Returns height in inches
        await queryLatestQuantity(.height, unit: .inch())
    }

    // MARK: - Data Queries

    func queryTodaySteps() async -> Int? {
        let start = Calendar.current.startOfDay(for: Date())
        guard let sum = await querySum(.stepCount, from: start, to: Date(), unit: .count()) else { return nil }
        return Int(sum)
    }

    func queryRestingHR() async -> Double? {
        await queryLatestQuantity(.restingHeartRate, unit: .count().unitDivided(by: .minute()))
    }

    func queryHRV() async -> Double? {
        await queryLatestQuantity(.heartRateVariabilitySDNN, unit: .secondUnit(with: .milli))
    }

    func querySleepAnalysis(for date: Date) async -> [HKCategorySample] {
        // Calendar.date(byAdding:) can return nil at DST transitions / near
        // calendar boundaries. Guard rather than crash.
        let calendar = Calendar.current
        guard
            let start = calendar.date(byAdding: .day, value: -1, to: calendar.startOfDay(for: date)),
            let nextDay = calendar.date(byAdding: .day, value: 1, to: date)
        else {
            return []
        }
        let end = calendar.startOfDay(for: nextDay)

        let predicate = HKQuery.predicateForSamples(withStart: start, end: end)
        let descriptor = HKSampleQueryDescriptor(
            predicates: [.categorySample(type: HKCategoryType(.sleepAnalysis), predicate: predicate)],
            sortDescriptors: [SortDescriptor(\.startDate)]
        )

        do {
            return try await descriptor.result(for: store)
        } catch {
            print("[HealthKit] Sleep query failed: \(error)")
            return []
        }
    }

    // MARK: - Backend Sync

    struct HealthMetricPayload: Codable, Sendable {
        let date: String
        let metric_type: String
        let value: Double
        let unit: String
        let source: String
    }

    func syncToBackend() async {
        // Collect last 7 days of data
        var metrics: [HealthMetricPayload] = []
        let calendar = Calendar.current
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"

        for dayOffset in 0..<7 {
            // Skip the day if calendar arithmetic returns nil (DST/leap edge case)
            guard let date = calendar.date(byAdding: .day, value: -dayOffset, to: Date()) else {
                continue
            }
            let dateString = formatter.string(from: date)

            let dayStart = calendar.startOfDay(for: date)
            guard let dayEnd = calendar.date(byAdding: .day, value: 1, to: dayStart) else {
                continue
            }

            if let steps = await querySum(.stepCount, from: dayStart, to: dayEnd, unit: .count()) {
                metrics.append(HealthMetricPayload(date: dateString, metric_type: "steps", value: steps, unit: "count", source: "apple_health"))
            }

            if let rhr = await queryDayAverage(.restingHeartRate, date: date, unit: .count().unitDivided(by: .minute())) {
                metrics.append(HealthMetricPayload(date: dateString, metric_type: "resting_hr", value: rhr, unit: "bpm", source: "apple_health"))
            }

            if let hrv = await queryDayAverage(.heartRateVariabilitySDNN, date: date, unit: .secondUnit(with: .milli)) {
                metrics.append(HealthMetricPayload(date: dateString, metric_type: "hrv", value: hrv, unit: "ms", source: "apple_health"))
            }
        }

        if !metrics.isEmpty {
            do {
                try await APIClient.shared.syncHealthKitMetrics(metrics)
                print("[HealthKit] Synced \(metrics.count) metrics to backend")
            } catch {
                print("[HealthKit] Backend sync failed: \(error)")
            }
        }
    }

    // MARK: - Private Query Helpers

    private func queryLatestQuantity(_ identifier: HKQuantityTypeIdentifier, unit: HKUnit) async -> Double? {
        let descriptor = HKSampleQueryDescriptor(
            predicates: [.quantitySample(type: HKQuantityType(identifier), predicate: nil)],
            sortDescriptors: [SortDescriptor(\.startDate, order: .reverse)],
            limit: 1
        )
        do {
            let results = try await descriptor.result(for: store)
            return results.first?.quantity.doubleValue(for: unit)
        } catch {
            return nil
        }
    }

    private func querySum(_ identifier: HKQuantityTypeIdentifier, from start: Date, to end: Date, unit: HKUnit) async -> Double? {
        let type = HKQuantityType(identifier)
        let predicate = HKQuery.predicateForSamples(withStart: start, end: end)

        return await withCheckedContinuation { continuation in
            let query = HKStatisticsQuery(quantityType: type, quantitySamplePredicate: predicate, options: .cumulativeSum) { _, result, error in
                let value = result?.sumQuantity()?.doubleValue(for: unit)
                continuation.resume(returning: value)
            }
            store.execute(query)
        }
    }

    private func queryDayAverage(_ identifier: HKQuantityTypeIdentifier, date: Date, unit: HKUnit) async -> Double? {
        let type = HKQuantityType(identifier)
        let start = Calendar.current.startOfDay(for: date)
        guard let end = Calendar.current.date(byAdding: .day, value: 1, to: start) else {
            return nil
        }
        let predicate = HKQuery.predicateForSamples(withStart: start, end: end)

        return await withCheckedContinuation { continuation in
            let query = HKStatisticsQuery(quantityType: type, quantitySamplePredicate: predicate, options: .discreteAverage) { _, result, error in
                let value = result?.averageQuantity()?.doubleValue(for: unit)
                continuation.resume(returning: value)
            }
            store.execute(query)
        }
    }
}
