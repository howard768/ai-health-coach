import SwiftUI

// MARK: - Screen 4: Connect Data Sources + Reward
// When a source connects, show data reward (information reveal).
// Coach acknowledgement card celebrates the connection.
// At least one source required — critical path.
// 4th grade reading level. 20pt margins, 8pt grid.

struct ConnectDataView: View {
    @Bindable var viewModel: OnboardingViewModel
    private let M = OnboardingLayout.margin

    var body: some View {
        VStack(spacing: 0) {
            ScrollView(showsIndicators: false) {
                VStack(alignment: .leading, spacing: 0) {

                    // Progress dots
                    DSStepDots(totalSteps: 4, currentStep: 2)
                        .frame(maxWidth: .infinity)
                        .padding(.top, DSSpacing.xxl)

                    Spacer().frame(height: DSSpacing.xxxl)

                    // Title
                    Text("Connect your\nhealth data")
                        .font(DSTypography.h1)
                        .foregroundStyle(DSColor.Text.primary)
                        .lineSpacing(4)

                    Spacer().frame(height: DSSpacing.sm)

                    Text("Your coach gets smarter with more data.")
                        .font(DSTypography.bodySM)
                        .foregroundStyle(DSColor.Text.secondary)

                    Spacer().frame(height: DSSpacing.xxl)

                    // Source cards
                    ForEach(DataSourceType.allCases) { source in
                        sourceCard(source)
                        Spacer().frame(height: DSSpacing.md)
                    }

                    // Data reward (shown when Oura is connected)
                    if viewModel.assessment.connectedSources.contains(.oura) {
                        Spacer().frame(height: DSSpacing.md)
                        dataRewardCard
                    }

                    // Coach acknowledgement
                    if !viewModel.assessment.connectedSources.isEmpty {
                        Spacer().frame(height: DSSpacing.xxl)
                        coachAcknowledgement
                    }

                    Spacer().frame(height: DSSpacing.xxl)

                    // Requirement note
                    Text("You need at least one source to start.")
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
                isDisabled: !viewModel.canProceedFromConnect
            ) {
                Analytics.Onboarding.connectContinued()
                viewModel.next()
            }
            .padding(.horizontal, M)
            .padding(.bottom, DSSpacing.lg)
        }
        .background(DSColor.Background.primary)
        .onAppear { Analytics.Onboarding.connectViewed() }
    }

    // MARK: - Source Card

    @ViewBuilder
    private func sourceCard(_ source: DataSourceType) -> some View {
        let isConnected = viewModel.assessment.connectedSources.contains(source)

        HStack(spacing: DSSpacing.lg) {
            // Icon placeholder
            Circle()
                .fill(isConnected ? Color.hex(0xFAF0DA) : DSColor.Surface.secondary)
                .frame(width: 44, height: 44)
                .overlay(
                    source == .oura
                        ? AnyView(SquatBlobIcon(isActive: isConnected, size: 24))
                        : source == .appleHealth
                            ? AnyView(Text("♥").font(.system(size: 18)).foregroundStyle(.red))
                            : AnyView(Image(systemName: "antenna.radiowaves.left.and.right").foregroundStyle(DSColor.Text.disabled))
                )
                .accessibilityHidden(true)

            VStack(alignment: .leading, spacing: DSSpacing.xxs) {
                Text(source.rawValue)
                    .font(DSTypography.bodyEmphasis)
                    .foregroundStyle(source.isAvailable ? DSColor.Text.primary : DSColor.Text.disabled)

                Text(source.subtitle)
                    .font(DSTypography.caption)
                    .foregroundStyle(DSColor.Text.tertiary)
            }

            Spacer()

            if isConnected {
                Circle()
                    .fill(DSColor.Status.success)
                    .frame(width: 28, height: 28)
                    .overlay(
                        Image(systemName: "checkmark")
                            .font(.system(size: 13, weight: .bold))
                            .foregroundStyle(.white)
                    )
                    .accessibilityHidden(true)
            } else if source.isAvailable {
                DSButton(title: source == .oura ? "Connect" : "Allow", style: .primary, size: .sm) {
                    viewModel.connectSource(source)
                }
            } else {
                Text("Soon")
                    .font(DSTypography.caption)
                    .foregroundStyle(DSColor.Text.disabled)
            }
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(source.rawValue), \(isConnected ? "connected" : source.isAvailable ? "not connected" : "coming soon")")
        .accessibilityHint(source.subtitle)
        .padding(DSSpacing.lg)
        .background(source.isAvailable ? DSColor.Surface.primary : DSColor.Surface.secondary)
        .dsCornerRadius(DSRadius.lg)
        .overlay(
            RoundedRectangle(cornerRadius: DSRadius.lg, style: .continuous)
                .stroke(DSColor.Background.tertiary, lineWidth: 1)
        )
        .opacity(source.isAvailable ? 1.0 : 0.6)
    }

    // MARK: - Data Reward Card

    private var dataRewardCard: some View {
        VStack(alignment: .leading, spacing: DSSpacing.sm) {
            Text("We found 7 days of data!")
                .font(DSTypography.bodySM)
                .foregroundStyle(DSColor.Purple.purple600)

            Text("Sleep: 87  ·  HRV: 62ms  ·  Readiness: High")
                .font(DSTypography.bodySM)
                .foregroundStyle(DSColor.Text.primary)
        }
        .padding(DSSpacing.lg)
        .background(DSColor.Purple.purple100)
        .dsCornerRadius(DSRadius.md)
        .transition(.scale.combined(with: .opacity))
    }

    // MARK: - Coach Acknowledgement

    private var coachAcknowledgement: some View {
        HStack(spacing: DSSpacing.md) {
            MeldMascot(state: .celebrating, size: 32)

            VStack(alignment: .leading, spacing: DSSpacing.xxs) {
                Text("Your coach just got smarter!")
                    .font(DSTypography.bodyEmphasis)
                    .foregroundStyle(DSColor.Text.primary)

                Text("Ready to help you reach your goals.")
                    .font(DSTypography.caption)
                    .foregroundStyle(DSColor.Text.tertiary)
            }
        }
        .padding(DSSpacing.lg)
        .background(Color.hex(0xFAF0DA)) // Amber tint
        .dsCornerRadius(DSRadius.md)
        .transition(.scale.combined(with: .opacity))
    }
}

#Preview {
    let vm = OnboardingViewModel()
    vm.assessment.connectedSources = [.oura]
    return ConnectDataView(viewModel: vm)
}
