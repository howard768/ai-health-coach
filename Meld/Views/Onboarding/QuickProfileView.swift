import SwiftUI
import UIKit

// MARK: - Screen 3: Quick Profile (Adaptive)
// Fields shown depend on goals selected in Screen 2.
// Pre-fills from HealthKit where available (green checkmark).
// All required fields for selected goals, no skip.
// 4th grade reading level. 20pt margins, 8pt grid.
//
// Build 6 revision (2026-04-16): replaced TextField + numeric-pad inputs with
// native SwiftUI `.pickerStyle(.wheel)` pickers for age, height, weight, and
// goal weight. Stephanie's build 3-5 feedback called these out as hard to use
// (no keyboard dismiss, awkward placeholder, keyboard covered the Next
// button). Wheel pickers match Apple Health / Apple Fitness onboarding
// convention, require zero text entry, and are fully accessible out of the
// box. When a value is still null the field is labeled "Tap to set" until
// the user interacts. Inline-expand-on-tap keeps the screen scannable.

struct QuickProfileView: View {
    @Bindable var viewModel: OnboardingViewModel

    // Sensible starting defaults for the wheel pickers. These do NOT write
    // back to the assessment until the user actually interacts with the
    // wheel, see the `isSet` flags below. This matches the "picker shows
    // something, but user hasn't confirmed" pattern Apple Health uses.
    @State private var ageValue: Int = 30
    @State private var heightFt: Int = 5
    @State private var heightIn: Int = 8
    @State private var weightValue: Int = 160
    @State private var targetWeightValue: Int = 145

    // Track which picker the user is actively editing. Only one picker is
    // expanded at a time to keep the scroll view short; tapping a collapsed
    // row expands it and collapses the others.
    @State private var activeField: ProfileField? = nil

    private let M = OnboardingLayout.margin

    enum ProfileField: String, CaseIterable {
        case age, height, weight, targetWeight
    }

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

                    // Age, always required
                    fieldLabel("AGE")
                    agePickerRow
                    if viewModel.prefilledAge != nil {
                        prefillBadge
                    }

                    // Height + Weight, required for weight loss or muscle goals
                    if viewModel.assessment.needsHeight {
                        Spacer().frame(height: DSSpacing.xxl)
                        fieldLabel("HEIGHT")
                        heightPickerRow

                        Spacer().frame(height: DSSpacing.xxl)
                        fieldLabel("WEIGHT")
                        weightPickerRow

                        if viewModel.prefilledHeightInches != nil || viewModel.prefilledWeightLbs != nil {
                            prefillBadge
                        }
                    }

                    // Target weight, required for weight loss
                    if viewModel.assessment.needsTargetWeight {
                        Spacer().frame(height: DSSpacing.xxl)
                        fieldLabel("GOAL WEIGHT")
                        targetWeightPickerRow
                    }

                    // Training experience, required for muscle
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

                    // Training days, required for muscle
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

                    // Chronotype, required for sleep
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

                    // Breathing room before the privacy line so it doesn't
                    // jam the Next CTA.
                    Spacer().frame(height: DSSpacing.huge)

                    // Privacy reassurance
                    Text("We keep your data private and safe.")
                        .font(DSTypography.caption)
                        .foregroundStyle(DSColor.Text.tertiary)
                        .frame(maxWidth: .infinity, alignment: .center)
                        .padding(.bottom, DSSpacing.xxl)
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
                // Collapse any open picker so the transition is clean.
                activeField = nil
                Analytics.Onboarding.profileCompleted()
                viewModel.next()
            }
            .padding(.horizontal, M)
            .padding(.bottom, DSSpacing.lg)
        }
        .background(DSColor.Background.primary)
        .onAppear {
            viewModel.applyPrefill()
            loadFromAssessment()
            Analytics.Onboarding.profileViewed()
            let prefilled = [viewModel.prefilledAge, viewModel.prefilledHeightInches].compactMap { $0 }.count
                + (viewModel.prefilledWeightLbs != nil ? 1 : 0)
            Analytics.Onboarding.profilePrefilledFields(count: prefilled)
        }
    }

    // MARK: - Initialize picker state from assessment (after HealthKit prefill)

    private func loadFromAssessment() {
        if let age = viewModel.assessment.age { ageValue = age }
        if let h = viewModel.assessment.heightInches {
            heightFt = max(3, min(7, h / 12))
            heightIn = max(0, min(11, h % 12))
        }
        if let w = viewModel.assessment.weightLbs { weightValue = Int(w) }
        if let tw = viewModel.assessment.targetWeightLbs { targetWeightValue = Int(tw) }
    }

    // MARK: - Picker Rows
    //
    // Each row renders:
    //   - A compact "current value" pill that's always visible
    //   - A checkmark (prefill badge) when HealthKit filled it in
    //   - An inline wheel picker that expands when the row is tapped
    //
    // Tapping a row sets activeField so only one picker is open at a time.

    private var agePickerRow: some View {
        pickerRow(
            field: .age,
            displayValue: viewModel.assessment.age.map { "\($0) years" } ?? "Tap to set"
        ) {
            Picker("Age", selection: $ageValue) {
                ForEach(13...99, id: \.self) { Text("\($0)").tag($0) }
            }
            .pickerStyle(.wheel)
            .frame(height: 150)
            .onChange(of: ageValue) { _, newValue in
                viewModel.assessment.age = newValue
                DSHaptic.selection()
            }
        }
    }

    private var heightPickerRow: some View {
        pickerRow(
            field: .height,
            displayValue: viewModel.assessment.heightInches.map {
                "\($0 / 12)' \($0 % 12)\""
            } ?? "Tap to set"
        ) {
            HStack(spacing: 0) {
                Picker("Feet", selection: $heightFt) {
                    ForEach(3...7, id: \.self) { Text("\($0) ft").tag($0) }
                }
                .pickerStyle(.wheel)
                .frame(maxWidth: .infinity)

                Picker("Inches", selection: $heightIn) {
                    ForEach(0...11, id: \.self) { Text("\($0) in").tag($0) }
                }
                .pickerStyle(.wheel)
                .frame(maxWidth: .infinity)
            }
            .frame(height: 150)
            .onChange(of: heightFt) { _, _ in syncHeight() }
            .onChange(of: heightIn) { _, _ in syncHeight() }
        }
    }

    private var weightPickerRow: some View {
        pickerRow(
            field: .weight,
            displayValue: viewModel.assessment.weightLbs.map {
                "\(Int($0)) lbs"
            } ?? "Tap to set"
        ) {
            Picker("Weight", selection: $weightValue) {
                ForEach(80...400, id: \.self) { Text("\($0) lbs").tag($0) }
            }
            .pickerStyle(.wheel)
            .frame(height: 150)
            .onChange(of: weightValue) { _, newValue in
                viewModel.assessment.weightLbs = Double(newValue)
                // Auto-seed a sensible target weight the first time the
                // user picks a weight, if their goal is loss and they
                // haven't set one yet.
                if viewModel.assessment.targetWeightLbs == nil {
                    let defaultTarget = max(newValue - 15, 100)
                    viewModel.assessment.targetWeightLbs = Double(defaultTarget)
                    targetWeightValue = defaultTarget
                }
                DSHaptic.selection()
            }
        }
    }

    private var targetWeightPickerRow: some View {
        pickerRow(
            field: .targetWeight,
            displayValue: viewModel.assessment.targetWeightLbs.map {
                "\(Int($0)) lbs"
            } ?? "Tap to set"
        ) {
            Picker("Goal weight", selection: $targetWeightValue) {
                ForEach(80...400, id: \.self) { Text("\($0) lbs").tag($0) }
            }
            .pickerStyle(.wheel)
            .frame(height: 150)
            .onChange(of: targetWeightValue) { _, newValue in
                viewModel.assessment.targetWeightLbs = Double(newValue)
                DSHaptic.selection()
            }
        }
    }

    // MARK: - Picker row scaffolding

    @ViewBuilder
    private func pickerRow<Content: View>(
        field: ProfileField,
        displayValue: String,
        @ViewBuilder picker: () -> Content
    ) -> some View {
        VStack(spacing: 0) {
            Button(action: {
                withAnimation(DSMotion.standard) {
                    activeField = (activeField == field) ? nil : field
                }
                DSHaptic.light()
            }) {
                HStack {
                    Text(displayValue)
                        .font(DSTypography.body)
                        .foregroundStyle(
                            displayValue == "Tap to set"
                                ? DSColor.Text.tertiary
                                : DSColor.Text.primary
                        )

                    Spacer()

                    Image(systemName: activeField == field ? "chevron.up" : "chevron.down")
                        .font(.system(size: 14, weight: .semibold))
                        .foregroundStyle(DSColor.Text.tertiary)
                }
                .frame(height: 48)
                .padding(.horizontal, DSSpacing.lg)
                .background(DSColor.Surface.secondary)
                .dsCornerRadius(DSRadius.md)
            }
            .buttonStyle(.plain)

            if activeField == field {
                picker()
                    .padding(.top, DSSpacing.xs)
                    .transition(.opacity.combined(with: .move(edge: .top)))
            }
        }
        .padding(.top, DSSpacing.sm)
    }

    // MARK: - Helpers

    private func syncHeight() {
        let total = heightFt * 12 + heightIn
        if total > 0 {
            viewModel.assessment.heightInches = total
            DSHaptic.selection()
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
