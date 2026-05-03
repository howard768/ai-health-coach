import SwiftUI

// MARK: - Meld Design System Spacing
// 4pt base grid with named tokens.
// Use these consistently instead of hardcoded values.

enum DSSpacing {

    /// 2pt, Icon-to-text micro gaps
    static let xxs: CGFloat = 2

    /// 4pt, Tight padding, minimal gaps
    static let xs: CGFloat = 4

    /// 8pt, Compact spacing, chip gaps
    static let sm: CGFloat = 8

    /// 12pt, Standard inner padding
    static let md: CGFloat = 12

    /// 16pt, Default padding (matches SwiftUI default)
    static let lg: CGFloat = 16

    /// 20pt, Card inner padding
    static let xl: CGFloat = 20

    /// 24pt, Section spacing
    static let xxl: CGFloat = 24

    /// 32pt, Large section gaps
    static let xxxl: CGFloat = 32

    /// 40pt, Screen-level top padding
    static let huge: CGFloat = 40

    /// 48pt, Hero spacing, display text areas
    static let max: CGFloat = 48
}

// MARK: - Padding Convenience Modifiers

extension View {

    /// Apply DS spacing as padding on all edges
    func dsPadding(_ spacing: CGFloat) -> some View {
        padding(spacing)
    }

    /// Apply DS spacing as horizontal padding
    func dsHPadding(_ spacing: CGFloat) -> some View {
        padding(.horizontal, spacing)
    }

    /// Apply DS spacing as vertical padding
    func dsVPadding(_ spacing: CGFloat) -> some View {
        padding(.vertical, spacing)
    }
}
