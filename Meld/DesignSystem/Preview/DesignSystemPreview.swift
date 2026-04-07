import SwiftUI

// MARK: - Design System Catalogue
// A scrollable preview of all design tokens and components.
// Open this view during development to QA tokens against Figma.

struct DesignSystemPreview: View {
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: DSSpacing.xxxl) {
                    colorSection
                    typographySection
                    spacingSection
                    cardSection
                    buttonSection
                    chipSection
                }
                .padding(DSSpacing.lg)
            }
            .background(DSColor.Background.primary)
            .navigationTitle("Design System")
        }
    }

    // MARK: - Colors

    private var colorSection: some View {
        VStack(alignment: .leading, spacing: DSSpacing.lg) {
            Text("Colors").font(DSTypography.h2).foregroundStyle(DSColor.Text.primary)

            Text("Purple").font(DSTypography.h3).foregroundStyle(DSColor.Text.secondary)
            HStack(spacing: DSSpacing.xs) {
                colorSwatch(DSColor.Purple.purple600, "600")
                colorSwatch(DSColor.Purple.purple500, "500")
                colorSwatch(DSColor.Purple.purple400, "400")
                colorSwatch(DSColor.Purple.purple300, "300")
                colorSwatch(DSColor.Purple.purple200, "200")
                colorSwatch(DSColor.Purple.purple100, "100")
                colorSwatch(DSColor.Purple.purple50, "50")
            }

            Text("Green").font(DSTypography.h3).foregroundStyle(DSColor.Text.secondary)
            HStack(spacing: DSSpacing.xs) {
                colorSwatch(DSColor.Green.green600, "600")
                colorSwatch(DSColor.Green.green500, "500")
                colorSwatch(DSColor.Green.green400, "400")
                colorSwatch(DSColor.Green.green300, "300")
                colorSwatch(DSColor.Green.green200, "200")
                colorSwatch(DSColor.Green.green100, "100")
            }

            Text("Status").font(DSTypography.h3).foregroundStyle(DSColor.Text.secondary)
            HStack(spacing: DSSpacing.xs) {
                colorSwatch(DSColor.Status.success, "Success")
                colorSwatch(DSColor.Status.warning, "Warning")
                colorSwatch(DSColor.Status.error, "Error")
                colorSwatch(DSColor.Status.info, "Info")
            }
        }
    }

    private func colorSwatch(_ color: Color, _ name: String) -> some View {
        VStack(spacing: DSSpacing.xxs) {
            RoundedRectangle(cornerRadius: DSRadius.sm, style: .continuous)
                .fill(color)
                .frame(width: 44, height: 44)
            Text(name)
                .font(DSTypography.caption)
                .foregroundStyle(DSColor.Text.tertiary)
        }
    }

    // MARK: - Typography

    private var typographySection: some View {
        VStack(alignment: .leading, spacing: DSSpacing.md) {
            Text("Typography").font(DSTypography.h2).foregroundStyle(DSColor.Text.primary)

            Text("Display 40/Thin").font(DSTypography.display).foregroundStyle(DSColor.Text.primary)
            Text("H1 28/Light").font(DSTypography.h1).foregroundStyle(DSColor.Text.primary)
            Text("H2 22/Regular").font(DSTypography.h2).foregroundStyle(DSColor.Text.primary)
            Text("H3 18/Medium").font(DSTypography.h3).foregroundStyle(DSColor.Text.primary)
            Text("87").font(DSTypography.metricXL).foregroundStyle(DSColor.Text.primary)
            Text("68 ms").font(DSTypography.metricLG).foregroundStyle(DSColor.Text.primary)
            Text("Body 16/Light — main text").font(DSTypography.body).foregroundStyle(DSColor.Text.primary)
            Text("Body SM 14/Regular").font(DSTypography.bodySM).foregroundStyle(DSColor.Text.secondary)
            Text("Caption 12/Regular").font(DSTypography.caption).foregroundStyle(DSColor.Text.tertiary)
            Text("HEART RATE").dsLabel().foregroundStyle(DSColor.Text.tertiary)
        }
    }

    // MARK: - Spacing

    private var spacingSection: some View {
        VStack(alignment: .leading, spacing: DSSpacing.md) {
            Text("Spacing").font(DSTypography.h2).foregroundStyle(DSColor.Text.primary)

            HStack(alignment: .bottom, spacing: DSSpacing.sm) {
                spacingBar(DSSpacing.xs, "xs\n4")
                spacingBar(DSSpacing.sm, "sm\n8")
                spacingBar(DSSpacing.md, "md\n12")
                spacingBar(DSSpacing.lg, "lg\n16")
                spacingBar(DSSpacing.xl, "xl\n20")
                spacingBar(DSSpacing.xxl, "xxl\n24")
                spacingBar(DSSpacing.xxxl, "xxxl\n32")
            }
        }
    }

    private func spacingBar(_ height: CGFloat, _ label: String) -> some View {
        VStack(spacing: DSSpacing.xxs) {
            RoundedRectangle(cornerRadius: DSRadius.xs, style: .continuous)
                .fill(DSColor.Purple.purple400)
                .frame(width: 32, height: height)
            Text(label)
                .font(DSTypography.caption)
                .foregroundStyle(DSColor.Text.tertiary)
                .multilineTextAlignment(.center)
        }
    }

    // MARK: - Cards

    private var cardSection: some View {
        VStack(alignment: .leading, spacing: DSSpacing.lg) {
            Text("Cards").font(DSTypography.h2).foregroundStyle(DSColor.Text.primary)

            DSCard(style: .metric) {
                VStack(alignment: .leading, spacing: DSSpacing.xs) {
                    Text("SLEEP EFFICIENCY").dsLabel().foregroundStyle(DSColor.Text.tertiary)
                    Text("91%").font(DSTypography.metricXL).foregroundStyle(DSColor.Text.primary)
                    Text("7h 12m total").font(DSTypography.caption).foregroundStyle(DSColor.Status.success)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }

            DSCard(style: .insight) {
                VStack(alignment: .leading, spacing: DSSpacing.sm) {
                    Text("Your Coach").font(DSTypography.bodySM).foregroundStyle(DSColor.Purple.purple500)
                    Text("Your HRV is 14% above baseline. Great recovery night.")
                        .font(DSTypography.body)
                        .foregroundStyle(DSColor.Text.primary)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
    }

    // MARK: - Buttons

    private var buttonSection: some View {
        VStack(alignment: .leading, spacing: DSSpacing.lg) {
            Text("Buttons").font(DSTypography.h2).foregroundStyle(DSColor.Text.primary)

            DSButton(title: "Primary Action", style: .primary) {}
            DSButton(title: "Secondary Action", style: .secondary) {}
            DSButton(title: "Ghost Action", style: .ghost) {}
        }
    }

    // MARK: - Chips

    private var chipSection: some View {
        VStack(alignment: .leading, spacing: DSSpacing.lg) {
            Text("Chips").font(DSTypography.h2).foregroundStyle(DSColor.Text.primary)

            DSChipRow(chips: [
                "How did my session go?",
                "Log dinner",
                "Recovery check"
            ])
        }
    }
}

#Preview("Light") {
    DesignSystemPreview()
        .preferredColorScheme(.light)
}

#Preview("Dark") {
    DesignSystemPreview()
        .preferredColorScheme(.dark)
}
