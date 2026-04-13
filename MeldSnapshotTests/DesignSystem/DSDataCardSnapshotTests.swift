import Testing
import SnapshotTesting
import SwiftUI
@testable import Meld

@Suite("DSDataCard Snapshots")
struct DSDataCardSnapshotTests {

    // MARK: - Summary Data Card

    @Test @MainActor func summaryCardDefault() {
        let view = DSSummaryDataCard(
            title: "Sleep Summary",
            value: "91",
            unit: "%",
            subtitle: "7h 12m total"
        )
        .frame(width: 360)
        .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func summaryCardTappable() {
        let view = DSSummaryDataCard(
            title: "HRV Status",
            value: "68",
            unit: "ms",
            subtitle: "14% above baseline",
            onTap: {}
        )
        .frame(width: 360)
        .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func summaryCardCustomTrendColor() {
        let view = DSSummaryDataCard(
            title: "Resting HR",
            value: "72",
            unit: "bpm",
            subtitle: "Higher than usual",
            trendColor: DSColor.Status.warning
        )
        .frame(width: 360)
        .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    // MARK: - Workout Card

    @Test @MainActor func workoutCard() {
        let view = DSWorkoutCard(exercises: [
            WorkoutExercise(name: "Squats", prescription: "4x5 @ 225lb"),
            WorkoutExercise(name: "RDL", prescription: "3x8 @ 185lb"),
            WorkoutExercise(name: "Leg Press", prescription: "3x10"),
            WorkoutExercise(name: "Walking Lunges", prescription: "2x12"),
        ])
        .frame(width: 360)
        .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    // MARK: - Citation Card

    @Test @MainActor func citationCard() {
        let view = DSCitationCard(
            text: "Dietary protein supports sleep quality through tryptophan availability and muscle recovery demands.",
            source: "Halson, S.L. (2014). Sleep in Elite Athletes. Sports Medicine."
        )
        .frame(width: 360)
        .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }
}
