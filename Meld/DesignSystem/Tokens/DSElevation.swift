import SwiftUI

// MARK: - Meld Design System Elevation / Shadows
// Light mode: standard drop shadows with varying intensity.
// Dark mode: subtle border glows instead of shadows (shadows don't read on dark backgrounds).
// The Figma metric card shadow (0px 2px 16px rgba(0,0,0,0.06)) maps to .medium.

enum DSElevation {
    case none
    case low
    case medium
    case high
    case modal
}

// MARK: - Elevation View Modifier

struct DSElevationModifier: ViewModifier {
    let level: DSElevation
    @Environment(\.colorScheme) private var colorScheme

    func body(content: Content) -> some View {
        if colorScheme == .dark {
            content.darkElevation(level)
        } else {
            content.lightElevation(level)
        }
    }
}

// MARK: - Light Mode Shadows

private extension View {
    @ViewBuilder
    func lightElevation(_ level: DSElevation) -> some View {
        switch level {
        case .none:
            self
        case .low:
            self.shadow(color: .black.opacity(0.04), radius: 2, x: 0, y: 1)
        case .medium:
            self.shadow(color: .black.opacity(0.06), radius: 8, x: 0, y: 2)
        case .high:
            self.shadow(color: .black.opacity(0.10), radius: 12, x: 0, y: 8)
        case .modal:
            self.shadow(color: .black.opacity(0.16), radius: 24, x: 0, y: 16)
        }
    }
}

// MARK: - Dark Mode Elevation (border glow instead of shadow)

private extension View {
    @ViewBuilder
    func darkElevation(_ level: DSElevation) -> some View {
        switch level {
        case .none:
            self
        case .low:
            self.overlay(
                RoundedRectangle(cornerRadius: DSRadius.lg, style: .continuous)
                    .stroke(Color.white.opacity(0.04), lineWidth: 1)
            )
        case .medium:
            self.overlay(
                RoundedRectangle(cornerRadius: DSRadius.lg, style: .continuous)
                    .stroke(Color.white.opacity(0.08), lineWidth: 1)
            )
        case .high:
            self.overlay(
                RoundedRectangle(cornerRadius: DSRadius.lg, style: .continuous)
                    .stroke(Color.white.opacity(0.10), lineWidth: 1)
            )
            .shadow(color: .white.opacity(0.03), radius: 8, x: 0, y: 0)
        case .modal:
            self.overlay(
                RoundedRectangle(cornerRadius: DSRadius.xxl, style: .continuous)
                    .stroke(Color.white.opacity(0.12), lineWidth: 1)
            )
            .shadow(color: .white.opacity(0.05), radius: 16, x: 0, y: 0)
        }
    }
}

// MARK: - View Extension

extension View {
    /// Apply design system elevation (adaptive light/dark)
    func dsElevation(_ level: DSElevation) -> some View {
        modifier(DSElevationModifier(level: level))
    }
}
