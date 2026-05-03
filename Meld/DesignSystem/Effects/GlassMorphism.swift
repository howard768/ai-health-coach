import SwiftUI

// MARK: - Glassmorphic Background Effect
// Frosted glass with weight, elegant but not flimsy.
// Uses .ultraThinMaterial + continuous corners + white-opacity stroke + soft shadow.
// Automatically adapts for dark mode via material system.

struct GlassBackground: ViewModifier {
    var radius: CGFloat = DSRadius.xl
    var strokeOpacity: Double? = nil
    @Environment(\.colorScheme) private var colorScheme

    private var resolvedStrokeOpacity: Double {
        strokeOpacity ?? (colorScheme == .dark ? 0.12 : 0.25)
    }

    func body(content: Content) -> some View {
        content
            .background(
                .ultraThinMaterial,
                in: RoundedRectangle(cornerRadius: radius, style: .continuous)
            )
            .overlay(
                RoundedRectangle(cornerRadius: radius, style: .continuous)
                    .stroke(
                        Color.white.opacity(resolvedStrokeOpacity),
                        lineWidth: 1
                    )
            )
            .shadow(
                color: colorScheme == .dark
                    ? .white.opacity(0.03)
                    : .black.opacity(0.06),
                radius: 8,
                x: 0,
                y: colorScheme == .dark ? 0 : 2
            )
    }
}

// MARK: - Glass Card Background (more opaque variant)

struct GlassCardBackground: ViewModifier {
    var radius: CGFloat = DSRadius.lg
    @Environment(\.colorScheme) private var colorScheme

    func body(content: Content) -> some View {
        content
            .background(
                .regularMaterial,
                in: RoundedRectangle(cornerRadius: radius, style: .continuous)
            )
            .overlay(
                RoundedRectangle(cornerRadius: radius, style: .continuous)
                    .stroke(
                        Color.white.opacity(colorScheme == .dark ? 0.08 : 0.2),
                        lineWidth: 0.5
                    )
            )
    }
}

// MARK: - View Extensions

extension View {
    /// Apply a glassmorphic background (frosted, stroked, shadowed)
    func glassBackground(radius: CGFloat = DSRadius.xl) -> some View {
        modifier(GlassBackground(radius: radius))
    }

    /// Apply a glass card background (more opaque, for content cards)
    func glassCard(radius: CGFloat = DSRadius.lg) -> some View {
        modifier(GlassCardBackground(radius: radius))
    }
}
