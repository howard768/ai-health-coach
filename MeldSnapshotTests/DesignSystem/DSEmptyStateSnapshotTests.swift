import Testing
import SnapshotTesting
import SwiftUI
@testable import Meld

@Suite("DSEmptyState Snapshots")
struct DSEmptyStateSnapshotTests {

    @Test @MainActor func mascotWithAction() {
        let view = DSEmptyState(
            title: "No health data yet",
            message: "Connect your Oura Ring or Apple Health to start seeing your metrics here.",
            actionTitle: "Connect a wearable",
            action: {}
        )
        .frame(width: 360, height: 500)
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func mascotWithoutAction() {
        let view = DSEmptyState(
            title: "Building your trends",
            message: "We need at least 7 days of data to show meaningful trends."
        )
        .frame(width: 360, height: 500)
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func withSFSymbolIllustration() {
        let view = DSEmptyState(
            title: "Start a conversation",
            message: "Your coach is ready to help. Ask about your sleep, recovery, or training.",
            actionTitle: "Say hello",
            action: {},
            illustration: {
                DSEmptyStateIcon(
                    systemName: "bubble.left.and.text.bubble.right",
                    color: DSColor.Purple.purple300
                )
            }
        )
        .frame(width: 360, height: 500)
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func withCustomIconColor() {
        let view = DSEmptyState(
            title: "Building your trends",
            message: "We need at least 7 days of data to show meaningful trends. You're on day 3.",
            illustration: {
                DSEmptyStateIcon(
                    systemName: "chart.line.uptrend.xyaxis",
                    color: DSColor.Green.green300
                )
            }
        )
        .frame(width: 360, height: 500)
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }
}
