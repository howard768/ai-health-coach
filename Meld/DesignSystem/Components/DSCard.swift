import SwiftUI

// MARK: - Meld Design System Card Component
// Cards are the primary content containers in the app.
// Variant-driven: each style maps to specific design tokens.

enum DSCardStyle {
    /// White background, medium elevation, lg radius — for health metrics
    case metric
    /// Purple-100 background, no shadow, xl radius — for coach insights
    case insight
    /// Glass material background — for elevated/overlay content
    case glass
    /// Subtle surface background — for data visualization cards
    case data
}

struct DSCard<Content: View>: View {
    let style: DSCardStyle
    @ViewBuilder let content: () -> Content

    var body: some View {
        content()
            .padding(DSSpacing.xl)
            .modifier(DSCardStyleModifier(style: style))
    }
}

// MARK: - Card Style Modifier

private struct DSCardStyleModifier: ViewModifier {
    let style: DSCardStyle
    @Environment(\.colorScheme) private var colorScheme

    func body(content: Content) -> some View {
        switch style {
        case .metric:
            content
                .background(DSColor.Surface.primary)
                .dsCornerRadius(DSRadius.lg)
                .dsElevation(.medium)

        case .insight:
            content
                .background(DSColor.Purple.purple100)
                .dsCornerRadius(DSRadius.xl)

        case .glass:
            content
                .glassBackground(radius: DSRadius.xl)

        case .data:
            content
                .background(DSColor.Surface.secondary)
                .dsCornerRadius(DSRadius.lg)
                .dsElevation(.low)
        }
    }
}

// MARK: - Convenience View Extensions

extension View {
    /// Wrap content in a metric card style
    func metricCard() -> some View {
        self
            .padding(DSSpacing.xl)
            .background(DSColor.Surface.primary)
            .dsCornerRadius(DSRadius.lg)
            .dsElevation(.medium)
    }

    /// Wrap content in an insight card style
    func insightCard() -> some View {
        self
            .padding(DSSpacing.xl)
            .background(DSColor.Purple.purple100)
            .dsCornerRadius(DSRadius.xl)
    }
}
