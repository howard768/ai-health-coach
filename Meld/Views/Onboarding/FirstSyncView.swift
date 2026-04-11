import SwiftUI

// MARK: - Screen 5: First Sync + Reward
// Shows what the coach learned, celebrates completion.
// Mascot transitions from thinking → celebrating.
// Summary card reveals actual data metrics.
// No badges for MVP — reward is information + acknowledgement.
// 4th grade reading level. 20pt margins, 8pt grid.

struct FirstSyncView: View {
    @Bindable var viewModel: OnboardingViewModel
    var onComplete: () -> Void = {}
    private let M = OnboardingLayout.margin

    var body: some View {
        VStack(spacing: 0) {
            ScrollView(showsIndicators: false) {
                VStack(spacing: 0) {

                    Spacer().frame(height: DSSpacing.huge)

                    // Mascot — large, animated
                    AnimatedMascot(
                        state: viewModel.isComplete ? .celebrating : .thinking,
                        size: 80
                    )
                    .frame(maxWidth: .infinity)

                    Spacer().frame(height: DSSpacing.xxxl)

                    // Title
                    Text(viewModel.isComplete ? "You're all set!" : "Setting things up...")
                        .font(DSTypography.h1)
                        .foregroundStyle(DSColor.Text.primary)
                        .frame(maxWidth: .infinity)
                        .multilineTextAlignment(.center)

                    Spacer().frame(height: DSSpacing.xxl)

                    if viewModel.isComplete {
                        // Summary card
                        summaryCard

                        Spacer().frame(height: DSSpacing.xxl)

                        // Coach message
                        coachMessage

                        Spacer().frame(height: DSSpacing.xxl)

                        // Progress bar (complete)
                        DSProgressBar(progress: 1.0, color: DSColor.Status.success)
                            .padding(.horizontal, DSSpacing.huge)

                        Spacer().frame(height: DSSpacing.lg)

                        Text("Your journey starts now.")
                            .font(DSTypography.bodySM)
                            .foregroundStyle(DSColor.Text.tertiary)
                            .frame(maxWidth: .infinity)
                            .multilineTextAlignment(.center)

                    } else {
                        // Sync in progress
                        VStack(spacing: DSSpacing.lg) {
                            DSProgressBar(progress: viewModel.syncProgress)
                                .padding(.horizontal, DSSpacing.huge)

                            Text(syncMessage)
                                .font(DSTypography.bodySM)
                                .foregroundStyle(DSColor.Text.secondary)
                                .frame(maxWidth: .infinity)
                                .multilineTextAlignment(.center)
                                .animation(.none, value: syncMessage)
                        }
                    }
                }
                .padding(.horizontal, M)
            }

            // CTA — only when sync complete
            if viewModel.isComplete {
                DSButton(title: "See your dashboard", style: .primary, size: .lg) {
                    onComplete()
                }
                .padding(.horizontal, M)
                .padding(.bottom, DSSpacing.lg)
            }
        }
        .background(DSColor.Background.primary)
        .task {
            await viewModel.startSync()
        }
    }

    // MARK: - Sync Message

    private var syncMessage: String {
        let step = Int(viewModel.syncProgress * 4)
        switch step {
        case 0: return "Connecting to your data..."
        case 1: return "Reading your sleep patterns..."
        case 2: return "Computing your baseline..."
        default: return "Getting your first insight ready..."
        }
    }

    // MARK: - Summary Card

    private var summaryCard: some View {
        VStack(alignment: .leading, spacing: DSSpacing.lg) {
            Text("HERE'S WHAT YOUR COACH KNOWS")
                .dsLabel()
                .foregroundStyle(DSColor.Text.tertiary)

            VStack(spacing: DSSpacing.md) {
                summaryRow(
                    label: "Sleep Score",
                    value: viewModel.fetchedSleepScore ?? "—",
                    source: viewModel.fetchedSleepScore != nil ? "Oura" : ""
                )
                summaryRow(
                    label: "HRV",
                    value: viewModel.fetchedHRV ?? "—",
                    source: viewModel.fetchedHRV != nil ? "Oura" : ""
                )
                summaryRow(label: "Goal", value: goalSummary, source: "You")
                if let bmi = viewModel.assessment.bmi {
                    summaryRow(label: "BMI", value: String(format: "%.1f", bmi), source: "Profile")
                }
            }
        }
        .metricCard()
    }

    private func summaryRow(label: String, value: String, source: String) -> some View {
        HStack {
            Text(label)
                .font(DSTypography.bodySM)
                .foregroundStyle(DSColor.Text.primary)
                .frame(width: 100, alignment: .leading)

            Text(value)
                .font(DSTypography.bodySM)
                .foregroundStyle(DSColor.Text.primary)

            Spacer()

            Text(source)
                .font(DSTypography.caption)
                .foregroundStyle(DSColor.Text.tertiary)
        }
    }

    private var goalSummary: String {
        viewModel.assessment.goals.map(\.rawValue).joined(separator: " + ")
    }

    // MARK: - Coach Message

    private var coachMessage: some View {
        HStack(spacing: DSSpacing.md) {
            AnimatedMascot(state: .idle, size: 28)

            VStack(alignment: .leading, spacing: DSSpacing.xxs) {
                Text("Your Coach")
                    .font(DSTypography.caption)
                    .foregroundStyle(DSColor.Purple.purple600)

                Text("I've looked at your data. Let's build a plan to hit your goals.")
                    .font(DSTypography.bodySM)
                    .foregroundStyle(DSColor.Text.primary)
                    .lineSpacing(3)
            }
        }
        .insightCard()
    }
}

#Preview("Syncing") {
    FirstSyncView(viewModel: OnboardingViewModel())
}

#Preview("Complete") {
    let vm = OnboardingViewModel()
    vm.isComplete = true
    vm.assessment.goals = [.loseWeight, .buildMuscle]
    vm.assessment.age = 32
    vm.assessment.heightInches = 70
    vm.assessment.weightLbs = 185
    return FirstSyncView(viewModel: vm)
}
