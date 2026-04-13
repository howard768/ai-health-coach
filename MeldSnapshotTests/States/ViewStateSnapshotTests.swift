import Testing
import SnapshotTesting
import SwiftUI
@testable import Meld

// MARK: - Loading State Snapshots

@Suite("Loading State Snapshots")
struct LoadingStateSnapshotTests {

    @Test @MainActor func dashboardSkeleton() {
        let view = DashboardSkeleton()
            .frame(width: 360, height: 700)
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func chatMessageSkeletonCoach() {
        let view = ChatMessageSkeleton(isCoach: true)
            .frame(width: 360)
            .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func chatMessageSkeletonUser() {
        let view = ChatMessageSkeleton(isCoach: false)
            .frame(width: 360)
            .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func typingIndicator() {
        let view = TypingIndicator()
            .frame(width: 360)
            .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func syncProgressOverlay() {
        let view = SyncProgressOverlay(
            progress: 0.65,
            message: "Reading your sleep patterns..."
        )
        .frame(width: 360)
        .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }
}

// MARK: - Empty State Snapshots

@Suite("Empty State Snapshots")
struct EmptyStateSnapshotTests {

    @Test @MainActor func dashboardEmpty() {
        let view = DashboardEmptyState()
            .frame(width: 360, height: 500)
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func coachChatEmpty() {
        let view = CoachChatEmptyState()
            .frame(width: 360, height: 500)
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func trendsEmpty() {
        let view = TrendsEmptyState(daysCollected: 3, daysNeeded: 7)
            .frame(width: 360, height: 500)
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func mealsEmpty() {
        let view = MealsEmptyState()
            .frame(width: 360, height: 500)
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func metricEmpty() {
        let view = MetricEmptyState(metricName: "HRV")
            .frame(width: 360, height: 500)
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }
}

// MARK: - Error State Snapshots

@Suite("Error State Snapshots")
struct ErrorStateSnapshotTests {

    @Test @MainActor func networkError() {
        let view = FullScreenError.networkError(onRetry: {})
            .frame(width: 360, height: 500)
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func serverError() {
        let view = FullScreenError.serverError(onRetry: {})
            .frame(width: 360, height: 500)
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func permissionDenied() {
        let view = FullScreenError.permissionDenied()
            .frame(width: 360, height: 500)
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func customFullScreenError() {
        let view = FullScreenError(
            title: "Something went wrong",
            message: "We could not load your data. Please try again.",
            retryTitle: "Retry",
            onRetry: {}
        )
        .frame(width: 360, height: 500)
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    // MARK: - Inline Banners

    @Test @MainActor func inlineErrorBanner() {
        let view = InlineErrorBanner(
            message: "Could not sync your latest data.",
            style: .error
        )
        .frame(width: 360)
        .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func inlineWarningBanner() {
        let view = InlineErrorBanner.syncFailed(onRetry: {})
            .frame(width: 360)
            .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func inlineInfoBanner() {
        let view = InlineErrorBanner.staleData()
            .frame(width: 360)
            .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }

    @Test @MainActor func inlineBannerWithDismiss() {
        let view = InlineErrorBanner(
            message: "New feature available!",
            style: .info,
            onDismiss: {}
        )
        .frame(width: 360)
        .padding()
        assertSnapshot(of: view, as: .image(layout: .sizeThatFits))
    }
}
