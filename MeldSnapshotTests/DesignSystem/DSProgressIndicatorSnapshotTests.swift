import Testing
import SnapshotTesting
import SwiftUI
@testable import Meld

@Suite("DSProgressIndicator Snapshots")
struct DSProgressIndicatorSnapshotTests {

    // MARK: - Step Dots

    @Test @MainActor func stepDotsFirstStep() {
        let view = DSStepDots(totalSteps: 5, currentStep: 0)
            .frame(width: 360)
            .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func stepDotsMiddleStep() {
        let view = DSStepDots(totalSteps: 5, currentStep: 2)
            .frame(width: 360)
            .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func stepDotsLastStep() {
        let view = DSStepDots(totalSteps: 5, currentStep: 4)
            .frame(width: 360)
            .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    // MARK: - Progress Bar

    @Test @MainActor func progressBarEmpty() {
        let view = DSProgressBar(progress: 0.0)
            .frame(width: 360)
            .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func progressBarPartial() {
        let view = DSProgressBar(progress: 0.35)
            .frame(width: 360)
            .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func progressBarMostly() {
        let view = DSProgressBar(progress: 0.7)
            .frame(width: 360)
            .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func progressBarComplete() {
        let view = DSProgressBar(progress: 1.0, color: DSColor.Status.success)
            .frame(width: 360)
            .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    // MARK: - Circular Progress

    @Test @MainActor func circularProgressDeterminate() {
        let view = DSCircularProgress(progress: 0.45)
            .frame(width: 360)
            .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func circularProgressComplete() {
        let view = DSCircularProgress(progress: 1.0, color: DSColor.Status.success)
            .frame(width: 360)
            .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func circularProgressIndeterminate() {
        let view = DSCircularProgress(progress: nil)
            .frame(width: 360)
            .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }
}
