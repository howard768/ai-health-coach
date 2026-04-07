import SwiftUI

// MARK: - Metric Detail View
// Stub detail screen for when a metric card is tapped.
// Will follow the 4-level data philosophy from Vision doc:
// 1. What happened (hero value)
// 2. Is it good or bad (vs baseline)
// 3. What to do about it (coaching advice)
// 4. Why it happened (cross-domain, literature-grounded)

struct MetricDetailView: View {
    let metric: HealthMetric
    @Environment(\.dismiss) private var dismiss

    private var accentColor: Color {
        switch metric.trend {
        case .positive: DSColor.Green.green500
        case .neutral: DSColor.Text.secondary
        case .negative: DSColor.Status.error
        }
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: DSSpacing.xxl) {

                // MARK: Hero Metric
                VStack(alignment: .leading, spacing: DSSpacing.sm) {
                    Text(metric.label.uppercased())
                        .dsLabel()
                        .foregroundStyle(DSColor.Text.tertiary)

                    HStack(alignment: .firstTextBaseline, spacing: DSSpacing.xs) {
                        Text(metric.value)
                            .font(DSTypography.display)
                            .foregroundStyle(DSColor.Text.primary)

                        Text(metric.unit)
                            .font(DSTypography.h2)
                            .foregroundStyle(DSColor.Text.secondary)
                    }

                    Text(metric.subtitle)
                        .font(DSTypography.body)
                        .foregroundStyle(accentColor)
                }

                // MARK: Trend Visualization (stub)
                DSCard(style: .data) {
                    VStack(alignment: .leading, spacing: DSSpacing.md) {
                        Text("7-Day Trend")
                            .font(DSTypography.h3)
                            .foregroundStyle(DSColor.Text.primary)

                        // Placeholder for contextual data visualization
                        // Per Vision doc: NOT a lazy line chart
                        // Should encode meaning and action, not just plot points
                        RoundedRectangle(cornerRadius: DSRadius.md, style: .continuous)
                            .fill(DSColor.Surface.secondary)
                            .frame(height: 160)
                            .overlay(
                                Text("Contextual visualization coming in Cycle 1")
                                    .font(DSTypography.bodySM)
                                    .foregroundStyle(DSColor.Text.disabled)
                            )
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                }

                // MARK: AI Insight (stub)
                DSCard(style: .insight) {
                    VStack(alignment: .leading, spacing: DSSpacing.md) {
                        HStack(spacing: DSSpacing.sm) {
                            SquatBlobIcon(isActive: true, size: 24)

                            Text("Coach's Analysis")
                                .font(DSTypography.h3)
                                .foregroundStyle(DSColor.Purple.purple600)
                        }

                        Text("Detailed AI analysis of your \(metric.category.accessibilityName.lowercased()) will appear here. This will include cross-domain connections, literature references, and personalized recommendations.")
                            .font(DSTypography.body)
                            .foregroundStyle(DSColor.Text.primary)
                            .lineSpacing(4)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                }

                // MARK: Data Source
                HStack(spacing: DSSpacing.xs) {
                    Image(systemName: "circle.fill")
                        .font(.system(size: 6))
                        .foregroundStyle(DSColor.Green.green400)

                    Text("Source: Oura Ring")
                        .font(DSTypography.caption)
                        .foregroundStyle(DSColor.Text.disabled)
                }
            }
            .padding(.horizontal, DSSpacing.lg)
            .padding(.top, DSSpacing.md)
            .padding(.bottom, DSSpacing.xxxl)
        }
        .background(DSColor.Background.primary)
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .principal) {
                Text(metric.label)
                    .font(DSTypography.h3)
                    .foregroundStyle(DSColor.Text.primary)
            }
        }
    }
}

#Preview {
    NavigationStack {
        MetricDetailView(metric: HealthMetric(
            category: .sleepEfficiency,
            label: "Sleep Efficiency",
            value: "91",
            unit: "%",
            subtitle: "7h 12m total",
            trend: .positive
        ))
    }
}
