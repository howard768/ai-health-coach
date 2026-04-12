import SwiftUI

// MARK: - Meld Design System Avatar
// Circular container for user photos, mascot icons, or initials.
// Four sizes matching the design grid.
// Supports: image, initials fallback, mascot variant.

enum DSAvatarSize {
    case sm   // 24pt — inline with text
    case md   // 32pt — chat messages, lists
    case lg   // 48pt — profile header compact
    case xl   // 64pt — profile hero, onboarding

    var points: CGFloat {
        switch self {
        case .sm: 24
        case .md: 32
        case .lg: 48
        case .xl: 64
        }
    }

    var fontSize: CGFloat {
        switch self {
        case .sm: 10
        case .md: 13
        case .lg: 20
        case .xl: 26
        }
    }
}

struct DSAvatar: View {
    let size: DSAvatarSize
    var image: Image? = nil
    var initials: String? = nil
    var backgroundColor: Color = DSColor.Purple.purple100
    var foregroundColor: Color = DSColor.Purple.purple500

    var body: some View {
        Group {
            if let image {
                image
                    .resizable()
                    .aspectRatio(contentMode: .fill)
            } else if let initials {
                Text(initials.prefix(2).uppercased())
                    .font(.system(size: size.fontSize, weight: .medium, design: .rounded))
                    .foregroundStyle(foregroundColor)
            } else {
                // Fallback: person icon
                Image(systemName: "person.fill")
                    .font(.system(size: size.fontSize))
                    .foregroundStyle(foregroundColor)
            }
        }
        .frame(width: size.points, height: size.points)
        .background(backgroundColor)
        .clipShape(Circle())
        .accessibilityHidden(true) // Decorative — parent provides label
    }
}

// MARK: - Mascot Avatar Variant

struct DSMascotAvatar: View {
    let size: DSAvatarSize

    var body: some View {
        MeldMascot(state: .idle, size: size.points * 0.75)
            .frame(width: size.points, height: size.points)
            .background(Color.hex(0xFAF0DA)) // Warm amber tint background for mascot
            .clipShape(Circle())
            .accessibilityLabel("Coach mascot")
    }
}

// MARK: - Previews

#Preview("All Sizes") {
    VStack(spacing: DSSpacing.lg) {
        HStack(spacing: DSSpacing.md) {
            DSAvatar(size: .sm, initials: "BH")
            DSAvatar(size: .md, initials: "BH")
            DSAvatar(size: .lg, initials: "BH")
            DSAvatar(size: .xl, initials: "BH")
        }
        HStack(spacing: DSSpacing.md) {
            DSAvatar(size: .sm)
            DSAvatar(size: .md)
            DSAvatar(size: .lg)
            DSAvatar(size: .xl)
        }
        HStack(spacing: DSSpacing.md) {
            DSMascotAvatar(size: .sm)
            DSMascotAvatar(size: .md)
            DSMascotAvatar(size: .lg)
            DSMascotAvatar(size: .xl)
        }
    }
    .padding()
}
