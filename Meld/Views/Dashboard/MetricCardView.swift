import SwiftUI

// MARK: - Metric Card
// Reusable health metric display matching Figma spec.
// Label (top) → Value + Unit (center) → Subtitle (bottom, colored by trend)

struct MetricCardView: View {
    let metric: HealthMetric

    private var subtitleColor: Color {
        switch metric.trend {
        case .positive: DSColor.Status.success
        case .neutral: DSColor.Text.tertiary
        case .negative: DSColor.Status.error
        }
    }

    var body: some View {
        DSCard(style: .metric) {
            VStack(alignment: .leading, spacing: DSSpacing.xs) {
                // Label
                Text(metric.label.uppercased())
                    .dsLabel()
                    .foregroundStyle(DSColor.Text.tertiary)

                // Value + Unit
                HStack(alignment: .firstTextBaseline, spacing: DSSpacing.xxs) {
                    Text(metric.value)
                        .font(DSTypography.metricXL)
                        .foregroundStyle(DSColor.Text.primary)

                    Text(metric.unit)
                        .font(DSTypography.bodySM)
                        .foregroundStyle(DSColor.Text.secondary)
                }

                // Subtitle
                Text(metric.subtitle)
                    .font(DSTypography.caption)
                    .foregroundStyle(subtitleColor)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }
}

#Preview {
    HStack(spacing: DSSpacing.md) {
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
