import SwiftUI

// MARK: - Meld Design System Button Component
// Enum-driven variants with consistent sizing and haptic feedback.

enum DSButtonStyle {
    /// Filled purple background, white text
    case primary
    /// Purple outline, purple text
    case secondary
    /// Text only, no background
    case ghost
    /// Pill-shaped action chip (used in coach chat)
    case chip
}

enum DSButtonSize {
    case sm
    case md
    case lg

    var verticalPadding: CGFloat {
        switch self {
        case .sm: DSSpacing.xs
        case .md: DSSpacing.sm
        case .lg: DSSpacing.md
        }
    }

    var horizontalPadding: CGFloat {
        switch self {
        case .sm: DSSpacing.sm
        case .md: DSSpacing.lg
        case .lg: DSSpacing.xl
        }
    }

    var font: Font {
        switch self {
        case .sm: DSTypography.caption
        case .md: DSTypography.bodySM
        case .lg: DSTypography.body
        }
    }
}

struct DSButton: View {
    let title: String
    let style: DSButtonStyle
    var size: DSButtonSize = .md
    var isLoading: Bool = false
    var isDisabled: Bool = false
    let action: () -> Void

    var body: some View {
        Button(action: {
            DSHaptic.medium()
            action()
        }) {
            Group {
                if isLoading {
                    ProgressView()
                        .tint(foregroundColor)
                } else {
                    Text(title)
                        .font(size.font)
                }
            }
            .frame(maxWidth: style == .chip ? nil : .infinity)
            .padding(.vertical, size.verticalPadding)
            .padding(.horizontal, size.horizontalPadding)
            .foregroundStyle(foregroundColor)
            .background(backgroundColor)
            .dsCornerRadius(cornerRadius)
            .overlay(borderOverlay)
        }
        .disabled(isDisabled || isLoading)
        .opacity(isDisabled ? 0.5 : 1.0)
    }

    // MARK: - Style Computed Properties

    private var foregroundColor: Color {
        switch style {
        case .primary: DSColor.Text.onPurple
        case .secondary: DSColor.Purple.purple500
        case .ghost: DSColor.Purple.purple500
        case .chip: DSColor.Green.green500
        }
    }

    private var backgroundColor: Color {
        switch style {
        case .primary: DSColor.Purple.purple500
        case .secondary: .clear
        case .ghost: .clear
        case .chip: .clear
        }
    }

    private var cornerRadius: CGFloat {
        switch style {
        case .chip: DSRadius.full
        default: DSRadius.sm
        }
    }

    @ViewBuilder
    private var borderOverlay: some View {
        switch style {
        case .secondary:
            RoundedRectangle(cornerRadius: DSRadius.sm, style: .continuous)
                .stroke(DSColor.Purple.purple300, lineWidth: 1)
        case .chip:
            Capsule()
                .stroke(DSColor.Text.disabled, lineWidth: 1)
        default:
            EmptyView()
        }
    }
}
