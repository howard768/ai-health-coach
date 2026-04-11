import SwiftUI

// MARK: - Meld Design System Typography
// Font: Roboto (5 weights: Thin, Light, Regular, Medium, Bold)
// All fonts registered in Info.plist under UIAppFonts.
// Uses `relativeTo:` for Dynamic Type accessibility scaling.

enum DSTypography {

    // MARK: - Font Names (must match filename minus .ttf)

    private enum FontName {
        static let thin = "Roboto-Thin"
        static let light = "Roboto-Light"
        static let regular = "Roboto-Regular"
        static let medium = "Roboto-Medium"
        static let bold = "Roboto-Bold"
    }

    // MARK: - Type Scale

    /// Hero text, taglines — 40pt Thin
    static let display = Font.custom(FontName.thin, size: 40, relativeTo: .largeTitle)

    /// Screen greeting — 28pt Light
    static let h1 = Font.custom(FontName.light, size: 28, relativeTo: .title)

    /// Section headers — 22pt Regular
    static let h2 = Font.custom(FontName.regular, size: 22, relativeTo: .title2)

    /// Card titles — 18pt Medium
    static let h3 = Font.custom(FontName.medium, size: 18, relativeTo: .title3)

    /// Large score numbers — 48pt Thin
    static let metricXL = Font.custom(FontName.thin, size: 48, relativeTo: .largeTitle)

    /// Secondary metrics — 32pt Light
    static let metricLG = Font.custom(FontName.light, size: 32, relativeTo: .title)

    /// Main body text — 16pt Light
    static let body = Font.custom(FontName.light, size: 16, relativeTo: .body)

    /// Supporting text — 14pt Regular
    static let bodySM = Font.custom(FontName.regular, size: 14, relativeTo: .subheadline)

    /// Timestamps, sources — 12pt Regular
    static let caption = Font.custom(FontName.regular, size: 12, relativeTo: .caption)

    /// Category labels — 11pt Medium, uppercase
    static let label = Font.custom(FontName.medium, size: 11, relativeTo: .caption2)

    /// Emphasis text — 16pt Medium
    static let bodyEmphasis = Font.custom(FontName.medium, size: 16, relativeTo: .body)

    /// Bold emphasis — 16pt Bold
    static let bodyBold = Font.custom(FontName.bold, size: 16, relativeTo: .body)
}

// MARK: - Label Style Modifier (uppercase + tracking)

struct DSLabelStyle: ViewModifier {
    func body(content: Content) -> some View {
        content
            .font(DSTypography.label)
            .tracking(0.8)
            .textCase(.uppercase)
    }
}

extension View {
    /// Apply the DS label style (11pt Medium, uppercase, tracked)
    func dsLabel() -> some View {
        modifier(DSLabelStyle())
    }
}

// MARK: - Font Registration Check (debug helper)

#if DEBUG
enum DSFontDebug {
    /// Print all available Roboto fonts to console. Call once on app launch to verify registration.
    static func verifyFonts() {
        let robotoFonts = UIFont.familyNames
            .filter { $0.lowercased().contains("roboto") }
            .flatMap { UIFont.fontNames(forFamilyName: $0) }

        if robotoFonts.isEmpty {
            Log.designSystem.warning("No Roboto fonts found. Check Info.plist UIAppFonts entries.")
        } else {
            Log.designSystem.info("Roboto fonts registered: \(robotoFonts.joined(separator: ", "))")
        }
    }
}
#endif
