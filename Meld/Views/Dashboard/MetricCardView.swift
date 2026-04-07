import SwiftUI

// MARK: - Metric Card
// Reusable health metric display matching Figma spec.
// Tappable — navigates to metric detail screen.
// Accessible — VoiceOver reads category, value, unit, trend.
// Category icon top-right for scanability.
// Label (top-left) → Value + Unit (center) → Subtitle (bottom, colored by trend)

struct MetricCardView: View {
    let metric: HealthMetric

    private var subtitleColor: Color {
        switch metric.trend {
        case .positive: DSColor.Accessible.greenText
        case .neutral: DSColor.Text.tertiary
        case .negative: DSColor.Status.error
        }
    }

    var body: some View {
        DSCard(style: .metric) {
            VStack(alignment: .leading, spacing: DSSpacing.xs) {
                // Label + category icon
                HStack {
                    Text(metric.label.uppercased())
                        .dsLabel()
                        .foregroundStyle(DSColor.Text.tertiary)

                    Spacer()

                    // Category icon for scanability
                    Image(systemName: metric.category.iconName)
                        .font(.system(size: 12, weight: .medium))
                        .foregroundStyle(DSColor.Text.disabled)
                }

                // Value + Unit
                HStack(alignment: .firstTextBaseline, spacing: DSSpacing.xxs) {
                    Text(metric.value)
                        .font(DSTypography.metricXL)
                        .foregroundStyle(DSColor.Text.primary)

                    Text(metric.unit)
                        .font(DSTypography.bodySM)
                        .foregroundStyle(DSColor.Text.secondary)
                }

                // Subtitle with trend
                Text(metric.subtitle)
                    .font(DSTypography.caption)
                    .foregroundStyle(subtitleColor)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        // MARK: Accessibility
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(accessibilityLabel)
        .accessibilityHint("Double-tap for details")
        .accessibilityAddTraits(.isButton)
    }

    // MARK: - Accessibility

    private var accessibilityLabel: String {
        "\(metric.category.accessibilityName): \(metric.value) \(metric.unit). \(metric.subtitle). \(metric.trend.accessibilityLabel)."
    }
}

#Preview {
    LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: DSSpacing.md) {
        MetricCardView(metric: HealthMetric(
            category: .sleepEfficiency,
            label: "Sleep Efficiency",
            value: "91",
            unit: "%",
            subtitle: "7h 12m total",
            trend: .positive
        ))
        MetricCardView(metric: HealthMetric(
            category: .hrv,
            label: "HRV Status",
            value: "68",
            unit: "ms",
            subtitle: "\u{2191} 14% vs baseline",
            trend: .positive
        ))
    }
    .padding()
    .background(DSColor.Background.primary)
}
