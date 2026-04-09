import SwiftUI

// MARK: - Data Source Detail View
// Shows connection status, last sync time, data types being synced,
// and option to disconnect. Anti-dark-pattern: disconnect is same
// friction as connect (one tap + confirm).

struct DataSourceDetailView: View {
    let source: DataSourceType
    let isConnected: Bool
    let lastSynced: String?
    @Environment(\.dismiss) private var dismiss
    @State private var showDisconnectConfirm = false

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: DSSpacing.xxl) {

                    // Status card
                    VStack(spacing: DSSpacing.lg) {
                        dataSourceIcon
                            .frame(width: 64, height: 64)

                        Text(source.rawValue)
                            .font(DSTypography.h2)
                            .foregroundStyle(DSColor.Text.primary)

                        HStack(spacing: DSSpacing.sm) {
                            Circle()
                                .fill(isConnected ? DSColor.Green.green500 : DSColor.Status.error)
                                .frame(width: 8, height: 8)
                            Text(isConnected ? "Connected" : "Not connected")
                                .font(DSTypography.bodySM)
                                .foregroundStyle(DSColor.Text.secondary)
                        }

                        if let lastSynced {
                            Text("Last synced: \(lastSynced)")
                                .font(DSTypography.caption)
                                .foregroundStyle(DSColor.Text.tertiary)
                        }
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.top, DSSpacing.xxl)

                    // Data types
                    VStack(alignment: .leading, spacing: DSSpacing.sm) {
                        DSSectionHeader(title: "DATA WE READ")

                        VStack(alignment: .leading, spacing: DSSpacing.md) {
                            ForEach(dataTypes, id: \.self) { dataType in
                                HStack(spacing: DSSpacing.md) {
                                    Image(systemName: "checkmark.circle.fill")
                                        .foregroundStyle(DSColor.Green.green500)
                                        .font(.system(size: 16))
                                    Text(dataType)
                                        .font(DSTypography.body)
                                        .foregroundStyle(DSColor.Text.primary)
                                }
                            }
                        }
                        .padding(DSSpacing.lg)
                        .background(DSColor.Background.secondary)
                        .clipShape(RoundedRectangle(cornerRadius: DSRadius.md))
                    }

                    // Sync button
                    if isConnected {
                        DSButton(title: "Sync now", style: .secondary, size: .lg) {
                            // TODO: trigger manual sync
                            DSHaptic.light()
                        }
                    }

                    Spacer().frame(height: DSSpacing.xxl)

                    // Disconnect
                    if isConnected {
                        Button {
                            showDisconnectConfirm = true
                        } label: {
                            Text("Disconnect \(source.rawValue)")
                                .font(DSTypography.body)
                                .foregroundStyle(DSColor.Status.error)
                                .frame(maxWidth: .infinity)
                        }
                    }
                }
                .padding(.horizontal, DSSpacing.xl)
                .padding(.bottom, 120)
            }
            .background(DSColor.Background.primary)
            .navigationTitle(source.rawValue)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Done") { dismiss() }
                }
            }
            .alert("Disconnect \(source.rawValue)?", isPresented: $showDisconnectConfirm) {
                Button("Disconnect", role: .destructive) {
                    // TODO: remove token from backend
                    dismiss()
                }
                Button("Cancel", role: .cancel) {}
            } message: {
                Text("Your data stays in Meld. You can reconnect any time.")
            }
        }
    }

    private var dataTypes: [String] {
        switch source {
        case .oura: ["Sleep stages and duration", "Heart rate variability (HRV)", "Resting heart rate", "Readiness score", "Body temperature"]
        case .appleHealth: ["Sleep analysis", "Steps and activity", "Heart rate", "HRV", "Workouts", "Body measurements"]
        case .peloton: ["Cycling workouts", "Running workouts", "Strength sessions", "Yoga sessions", "Calories burned"]
        case .garmin: ["Daily steps", "Heart rate", "Sleep data", "Stress levels", "Body Battery", "Activities"]
        }
    }

    @ViewBuilder
    private var dataSourceIcon: some View {
        let imageName: String = switch source {
        case .oura: "oura"
        case .appleHealth: "apple-health"
        case .peloton: "peloton"
        case .garmin: "garmin"
        }

        Image(imageName)
            .resizable()
            .aspectRatio(contentMode: .fit)
            .clipShape(RoundedRectangle(cornerRadius: 14))
    }
}
