import Testing
import SnapshotTesting
import SwiftUI
@testable import Meld

@Suite("DSTextField Snapshots")
struct DSTextFieldSnapshotTests {

    @Test @MainActor func standardEmpty() {
        let view = DSTextField(
            placeholder: "Ask your coach anything...",
            text: .constant(""),
            style: .standard
        )
        .frame(width: 360)
        .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func standardWithText() {
        let view = DSTextField(
            placeholder: "Ask your coach anything...",
            text: .constant("How's my sleep?"),
            style: .standard,
            onSubmit: {}
        )
        .frame(width: 360)
        .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func glassEmpty() {
        let view = DSTextField(
            placeholder: "Ask your coach anything...",
            text: .constant(""),
            style: .glass
        )
        .frame(width: 360)
        .padding()
        .background(DSColor.Purple.purple500)
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func glassWithText() {
        let view = DSTextField(
            placeholder: "Ask your coach anything...",
            text: .constant("Plan my workout"),
            style: .glass,
            onSubmit: {}
        )
        .frame(width: 360)
        .padding()
        .background(DSColor.Purple.purple500)
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }
}
