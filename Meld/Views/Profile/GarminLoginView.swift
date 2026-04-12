import SwiftUI

// MARK: - Garmin Login View
//
// Garmin Connect uses username/password (NOT OAuth) via the garminconnect
// library on the backend. The library handles SSO server-side; we just need
// to collect the credentials, post them once, and the backend stores the
// resulting OAuth session token (NOT the password — see P0-2 fix).

struct GarminLoginView: View {
    @State private var username = ""
    @State private var password = ""
    @State private var isLoading = false
    @State private var isConnected = false
    @State private var errorMessage: String?
    @Environment(\.dismiss) private var dismiss
    @FocusState private var focusedField: Field?

    enum Field {
        case username, password
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: DSSpacing.xxl) {
                    if isConnected {
                        connectedView
                    } else {
                        loginForm
                    }
                }
                .padding(.horizontal, DSSpacing.xl)
                .padding(.top, DSSpacing.xxl)
            }
            .background(DSColor.Background.primary)
            .navigationTitle("Connect Garmin")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
            }
            .safeAreaInset(edge: .bottom) {
                if !isConnected {
                    DSButton(
                        title: isLoading ? "Connecting..." : "Connect Garmin",
                        style: .primary,
                        size: .lg,
                        isDisabled: isLoading || username.isEmpty || password.isEmpty
                    ) {
                        Task { await login() }
                    }
                    .padding(.horizontal, DSSpacing.xl)
                    .padding(.bottom, DSSpacing.xl)
                } else {
                    DSButton(title: "Done", style: .primary, size: .lg) { dismiss() }
                        .padding(.horizontal, DSSpacing.xl)
                        .padding(.bottom, DSSpacing.xl)
                }
            }
        }
    }

    // MARK: - Connected state

    private var connectedView: some View {
        VStack(spacing: DSSpacing.lg) {
            MeldMascot(state: .celebrating, size: 64)
            Text("Garmin connected")
                .font(DSTypography.h2)
                .foregroundStyle(DSColor.Text.primary)
            Text("Steps, heart rate, sleep, stress, and activities will sync automatically.")
                .font(DSTypography.bodySM)
                .foregroundStyle(DSColor.Text.secondary)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
        .padding(.top, DSSpacing.xxl)
    }

    // MARK: - Login form

    private var loginForm: some View {
        VStack(alignment: .leading, spacing: DSSpacing.lg) {
            Text("Sign in to Garmin")
                .font(DSTypography.h2)
                .foregroundStyle(DSColor.Text.primary)

            Text("Use your Garmin Connect username and password. We use this once to get a secure session token, then forget your password.")
                .font(DSTypography.bodySM)
                .foregroundStyle(DSColor.Text.secondary)
                .lineSpacing(3)

            VStack(alignment: .leading, spacing: DSSpacing.md) {
                TextField("Email or username", text: $username)
                    .textContentType(.username)
                    .keyboardType(.emailAddress)
                    .autocorrectionDisabled()
                    .textInputAutocapitalization(.never)
                    .padding(DSSpacing.lg)
                    .background(DSColor.Background.secondary)
                    .clipShape(RoundedRectangle(cornerRadius: DSRadius.md))
                    .focused($focusedField, equals: .username)
                    .onSubmit { focusedField = .password }

                SecureField("Password", text: $password)
                    .textContentType(.password)
                    .padding(DSSpacing.lg)
                    .background(DSColor.Background.secondary)
                    .clipShape(RoundedRectangle(cornerRadius: DSRadius.md))
                    .focused($focusedField, equals: .password)
                    .onSubmit {
                        if !username.isEmpty && !password.isEmpty {
                            Task { await login() }
                        }
                    }
            }

            // What we sync
            VStack(alignment: .leading, spacing: DSSpacing.sm) {
                Text("What we'll sync")
                    .font(DSTypography.bodySM.weight(.medium))
                    .foregroundStyle(DSColor.Text.primary)
                Text("Steps · Heart rate · Sleep · Stress · Body battery · Activities")
                    .font(DSTypography.caption)
                    .foregroundStyle(DSColor.Text.secondary)
            }
            .padding(DSSpacing.lg)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(DSColor.Background.secondary)
            .clipShape(RoundedRectangle(cornerRadius: DSRadius.md))

            if let errorMessage {
                Text(errorMessage)
                    .font(DSTypography.caption)
                    .foregroundStyle(DSColor.Status.error)
                    .multilineTextAlignment(.leading)
            }
        }
    }

    // MARK: - Actions

    private func login() async {
        isLoading = true
        errorMessage = nil
        do {
            try await APIClient.shared.loginGarmin(username: username, password: password)
            isConnected = true
            // Clear the password from memory immediately
            password = ""
            DSHaptic.success()
        } catch {
            errorMessage = "Couldn't sign in to Garmin. Double-check your username and password."
            DSHaptic.error()
        }
        isLoading = false
    }
}
