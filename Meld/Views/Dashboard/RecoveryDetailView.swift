import SwiftUI

// MARK: - Recovery Detail View
// Detail screen for the Recovery Readiness card.
// Shows readiness level, contributing factors, and coaching advice.

struct RecoveryDetailView: View {
    let readiness: RecoveryReadiness

    private var levelColor: Color {
        switch readiness.level {
        case .high: DSColor.Green.green500
        case .moderate: DSColor.Status.warning
        case .low: DSColor.Status.error
        }
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: DSSpacing.xxl) {

                // MARK: Hero
                VStack(alignment: .leading, spacing: DSSpacing.sm) {
                    Text("RECOVERY READINESS")
                        .dsLabel()
                        .foregroundStyle(DSColor.Text.tertiary)

                    Text(readiness.level.rawValue)
                        .font(DSTypography.display)
                        .foregroundStyle(levelColor)

                    Text(readiness.description)
                        .font(DSTypography.body)
                        .foregroundStyle(DSColor.Text.secondary)
                }

                // MARK: Contributing Factors (stub)
                DSCard(style: .metric) {
                    VStack(alignment: .leading, spacing: DSSpacing.md) {
                        Text("Contributing Factors")
                            .font(DSTypography.h3)
                            .foregroundStyle(DSColor.Text.primary)

                        factorRow(label: "Sleep Quality", value: "High", color: DSColor.Green.green500)
                        factorRow(label: "HRV Trend", value: "+14%", color: DSColor.Green.green500)
                        factorRow(label: "Resting HR", value: "Stable", color: DSColor.Text.secondary)
                        factorRow(label: "Recent Training Load", value: "Moderate", color: DSColor.Status.warning)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                }

                // MARK: Coach Recommendation (stub)
                DSCard(style: .insight) {
                    VStack(alignment: .leading, spacing: DSSpacing.md) {
                        HStack(spacing: DSSpacing.sm) {
                            SquatBlobIcon(isActive: true, size: 24)

                            Text("Recommendation")
                                .font(DSTypography.h3)
                                .foregroundStyle(DSColor.Purple.purple600)
                        }

                        Text("Your recovery metrics are aligned for high-intensity training. This is an ideal day for progressive overload on compound movements. Consider increasing working weight by 2.5-5lbs on your primary lifts.")
                            .font(DSTypography.body)
                            .foregroundStyle(DSColor.Text.primary)
                            .lineSpacing(4)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                }
            }
            .padding(.horizontal, DSSpacing.lg)
            .padding(.top, DSSpacing.md)
            .padding(.bottom, DSSpacing.xxxl)
        }
        .background(DSColor.Background.primary)
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .principal) {
                Text("Recovery")
                    .font(DSTypography.h3)
                    .foregroundStyle(DSColor.Text.primary)
            }
        }
    }

    private func factorRow(label: String, value: String, color: Color) -> some View {
        HStack {
            Text(label)
                .font(DSTypography.body)
                .foregroundStyle(DSColor.Text.primary)
            Spacer()
            Text(value)
                .font(DSTypography.bodyEmphasis)
                .foregroundStyle(color)
        }
        .padding(.vertical, DSSpacing.xs)
    }
}

#Preview {
    NavigationStack {
        RecoveryDetailView(readiness: RecoveryReadiness(
            level: .high,
            description: "Good for intensity today"
        ))
    }
}
