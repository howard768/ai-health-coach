import SwiftUI

// MARK: - Metric Card (Compact Dashboard)
// Each metric type gets a mini visualization matching its detail view:
// - Sleep → mini arc gauge
// - HRV → mini range band
// - Resting HR → mini range band (inverted)
// - Consistency → mini dot array
//
// Research: gauges and visual analogies outperform numbers alone
// (83% comprehension, PMC7309237). Even at compact card size,
// the visualization adds instant meaning.

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
            VStack(alignment: .leading, spacing: DSSpacing.sm) {
                // Label
                Text(metric.label.uppercased())
                    .dsLabel()
                    .foregroundStyle(DSColor.Text.tertiary)

                // Mini visualization per metric type
                miniVisualization

                // Subtitle with trend
                Text(metric.subtitle)
                    .font(DSTypography.caption)
                    .foregroundStyle(subtitleColor)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(accessibilityLabel)
        .accessibilityHint("Double-tap for details")
        .accessibilityAddTraits(.isButton)
    }

    // MARK: - Mini Visualization (per metric type)

    @ViewBuilder
    private var miniVisualization: some View {
        switch metric.category {
        case .sleepEfficiency:
            // Mini arc gauge — compact version
            HStack(alignment: .bottom, spacing: DSSpacing.sm) {
                // Value
                HStack(alignment: .firstTextBaseline, spacing: DSSpacing.xxs) {
                    Text(metric.value)
                        .font(DSTypography.metricLG)
                        .foregroundStyle(DSColor.Text.primary)
                    Text(metric.unit)
                        .font(DSTypography.caption)
                        .foregroundStyle(DSColor.Text.secondary)
                }

                Spacer()

                // Mini arc gauge (48pt wide)
                ArcGaugeMini(value: (Double(metric.value) ?? 0) / 100.0)
                    .frame(width: 48, height: 28)
            }

        case .hrv:
            // Value + mini range band
            VStack(alignment: .leading, spacing: DSSpacing.xs) {
                HStack(alignment: .firstTextBaseline, spacing: DSSpacing.xxs) {
                    Text(metric.value)
                        .font(DSTypography.metricLG)
                        .foregroundStyle(DSColor.Text.primary)
                    Text(metric.unit)
                        .font(DSTypography.caption)
                        .foregroundStyle(DSColor.Text.secondary)
                }

                // Mini range band
                RangeBandMini(normalizedPosition: 0.72) // 68ms in 42-78 range
            }

        case .restingHR:
            // Value + mini range band (inverted)
            VStack(alignment: .leading, spacing: DSSpacing.xs) {
                HStack(alignment: .firstTextBaseline, spacing: DSSpacing.xxs) {
                    Text(metric.value)
                        .font(DSTypography.metricLG)
                        .foregroundStyle(DSColor.Text.primary)
                    Text(metric.unit)
                        .font(DSTypography.caption)
                        .foregroundStyle(DSColor.Text.secondary)
                }

                // Mini range band
                RangeBandMini(normalizedPosition: 0.3) // 58bpm in 52-72 range (lower = better)
            }

        case .consistency:
            // Mini dot array (7 dots + fraction)
            VStack(alignment: .leading, spacing: DSSpacing.xs) {
                HStack(alignment: .firstTextBaseline, spacing: DSSpacing.xxs) {
                    Text(metric.value)
                        .font(DSTypography.metricLG)
                        .foregroundStyle(DSColor.Text.primary)
                    Text(metric.unit)
                        .font(DSTypography.caption)
                        .foregroundStyle(DSColor.Text.secondary)
                }

                // Mini 7-dot strip
                DotArrayMini(trainedDays: 5, totalDays: 7)
            }
        }
    }

    private var accessibilityLabel: String {
        "\(metric.category.accessibilityName): \(metric.value) \(metric.unit). \(metric.subtitle). \(metric.trend.accessibilityLabel)."
    }
}

// MARK: - Mini Arc Gauge (compact, no labels)

private struct ArcGaugeMini: View {
    let value: Double // 0-1

    var body: some View {
        Canvas { context, size in
            let w = size.width
            let h = size.height
            let radius = min(w, h * 1.6) / 2 - 3
            let center = CGPoint(x: w / 2, y: h)
            let strokeW: CGFloat = 4

            // Background track
            var track = Path()
            track.addArc(center: center, radius: radius, startAngle: .degrees(180), endAngle: .degrees(0), clockwise: false)
            context.stroke(track, with: .color(DSColor.Surface.secondary), style: StrokeStyle(lineWidth: strokeW, lineCap: .round))

            // Fill arc
            let fillColor: Color = value >= 0.85 ? DSColor.Status.success : value >= 0.74 ? DSColor.Status.warning : DSColor.Status.error
            var fill = Path()
            fill.addArc(center: center, radius: radius, startAngle: .degrees(180), endAngle: .degrees(180 + value * 180), clockwise: false)
            context.stroke(fill, with: .color(fillColor), style: StrokeStyle(lineWidth: strokeW, lineCap: .round))
        }
    }
}

// MARK: - Mini Range Band (compact horizontal bar)

private struct RangeBandMini: View {
    let normalizedPosition: CGFloat // 0-1

    var body: some View {
        GeometryReader { geo in
            ZStack(alignment: .leading) {
                // Track
                Capsule()
                    .fill(DSColor.Surface.secondary)
                    .frame(height: 6)

                // Gradient fill
                Capsule()
                    .fill(
                        LinearGradient(
                            colors: [DSColor.Purple.purple200, DSColor.Purple.purple500],
                            startPoint: .leading,
                            endPoint: .trailing
                        )
                    )
                    .frame(height: 6)

                // Position marker
                Circle()
                    .fill(DSColor.Text.primary)
                    .frame(width: 8, height: 8)
                    .offset(x: normalizedPosition * (geo.size.width - 8))
            }
        }
        .frame(height: 8)
    }
}

// MARK: - Mini Dot Array (compact 7 dots)

private struct DotArrayMini: View {
    let trainedDays: Int
    let totalDays: Int

    var body: some View {
        HStack(spacing: 4) {
            ForEach(0..<totalDays, id: \.self) { day in
                Circle()
                    .fill(day < trainedDays ? DSColor.Green.green500 : DSColor.Text.disabled.opacity(0.4))
                    .frame(width: 8, height: 8)
            }
        }
    }
}

// MARK: - Previews

#Preview("All Cards") {
    LazyVGrid(columns: [GridItem(.flexible(), spacing: 12), GridItem(.flexible())], spacing: 12) {
        MetricCardView(metric: HealthMetric(
            category: .sleepEfficiency, label: "Sleep Efficiency",
            value: "91", unit: "%", subtitle: "7h 12m total", trend: .positive
        ))
        MetricCardView(metric: HealthMetric(
            category: .hrv, label: "HRV Status",
            value: "68", unit: "ms", subtitle: "↑ 14% vs baseline", trend: .positive
        ))
        MetricCardView(metric: HealthMetric(
            category: .restingHR, label: "Resting HR",
            value: "58", unit: "bpm", subtitle: "Stable this week", trend: .neutral
        ))
        MetricCardView(metric: HealthMetric(
            category: .consistency, label: "Consistency",
            value: "5/7", unit: "days", subtitle: "On track this week", trend: .positive
        ))
    }
    .padding()
    .background(DSColor.Background.primary)
}
