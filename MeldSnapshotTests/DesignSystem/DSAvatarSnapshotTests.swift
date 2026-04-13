import Testing
import SnapshotTesting
import SwiftUI
@testable import Meld

@Suite("DSAvatar Snapshots")
struct DSAvatarSnapshotTests {

    // MARK: - Sizes with Initials

    @Test @MainActor func smallWithInitials() {
        let view = DSAvatar(size: .sm, initials: "BH")
            .frame(width: 360)
            .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func mediumWithInitials() {
        let view = DSAvatar(size: .md, initials: "BH")
            .frame(width: 360)
            .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func largeWithInitials() {
        let view = DSAvatar(size: .lg, initials: "BH")
            .frame(width: 360)
            .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func extraLargeWithInitials() {
        let view = DSAvatar(size: .xl, initials: "BH")
            .frame(width: 360)
            .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    // MARK: - Fallback (no image, no initials)

    @Test @MainActor func fallbackIcon() {
        let view = DSAvatar(size: .lg)
            .frame(width: 360)
            .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    // MARK: - All Sizes Row

    @Test @MainActor func allSizesRow() {
        let view = HStack(spacing: 12) {
            DSAvatar(size: .sm, initials: "BH")
            DSAvatar(size: .md, initials: "BH")
            DSAvatar(size: .lg, initials: "BH")
            DSAvatar(size: .xl, initials: "BH")
        }
        .frame(width: 360)
        .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    // MARK: - Mascot Avatar

    @Test @MainActor func mascotAvatarMedium() {
        let view = DSMascotAvatar(size: .md)
            .frame(width: 360)
            .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func mascotAvatarLarge() {
        let view = DSMascotAvatar(size: .lg)
            .frame(width: 360)
            .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }
}
