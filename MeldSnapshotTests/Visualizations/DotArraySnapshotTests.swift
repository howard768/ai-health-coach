import Testing
import SnapshotTesting
import SwiftUI
@testable import Meld

@Suite("DotArray Snapshots")
struct DotArraySnapshotTests {

    @Test @MainActor func goalReached() {
        let view = DotArray(
            trainedDays: [0, 1, 2, 3, 4],
            todayIndex: 5,
            target: 5
        )
        .frame(width: 360)
        .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func midWeekProgress() {
        let view = DotArray(
            trainedDays: [0, 2],
            todayIndex: 3,
            target: 4
        )
        .frame(width: 360)
        .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func startOfWeek() {
        let view = DotArray(
            trainedDays: [],
            todayIndex: 0,
            target: 4
        )
        .frame(width: 360)
        .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func endOfWeekAllTrained() {
        let view = DotArray(
            trainedDays: [0, 1, 2, 3, 4, 5, 6],
            todayIndex: 6,
            target: 5
        )
        .frame(width: 360)
        .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    // MARK: - Calendar Heatmap

    @Test @MainActor func calendarHeatmapWithStreak() {
        let view = TrainingCalendarHeatmap(
            weeks: [
                [true, true, false, true, true, false, false],
                [true, true, true, false, true, true, false],
                [true, true, false, true, true, false, false],
                [true, true, true, true, true, nil, nil],
            ],
            currentStreak: 5
        )
        .frame(width: 360)
        .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func calendarHeatmapNoStreak() {
        let view = TrainingCalendarHeatmap(
            weeks: [
                [true, false, false, true, false, false, false],
                [false, true, false, false, true, false, false],
                [true, false, false, false, false, false, false],
                [false, false, nil, nil, nil, nil, nil],
            ],
            currentStreak: 0
        )
        .frame(width: 360)
        .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }
}
