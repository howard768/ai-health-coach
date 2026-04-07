import SwiftUI

// MARK: - Empty State Views
// 5 predefined empty states for screens with no content.
// Each uses DSEmptyState with appropriate illustration + copy.
// All copy at 4th grade reading level.

// MARK: - Predefined Empty States

struct DashboardEmptyState: View {
    var onConnect: () -> Void = {}

    var body: some View {
        DSEmptyState(
            title: "No health data yet",
            message: "Connect your Oura Ring or Apple Health to see your daily insights.",
            actionTitle: "Connect a source",
            action: onConnect
        )
    }
}

struct CoachChatEmptyState: View {
    var quickActions: [String] = ["How's my sleep?", "Plan my workout", "What should I eat?"]
    var onQuickAction: (String) -> Void = { _ in }

    var body: some View {
        VStack(spacing: DSSpacing.xxl) {
            Spacer()

            AnimatedMascot(state: .greeting, size: 64)

            VStack(spacing: DSSpacing.sm) {
                Text("Your coach is ready")
                    .font(DSTypography.h2)
                    .foregroundStyle(DSColor.Text.primary)

                Text("Ask anything about your health, or pick a topic below.")
                    .font(DSTypography.body)
                    .foregroundStyle(DSColor.Text.secondary)
                    .multilineTextAlignment(.center)
                    .lineSpacing(4)
            }
            .padding(.horizontal, DSSpacing.xxxl)

            DSChipRow(chips: quickActions, onTap: onQuickAction)

            Spacer()
        }
    }
}

struct TrendsEmptyState: View {
    var daysCollected: Int = 3
    var daysNeeded: Int = 7

    var body: some View {
        VStack(spacing: DSSpacing.xxl) {
            Spacer()

            // Progress ring showing how close they are
            DSCircularProgress(
                progress: Double(daysCollected) / Double(daysNeeded),
                size: 80,
                lineWidth: 6,
                color: DSColor.Purple.purple500
            )
            .overlay(
                Text("\(daysCollected)/\(daysNeeded)")
                    .font(DSTypography.h3)
                    .foregroundStyle(DSColor.Text.primary)
            )

            VStack(spacing: DSSpacing.sm) {
                Text("Building your trends")
                    .font(DSTypography.h2)
                    .foregroundStyle(DSColor.Text.primary)

                Text("We need \(daysNeeded) days of data to show your patterns. You're on day \(daysCollected).")
                    .font(DSTypography.body)
                    .foregroundStyle(DSColor.Text.secondary)
                    .multilineTextAlignment(.center)
                    .lineSpacing(4)
            }
            .padding(.horizontal, DSSpacing.xxxl)

            // Mini progress bar
            VStack(spacing: DSSpacing.xs) {
                DSProgressBar(progress: Double(daysCollected) / Double(daysNeeded))
                    .padding(.horizontal, DSSpacing.huge)

                Text("\(daysNeeded - daysCollected) more days to go")
                    .font(DSTypography.caption)
                    .foregroundStyle(DSColor.Text.tertiary)
            }

            Spacer()
        }
    }
}

struct MealsEmptyState: View {
    var onLogMeal: () -> Void = {}

    var body: some View {
        DSEmptyState(
            title: "No meals logged yet",
            message: "Take a photo of your food to log it. Your coach uses this to connect the dots.",
            actionTitle: "Log a meal",
            action: onLogMeal,
            illustration: {
                DSEmptyStateIcon(
                    systemName: "camera.fill",
                    color: DSColor.Purple.purple300
                )
            }
        )
    }
}

struct MetricEmptyState: View {
    let metricName: String

    var body: some View {
        DSEmptyState(
            title: "No \(metricName.lowercased()) data",
            message: "Connect a wearable that tracks \(metricName.lowercased()) to see this metric.",
            illustration: {
                DSEmptyStateIcon(
                    systemName: "waveform.path.ecg",
                    color: DSColor.Text.disabled
                )
            }
        )
    }
}

// MARK: - Previews

#Preview("Dashboard") { DashboardEmptyState() }
#Preview("Coach Chat") { CoachChatEmptyState() }
#Preview("Trends") { TrendsEmptyState() }
#Preview("Meals") { MealsEmptyState() }
#Preview("Metric") { MetricEmptyState(metricName: "HRV") }
