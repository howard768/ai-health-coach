import Testing
import SnapshotTesting
import SwiftUI
@testable import Meld

@Suite("MeldMascot Snapshots")
struct MeldMascotSnapshotTests {

    @Test @MainActor func idleState() {
        let view = MeldMascot(state: .idle, size: 96)
            .frame(width: 360)
            .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func thinkingState() {
        let view = MeldMascot(state: .thinking, size: 96)
            .frame(width: 360)
            .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func celebratingState() {
        let view = MeldMascot(state: .celebrating, size: 96)
            .frame(width: 360)
            .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func concernedState() {
        let view = MeldMascot(state: .concerned, size: 96)
            .frame(width: 360)
            .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func greetingState() {
        let view = MeldMascot(state: .greeting, size: 96)
            .frame(width: 360)
            .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func errorState() {
        let view = MeldMascot(state: .error, size: 96)
            .frame(width: 360)
            .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func smallSize() {
        let view = MeldMascot(state: .idle, size: 32)
            .frame(width: 360)
            .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func defaultSize() {
        let view = MeldMascot()
            .frame(width: 360)
            .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }
}
