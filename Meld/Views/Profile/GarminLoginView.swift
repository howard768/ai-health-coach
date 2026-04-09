import SwiftUI

// MARK: - Garmin Login View
// Username/password authentication via garminconnect SSO.

struct GarminLoginView: View {
    @State private var username = ""
    @State private var password = ""
    @State private var isLoading = false
    @State private var isConnected = false
    @State private var errorMessage: String?
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            VStack(spacing: DSSpacing.xxl) {
                Spacer()

                if isConnected {
                    VStack(spacing: DSSpacing.lg) {
                        AnimatedMascot(state: .celebrating, size: 64)
                        Text("Garmin connected")
                            .font(DSTypography.h2)
                            .foregroundStyle(DSColor.Text.primary)
                        Text("Steps, heart rate, sleep, and more will sync automatically.")
                            .font(DSTypography.bodySM)
                            .foregroundStyle(DSColor.Text.secondary)
                            .multilineTextAlignment(.center)
                    }
                } else {
                    VStack(alignment: .leading, spacing: DSSpacing.lg) {
                        Text("Connect Garmin")
                            .font(DSTypography.h2)
                            .foregroundStyle(DSColor.Text.primary)
                        Text("Garmin uses secure OAuth to connect. You'll be redirected to Garmin's login page to authorize Meld.")
                            .font(DSTypography.bodySM)
                            .foregroundStyle(DSColor.Text.secondary)

                        // Info card
                        VStack(alignment: .leading, spacing: DSSpacing.sm) {
                            Text("What we'll access:")
                                .font(DSTypography.bodySM.weight(.medium))
                                .foregroundStyle(DSColor.Text.primary)
                            Text("Steps, heart rate, sleep, stress, body battery, and activities")
                                .font(DSTypography.caption)
                                .foregroundStyle(DSColor.Text.secondary)
                        }
                        .padding(DSSpacing.lg)
                        .background(DSColor.Background.secondary)
                        .clipShape(RoundedRectangle(cornerRadius: DSRadius.md))

                        if let error = errorMessage {
                            Text(error)
                                .font(DSTypography.caption)
                                .foregroundStyle(DSColor.Status.error)
                        }
                    }
                    .padding(.horizontal, DSSpacing.xl)
                }

                Spacer()

                if isConnected {
                    DSButton(title: "Done", style: .primary, size: .lg) { dismiss() }
                        .padding(.horizontal, DSSpacing.xl)
                } else {
                    DSButton(
                        title: "Connect with Garmin",
                        style: .primary, size: .lg
                    ) {
                        // TODO: Open Garmin OAuth URL in browser when Developer Program credentials are available
                        errorMessage = "Garmin OAuth integration pending. Apply at developer.garmin.com."
                    }
                    .padding(.horizontal, DSSpacing.xl)
                }

                Spacer().frame(height: DSSpacing.xxl)
            }
            .background(DSColor.Background.primary)
            .navigationTitle("Garmin")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
            }
        }
    }

    private func login() async {
        isLoading = true
        errorMessage = nil
        do {
            try await APIClient.shared.loginGarmin(username: username, password: password)
            isConnected = true
            DSHaptic.success()
        } catch {
            errorMessage = "Login failed. Check your credentials and try again."
            DSHaptic.error()
        }
        isLoading = false
    }
}
