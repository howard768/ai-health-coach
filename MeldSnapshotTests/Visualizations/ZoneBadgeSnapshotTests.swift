import Testing
import SnapshotTesting
import SwiftUI
@testable import Meld

@Suite("ZoneBadge Snapshots")
struct ZoneBadgeSnapshotTests {

    // MARK: - Recovery Zones

    @Test @MainActor func highRecovery() {
        let view = ZoneBadge(zone: .high, score: 82)
            .frame(width: 360)
            .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func moderateRecovery() {
        let view = ZoneBadge(zone: .moderate, score: 55)
            .frame(width: 360)
            .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func lowRecovery() {
        let view = ZoneBadge(zone: .low, score: 22)
            .frame(width: 360)
            .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func highRecoveryNoScore() {
        let view = ZoneBadge(zone: .high)
            .frame(width: 360)
            .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func customBadgeSize() {
        let view = ZoneBadge(zone: .moderate, score: 48, badgeSize: 80)
            .frame(width: 360)
            .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    // MARK: - RecoveryZone.from(score:)

    @Test @MainActor func zoneFromHighScore() {
        let zone = RecoveryZone.from(score: 0.82)
        let view = ZoneBadge(zone: zone, score: 82)
            .frame(width: 360)
            .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func zoneFromLowScore() {
        let zone = RecoveryZone.from(score: 0.20)
        let view = ZoneBadge(zone: zone, score: 20)
            .frame(width: 360)
            .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    // MARK: - Contributing Factors

    @Test @MainActor func contributingFactors() {
        let view = ContributingFactors(factors: [
            ContributingFactor(name: "Sleep Quality", value: 0.91, status: .good),
            ContributingFactor(name: "HRV vs Baseline", value: 0.78, status: .good),
            ContributingFactor(name: "Resting Heart Rate", value: 0.65, status: .watch),
            ContributingFactor(name: "Training Load", value: 0.45, status: .watch),
        ])
        .frame(width: 360)
        .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }
}
