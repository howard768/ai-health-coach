import Testing
import SnapshotTesting
import SwiftUI
@testable import Meld

@Suite("Sparkline Snapshots")
struct SparklineSnapshotTests {

    // MARK: - Bar Sparkline

    @Test @MainActor func barSparklineDefault() {
        let view = BarSparkline(values: [0.6, 0.8, 0.7, 0.9, 0.85, 0.88, 0.95])
            .frame(width: 150, height: 40)
            .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func barSparklineNoHighlight() {
        let view = BarSparkline(
            values: [0.5, 0.7, 0.6, 0.9, 0.8, 0.85, 0.95],
            highlightLast: false
        )
        .frame(width: 150, height: 40)
        .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func barSparklineCustomColors() {
        let view = BarSparkline(
            values: [0.4, 0.6, 0.5, 0.7, 0.65, 0.72, 0.80],
            barColor: DSColor.Green.green200,
            highlightColor: DSColor.Green.green500
        )
        .frame(width: 150, height: 40)
        .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    // MARK: - Area Sparkline

    @Test @MainActor func areaSparklineWithBaseline() {
        let view = AreaSparkline(
            values: [52, 58, 55, 62, 68, 64, 68],
            baseline: 58
        )
        .frame(width: 320, height: 60)
        .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func areaSparklineNoBaseline() {
        let view = AreaSparkline(
            values: [52, 58, 55, 62, 68, 64, 68]
        )
        .frame(width: 320, height: 60)
        .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func areaSparklineRHRColors() {
        let view = AreaSparkline(
            values: [62, 60, 61, 58, 59, 57, 58],
            baseline: 60,
            fillColor: DSColor.Green.green100,
            lineColor: DSColor.Green.green500,
            highlightColor: DSColor.Green.green600
        )
        .frame(width: 320, height: 60)
        .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }
}
