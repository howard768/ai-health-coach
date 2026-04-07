import SwiftUI

// MARK: - Screen 3: Quick Profile (Adaptive)
// Fields shown depend on goals selected in Screen 2.
// Pre-fills from HealthKit where available (green checkmark).
// All required fields for selected goals — no skip.
// 4th grade reading level. 20pt margins, 8pt grid.

struct QuickProfileView: View {
    @Bindable var viewModel: OnboardingViewModel
    private let M = OnboardingLayout.margin

    var body: some View {
        VStack(spacing: 0) {
            ScrollView(showsIndicators: false) {
                VStack(alignment: .leading, spacing: 0) {

                    // Progress dots
                    DSStepDots(totalSteps: 4, currentStep: 1)
                        .frame(maxWidth: .infinity)
                        .padding(.top, DSSpacing.xxl)

                    Spacer().frame(height: DSSpacing.xxxl)

                    // Title
                    Text("A little about you")
                        .font(DSTypography.h1)
                        .foregroundStyle(DSColor.Text.primary)

                    Spacer().frame(height: DSSpacing.sm)

                    Text("This helps your coach know you better.")
                        .font(DSTypography.bodySM)
                        .foregroundStyle(DSColor.Text.secondary)

                    Spacer().frame(height: DSSpacing.xxl)

                    // Age — always required
                    fieldLabel("AGE")
                    ageField
                    if viewModel.prefilledAge != nil {
                        prefillBadge
                    }

                    // Height + Weight — required for weight loss / muscle
                    if viewModel.assessment.needsHeight {
                        Spacer().frame(height: DSSpacing.xxl)
                        HStack(spacing: DSSpacing.lg) {
                            VStack(alignment: .leading, spacing: DSSpacing.sm) {
                                fieldLabel("HEIGHT")
                                fieldBox(viewModel.prefilledHeightInches != nil
                                    ? viewModel.heightString(viewModel.prefilledHeightInches!)
                                    : "")
                            }
                            VStack(alignment: .leading, spacing: DSSpacing.sm) {
                                fieldLabel("WEIGHT")
                                fieldBox(viewModel.prefilledWeightLbs != nil
                                    ? "\(Int(viewModel.prefilledWeightLbs!)) lbs"
                                    : "")
                            }
                        }
                    }

                    // Target weight — required for weight loss
                    if viewModel.assessment.needsTargetWeight {
                        Spacer().frame(height: DSSpacing.xxl)
                        fieldLabel("GOAL WEIGHT")
                        fieldBox(viewModel.assessment.targetWeightLbs != nil
                            ? "\(Int(viewModel.assessment.targetWeightLbs!)) lbs"
                            : "170 lbs", dimmed: true)
                    }

                    // Training experience — required for muscle
                    if viewModel.assessment.needsExperience {
                        Spacer().frame(height: DSSpacing.xxl)
                        fieldLabel("HOW LONG HAVE YOU TRAINED?")
                        Spacer().frame(height: DSSpacing.sm)
                        FlowLayout(spacing: DSSpacing.sm) {
                            ForEach(TrainingExperience.allCases) { exp in
                                DSChip(
                                    title: exp.rawValue,
                                    isSelected: viewModel.assessment.trainingExperience == exp
                                ) {
                                    viewModel.assessment.trainingExperience = exp
                                    DSHaptic.selection()
                                }
                            }
                        }
                    }

                    // Training days — required for muscle
                    if viewModel.assessment.needsTrainingDays {
                        Spacer().frame(height: DSSpacing.xxl)
                        fieldLabel("DAYS PER WEEK YOU TRAIN")
                        Spacer().frame(height: DSSpacing.sm)
                        HStack(spacing: DSSpacing.sm) {
                            ForEach(2...6, id: \.self) { day in
                                Button(action: {
                                    viewModel.assessment.trainingDaysPerWeek = day
                                    DSHaptic.selection()
                                }) {
                                    Text("\(day)")
                                        .font(DSTypography.bodyEmphasis)
                                        .foregroundStyle(
                                            viewModel.assessment.trainingDaysPerWeek == day
                                                ? DSColor.Text.onGreen
                                                : DSColor.Text.primary
                                        )
                                        .frame(width: 56, height: 44)
                                        .background(
                                            viewModel.assessment.trainingDaysPerWeek == day
                                                ? DSColor.Green.green500
                                                : DSColor.Surface.primary
                                        )
                                        .dsCornerRadius(DSRadius.sm)
                                        .overlay(
                                            RoundedRectangle(cornerRadius: DSRadius.sm, style: .continuous)
                                                .stroke(
                                                    viewModel.assessment.trainingDaysPerWeek == day
                                                        ? Color.clear
                                                        : DSColor.Text.disabled,
                                                    lineWidth: 1
                                                )
                                        )
                                }
                            }
                        }
                    }

                    // Chronotype — required for sleep
                    if viewModel.assessment.needsChronotype {
                        Spacer().frame(height: DSSpacing.xxl)
                        fieldLabel("ARE YOU A...")
                        Spacer().frame(height: DSSpacing.sm)
                        FlowLayout(spacing: DSSpacing.sm) {
                            ForEach(Chronotype.allCases) { ct in
                                DSChip(
                                    title: ct.rawValue,
                                    isSelected: viewModel.assessment.chronotype == ct
                                ) {
                                    viewModel.assessment.chronotype = ct
                                    DSHaptic.selection()
                                }
                            }
                        }
                    }

                    Spacer().frame(height: DSSpacing.xxxl)

                    // Privacy reassurance
                    Text("We keep your data private and safe.")
                        .font(DSTypography.caption)
                        .foregroundStyle(DSColor.Text.tertiary)
                }
                .padding(.horizontal, M)
            }

            // CTA
            DSButton(
                title: "Next",
                style: .primary,
                size: .lg,
                isDisabled: !viewModel.canProceedFromProfile
            ) {
                viewModel.next()
            }
            .padding(.horizontal, M)
            .padding(.bottom, DSSpacing.lg)
        }
        .background(DSColor.Background.primary)
        .onAppear {
            viewModel.applyPrefill()
        }
    }

    // MARK: - Subviews

    private func fieldLabel(_ text: String) -> some View {
        Text(text)
            .dsLabel()
            .foregroundStyle(DSColor.Text.tertiary)
    }

    private func fieldBox(_ value: String, dimmed: Bool = false) -> some View {
        HStack {
            Text(value)
                .font(DSTypography.body)
                .foregroundStyle(dimmed ? DSColor.Text.tertiary : DSColor.Text.primary)
            Spacer()
        }
        .frame(height: 48)
        .padding(.horizontal, DSSpacing.lg)
        .background(DSColor.Surface.secondary)
        .dsCornerRadius(DSRadius.md)
    }

    private var ageField: some View {
        HStack {
            Text(viewModel.assessment.age != nil ? "\(viewModel.assessment.age!)" : "")
                .font(DSTypography.body)
                .foregroundStyle(DSColor.Text.primary)
            Spacer()
            if viewModel.prefilledAge != nil {
                Circle()
                    .fill(DSColor.Status.success)
                    .frame(width: 20, height: 20)
                    .overlay(
                        Image(systemName: "checkmark")
                            .font(.system(size: 11, weight: .bold))
                            .foregroundStyle(.white)
                    )
            }
        }
        .frame(height: 48)
        .padding(.horizontal, DSSpacing.lg)
        .background(DSColor.Surface.secondary)
        .dsCornerRadius(DSRadius.md)
        .padding(.top, DSSpacing.sm)
    }

    private var prefillBadge: some View {
        HStack {
            Spacer()
            Text("From Apple Health")
                .font(.system(size: 10))
                .foregroundStyle(DSColor.Accessible.greenText)
        }
        .padding(.top, DSSpacing.xs)
    }
}

#Preview {
    let vm = OnboardingViewModel()
    vm.assessment.goals = [.loseWeight, .buildMuscle]
    return QuickProfileView(viewModel: vm)
}
