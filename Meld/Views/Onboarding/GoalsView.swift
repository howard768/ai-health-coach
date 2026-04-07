import SwiftUI

// MARK: - Screen 2: Goals (Multi-select)
// User picks health goals. Cannot skip — critical path.
// Chips animate on selection. Mascot micro-celebrates.
// 4th grade reading level. 20pt margins, 8pt grid.

struct GoalsView: View {
    @Bindable var viewModel: OnboardingViewModel
    @State private var showTextField = false
    private let M = OnboardingLayout.margin

    var body: some View {
        VStack(spacing: 0) {
            ScrollView(showsIndicators: false) {
                VStack(alignment: .leading, spacing: 0) {

                    // Progress dots
                    DSStepDots(totalSteps: 4, currentStep: 0)
                        .frame(maxWidth: .infinity)
                        .padding(.top, DSSpacing.xxl)

                    Spacer().frame(height: DSSpacing.xxxl)

                    // Title
                    Text("What do you want\nto work on?")
                        .font(DSTypography.h1)
                        .foregroundStyle(DSColor.Text.primary)
                        .lineSpacing(4)

                    Spacer().frame(height: DSSpacing.sm)

                    Text("Pick all that fit you.")
                        .font(DSTypography.bodySM)
                        .foregroundStyle(DSColor.Text.secondary)

                    Spacer().frame(height: DSSpacing.xxl)

                    // Goal chips — wrapping grid
                    FlowLayout(spacing: DSSpacing.sm) {
                        ForEach(HealthGoal.allCases) { goal in
                            DSChip(
                                title: goal.rawValue,
                                isSelected: viewModel.assessment.goals.contains(goal)
                            ) {
                                viewModel.toggleGoal(goal)
                            }
                        }
                    }

                    Spacer().frame(height: DSSpacing.xxxl)

                    // Divider
                    Rectangle()
                        .fill(DSColor.Background.tertiary)
                        .frame(height: 1)

                    Spacer().frame(height: DSSpacing.xxl)

                    // Free text option
                    Text("Want to share more?")
                        .font(DSTypography.bodyEmphasis)
                        .foregroundStyle(DSColor.Text.primary)

                    Spacer().frame(height: DSSpacing.md)

                    DSTextField(
                        placeholder: "Tell us in your own words...",
                        text: $viewModel.assessment.customGoalText
                    )

                    Spacer().frame(height: DSSpacing.xxl)

                    // Reassurance
                    Text("You can change these any time.")
                        .font(DSTypography.caption)
                        .foregroundStyle(DSColor.Text.tertiary)
                }
                .padding(.horizontal, M)
            }

            // Mascot subtle presence
            HStack {
                Spacer()
                AnimatedMascot(
                    state: viewModel.canProceedFromGoals ? .celebrating : .idle,
                    size: 32
                )
                .padding(.trailing, M)
            }

            // CTA
            DSButton(
                title: "Next",
                style: .primary,
                size: .lg,
                isDisabled: !viewModel.canProceedFromGoals
            ) {
                Analytics.Onboarding.goalsSelected(goals: viewModel.assessment.goals.map(\.rawValue))
                Analytics.Onboarding.goalsContinued()
                viewModel.next()
            }
            .padding(.horizontal, M)
            .padding(.bottom, DSSpacing.lg)
        }
        .background(DSColor.Background.primary)
        .onAppear { Analytics.Onboarding.goalsViewed() }
    }
}

// MARK: - Flow Layout (wrapping chips)

struct FlowLayout: Layout {
    var spacing: CGFloat = 8

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let result = arrange(proposal: proposal, subviews: subviews)
        return result.size
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        let result = arrange(proposal: ProposedViewSize(width: bounds.width, height: nil), subviews: subviews)
        for (index, position) in result.positions.enumerated() {
            subviews[index].place(at: CGPoint(x: bounds.minX + position.x, y: bounds.minY + position.y), proposal: .unspecified)
        }
    }

    private func arrange(proposal: ProposedViewSize, subviews: Subviews) -> (size: CGSize, positions: [CGPoint]) {
        let maxWidth = proposal.width ?? .infinity
        var positions: [CGPoint] = []
        var x: CGFloat = 0
        var y: CGFloat = 0
        var rowHeight: CGFloat = 0

        for subview in subviews {
            let size = subview.sizeThatFits(.unspecified)
            if x + size.width > maxWidth && x > 0 {
                x = 0
                y += rowHeight + spacing
                rowHeight = 0
            }
            positions.append(CGPoint(x: x, y: y))
            rowHeight = max(rowHeight, size.height)
            x += size.width + spacing
        }

        return (CGSize(width: maxWidth, height: y + rowHeight), positions)
    }
}

#Preview {
    GoalsView(viewModel: OnboardingViewModel())
}
