import SwiftUI

// MARK: - Profile & Settings Screen
// Combined Profile + Settings on the Profile tab.
// Research: in a health app, profile data IS settings —
// age, weight, and goals directly control coaching.
//
// 6 sections, max 7 items each, max 2 levels deep.
// Anti-dark-pattern: privacy controls at same depth as features,
// symmetric friction, plain language, honest defaults.
//
// Grid: 20pt margins, 8pt vertical rhythm.

struct ProfileSettingsView: View {
    @State private var showDeleteConfirmation = false
    @State private var showSignOutConfirmation = false
    @State private var profile: APIUserProfile?
    private let M: CGFloat = 20

    var body: some View {
        ScrollView {
            VStack(spacing: DSSpacing.xxl) {

                // Profile header
                profileHeader

                // Section 1: You
                youSection

                // Section 2: Data Sources
                dataSourcesSection

                // Section 3: Coaching
                coachingSection

                // Section 4: Privacy & Data
                privacySection

                // Section 5: Account
                accountSection

                // Section 6: About
                aboutSection

                // Delete Account (isolated, bottom, maximum separation)
                deleteAccountSection
            }
            .padding(.horizontal, M)
            .padding(.top, DSSpacing.md)
            .padding(.bottom, DSSpacing.huge)
        }
        .background(DSColor.Background.primary)
        .navigationTitle("Profile")
        .task {
            do {
                profile = try await APIClient.shared.fetchUserProfile()
            } catch {
                // Keep nil — shows "--" placeholders
            }
        }
        .navigationBarTitleDisplayMode(.large)
        .alert("Sign out?", isPresented: $showSignOutConfirmation) {
            Button("Cancel", role: .cancel) {}
            Button("Sign Out", role: .destructive) {
                // Sign out action
            }
        } message: {
            Text("Your data stays safe. You can sign back in any time.")
        }
    }

    // MARK: - Profile Header

    private var profileHeader: some View {
        HStack(spacing: DSSpacing.lg) {
            DSAvatar(size: .xl, initials: profile?.initials ?? "?")

            VStack(alignment: .leading, spacing: DSSpacing.xs) {
                Text(profile?.name ?? "Loading...")
                    .font(DSTypography.h2)
                    .foregroundStyle(DSColor.Text.primary)

                Text(profile?.goalsString ?? "--")
                    .font(DSTypography.bodySM)
                    .foregroundStyle(DSColor.Text.secondary)

                if let since = profile?.member_since {
                    Text("Member since \(since)")
                        .font(DSTypography.caption)
                        .foregroundStyle(DSColor.Text.tertiary)
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.vertical, DSSpacing.md)
    }

    // MARK: - Section 1: You

    private var youSection: some View {
        settingsCard {
            DSSectionHeader(title: "YOU")

            settingsRow(title: "Name", value: profile?.name ?? "--")
            DSDivider()
            settingsRow(title: "Age", value: profile?.age.map { "\($0)" } ?? "--")
            DSDivider()
            settingsRow(title: "Weight", value: profile?.weightString ?? "--")
            DSDivider()
            settingsRow(title: "Height", value: profile?.heightString ?? "--")
            DSDivider()
            navigationRow(title: "Goals", subtitle: profile?.goalsString ?? "--")
        }
    }

    // MARK: - Section 2: Data Sources

    @State private var showPelotonLogin = false
    @State private var showGarminLogin = false
    @State private var selectedDataSource: DataSourceType?

    private var dataSourcesSection: some View {
        settingsCard {
            DSSectionHeader(title: "DATA SOURCES")

            ForEach(DataSourceType.allCases) { source in
                if source != DataSourceType.allCases.first {
                    DSDivider()
                }
                Button {
                    handleDataSourceTap(source)
                } label: {
                    DSListRow(title: source.rawValue, subtitle: source.subtitle, leading: {
                        dataSourceIcon(source)
                    }, trailing: {
                        HStack(spacing: DSSpacing.sm) {
                            DSListStatusDot(isConnected: isSourceConnected(source))
                            DSListChevron()
                        }
                    })
                }
                .buttonStyle(.plain)
            }
        }
        .sheet(isPresented: $showPelotonLogin) {
            PelotonLoginView()
        }
        .sheet(isPresented: $showGarminLogin) {
            GarminLoginView()
        }
        .sheet(item: $selectedDataSource) { source in
            DataSourceDetailView(
                source: source,
                isConnected: isSourceConnected(source),
                lastSynced: profile?.data_sources.first(where: { $0.name == source.rawValue })?.last_synced
            )
        }
    }

    private func handleDataSourceTap(_ source: DataSourceType) {
        let connected = isSourceConnected(source)

        if connected {
            // Show detail view for connected sources
            selectedDataSource = source
        } else {
            // Show connection flow for unconnected sources
            switch source {
            case .oura:
                // Oura OAuth — show detail with reconnect option
                selectedDataSource = source
            case .appleHealth:
                Task {
                    let granted = await HealthKitService.shared.requestAuthorization()
                    if granted {
                        await HealthKitService.shared.syncToBackend()
                        DSHaptic.success()
                    }
                }
            case .peloton:
                showPelotonLogin = true
            case .garmin:
                showGarminLogin = true
            }
        }
    }

    private func dataSourceIcon(_ source: DataSourceType) -> some View {
        let imageName: String = switch source {
        case .oura: "oura"
        case .appleHealth: "apple-health"
        case .peloton: "peloton"
        case .garmin: "garmin"
        }

        return Image(imageName)
            .resizable()
            .aspectRatio(contentMode: .fit)
            .frame(width: 32, height: 32)
            .clipShape(RoundedRectangle(cornerRadius: 8))
    }

    private func isSourceConnected(_ source: DataSourceType) -> Bool {
        // Check from profile API data
        if let sources = profile?.data_sources {
            return sources.contains { $0.name == source.rawValue && $0.connected }
        }
        return source == .oura // Default: assume Oura connected
    }

    // MARK: - Section 3: Coaching

    private var coachingSection: some View {
        settingsCard {
            DSSectionHeader(title: "COACHING")

            NavigationLink {
                NotificationPreferencesView()
            } label: {
                DSListRow(
                    title: "Notifications",
                    subtitle: "Morning brief, nudges, alerts",
                    leading: {
                        Image(systemName: "bell")
                            .foregroundStyle(DSColor.Text.secondary)
                    },
                    trailing: {
                        Image(systemName: "chevron.right")
                            .font(.caption)
                            .foregroundStyle(DSColor.Text.tertiary)
                    }
                )
            }
            .buttonStyle(.plain)
        }
    }

    // MARK: - Section 4: Privacy & Data

    private var privacySection: some View {
        settingsCard {
            DSSectionHeader(title: "PRIVACY & DATA")

            navigationRow(title: "What We Collect", subtitle: "See all data we store about you")
            DSDivider()
            navigationRow(title: "Export My Data", subtitle: "Download your health data")
            DSDivider()

            // Delete My Data — destructive, plain language, not buried
            Button(action: { showDeleteConfirmation = true }) {
                HStack {
                    Text("Delete My Data")
                        .font(DSTypography.body)
                        .foregroundStyle(DSColor.Status.error)
                    Spacer()
                    DSListChevron()
                }
                .padding(.vertical, DSSpacing.md)
                .padding(.horizontal, DSSpacing.lg)
            }

            DSDivider()
            navigationRow(title: "Privacy Policy", subtitle: nil)
        }
        .alert("Delete all your health data?", isPresented: $showDeleteConfirmation) {
            Button("Cancel", role: .cancel) {}
            Button("Delete Everything", role: .destructive) {
                // Delete data action
            }
        } message: {
            Text("This permanently removes all your health data from Meld. Your account will stay active but empty. This can't be undone.")
        }
    }

    // MARK: - Section 5: Account

    private var accountSection: some View {
        settingsCard {
            DSSectionHeader(title: "ACCOUNT")

            settingsRow(title: "Email", value: "howard.768@gmail.com")

            DSDivider()

            Button(action: { showSignOutConfirmation = true }) {
                Text("Sign Out")
                    .font(DSTypography.body)
                    .foregroundStyle(DSColor.Status.error)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, DSSpacing.md)
            }
        }
    }

    // MARK: - Section 6: About

    private var aboutSection: some View {
        settingsCard {
            DSSectionHeader(title: "ABOUT")

            settingsRow(title: "Version", value: "0.1.0 (1)")
            DSDivider()
            navigationRow(title: "Help & Support", subtitle: nil)
            DSDivider()
            navigationRow(title: "Terms of Service", subtitle: nil)
            DSDivider()
            navigationRow(title: "Open Source Licenses", subtitle: nil)
        }
    }

    // MARK: - Delete Account (isolated, maximum separation)

    private var deleteAccountSection: some View {
        VStack(spacing: DSSpacing.sm) {
            Button(action: {
                // Delete account flow — escalating friction
            }) {
                Text("Delete Account")
                    .font(DSTypography.bodySM)
                    .foregroundStyle(DSColor.Status.error)
            }

            Text("This permanently removes your account and all data.")
                .font(DSTypography.caption)
                .foregroundStyle(DSColor.Text.disabled)
                .multilineTextAlignment(.center)
        }
        .padding(.top, DSSpacing.huge)
    }

    // MARK: - Helpers

    private func settingsCard<Content: View>(@ViewBuilder content: () -> Content) -> some View {
        VStack(alignment: .leading, spacing: 0) {
            content()
        }
        .background(DSColor.Surface.primary)
        .dsCornerRadius(DSRadius.lg)
        .dsElevation(.low)
    }

    private func settingsRow(title: String, value: String) -> some View {
        HStack {
            Text(title)
                .font(DSTypography.body)
                .foregroundStyle(DSColor.Text.primary)
            Spacer()
            Text(value)
                .font(DSTypography.body)
                .foregroundStyle(DSColor.Text.secondary)
        }
        .padding(.vertical, DSSpacing.md)
        .padding(.horizontal, DSSpacing.lg)
    }

    private func navigationRow(title: String, subtitle: String?) -> some View {
        Button(action: {
            // Navigation
        }) {
            HStack {
                VStack(alignment: .leading, spacing: DSSpacing.xxs) {
                    Text(title)
                        .font(DSTypography.body)
                        .foregroundStyle(DSColor.Text.primary)
                    if let subtitle {
                        Text(subtitle)
                            .font(DSTypography.caption)
                            .foregroundStyle(DSColor.Text.tertiary)
                    }
                }
                Spacer()
                DSListChevron()
            }
            .padding(.vertical, DSSpacing.md)
            .padding(.horizontal, DSSpacing.lg)
        }
    }
}

#Preview {
    NavigationStack {
        ProfileSettingsView()
    }
}
