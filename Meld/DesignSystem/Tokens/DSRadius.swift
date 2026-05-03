import SwiftUI

// MARK: - Meld Design System Corner Radii
// All corners use .continuous style (iOS squircle curve).
// Follow the concentric radius rule: inner radius = outer radius - padding.

enum DSRadius {

    /// 4pt, Badges, tiny elements
    static let xs: CGFloat = 4

    /// 8pt, Chips, buttons
    static let sm: CGFloat = 8

    /// 12pt, Input fields, small cards
    static let md: CGFloat = 12

    /// 16pt, Metric cards (from Figma)
    static let lg: CGFloat = 16

    /// 20pt, Insight cards, large cards (from Figma)
    static let xl: CGFloat = 20

    /// 28pt, Modals, sheets
    static let xxl: CGFloat = 28

    /// Capsule, Pills, toggles, full rounding
    static let full: CGFloat = .infinity
}

// MARK: - Continuous Corner Radius Modifier

extension View {
    /// Apply a continuous corner radius (iOS squircle) with DS token
    func dsCornerRadius(_ radius: CGFloat) -> some View {
        clipShape(RoundedRectangle(cornerRadius: radius, style: .continuous))
    }
}

extension Shape where Self == RoundedRectangle {
    /// Create a squircle (continuous rounded rect) with a DS radius token
    static func dsRounded(_ radius: CGFloat) -> RoundedRectangle {
        RoundedRectangle(cornerRadius: radius, style: .continuous)
    }
}
