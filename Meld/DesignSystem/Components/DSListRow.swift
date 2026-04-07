import SwiftUI

// MARK: - Meld Design System List Row, Divider, Toggle
// Standard patterns for Settings, Data Sources, and list-based screens.
// All use DS tokens. No hardcoded values.

// MARK: - List Row

struct DSListRow<Leading: View, Trailing: View>: View {
    let title: String
    var subtitle: String? = nil
    @ViewBuilder var leading: () -> Leading
    @ViewBuilder var trailing: () -> Trailing

    var body: some View {
        HStack(spacing: DSSpacing.md) {
            // Leading icon/image
            leading()
                .frame(width: 32, height: 32)

            // Text
            VStack(alignment: .leading, spacing: DSSpacing.xxs) {
                Text(title)
                    .font(DSTypography.body)
                    .foregroundStyle(DSColor.Text.primary)

                if let subtitle {
                    Text(subtitle)
                        .font(DSTypography.caption)
                        .foregroundStyle(DSColor.Text.tertiary)
                }
            }

            Spacer()

            // Trailing accessory
            trailing()
        }
        .padding(.vertical, DSSpacing.md)
        .padding(.horizontal, DSSpacing.lg)
        .contentShape(Rectangle())
        .accessibilityElement(children: .combine)
    }
}

// MARK: - Convenience initializers

extension DSListRow where Leading == EmptyView {
    init(
        title: String,
        subtitle: String? = nil,
        @ViewBuilder trailing: @escaping () -> Trailing
    ) {
        self.title = title
        self.subtitle = subtitle
        self.leading = { EmptyView() }
        self.trailing = trailing
    }
}

extension DSListRow where Trailing == DSListChevron {
    init(
        title: String,
        subtitle: String? = nil,
        @ViewBuilder leading: @escaping () -> Leading
    ) {
        self.title = title
        self.subtitle = subtitle
        self.leading = leading
        self.trailing = { DSListChevron() }
    }
}

// MARK: - List Chevron (trailing arrow)

struct DSListChevron: View {
    var body: some View {
        Image(systemName: "chevron.right")
            .font(.system(size: 13, weight: .semibold))
            .foregroundStyle(DSColor.Text.disabled)
    }
}

// MARK: - List Status Dot (connection status indicator)

struct DSListStatusDot: View {
    let isConnected: Bool

    var body: some View {
        Circle()
            .fill(isConnected ? DSColor.Status.success : DSColor.Text.disabled)
            .frame(width: 8, height: 8)
            .accessibilityLabel(isConnected ? "Connected" : "Disconnected")
    }
}

// MARK: - Divider

struct DSDivider: View {
    var inset: CGFloat = DSSpacing.lg

    var body: some View {
        Rectangle()
            .fill(DSColor.Background.tertiary)
            .frame(height: 1)
            .padding(.leading, inset)
    }
}

// MARK: - Toggle (styled)

struct DSToggle: View {
    let title: String
    @Binding var isOn: Bool
    var subtitle: String? = nil

    var body: some View {
        HStack(spacing: DSSpacing.md) {
            VStack(alignment: .leading, spacing: DSSpacing.xxs) {
                Text(title)
                    .font(DSTypography.body)
                    .foregroundStyle(DSColor.Text.primary)

                if let subtitle {
                    Text(subtitle)
                        .font(DSTypography.caption)
                        .foregroundStyle(DSColor.Text.tertiary)
                }
            }

            Spacer()

            Toggle("", isOn: $isOn)
                .tint(DSColor.Green.green500)
                .labelsHidden()
                .onChange(of: isOn) { _, _ in
                    DSHaptic.selection()
                }
        }
        .padding(.vertical, DSSpacing.md)
        .padding(.horizontal, DSSpacing.lg)
    }
}

// MARK: - Section Header

struct DSSectionHeader: View {
    let title: String

    var body: some View {
        Text(title.uppercased())
            .dsLabel()
            .foregroundStyle(DSColor.Text.tertiary)
            .padding(.horizontal, DSSpacing.lg)
            .padding(.top, DSSpacing.xxl)
            .padding(.bottom, DSSpacing.sm)
            .accessibilityAddTraits(.isHeader)
    }
}

// MARK: - Previews

#Preview("List Components") {
    VStack(spacing: 0) {
        DSSectionHeader(title: "Connected Sources")

        DSListRow(title: "Oura Ring", subtitle: "Last synced 2 min ago", leading: {
            Image(systemName: "circle.hexagongrid.fill")
                .foregroundStyle(DSColor.Green.green500)
        }, trailing: {
            DSListChevron()
        })

        DSDivider()

        DSListRow(title: "Eight Sleep", subtitle: "Not connected", leading: {
            Image(systemName: "bed.double.fill")
                .foregroundStyle(DSColor.Text.disabled)
        }, trailing: {
            DSListStatusDot(isConnected: false)
        })

        DSDivider()

        DSToggle(title: "Push Notifications", isOn: .constant(true), subtitle: "Get proactive coaching alerts")

        DSDivider()

        DSToggle(title: "Dark Mode", isOn: .constant(false))
    }
    .background(DSColor.Surface.primary)
}
