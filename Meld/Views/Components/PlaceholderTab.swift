import SwiftUI

// MARK: - Placeholder Tab View
// Used for tabs not yet built (Coach, Trends, Meals, Profile).
// Shows the tab name and which cycle it's planned for.

struct PlaceholderTab: View {
    let title: String
    let subtitle: String

    var body: some View {
        VStack(spacing: DSSpacing.md) {
            Text(title)
                .font(DSTypography.h1)
                .foregroundStyle(DSColor.Text.primary)
            Text(subtitle)
                .font(DSTypography.bodySM)
                .foregroundStyle(DSColor.Text.tertiary)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(DSColor.Background.primary)
    }
}
