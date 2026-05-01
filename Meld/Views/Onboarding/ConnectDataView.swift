import SwiftUI

// MARK: - Screen 4: Connect Data Sources + Reward
// When a source connects, show data reward (information reveal).
// Coach acknowledgement card celebrates the connection.
// At least one source required — critical path.
// 4th grade reading level. 20pt margins, 8pt grid.

struct ConnectDataView: View {
    @Bindable var viewModel: OnboardingViewModel
    @Environment(\.scenePhase) private var scenePhase
    @ObservedObject private var navigator = NotificationNavigator.shared
    @State private var ouraErrorReason: String?
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

                    // Hint shown after the user returns from Safari but we
                    // haven't yet confirmed Oura is connected server-side.
                    if viewModel.pendingOuraConnect {
                        Spacer().frame(height: DSSpacing.md)
                        pendingOuraHint
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
        .task {
            // Pick up server-side connection state in case Oura already had a
            // token from a previous run (edge case: user re-opened onboarding).
            await viewModel.refreshConnectionStatus()
        }
        .onChange(of: scenePhase) { _, newPhase in
            // When the app returns to foreground (e.g. after Safari OAuth),
            // poll the backend to see if the Oura token was attached.
            if newPhase == .active && viewModel.pendingOuraConnect {
                Task { await viewModel.refreshConnectionStatus() }
            }
        }
        .onChange(of: navigator.lastOuraOutcome) { _, outcome in
            // Backend redirected Safari to meld://oura/connected (or
            // meld://oura/error?reason=...). On success, the existing
            // refreshConnectionStatus() picks up the new token. On error,
            // show an alert so the user knows to retry instead of waiting.
            guard let outcome else { return }
            switch outcome {
            case .connected:
                Task { await viewModel.refreshConnectionStatus() }
            case .error(let reason):
                ouraErrorReason = reason
            }
            navigator.lastOuraOutcome = nil  // consume so we only react once
        }
        .alert(
            "Couldn't connect Oura",
            isPresented: Binding(
                get: { ouraErrorReason != nil },
                set: { if !$0 { ouraErrorReason = nil } }
            ),
            presenting: ouraErrorReason
        ) { _ in
            Button("OK", role: .cancel) {}
        } message: { reason in
            Text(ouraErrorMessage(for: reason))
        }
    }

    /// Map a backend error reason code to user-facing copy.
    /// Reasons come from `_oura_error_deeplink(...)` in `backend/app/routers/auth.py`,
    /// plus standard OAuth error codes Oura passes through (RFC 6749 §4.1.2.1).
    private func ouraErrorMessage(for reason: String) -> String {
        switch reason {
        case "access_denied":
            return "Oura connection was cancelled. Tap Connect to try again."
        case "invalid_state":
            return "Your session expired before Oura could connect. Try connecting again."
        case "exchange_failed":
            return "Oura's servers couldn't complete the connection. Try again in a moment."
        case "missing_code":
            return "Oura didn't return a valid response. Try connecting again."
        default:
            return "Something went wrong. Try connecting again."
        }
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
                    Task { await viewModel.connectSource(source) }
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

    // MARK: - Pending Oura Hint
    //
    // Previously this spot showed a hard-coded "We found 7 days of data!
    // Sleep: 87 · HRV: 62ms · Readiness: High" card as soon as the user
    // tapped Connect, regardless of whether Oura actually connected or what
    // the real numbers were. That lie was the #1 trust-breaker in beta:
    // Stephanie called out "My sleep was not 87" in build 3 feedback. Now
    // that connectSource() opens Safari instead of faking success, we show
    // a plain "checking" hint until refreshConnectionStatus() confirms the
    // token landed. Real Oura numbers surface later on the dashboard.

    private var pendingOuraHint: some View {
        VStack(alignment: .leading, spacing: DSSpacing.sm) {
            Text("Finishing Oura connection…")
                .font(DSTypography.bodySM)
                .foregroundStyle(DSColor.Purple.purple600)

            Text("If you just came back from Safari, give it a second.")
                .font(DSTypography.caption)
                .foregroundStyle(DSColor.Text.tertiary)
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
