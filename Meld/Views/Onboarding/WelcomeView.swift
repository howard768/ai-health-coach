import SwiftUI

// MARK: - Screen 1: Welcome + Apple Sign In
// PAS framework: Problem → Agitation → Solution
// Loss framing + curiosity gap + real insight preview
// All copy at 4th grade reading level.
// Grid: 20pt margins, 8pt vertical rhythm.

struct WelcomeView: View {
    let viewModel: OnboardingViewModel
    private let M = OnboardingLayout.margin

    var body: some View {
        VStack(spacing: 0) {
            ScrollView(showsIndicators: false) {
                VStack(alignment: .leading, spacing: 0) {

                    // Brand: mascot + name
                    HStack(spacing: DSSpacing.md) {
                        AnimatedMascot(state: .greeting, size: 40)
                        Text("Meld")
                            .font(DSTypography.h2)
                            .foregroundStyle(DSColor.Text.primary)
                    }
                    .padding(.top, DSSpacing.xxxl)

                    Spacer().frame(height: DSSpacing.xxxl)

                    // Hook: loss framing + curiosity gap
                    VStack(alignment: .leading, spacing: 0) {
                        Text("Your body sends\nsignals every night.")
                            .font(DSTypography.h1)
                            .foregroundStyle(DSColor.Text.primary)
                            .lineSpacing(4)

                        Text("Are you reading them?")
                            .font(DSTypography.h1)
                            .foregroundStyle(DSColor.Purple.purple500)
                            .padding(.top, DSSpacing.xs)
                    }

                    Spacer().frame(height: DSSpacing.xxl)

                    // Agitation
                    Text("Your Oura and Apple Health collect data every day. But no one is connecting the dots for you.")
                        .font(DSTypography.body)
                        .foregroundStyle(DSColor.Text.secondary)
                        .lineSpacing(4)

                    Spacer().frame(height: DSSpacing.xxl)

                    // Proof: real insight preview
                    insightCard

                    Spacer().frame(height: DSSpacing.xxl)

                    // Solution
                    Text("Meld connects your health data, finds hidden patterns, and tells you exactly what to do each day.")
                        .font(DSTypography.body)
                        .foregroundStyle(DSColor.Text.secondary)
                        .lineSpacing(4)

                    Spacer().frame(height: DSSpacing.xxl)

                    // Social proof
                    socialProofCard
                }
                .padding(.horizontal, M)
            }

            // CTA anchored at bottom
            VStack(spacing: DSSpacing.sm) {
                Button(action: {
                    Analytics.Onboarding.appleSignInTapped()
                    // Apple Sign In would go here — for now skip to goals
                    Analytics.Onboarding.appleSignInCompleted()
                    viewModel.next()
                }) {
                    Text("Sign in with Apple")
                        .font(DSTypography.bodyEmphasis)
                        .foregroundStyle(.white)
                        .frame(maxWidth: .infinity)
                        .frame(height: 52)
                        .background(DSColor.Text.primary)
                        .dsCornerRadius(DSRadius.lg)
                }

                Text("By signing in, you agree to our Terms & Privacy Policy.")
                    .font(.system(size: 10))
                    .foregroundStyle(DSColor.Text.disabled)
                    .multilineTextAlignment(.center)
            }
            .padding(.horizontal, M)
            .padding(.bottom, DSSpacing.lg)
        }
        .background(DSColor.Background.primary)
        .onAppear { Analytics.Onboarding.welcomeViewed() }
    }

    // MARK: - Insight Card

    private var insightCard: some View {
        VStack(alignment: .leading, spacing: DSSpacing.md) {
            HStack(spacing: DSSpacing.sm) {
                AnimatedMascot(state: .idle, size: 24)

                Text("Your Coach spotted this:")
                    .font(DSTypography.caption)
                    .foregroundStyle(DSColor.Purple.purple600)
            }

            Text("Your deep sleep goes up 22% on days you eat more protein.")
                .font(DSTypography.bodyEmphasis)
                .foregroundStyle(DSColor.Text.primary)
                .lineSpacing(3)

            Text("From your Oura sleep + food log")
                .font(DSTypography.caption)
                .foregroundStyle(DSColor.Text.tertiary)

            // Mini trend bars
            HStack(alignment: .bottom, spacing: 6) {
                ForEach([12, 18, 14, 24, 20, 28, 26, 36], id: \.self) { h in
                    RoundedRectangle(cornerRadius: 3, style: .continuous)
                        .fill(h == 36 ? DSColor.Purple.purple500 : DSColor.Purple.purple300)
                        .frame(width: 14, height: CGFloat(h))
                }
            }
            .frame(height: 36, alignment: .bottom)
        }
        .insightCard()
    }

    // MARK: - Social Proof

    private var socialProofCard: some View {
        HStack(spacing: DSSpacing.md) {
            AnimatedMascot(state: .idle, size: 24)

            Text("Built by a health tech team that's coached 3M+ people at Lark Health.")
                .font(DSTypography.bodySM)
                .foregroundStyle(DSColor.Text.tertiary)
                .lineSpacing(3)
        }
        .padding(DSSpacing.lg)
        .background(DSColor.Surface.secondary)
        .dsCornerRadius(DSRadius.md)
    }
}

#Preview {
    WelcomeView(viewModel: OnboardingViewModel())
}
