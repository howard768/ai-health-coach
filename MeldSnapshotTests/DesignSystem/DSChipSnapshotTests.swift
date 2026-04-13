import Testing
import SnapshotTesting
import SwiftUI
@testable import Meld

@Suite("DSChip Snapshots")
struct DSChipSnapshotTests {

    @Test @MainActor func defaultState() {
        let view = DSChip(title: "How's my sleep?", isSelected: false) {}
            .frame(width: 360)
            .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func selectedState() {
        let view = DSChip(title: "How's my sleep?", isSelected: true) {}
            .frame(width: 360)
            .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func chipRow() {
        let view = DSChipRow(chips: [
            "How's my sleep?",
            "Plan my workout",
            "What should I eat?"
        ])
        .frame(width: 360)
        .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }
}
