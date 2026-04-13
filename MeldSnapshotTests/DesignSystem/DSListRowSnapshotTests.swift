import Testing
import SnapshotTesting
import SwiftUI
@testable import Meld

@Suite("DSListRow Snapshots")
struct DSListRowSnapshotTests {

    // MARK: - List Row Variants

    @Test @MainActor func rowWithLeadingIconAndChevron() {
        let view = DSListRow(title: "Oura Ring", subtitle: "Last synced 2 min ago", leading: {
            Image(systemName: "circle.hexagongrid.fill")
                .foregroundStyle(DSColor.Green.green500)
        }, trailing: {
            DSListChevron()
        })
        .frame(width: 360)
        .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func rowWithStatusDot() {
        let view = DSListRow(title: "Eight Sleep", subtitle: "Not connected", leading: {
            Image(systemName: "bed.double.fill")
                .foregroundStyle(DSColor.Text.disabled)
        }, trailing: {
            DSListStatusDot(isConnected: false)
        })
        .frame(width: 360)
        .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func rowTitleOnly() {
        let view = DSListRow(title: "Privacy Policy", trailing: {
            DSListChevron()
        })
        .frame(width: 360)
        .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    // MARK: - Supporting Components

    @Test @MainActor func statusDotConnected() {
        let view = DSListStatusDot(isConnected: true)
            .frame(width: 360)
            .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func statusDotDisconnected() {
        let view = DSListStatusDot(isConnected: false)
            .frame(width: 360)
            .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func dividerDefault() {
        let view = DSDivider()
            .frame(width: 360)
            .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func sectionHeader() {
        let view = DSSectionHeader(title: "Connected Sources")
            .frame(width: 360)
            .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func toggleOn() {
        let view = DSToggle(title: "Push Notifications", isOn: .constant(true), subtitle: "Get proactive coaching alerts")
            .frame(width: 360)
            .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func toggleOff() {
        let view = DSToggle(title: "Dark Mode", isOn: .constant(false))
            .frame(width: 360)
            .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    // MARK: - Composed List

    @Test @MainActor func composedSettingsList() {
        let view = VStack(spacing: 0) {
            DSSectionHeader(title: "Connected Sources")
            DSListRow(title: "Oura Ring", subtitle: "Last synced 2 min ago", leading: {
                Image(systemName: "circle.hexagongrid.fill")
                    .foregroundStyle(DSColor.Green.green500)
            }, trailing: {
                DSListChevron()
            })
            DSDivider()
            DSToggle(title: "Push Notifications", isOn: .constant(true), subtitle: "Get proactive coaching alerts")
        }
        .background(DSColor.Surface.primary)
        .frame(width: 360)
        .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }
}
