import Testing
import SnapshotTesting
import SwiftUI
@testable import Meld

@Suite("RangeBand Snapshots")
struct RangeBandSnapshotTests {

    @Test @MainActor func hrvAboveAverage() {
        let view = RangeBand(
            currentValue: 68,
            personalMin: 42,
            personalMax: 82,
            personalAverage: 58,
            displayValue: "68",
            unit: "ms",
            label: "HRV",
            higherIsBetter: true
        )
        .frame(width: 200)
        .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func hrvBelowAverage() {
        let view = RangeBand(
            currentValue: 48,
            personalMin: 42,
            personalMax: 82,
            personalAverage: 58,
            displayValue: "48",
            unit: "ms",
            label: "HRV",
            higherIsBetter: true
        )
        .frame(width: 200)
        .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func hrvInRange() {
        let view = RangeBand(
            currentValue: 59,
            personalMin: 42,
            personalMax: 82,
            personalAverage: 58,
            displayValue: "59",
            unit: "ms",
            label: "HRV",
            higherIsBetter: true
        )
        .frame(width: 200)
        .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func restingHeartRateGood() {
        let view = RangeBand(
            currentValue: 58,
            personalMin: 52,
            personalMax: 72,
            personalAverage: 62,
            displayValue: "58",
            unit: "bpm",
            label: "RESTING HR",
            higherIsBetter: false
        )
        .frame(width: 200)
        .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func restingHeartRateHigh() {
        let view = RangeBand(
            currentValue: 70,
            personalMin: 52,
            personalMax: 72,
            personalAverage: 62,
            displayValue: "70",
            unit: "bpm",
            label: "RESTING HR",
            higherIsBetter: false
        )
        .frame(width: 200)
        .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func fullWidth() {
        let view = RangeBand(
            currentValue: 68,
            personalMin: 42,
            personalMax: 82,
            personalAverage: 58,
            displayValue: "68",
            unit: "ms",
            label: "HRV",
            higherIsBetter: true
        )
        .frame(width: 360)
        .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }
}
