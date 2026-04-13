import Testing
import SnapshotTesting
import SwiftUI
@testable import Meld

@Suite("ArcGauge Snapshots")
struct ArcGaugeSnapshotTests {

    @Test @MainActor func highValue() {
        let view = ArcGauge(
            value: 0.91,
            displayValue: "91",
            unit: "%",
            label: "SLEEP",
            subtitle: "7h 12m total"
        )
        .frame(width: 200)
        .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func midValue() {
        let view = ArcGauge(
            value: 0.78,
            displayValue: "78",
            unit: "%",
            label: "SLEEP",
            subtitle: "6h 20m total"
        )
        .frame(width: 200)
        .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func lowValue() {
        let view = ArcGauge(
            value: 0.62,
            displayValue: "62",
            unit: "%",
            label: "SLEEP",
            subtitle: "4h 50m total"
        )
        .frame(width: 200)
        .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func veryLowValue() {
        let view = ArcGauge(
            value: 0.30,
            displayValue: "30",
            unit: "%",
            label: "SLEEP",
            subtitle: "2h 15m total"
        )
        .frame(width: 200)
        .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func fullWidth() {
        let view = ArcGauge(
            value: 0.91,
            displayValue: "91",
            unit: "%",
            label: "SLEEP EFFICIENCY",
            subtitle: "7h 12m total"
        )
        .frame(width: 360)
        .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func customThresholds() {
        let view = ArcGauge(
            value: 0.55,
            displayValue: "55",
            unit: "%",
            label: "READINESS",
            subtitle: "Below average",
            lowThreshold: 0.40,
            midThreshold: 0.70,
            lowLabel: "Rest needed",
            midLabel: "Take it easy",
            highLabel: "Ready to go"
        )
        .frame(width: 200)
        .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }
}
