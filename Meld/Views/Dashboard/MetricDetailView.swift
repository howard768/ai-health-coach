import SwiftUI

// MARK: - Metric Detail View
// Full detail screen with research-based visualizations.
// 4-level data philosophy:
// 1. What happened (hero visualization)
// 2. Is it good or bad (zone/range context)
// 3. What to do about it (coaching advice)
// 4. Why it happened (cross-domain, literature-grounded)
//
// Each metric type gets its own visualization:
// - Sleep → ArcGauge
// - HRV → RangeBand + AreaSparkline
// - Resting HR → RangeBand (inverted) + AreaSparkline
// - Consistency → DotArray + CalendarHeatmap

struct MetricDetailView: View {
    let metric: HealthMetric
    private let M: CGFloat = 20

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: DSSpacing.xxl) {
                // Level 1 & 2: Hero visualization with context
                heroVisualization

                // 7-day trend (sparkline)
                trendSection

                // Level 3: Coach's analysis
                coachAnalysis

                // Level 4: Cross-domain insight (stub)
                crossDomainInsight

                // Data source
                sourceAttribution
            }
            .padding(.horizontal, M)
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

    // MARK: - Hero Visualization (per metric type)

    @ViewBuilder
    private var heroVisualization: some View {
        switch metric.category {
        case .sleepEfficiency:
            DSCard(style: .metric) {
                ArcGauge(
                    value: Double(metric.value) ?? 0 / 100.0,
                    displayValue: metric.value,
                    unit: metric.unit,
                    label: "SLEEP EFFICIENCY",
                    subtitle: metric.subtitle
                )
            }

        case .hrv:
            DSCard(style: .metric) {
                RangeBand(
                    currentValue: Double(metric.value) ?? 68,
                    personalMin: 42,
                    personalMax: 82,
                    personalAverage: 58,
                    displayValue: metric.value,
                    unit: metric.unit,
                    label: "HRV",
                    higherIsBetter: true
                )
            }

        case .restingHR:
            DSCard(style: .metric) {
                RangeBand(
                    currentValue: Double(metric.value) ?? 58,
                    personalMin: 52,
                    personalMax: 72,
                    personalAverage: 62,
                    displayValue: metric.value,
                    unit: metric.unit,
                    label: "RESTING HR",
                    higherIsBetter: false
                )
            }

        case .consistency:
            DSCard(style: .metric) {
                DotArray(
                    trainedDays: [0, 1, 2, 3, 4],
                    todayIndex: 5,
                    target: 5
                )
            }
        }
    }

    // MARK: - 7-Day Trend

    private var trendSection: some View {
        DSCard(style: .data) {
            VStack(alignment: .leading, spacing: DSSpacing.md) {
                Text("7-Day Trend")
                    .font(DSTypography.h3)
                    .foregroundStyle(DSColor.Text.primary)

                Group {
                    switch metric.category {
                    case .sleepEfficiency:
                        BarSparkline(values: [0.82, 0.88, 0.85, 0.91, 0.87, 0.90, 0.91])
                            .frame(height: 48)

                    case .hrv:
                        AreaSparkline(
                            values: [52, 58, 55, 62, 68, 64, 68],
                            baseline: 58
                        )
                        .frame(height: 60)

                    case .restingHR:
                        AreaSparkline(
                            values: [62, 60, 61, 58, 59, 57, 58],
                            baseline: 60,
                            fillColor: DSColor.Green.green100,
                            lineColor: DSColor.Green.green500,
                            highlightColor: DSColor.Green.green600
                        )
                        .frame(height: 60)

                    case .consistency:
                        TrainingCalendarHeatmap(
                            weeks: [
                                [true, true, false, true, true, false, false],
                                [true, true, true, false, true, true, false],
                                [true, true, false, true, true, false, false],
                                [true, true, true, true, true, nil, nil],
                            ],
                            currentStreak: 5
                        )
                    }
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    // MARK: - Level 3: Coach Analysis

    private var coachAnalysis: some View {
        DSCard(style: .insight) {
            VStack(alignment: .leading, spacing: DSSpacing.md) {
                HStack(spacing: DSSpacing.sm) {
                    AnimatedMascot(state: .idle, size: 24)

                    Text("Coach's Take")
                        .font(DSTypography.h3)
                        .foregroundStyle(DSColor.Purple.purple600)
                }

                Text(coachText)
                    .font(DSTypography.body)
                    .foregroundStyle(DSColor.Text.primary)
                    .lineSpacing(4)

                // Ask about this
                DSChip(title: "Ask your coach about this") {
                    AppDelegate.pendingTab = "coach"
                    DSHaptic.light()
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    private var coachText: String {
        switch metric.category {
        case .sleepEfficiency:
            "Your sleep was great last night. You spent most of your time in bed actually sleeping. Keep doing what you did yesterday."
        case .hrv:
            "Your HRV is higher than usual. This means your body is handling stress well. Today is a good day to push harder in your workout."
        case .restingHR:
            "Your resting heart rate is steady. This is a sign your heart is getting stronger. Keep up your training."
        case .consistency:
            "You've trained 5 out of 5 days this week. That's right on target. Consistency matters more than any single workout."
        }
    }

    // MARK: - Level 4: Cross-Domain Insight

    private var crossDomainInsight: some View {
        VStack(alignment: .leading, spacing: DSSpacing.md) {
            Text("Connected Insight")
                .font(DSTypography.h3)
                .foregroundStyle(DSColor.Text.primary)

            // Paired insight card
            HStack(spacing: DSSpacing.md) {
                VStack(alignment: .leading, spacing: DSSpacing.xs) {
                    Text("Protein")
                        .font(DSTypography.caption)
                        .foregroundStyle(DSColor.Text.tertiary)
                    Text("142g")
                        .font(DSTypography.h3)
                        .foregroundStyle(DSColor.Text.primary)
                    Text("up 30g")
                        .font(DSTypography.caption)
                        .foregroundStyle(DSColor.Status.success)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(DSSpacing.lg)
                .background(DSColor.Surface.secondary)
                .dsCornerRadius(DSRadius.md)

                Image(systemName: "arrow.right")
                    .font(.system(size: 14))
                    .foregroundStyle(DSColor.Text.disabled)

                VStack(alignment: .leading, spacing: DSSpacing.xs) {
                    Text("Deep Sleep")
                        .font(DSTypography.caption)
                        .foregroundStyle(DSColor.Text.tertiary)
                    Text("1h 48m")
                        .font(DSTypography.h3)
                        .foregroundStyle(DSColor.Text.primary)
                    Text("up 12 min")
                        .font(DSTypography.caption)
                        .foregroundStyle(DSColor.Status.success)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(DSSpacing.lg)
                .background(DSColor.Surface.secondary)
                .dsCornerRadius(DSRadius.md)
            }

            Text("When you eat more protein, you tend to sleep deeper. Research shows protein helps sleep through a process in your body.")
                .font(DSTypography.bodySM)
                .foregroundStyle(DSColor.Text.secondary)
                .lineSpacing(3)

            DSCitationCard(
                text: "Protein supports sleep quality through tryptophan availability.",
                source: "Halson, S.L. (2014). Sleep in Elite Athletes."
            )
        }
    }

    // MARK: - Source Attribution

    private var sourceAttribution: some View {
        HStack(spacing: DSSpacing.xs) {
            Circle()
                .fill(DSColor.Green.green400)
                .frame(width: 6, height: 6)
            Text("Source: Oura Ring")
                .font(DSTypography.caption)
                .foregroundStyle(DSColor.Text.disabled)
        }
    }
}

#Preview("Sleep") {
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

#Preview("HRV") {
    NavigationStack {
        MetricDetailView(metric: HealthMetric(
            category: .hrv,
            label: "HRV Status",
            value: "68",
            unit: "ms",
            subtitle: "↑ 14% vs baseline",
            trend: .positive
        ))
    }
}
