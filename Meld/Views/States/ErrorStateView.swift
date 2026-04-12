import SwiftUI

// MARK: - Error State Views
// Two structural patterns:
// 1. Full-screen error (when nothing can load — mascot concerned)
// 2. Inline error banner (when one section fails)
// All copy at 4th grade reading level.

// MARK: - Full-Screen Error

struct FullScreenError: View {
    let title: String
    let message: String
    var retryTitle: String = "Try again"
    var onRetry: (() -> Void)? = nil

    var body: some View {
        VStack(spacing: DSSpacing.xxl) {
            Spacer()

            MeldMascot(state: .concerned, size: 64)

            VStack(spacing: DSSpacing.sm) {
                Text(title)
                    .font(DSTypography.h2)
                    .foregroundStyle(DSColor.Text.primary)
                    .multilineTextAlignment(.center)

                Text(message)
                    .font(DSTypography.body)
                    .foregroundStyle(DSColor.Text.secondary)
                    .multilineTextAlignment(.center)
                    .lineSpacing(4)
            }
            .padding(.horizontal, DSSpacing.xxxl)

            if let onRetry {
                DSButton(title: retryTitle, style: .primary, size: .lg, action: onRetry)
                    .padding(.horizontal, DSSpacing.huge)
            }

            Spacer()
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(DSColor.Background.primary)
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(title). \(message)")
    }
}

// MARK: - Inline Error Banner

struct InlineErrorBanner: View {
    let message: String
    var style: BannerStyle = .error
    var actionTitle: String? = nil
    var onAction: (() -> Void)? = nil
    var onDismiss: (() -> Void)? = nil

    enum BannerStyle {
        case error, warning, info

        var backgroundColor: Color {
            switch self {
            case .error: Color.hex(0xFDE8E8) // Light red
            case .warning: Color.hex(0xFFF3D6) // Light amber
            case .info: DSColor.Purple.purple50
            }
        }

        var iconColor: Color {
            switch self {
            case .error: DSColor.Status.error
            case .warning: DSColor.Status.warning
            case .info: DSColor.Status.info
            }
        }

        var iconName: String {
            switch self {
            case .error: "exclamationmark.circle.fill"
            case .warning: "exclamationmark.triangle.fill"
            case .info: "info.circle.fill"
            }
        }
    }

    var body: some View {
        HStack(spacing: DSSpacing.md) {
            Image(systemName: style.iconName)
                .font(.system(size: 18))
                .foregroundStyle(style.iconColor)

            VStack(alignment: .leading, spacing: DSSpacing.xxs) {
                Text(message)
                    .font(DSTypography.bodySM)
                    .foregroundStyle(DSColor.Text.primary)
                    .lineSpacing(2)

                if let actionTitle, let onAction {
                    Button(action: onAction) {
                        Text(actionTitle)
                            .font(DSTypography.bodySM)
                            .foregroundStyle(DSColor.Accessible.greenText)
                    }
                }
            }

            Spacer()

            if let onDismiss {
                Button(action: onDismiss) {
                    Image(systemName: "xmark")
                        .font(.system(size: 12, weight: .semibold))
                        .foregroundStyle(DSColor.Text.tertiary)
                        .frame(width: 28, height: 28)
                }
            }
        }
        .padding(DSSpacing.lg)
        .background(style.backgroundColor)
        .dsCornerRadius(DSRadius.md)
        .accessibilityElement(children: .combine)
        .accessibilityLabel(message)
    }
}

// MARK: - Predefined Error States

extension FullScreenError {
    /// Network failure — no connection
    static func networkError(onRetry: @escaping () -> Void) -> FullScreenError {
        FullScreenError(
            title: "Can't connect",
            message: "Check your internet and try again.",
            onRetry: onRetry
        )
    }

    /// API error — server issue
    static func serverError(onRetry: @escaping () -> Void) -> FullScreenError {
        FullScreenError(
            title: "Something went wrong",
            message: "We're fixing it. Try again in a bit.",
            onRetry: onRetry
        )
    }

    /// Permission denied — HealthKit
    static func permissionDenied() -> FullScreenError {
        FullScreenError(
            title: "We need access",
            message: "Open Settings to let Meld read your health data.",
            retryTitle: "Open Settings"
        )
    }
}

extension InlineErrorBanner {
    /// Sync failed — inline
    static func syncFailed(onRetry: @escaping () -> Void) -> InlineErrorBanner {
        InlineErrorBanner(
            message: "Sync failed. Your data may be old.",
            style: .warning,
            actionTitle: "Try again",
            onAction: onRetry
        )
    }

    /// Stale data — informational
    static func staleData() -> InlineErrorBanner {
        InlineErrorBanner(
            message: "Data hasn't been updated in a while.",
            style: .info
        )
    }
}

// MARK: - Previews

#Preview("Full Screen - Network") {
    FullScreenError.networkError(onRetry: {})
}

#Preview("Full Screen - Server") {
    FullScreenError.serverError(onRetry: {})
}

#Preview("Full Screen - Permission") {
    FullScreenError.permissionDenied()
}

#Preview("Inline Banners") {
    VStack(spacing: DSSpacing.lg) {
        InlineErrorBanner.syncFailed(onRetry: {})
        InlineErrorBanner.staleData()
        InlineErrorBanner(message: "New feature available!", style: .info, onDismiss: {})
    }
    .padding()
}
