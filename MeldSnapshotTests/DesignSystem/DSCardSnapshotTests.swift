import Testing
import SnapshotTesting
import SwiftUI
@testable import Meld

@Suite("DSCard Snapshots")
struct DSCardSnapshotTests {

    @Test @MainActor func metricStyle() {
        let view = DSCard(style: .metric) {
            VStack(alignment: .leading, spacing: 4) {
                Text("Sleep Score")
                    .font(DSTypography.caption)
                    .foregroundStyle(DSColor.Text.tertiary)
                Text("91%")
                    .font(DSTypography.metricLG)
                    .foregroundStyle(DSColor.Text.primary)
            }
        }
        .frame(width: 360)
        .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func insightStyle() {
        let view = DSCard(style: .insight) {
            VStack(alignment: .leading, spacing: 4) {
                Text("Coach Insight")
                    .font(DSTypography.bodySM)
                    .foregroundStyle(DSColor.Text.tertiary)
                Text("Your HRV has been trending upward for 5 days. Great recovery.")
                    .font(DSTypography.body)
                    .foregroundStyle(DSColor.Text.primary)
            }
        }
        .frame(width: 360)
        .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func glassStyle() {
        let view = DSCard(style: .glass) {
            VStack(alignment: .leading, spacing: 4) {
                Text("Overlay Content")
                    .font(DSTypography.body)
                    .foregroundStyle(DSColor.Text.primary)
            }
        }
        .frame(width: 360)
        .padding()
        .background(DSColor.Purple.purple500)
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func dataStyle() {
        let view = DSCard(style: .data) {
            VStack(alignment: .leading, spacing: 4) {
                Text("HRV Trend")
                    .font(DSTypography.caption)
                    .foregroundStyle(DSColor.Text.tertiary)
                Text("7-day average: 62ms")
                    .font(DSTypography.body)
                    .foregroundStyle(DSColor.Text.primary)
            }
        }
        .frame(width: 360)
        .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }
}
