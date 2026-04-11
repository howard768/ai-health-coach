import SwiftUI

// MARK: - Screen 3: Quick Profile (Adaptive)
// Fields shown depend on goals selected in Screen 2.
// Pre-fills from HealthKit where available (green checkmark).
// All required fields for selected goals — no skip.
// 4th grade reading level. 20pt margins, 8pt grid.

struct QuickProfileView: View {
    @Bindable var viewModel: OnboardingViewModel

    // String intermediaries for numeric inputs — more reliable than
    // Binding<Int?> with ParseableFormatStyle on optional types.
    @State private var ageText: String = ""
    @State private var heightFtText: String = "5"
    @State private var heightInText: String = "8"
    @State private var weightText: String = ""
    @State private var targetWeightText: String = ""

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
                    ageInputField
                    if viewModel.prefilledAge != nil {
                        prefillBadge
                    }

                    // Height + Weight — required for weight loss / muscle
                    if viewModel.assessment.needsHeight {
                        Spacer().frame(height: DSSpacing.xxl)
                        HStack(spacing: DSSpacing.lg) {
                            VStack(alignment: .leading, spacing: DSSpacing.sm) {
                                fieldLabel("HEIGHT")
                                heightInputField
                            }
                            VStack(alignment: .leading, spacing: DSSpacing.sm) {
                                fieldLabel("WEIGHT")
                                weightInputField
                            }
                        }
                        if viewModel.prefilledHeightInches != nil || viewModel.prefilledWeightLbs != nil {
                            prefillBadge
                        }
                    }

                    // Target weight — required for weight loss
                    if viewModel.assessment.needsTargetWeight {
                        Spacer().frame(height: DSSpacing.xxl)
                        fieldLabel("GOAL WEIGHT")
                        targetWeightInputField
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
                Analytics.Onboarding.profileCompleted()
                viewModel.next()
            }
            .padding(.horizontal, M)
            .padding(.bottom, DSSpacing.lg)
        }
        .background(DSColor.Background.primary)
        .onAppear {
            viewModel.applyPrefill()
            initTextFields()
            Analytics.Onboarding.profileViewed()
            let prefilled = [viewModel.prefilledAge, viewModel.prefilledHeightInches].compactMap { $0 }.count
                + (viewModel.prefilledWeightLbs != nil ? 1 : 0)
            Analytics.Onboarding.profilePrefilledFields(count: prefilled)
        }
    }

    // MARK: - Initialize text fields from assessment (after HealthKit prefill)

    private func initTextFields() {
        if let age = viewModel.assessment.age { ageText = "\(age)" }
        if let h = viewModel.assessment.heightInches {
            heightFtText = "\(h / 12)"
            heightInText = "\(h % 12)"
        }
        if let w = viewModel.assessment.weightLbs { weightText = "\(Int(w))" }
        if let tw = viewModel.assessment.targetWeightLbs { targetWeightText = "\(Int(tw))" }
    }

    // MARK: - Editable Input Fields

    private var ageInputField: some View {
        HStack {
            TextField("—", text: $ageText)
                .keyboardType(.numberPad)
                .font(DSTypography.body)
                .foregroundStyle(DSColor.Text.primary)
                .onChange(of: ageText) { _, newValue in
                    viewModel.assessment.age = Int(newValue)
                }
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

    private var heightInputField: some View {
        HStack(spacing: DSSpacing.xs) {
            TextField("5", text: $heightFtText)
                .keyboardType(.numberPad)
                .font(DSTypography.body)
                .foregroundStyle(DSColor.Text.primary)
                .frame(width: 28)
                .onChange(of: heightFtText) { _, _ in syncHeight() }
            Text("ft")
                .font(DSTypography.caption)
                .foregroundStyle(DSColor.Text.tertiary)
            TextField("8", text: $heightInText)
                .keyboardType(.numberPad)
                .font(DSTypography.body)
                .foregroundStyle(DSColor.Text.primary)
                .frame(width: 28)
                .onChange(of: heightInText) { _, _ in syncHeight() }
            Text("in")
                .font(DSTypography.caption)
                .foregroundStyle(DSColor.Text.tertiary)
            Spacer()
        }
        .frame(height: 48)
        .padding(.horizontal, DSSpacing.lg)
        .background(DSColor.Surface.secondary)
        .dsCornerRadius(DSRadius.md)
    }

    private var weightInputField: some View {
        HStack {
            TextField("—", text: $weightText)
                .keyboardType(.decimalPad)
                .font(DSTypography.body)
                .foregroundStyle(DSColor.Text.primary)
                .onChange(of: weightText) { _, newValue in
                    if newValue.isEmpty {
                        viewModel.assessment.weightLbs = nil
                    } else if let w = Double(newValue) {
                        viewModel.assessment.weightLbs = w
                        // Auto-set default target weight on first entry
                        if viewModel.assessment.targetWeightLbs == nil && targetWeightText.isEmpty {
                            let defaultTarget = max(w - 15, 100)
                            viewModel.assessment.targetWeightLbs = defaultTarget
                            targetWeightText = "\(Int(defaultTarget))"
                        }
                    }
                }
            Text("lbs")
                .font(DSTypography.caption)
                .foregroundStyle(DSColor.Text.tertiary)
        }
        .frame(height: 48)
        .padding(.horizontal, DSSpacing.lg)
        .background(DSColor.Surface.secondary)
        .dsCornerRadius(DSRadius.md)
    }

    private var targetWeightInputField: some View {
        HStack {
            TextField("—", text: $targetWeightText)
                .keyboardType(.decimalPad)
                .font(DSTypography.body)
                .foregroundStyle(DSColor.Text.primary)
                .onChange(of: targetWeightText) { _, newValue in
                    if newValue.isEmpty {
                        viewModel.assessment.targetWeightLbs = nil
                    } else if let tw = Double(newValue) {
                        viewModel.assessment.targetWeightLbs = tw
                    }
                }
            Text("lbs")
                .font(DSTypography.caption)
                .foregroundStyle(DSColor.Text.tertiary)
        }
        .frame(height: 48)
        .padding(.horizontal, DSSpacing.lg)
        .background(DSColor.Surface.secondary)
        .dsCornerRadius(DSRadius.md)
        .padding(.top, DSSpacing.sm)
    }

    // MARK: - Helpers

    private func syncHeight() {
        let ft = Int(heightFtText) ?? 0
        let inch = Int(heightInText) ?? 0
        let total = ft * 12 + inch
        if total > 0 {
            viewModel.assessment.heightInches = total
        }
    }

    private func fieldLabel(_ text: String) -> some View {
        Text(text)
            .dsLabel()
            .foregroundStyle(DSColor.Text.tertiary)
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
