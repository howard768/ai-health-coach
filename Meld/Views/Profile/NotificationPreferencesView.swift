import SwiftUI

// MARK: - Notification Preferences
// Granular control over each notification category.
// Anti-dark-pattern: symmetric friction (same taps to enable/disable).
// Fetches from and saves to backend API.

struct NotificationPreferencesView: View {
    @State private var prefs = APINotificationPreferences.defaults
    @State private var isLoading = true
    @State private var systemEnabled = true

    var body: some View {
        ScrollView(showsIndicators: false) {
            VStack(alignment: .leading, spacing: 0) {

                // System status banner (if notifications disabled at OS level)
                if !systemEnabled {
                    systemDisabledBanner
                    Spacer().frame(height: DSSpacing.xxl)
                }

                // Daily Coaching
                DSSectionHeader(title: "DAILY COACHING")
                Spacer().frame(height: DSSpacing.sm)

                settingsCard {
                    DSToggle(
                        title: "Morning Brief",
                        isOn: $prefs.morning_brief,
                        subtitle: "Recovery score and today's focus"
                    )
                    DSDivider()
                    DSToggle(
                        title: "Bedtime Coaching",
                        isOn: $prefs.bedtime_coaching,
                        subtitle: "Wind-down reminder at your sleep time"
                    )
                }

                Spacer().frame(height: DSSpacing.xxl)

                // Insights & Nudges
                DSSectionHeader(title: "INSIGHTS")
                Spacer().frame(height: DSSpacing.sm)

                settingsCard {
                    DSToggle(
                        title: "Coaching Nudges",
                        isOn: $prefs.coaching_nudge,
                        subtitle: "Cross-domain insights from your data, 2-3x per week"
                    )
                    DSDivider()
                    DSToggle(
                        title: "Streak Alerts",
                        isOn: $prefs.streak_alerts,
                        subtitle: "Heads up when you're close to missing a goal"
                    )
                    DSDivider()
                    DSToggle(
                        title: "Weekly Review",
                        isOn: $prefs.weekly_review,
                        subtitle: "Sunday summary of your week"
                    )
                }

                Spacer().frame(height: DSSpacing.xxl)

                // Health & Safety
                DSSectionHeader(title: "HEALTH")
                Spacer().frame(height: DSSpacing.sm)

                settingsCard {
                    DSToggle(
                        title: "Health Alerts",
                        isOn: $prefs.health_alerts,
                        subtitle: "When something unusual shows up in your data"
                    )

                    // Recommended label
                    Text("Recommended")
                        .font(DSTypography.caption)
                        .foregroundStyle(DSColor.Green.green500)
                        .padding(.leading, DSSpacing.lg)
                        .padding(.bottom, DSSpacing.sm)
                }

                Spacer().frame(height: DSSpacing.xxl)

                // Quiet Hours
                DSSectionHeader(title: "QUIET HOURS")
                Spacer().frame(height: DSSpacing.sm)

                settingsCard {
                    HStack {
                        Text("Start")
                            .font(DSTypography.body)
                            .foregroundStyle(DSColor.Text.primary)
                        Spacer()
                        Text(prefs.quiet_hours_start)
                            .font(DSTypography.body)
                            .foregroundStyle(DSColor.Text.secondary)
                    }
                    .padding(.vertical, DSSpacing.xs)

                    DSDivider()

                    HStack {
                        Text("End")
                            .font(DSTypography.body)
                            .foregroundStyle(DSColor.Text.primary)
                        Spacer()
                        Text(prefs.quiet_hours_end)
                            .font(DSTypography.body)
                            .foregroundStyle(DSColor.Text.secondary)
                    }
                    .padding(.vertical, DSSpacing.xs)
                }

                Spacer().frame(height: DSSpacing.md)

                Text("No notifications during quiet hours.")
                    .font(DSTypography.caption)
                    .foregroundStyle(DSColor.Text.tertiary)
                    .padding(.horizontal, DSSpacing.lg)

                Spacer().frame(height: 100)
            }
            .padding(.horizontal, DSSpacing.xl)
        }
        .background(DSColor.Background.primary)
        .navigationTitle("Notifications")
        .navigationBarTitleDisplayMode(.large)
        .task {
            await loadPreferences()
            await checkSystemPermission()
        }
        .onChange(of: prefs.morning_brief) { _, _ in savePreferences() }
        .onChange(of: prefs.coaching_nudge) { _, _ in savePreferences() }
        .onChange(of: prefs.bedtime_coaching) { _, _ in savePreferences() }
        .onChange(of: prefs.streak_alerts) { _, _ in savePreferences() }
        .onChange(of: prefs.weekly_review) { _, _ in savePreferences() }
        .onChange(of: prefs.health_alerts) { _, _ in savePreferences() }
        .onChange(of: prefs.workout_reminders) { _, _ in savePreferences() }
    }

    // MARK: - System Disabled Banner

    @ViewBuilder
    private var systemDisabledBanner: some View {
        HStack(spacing: DSSpacing.md) {
            Image(systemName: "bell.slash")
                .foregroundStyle(DSColor.Status.warning)
            VStack(alignment: .leading, spacing: DSSpacing.xs) {
                Text("Notifications are off")
                    .font(DSTypography.bodySM.weight(.medium))
                    .foregroundStyle(DSColor.Text.primary)
                Text("Turn them on in iPhone Settings to get coaching updates.")
                    .font(DSTypography.caption)
                    .foregroundStyle(DSColor.Text.secondary)
            }
            Spacer()
        }
        .padding(DSSpacing.lg)
        .background(DSColor.Background.secondary)
        .clipShape(RoundedRectangle(cornerRadius: DSRadius.md))
    }

    // MARK: - Settings Card

    @ViewBuilder
    private func settingsCard(@ViewBuilder content: () -> some View) -> some View {
        VStack(alignment: .leading, spacing: 0) {
            content()
        }
        .padding(.horizontal, DSSpacing.lg)
        .padding(.vertical, DSSpacing.md)
        .background(DSColor.Background.secondary)
        .clipShape(RoundedRectangle(cornerRadius: DSRadius.md))
    }

    // MARK: - Data

    private func loadPreferences() async {
        do {
            prefs = try await APIClient.shared.fetchNotificationPreferences()
            isLoading = false
        } catch {
            isLoading = false
        }
    }

    private func checkSystemPermission() async {
        let status = await NotificationService.shared.getPermissionStatus()
        systemEnabled = status == .authorized
    }

    private func savePreferences() {
        Task {
            do {
                try await APIClient.shared.updateNotificationPreferences(prefs)
            } catch {
                print("[Notifications] Failed to save preferences: \(error)")
            }
        }
    }
}
