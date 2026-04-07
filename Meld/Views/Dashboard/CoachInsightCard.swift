import SwiftUI

// MARK: - Coach Insight Card
// Purple-100 background card showing the AI coach's daily insight.
// Matches Figma "Dashboard v3" coach card.
// Mascot avatar (placeholder circle) + "Your Coach" + timestamp + message + CTA

struct CoachInsightCard: View {
    let insight: CoachInsight

    var body: some View {
        DSCard(style: .insight) {
            VStack(alignment: .leading, spacing: DSSpacing.md) {

                // Coach header: avatar + name + timestamp
                HStack(spacing: DSSpacing.sm) {
                    // Mascot avatar placeholder
                    // Will be replaced with actual mascot asset
                    Circle()
                        .fill(DSColor.Green.green400)
                        .frame(width: 32, height: 32)
                        .overlay(
                            // Placeholder eyes for mascot
                            HStack(spacing: 4) {
                                Circle().fill(Color.white).frame(width: 6, height: 6)
                                Circle().fill(Color.white).frame(width: 6, height: 6)
                            }
                        )

                    VStack(alignment: .leading, spacing: DSSpacing.xxs) {
                        Text("Your Coach")
                            .font(DSTypography.bodySM)
                            .foregroundStyle(DSColor.Purple.purple600)

                        Text(timeAgo)
                            .font(DSTypography.caption)
                            .foregroundStyle(DSColor.Text.tertiary)
                    }
                }

                // Insight message
                Text(insight.message)
                    .font(DSTypography.body)
                    .foregroundStyle(DSColor.Text.primary)
                    .lineSpacing(4)

                // Continue in chat CTA
                Button(action: {
                    DSHaptic.light()
                    // TODO: Navigate to Coach tab
                }) {
                    Text("Continue in chat \u{2192}")
                        .font(DSTypography.bodySM)
                        .foregroundStyle(DSColor.Green.green500)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    // MARK: - Time Formatting

    private var timeAgo: String {
        let formatter = RelativeDateTimeFormatter()
        formatter.unitsStyle = .short
        return formatter.localizedString(for: insight.timestamp, relativeTo: Date())
    }
}

#Preview {
    CoachInsightCard(insight: CoachInsight(
        message: "Your HRV is 14% above your 7-day baseline and sleep efficiency hit 91%. Great recovery night. Today is ideal for progressive overload on your leg day. Prioritize compound lifts.",
        timestamp: Date()
    ))
    .padding()
    .background(DSColor.Background.primary)
}
