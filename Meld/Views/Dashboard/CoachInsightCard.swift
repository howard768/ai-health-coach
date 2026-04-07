import SwiftUI

// MARK: - Coach Insight Card
// Purple-100 background card showing the AI coach's daily insight.
// Uses the actual SquatBlob pixel-art mascot (not a placeholder).
// The entire card is tappable — navigates to Coach tab.
// CTA is a proper button with 44pt minimum touch target.

struct CoachInsightCard: View {
    let insight: CoachInsight
    var onContinueInChat: () -> Void = {}

    var body: some View {
        Button(action: {
            DSHaptic.light()
            onContinueInChat()
        }) {
            DSCard(style: .insight) {
                VStack(alignment: .leading, spacing: DSSpacing.md) {

                    // Coach header: mascot + name + timestamp
                    HStack(spacing: DSSpacing.sm) {
                        // Actual SquatBlob mascot from Figma
                        SquatBlobIcon(isActive: true, size: 32)

                        VStack(alignment: .leading, spacing: DSSpacing.xxs) {
                            Text("Your Coach")
                                .font(DSTypography.bodyEmphasis)
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
                        .multilineTextAlignment(.leading)

                    // CTA — proper button with accessible touch target
                    HStack(spacing: DSSpacing.xs) {
                        Text("Continue in chat")
                            .font(DSTypography.bodyEmphasis)
                            .foregroundStyle(DSColor.Accessible.greenText)

                        Image(systemName: "arrow.right")
                            .font(.system(size: 13, weight: .semibold))
                            .foregroundStyle(DSColor.Accessible.greenText)
                    }
                    .frame(height: 44) // Minimum 44pt touch target
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .accessibilityLabel("Continue conversation with your coach")
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
        .buttonStyle(.plain)
        // MARK: Accessibility
        .accessibilityElement(children: .combine)
        .accessibilityLabel(insightAccessibilityLabel)
        .accessibilityHint("Double-tap to continue the conversation with your coach")
        .accessibilityAddTraits(.isButton)
    }

    // MARK: - Time Formatting

    private var timeAgo: String {
        let formatter = RelativeDateTimeFormatter()
        formatter.unitsStyle = .short
        return formatter.localizedString(for: insight.timestamp, relativeTo: Date())
    }

    // MARK: - Accessibility

    private var insightAccessibilityLabel: String {
        "Coach insight from \(timeAgo). \(insight.message). Continue in chat."
    }
}

#Preview("Light") {
    CoachInsightCard(insight: CoachInsight(
        message: "Your HRV is 14% above your 7-day baseline and sleep efficiency hit 91%. Great recovery night. Today is ideal for progressive overload on your leg day. Prioritize compound lifts.",
        timestamp: Date().addingTimeInterval(-300)
    ))
    .padding()
    .background(DSColor.Background.primary)
}

#Preview("Dark") {
    CoachInsightCard(insight: CoachInsight(
        message: "Your HRV is 14% above your 7-day baseline and sleep efficiency hit 91%. Great recovery night. Today is ideal for progressive overload on your leg day. Prioritize compound lifts.",
        timestamp: Date().addingTimeInterval(-300)
    ))
    .padding()
    .background(DSColor.Background.primary)
    .preferredColorScheme(.dark)
}
