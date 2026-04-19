import SwiftUI

// MARK: - Meld Design System Colors
// Source of truth: Figma file SdHDNSLZVsCtYWs2NttWnj, Design System page
// All colors support light + dark mode via adaptive pairs.
// Defined programmatically for maintainability — no xcassets dependency.

enum DSColor {

    // MARK: - Background

    enum Background {
        /// Main app background
        static let primary = Color(light: .hex(0xFFFFFF), dark: .hex(0x121217))
        /// Card backgrounds, subtle sections
        static let secondary = Color(light: .hex(0xF7F7FA), dark: .hex(0x1C1C24))
        /// Dividers, inactive areas
        static let tertiary = Color(light: .hex(0xF2F2F5), dark: .hex(0x26262F))
    }

    // MARK: - Surface (Cards, elevated elements)

    enum Surface {
        /// Default card/sheet background
        static let primary = Color(light: .hex(0xFFFFFF), dark: .hex(0x1C1C24))
        /// Secondary card surfaces
        static let secondary = Color(light: .hex(0xF7F7FA), dark: .hex(0x26262F))
        /// Elevated elements (modals, popovers)
        static let elevated = Color(light: .hex(0xFFFFFF), dark: .hex(0x2A2A33))
    }

    // MARK: - Text

    enum Text {
        /// Headings, main body text
        static let primary = Color(light: .hex(0x121217), dark: .hex(0xF2F2F5))
        /// Subtitles, secondary info
        static let secondary = Color(light: .hex(0x666673), dark: .hex(0x9999A3))
        /// Captions, timestamps, labels
        /// Adjusted from Figma #9999A3 (2.8:1) to #737380 (4.5:1) for WCAG AA compliance
        static let tertiary = Color(light: .hex(0x737380), dark: .hex(0x8A8A96))
        /// Inactive text
        static let disabled = Color(light: .hex(0xC7C7CC), dark: .hex(0x444450))
        /// Text on purple backgrounds
        static let onPurple = Color.white
        /// Text on green backgrounds
        static let onGreen = Color.white
    }

    // MARK: - Purple (Primary Brand)

    enum Purple {
        static let purple600 = Color(light: .hex(0x5438A6), dark: .hex(0x6B52B8))
        static let purple500 = Color(light: .hex(0x6B52B8), dark: .hex(0x8C75CC))
        static let purple400 = Color(light: .hex(0x8C75CC), dark: .hex(0xB8A8E3))
        static let purple300 = Color(light: .hex(0xB8A8E3), dark: .hex(0x8C75CC))
        static let purple200 = Color(light: .hex(0xDED6F2), dark: .hex(0x3D2E6B))
        static let purple100 = Color(light: .hex(0xF2EDFC), dark: .hex(0x2A2249))
        static let purple50  = Color(light: .hex(0xFAF7FF), dark: .hex(0x1E1A33))
    }

    // MARK: - Green (Accent)

    enum Green {
        static let green600 = Color(light: .hex(0x178066), dark: .hex(0x219E80))
        static let green500 = Color(light: .hex(0x219E80), dark: .hex(0x33BA99))
        static let green400 = Color(light: .hex(0x33BA99), dark: .hex(0x73D4BA))
        static let green300 = Color(light: .hex(0x73D4BA), dark: .hex(0x33BA99))
        static let green200 = Color(light: .hex(0xBAEBDB), dark: .hex(0x1A3D33))
        static let green100 = Color(light: .hex(0xE5F7F0), dark: .hex(0x152E26))
    }

    // MARK: - Status

    enum Status {
        /// Positive trends, on-track indicators
        static let success = Color(light: .hex(0x219E80), dark: .hex(0x33BA99))
        /// Caution, needs attention
        static let warning = Color(light: .hex(0xE5A626), dark: .hex(0xF0B840))
        /// Negative trends, alerts
        static let error   = Color(light: .hex(0xD94040), dark: .hex(0xE55C5C))
        /// Informational
        static let info    = Color(light: .hex(0x4D80D9), dark: .hex(0x6B9AE8))
    }

    // MARK: - Glass (for glassmorphic effects)

    enum Glass {
        /// Stroke for glass cards
        static let stroke = Color(light: Color.white.opacity(0.25), dark: Color.white.opacity(0.12))
        /// Fill for glass overlays
        static let fill   = Color(light: Color.white.opacity(0.08), dark: Color.white.opacity(0.05))
    }

    // MARK: - Accessible Green for Text
    // Green 500 (#219E80) on white = 3.9:1 — fails WCAG AA for normal text.
    // Use green600 (#178066) for green text on light backgrounds = 5.5:1 — passes.
    // Green 500 is fine for: large text, icons, backgrounds, non-text decorative elements.

    enum Accessible {
        /// Green that passes WCAG AA for normal text on white/light backgrounds
        static let greenText = Color(light: .hex(0x178066), dark: .hex(0x33BA99))
    }

    // MARK: - Tab Bar

    enum TabBar {
        /// Active tab icon + label
        static let active = Purple.purple600
        /// Active state indicator (dot below label)
        static let indicator = Green.green500
        /// Inactive tab icon + label
        static let inactive = Text.tertiary
    }
}

// MARK: - Color Utilities

extension Color {

    /// Create a color from a hex integer (e.g., 0xFF5733)
    static func hex(_ hex: UInt, opacity: Double = 1.0) -> Color {
        Color(
            red: Double((hex >> 16) & 0xFF) / 255.0,
            green: Double((hex >> 8) & 0xFF) / 255.0,
            blue: Double(hex & 0xFF) / 255.0,
            opacity: opacity
        )
    }

    /// Create an adaptive color that resolves differently for light and dark mode
    init(light: Color, dark: Color) {
        self.init(uiColor: UIColor { traitCollection in
            switch traitCollection.userInterfaceStyle {
            case .dark:
                return UIColor(dark)
            default:
                return UIColor(light)
            }
        })
    }
}
