import SwiftUI

// MARK: - Meld Design System Icon Component
// Wrapper for custom icons with consistent sizing and tinting.
// Icons should be PDF vectors in Assets.xcassets with "Preserve Vector Data" enabled
// and "Render As: Template Image" for tintability.
//
// For now, uses SF Symbols as development placeholders only.
// These will be replaced with custom Figma-exported icons.

enum DSIconSize {
    case sm   // 16pt
    case md   // 24pt
    case lg   // 32pt
    case xl   // 48pt

    var points: CGFloat {
        switch self {
        case .sm: 16
        case .md: 24
        case .lg: 32
        case .xl: 48
        }
    }
}

struct DSIcon: View {
    let systemName: String  // Temporary: will be replaced with custom icon names
    var size: DSIconSize = .md
    var color: Color = DSColor.Text.primary

    var body: some View {
        Image(systemName: systemName)
            .font(.system(size: size.points * 0.6))
            .frame(width: size.points, height: size.points)
            .foregroundStyle(color)
    }
}

// MARK: - Custom Icon (for when Figma assets are exported)

struct DSCustomIcon: View {
    let name: String
    var size: DSIconSize = .md
    var color: Color = DSColor.Text.primary

    var body: some View {
        Image(name)
            .renderingMode(.template)
            .resizable()
            .aspectRatio(contentMode: .fit)
            .frame(width: size.points, height: size.points)
            .foregroundStyle(color)
    }
}
