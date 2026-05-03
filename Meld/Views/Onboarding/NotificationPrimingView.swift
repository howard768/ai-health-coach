import SwiftUI

// MARK: - Screen 5: Notification Permission Priming
// Pre-permission screen shown AFTER data source connect, BEFORE first sync.
// Research: pre-permission priming raises opt-in from 40% to 65-85%.
// No guilt language. Symmetric friction: one tap on, one tap skip.
// 4th grade reading level. 20pt margins, 8pt grid.

struct NotificationPrimingView: View {
    @Bindable var viewModel: OnboardingViewModel
    @State private var permissionGranted = false
    private let M = OnboardingLayout.margin

    var body: some View {
        VStack(spacing: 0) {
            ScrollView(showsIndicators: false) {
                VStack(alignment: .leading, spacing: 0) {

                    // Progress dots
                    DSStepDots(totalSteps: 5, currentStep: 3)
                        .frame(maxWidth: .infinity)
                        .padding(.top, DSSpacing.xxl)

                    Spacer().frame(height: DSSpacing.xxl)

                    // Mascot
                    MeldMascot(state: .greeting, size: 64)
                        .frame(maxWidth: .infinity)
                        .padding(.bottom, DSSpacing.lg)

                    // Title
                    Text("Your coach wants\nto check in")
                        .font(DSTypography.h1)
                        .foregroundStyle(DSColor.Text.primary)
                        .lineSpacing(4)

                    Spacer().frame(height: DSSpacing.sm)

                    Text("A quick update each morning based on your data.")
                        .font(DSTypography.bodySM)
                        .foregroundStyle(DSColor.Text.secondary)

                    Spacer().frame(height: DSSpacing.xxl)

                    // Example notifications
                    VStack(spacing: DSSpacing.md) {
                        exampleNotification(
                            title: "Recovery: High",
                            body: "Great sleep last night. Good day to push your workout.",
                            time: "8:02 AM"
                        )
                        exampleNotification(
                            title: "Wind-down time",
                            body: "Your HRV is elevated. Try a breathing exercise.",
                            time: "10:15 PM"
                        )
                        exampleNotification(
                            title: "Week in review",
                            body: "Sleep up 8%, 5 of 7 workout days. Nice work.",
                            time: "Sun 6 PM"
                        )
                    }

                    Spacer().frame(height: DSSpacing.xxl)

                    // Privacy note
                    Text("You can change these anytime in Settings.")
                        .font(DSTypography.caption)
                        .foregroundStyle(DSColor.Text.tertiary)
                }
                .padding(.horizontal, M)
            }

            // CTAs
            VStack(spacing: DSSpacing.md) {
                DSButton(
                    title: permissionGranted ? "Done" : "Turn on",
                    style: .primary,
                    size: .lg,
                    isDisabled: false
                ) {
                    if permissionGranted {
                        viewModel.next()
                    } else {
                        Task {
                            permissionGranted = await NotificationService.shared.requestPermission()
                            if permissionGranted {
                                // Persist default preferences to backend so the user's
                                // record exists before the first notification fires.
                                // Non-fatal, onboarding continues regardless.
                                Task { try? await APIClient.shared.updateNotificationPreferences(.defaults) }
                            }
                            Analytics.Onboarding.notificationsDecided(granted: permissionGranted)
                            // Always proceed, don't block onboarding on permission
                            viewModel.next()
                        }
                    }
                }

                Button {
                    Analytics.Onboarding.notificationsSkipped()
                    viewModel.next()
                } label: {
                    Text("Not now")
                        .font(DSTypography.bodySM)
                        .foregroundStyle(DSColor.Text.secondary)
                }
            }
            .padding(.horizontal, M)
            .padding(.bottom, DSSpacing.lg)
        }
        .background(DSColor.Background.primary)
    }

    // MARK: - Example Notification Card

    @ViewBuilder
    private func exampleNotification(title: String, body: String, time: String) -> some View {
        HStack(alignment: .top, spacing: DSSpacing.md) {
            // App icon placeholder
            RoundedRectangle(cornerRadius: DSRadius.sm)
                .fill(DSColor.Purple.purple100)
                .frame(width: 36, height: 36)
                .overlay(
                    MeldMascot(state: .idle, size: 24)
                )

            VStack(alignment: .leading, spacing: DSSpacing.xs) {
                HStack {
                    Text("Meld")
                        .font(DSTypography.caption.weight(.medium))
                        .foregroundStyle(DSColor.Text.primary)
                    Spacer()
                    Text(time)
                        .font(DSTypography.caption)
                        .foregroundStyle(DSColor.Text.tertiary)
                }
                Text(title)
                    .font(DSTypography.bodySM.weight(.medium))
                    .foregroundStyle(DSColor.Text.primary)
                Text(body)
                    .font(DSTypography.caption)
                    .foregroundStyle(DSColor.Text.secondary)
                    .lineLimit(2)
            }
        }
        .padding(DSSpacing.md)
        .background(DSColor.Background.secondary)
        .clipShape(RoundedRectangle(cornerRadius: DSRadius.md))
    }
}

// MARK: - Analytics Extension

private extension Analytics.Onboarding {
    static func notificationsDecided(granted: Bool) {
        Analytics.signal("Onboarding.notificationsDecided", parameters: ["granted": granted ? "true" : "false"])
    }

    static func notificationsSkipped() {
        Analytics.signal("Onboarding.notificationsSkipped")
    }
}
