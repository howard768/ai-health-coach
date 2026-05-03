import SwiftUI

// MARK: - Meld Design System Empty State
// Centered composition for screens with no content.
// Uses iOS 17's ContentUnavailableView as structural base when appropriate,
// but styled with our DS tokens for brand consistency.
//
// Pattern: Illustration slot → Title → Body → Primary action
// The illustration slot accepts any View, mascot, icon, custom art.

struct DSEmptyState<Illustration: View>: View {
    let title: String
    let message: String
    var actionTitle: String? = nil
    var action: (() -> Void)? = nil
    @ViewBuilder var illustration: () -> Illustration

    var body: some View {
        VStack(spacing: DSSpacing.xxl) {
            // Illustration (mascot, icon, custom art)
            illustration()
                .frame(maxWidth: 200, maxHeight: 160)

            // Text content
            VStack(spacing: DSSpacing.sm) {
                Text(title)
                    .font(DSTypography.h2)
                    .foregroundStyle(DSColor.Text.primary)
                    .multilineTextAlignment(.center)

                Text(message)
                    .font(DSTypography.body)
                    .foregroundStyle(DSColor.Text.secondary)
                    .multilineTextAlignment(.center)
                    .lineSpacing(4)
            }
            .padding(.horizontal, DSSpacing.xxxl)

            // Action button (optional)
            if let actionTitle, let action {
                DSButton(title: actionTitle, style: .primary, size: .lg, action: action)
                    .padding(.horizontal, DSSpacing.huge)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .padding(DSSpacing.xl)
        .accessibilityElement(children: .combine)
    }
}

// MARK: - Convenience: Empty state with mascot

extension DSEmptyState where Illustration == MeldMascot {
    /// Empty state using the Meld mascot as illustration. Reads equipped
    /// accessories from the global wardrobe so locked screens still show
    /// off the user's earned customizations.
    init(
        title: String,
        message: String,
        actionTitle: String? = nil,
        action: (() -> Void)? = nil
    ) {
        self.title = title
        self.message = message
        self.actionTitle = actionTitle
        self.action = action
        self.illustration = { MeldMascot(state: .idle, size: 80) }
    }
}

// MARK: - Convenience: Empty state with SF Symbol placeholder

struct DSEmptyStateIcon: View {
    let systemName: String
    var color: Color = DSColor.Text.disabled

    var body: some View {
        Image(systemName: systemName)
            .font(.system(size: 48, weight: .light))
            .foregroundStyle(color)
    }
}

// MARK: - Previews

#Preview("Mascot") {
    DSEmptyState(
        title: "No health data yet",
        message: "Connect your Oura Ring or Apple Health to start seeing your metrics here.",
        actionTitle: "Connect a wearable"
    )
}

#Preview("With Icon") {
    DSEmptyState(
        title: "Start a conversation",
        message: "Your coach is ready to help. Ask about your sleep, recovery, or training.",
        actionTitle: "Say hello",
        illustration: {
            DSEmptyStateIcon(systemName: "bubble.left.and.text.bubble.right", color: DSColor.Purple.purple300)
        }
    )
}

#Preview("Trends - Need Data") {
    DSEmptyState(
        title: "Building your trends",
        message: "We need at least 7 days of data to show meaningful trends. You're on day 3.",
        illustration: {
            DSEmptyStateIcon(systemName: "chart.line.uptrend.xyaxis", color: DSColor.Green.green300)
        }
    )
}

#Preview("Dark") {
    DSEmptyState(
        title: "No health data yet",
        message: "Connect your Oura Ring or Apple Health to start seeing your metrics here.",
        actionTitle: "Connect a wearable"
    )
    .background(DSColor.Background.primary)
    .preferredColorScheme(.dark)
}
