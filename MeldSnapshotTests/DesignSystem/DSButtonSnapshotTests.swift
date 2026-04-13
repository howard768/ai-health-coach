import Testing
import SnapshotTesting
import SwiftUI
@testable import Meld

@Suite("DSButton Snapshots")
struct DSButtonSnapshotTests {

    // MARK: - Style Variants

    @Test @MainActor func primaryStyle() {
        let view = DSButton(title: "Continue", style: .primary) {}
            .frame(width: 360)
            .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func secondaryStyle() {
        let view = DSButton(title: "Skip for now", style: .secondary) {}
            .frame(width: 360)
            .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func ghostStyle() {
        let view = DSButton(title: "Cancel", style: .ghost) {}
            .frame(width: 360)
            .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func chipStyle() {
        let view = DSButton(title: "How's my sleep?", style: .chip) {}
            .frame(width: 360)
            .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    // MARK: - Sizes

    @Test @MainActor func smallSize() {
        let view = DSButton(title: "Small", style: .primary, size: .sm) {}
            .frame(width: 360)
            .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func largeSize() {
        let view = DSButton(title: "Get started", style: .primary, size: .lg) {}
            .frame(width: 360)
            .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    // MARK: - States

    @Test @MainActor func disabledState() {
        let view = DSButton(title: "Continue", style: .primary, isDisabled: true) {}
            .frame(width: 360)
            .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func loadingState() {
        let view = DSButton(title: "Saving...", style: .primary, isLoading: true) {}
            .frame(width: 360)
            .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func secondaryDisabled() {
        let view = DSButton(title: "Not available", style: .secondary, isDisabled: true) {}
            .frame(width: 360)
            .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }
}
