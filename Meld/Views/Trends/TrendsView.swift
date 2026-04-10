import SwiftUI
import Charts

// MARK: - Trends Tab
// Health metrics over time with contextual visualization.
// Time range selector (7d / 30d / 90d).
// Per-metric trend cards with area sparklines and AI trend insights.
// Research: trends ARE the one place where historical charts are justified,
// but each chart must still encode meaning (baseline, annotations, context).
//
// Grid: 20pt margins, 8pt vertical rhythm.

struct TrendsView: View {
    @State private var selectedRange: TimeRange = .week
    @State private var selectedMetric: MetricCategory? = nil
    @State private var trendsData: APITrendsResponse?
    @State private var patterns: [APIPatternInsight] = []
    private let M: CGFloat = 20

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: DSSpacing.xxl) {

                // Time range selector
                timeRangeSelector

                // Trend summary (headline insight)
                trendSummaryCard

                // Per-metric trend cards
                ForEach(MetricCategory.allCases, id: \.self) { metric in
                    TrendCard(metric: metric, range: selectedRange, apiData: trendsData)
                }

                // Cross-domain trend insight
                crossDomainTrendInsight

                // Nutrition trend (if meals logged)
                nutritionTrendCard
            }
            .padding(.horizontal, M)
            .padding(.top, DSSpacing.md)
            .padding(.bottom, 120) // Room for tab bar
        }
        .background(DSColor.Background.primary)
        .navigationTitle("Trends")
        .navigationBarTitleDisplayMode(.large)
        .task {
            await loadTrends()
            await loadPatterns()
        }
        .onChange(of: selectedRange) { _, _ in Task { await loadTrends() } }
    }

    private func loadTrends() async {
        let days: Int
        switch selectedRange {
        case .week: days = 7
        case .month: days = 30
        case .quarter: days = 90
        }
        do {
            trendsData = try await APIClient.shared.fetchTrends(rangeDays: days)
        } catch {
            // Keep existing data on error
        }
    }

    private func loadPatterns() async {
        do {
            let result = try await APIClient.shared.fetchTrendPatterns()
            patterns = result.patterns
        } catch {
            // Keep existing patterns on error
        }
    }

    // MARK: - Time Range Selector

    private var timeRangeSelector: some View {
        HStack(spacing: 0) {
            ForEach(TimeRange.allCases) { range in
                Button(action: {
                    withAnimation(DSMotion.snappy) {
                        selectedRange = range
                    }
                    DSHaptic.selection()
                }) {
                    Text(range.label)
                        .font(DSTypography.bodySM)
                        .foregroundStyle(selectedRange == range ? DSColor.Text.onPurple : DSColor.Text.secondary)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, DSSpacing.sm)
                        .background(selectedRange == range ? DSColor.Purple.purple500 : Color.clear)
                        .dsCornerRadius(DSRadius.sm)
                }
            }
        }
        .padding(DSSpacing.xs)
        .background(DSColor.Surface.secondary)
        .dsCornerRadius(DSRadius.md)
    }

    // MARK: - Trend Summary

    private var trendSummaryCard: some View {
        DSCard(style: .insight) {
            VStack(alignment: .leading, spacing: DSSpacing.md) {
                HStack(spacing: DSSpacing.sm) {
                    AnimatedMascot(state: .idle, size: 24)
                    Text("This \(selectedRange.label.lowercased())")
                        .font(DSTypography.h3)
                        .foregroundStyle(DSColor.Purple.purple600)
                }

                Text(summaryText)
                    .font(DSTypography.body)
                    .foregroundStyle(DSColor.Text.primary)
                    .lineSpacing(4)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    private var summaryText: String {
        switch selectedRange {
        case .week:
            "Your sleep and HRV are both trending up. Resting heart rate is stable. You trained 5 of 7 days. Strong week."
        case .month:
            "Your sleep got better over the last 30 days. HRV is up 8% from where you started. Your body is adapting to your training."
        case .quarter:
            "Big picture: your fitness is improving. Resting HR dropped 4 bpm, HRV is up 15%, and you've been consistent 80% of the time."
        }
    }

    // MARK: - Cross-Domain Trend

    private var crossDomainTrendInsight: some View {
        let topPattern = patterns.first
        return DSCard(style: .data) {
            VStack(alignment: .leading, spacing: DSSpacing.md) {
                Text("Pattern Found")
                    .font(DSTypography.h3)
                    .foregroundStyle(DSColor.Text.primary)

                Text(topPattern?.pattern_text ?? "Your HRV tends to be higher on days after you eat dinner before 7pm. This pattern showed up 5 out of the last 7 times.")
                    .font(DSTypography.body)
                    .foregroundStyle(DSColor.Text.secondary)
                    .lineSpacing(4)

                if let pattern = topPattern {
                    Text("\(pattern.days_matched) of \(pattern.days_total) days · \(Int(pattern.confidence * 100))% confidence")
                        .font(DSTypography.caption)
                        .foregroundStyle(DSColor.Text.tertiary)
                }

                DSChip(title: "Ask coach about this") {
                    NotificationCenter.default.post(name: .init("MeldSwitchTab"), object: nil, userInfo: ["tab": "coach"])
                    DSHaptic.light()
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    // MARK: - Nutrition Trend

    private var nutritionTrendCard: some View {
        let n = trendsData?.nutrition
        let avgProtein = n.map { Int($0.avg_protein_g) }
        let targetProtein = n.map { Int($0.target_protein_g) } ?? 100
        let avgCalories = n.map { Int($0.avg_calories) }
        let targetCalories = n.map { Int($0.target_calories) } ?? 2000
        let daysLogged = n?.days_logged
        let rangeDays = trendsData?.range_days ?? selectedRange.days

        return DSCard(style: .metric) {
            VStack(alignment: .leading, spacing: DSSpacing.md) {
                Text("NUTRITION")
                    .dsLabel()
                    .foregroundStyle(DSColor.Text.tertiary)

                HStack(spacing: DSSpacing.xxl) {
                    VStack(alignment: .leading, spacing: DSSpacing.xxs) {
                        Text("Avg Protein")
                            .font(DSTypography.caption)
                            .foregroundStyle(DSColor.Text.tertiary)
                        Text(avgProtein.map { "\($0)g" } ?? "—")
                            .font(DSTypography.h3)
                            .foregroundStyle(DSColor.Text.primary)
                        Text("Target: \(targetProtein)g")
                            .font(DSTypography.caption)
                            .foregroundStyle(
                                (avgProtein ?? 0) >= targetProtein
                                    ? DSColor.Accessible.greenText
                                    : DSColor.Status.warning
                            )
                    }

                    VStack(alignment: .leading, spacing: DSSpacing.xxs) {
                        Text("Avg Calories")
                            .font(DSTypography.caption)
                            .foregroundStyle(DSColor.Text.tertiary)
                        Text(avgCalories.map { $0.formatted() } ?? "—")
                            .font(DSTypography.h3)
                            .foregroundStyle(DSColor.Text.primary)
                        Text("Target: \(targetCalories.formatted())")
                            .font(DSTypography.caption)
                            .foregroundStyle(DSColor.Accessible.greenText)
                    }

                    VStack(alignment: .leading, spacing: DSSpacing.xxs) {
                        Text("Logged")
                            .font(DSTypography.caption)
                            .foregroundStyle(DSColor.Text.tertiary)
                        Text(daysLogged.map { "\($0)/\(rangeDays)" } ?? "—")
                            .font(DSTypography.h3)
                            .foregroundStyle(DSColor.Text.primary)
                        Text("days")
                            .font(DSTypography.caption)
                            .foregroundStyle(DSColor.Text.tertiary)
                    }
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }
}

// MARK: - Time Range

enum TimeRange: String, CaseIterable, Identifiable {
    case week = "7D"
    case month = "30D"
    case quarter = "90D"

    var id: String { rawValue }

    var label: String { rawValue }

    var days: Int {
        switch self {
        case .week: 7
        case .month: 30
        case .quarter: 90
        }
    }
}

// MARK: - Individual Trend Card

private struct TrendCard: View {
    let metric: MetricCategory
    let range: TimeRange
    var apiData: APITrendsResponse?

    var body: some View {
        DSCard(style: .metric) {
            VStack(alignment: .leading, spacing: DSSpacing.md) {
                // Header
                HStack {
                    Text(metric.accessibilityName.uppercased())
                        .dsLabel()
                        .foregroundStyle(DSColor.Text.tertiary)

                    Spacer()

                    // Trend direction
                    HStack(spacing: DSSpacing.xxs) {
                        Image(systemName: trendIcon)
                            .font(.system(size: 10, weight: .bold))
                            .foregroundStyle(trendColor)
                        Text(trendText)
                            .font(DSTypography.caption)
                            .foregroundStyle(trendColor)
                    }
                }

                // Current value + unit
                HStack(alignment: .firstTextBaseline, spacing: DSSpacing.xxs) {
                    Text(currentValue)
                        .font(DSTypography.h2)
                        .foregroundStyle(DSColor.Text.primary)
                    Text(currentUnit)
                        .font(DSTypography.bodySM)
                        .foregroundStyle(DSColor.Text.secondary)
                }

                // Area sparkline with baseline
                AreaSparkline(
                    values: trendData,
                    baseline: baselineValue,
                    fillColor: chartFillColor,
                    lineColor: chartLineColor,
                    highlightColor: chartHighlightColor
                )
                .frame(height: 64)

                // Context line
                Text(contextText)
                    .font(DSTypography.caption)
                    .foregroundStyle(DSColor.Text.tertiary)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    // MARK: - Per-Metric Data

    private var currentValue: String {
        switch metric {
        case .sleepEfficiency: "91"
        case .hrv: "68"
        case .restingHR: "58"
        case .consistency: "5/7"
        }
    }

    private var currentUnit: String {
        switch metric {
        case .sleepEfficiency: "%"
        case .hrv: "ms"
        case .restingHR: "bpm"
        case .consistency: "days"
        }
    }

    private var trendData: [Double] {
        // Use real API data if available, fall back to hardcoded
        let apiKey: String
        switch metric {
        case .sleepEfficiency: apiKey = "sleep_efficiency"
        case .hrv: apiKey = "hrv"
        case .restingHR: apiKey = "resting_hr"
        case .consistency: apiKey = "readiness"
        }
        if let values = apiData?.metrics[apiKey]?.values, !values.isEmpty {
            return values
        }
        // Fallback (only used if API hasn't loaded yet)
        switch metric {
        case .sleepEfficiency: return [82, 85, 88, 84, 91, 87, 91]
        case .hrv: return [52, 55, 58, 62, 58, 64, 68]
        case .restingHR: return [64, 62, 63, 60, 61, 59, 58]
        case .consistency: return [3, 4, 5, 4, 5, 5, 5]
        }
    }

    private var baselineValue: Double {
        let apiKey: String
        switch metric {
        case .sleepEfficiency: apiKey = "sleep_efficiency"
        case .hrv: apiKey = "hrv"
        case .restingHR: apiKey = "resting_hr"
        case .consistency: apiKey = "readiness"
        }
        if let baseline = apiData?.metrics[apiKey]?.baseline, baseline > 0 {
            return baseline
        }
        switch metric {
        case .sleepEfficiency: return 85
        case .hrv: return 58
        case .restingHR: return 62
        case .consistency: return 4
        }
    }

    private var trendIcon: String {
        switch metric {
        case .sleepEfficiency, .hrv, .consistency: "arrow.up.right"
        case .restingHR: "arrow.down.right" // Lower is better
        }
    }

    private var trendColor: Color {
        switch metric {
        case .sleepEfficiency, .hrv, .consistency: DSColor.Status.success
        case .restingHR: DSColor.Status.success // Down is good for HR
        }
    }

    private var trendText: String {
        switch metric {
        case .sleepEfficiency: "+6% this \(range.label.lowercased())"
        case .hrv: "+17% this \(range.label.lowercased())"
        case .restingHR: "-4 bpm this \(range.label.lowercased())"
        case .consistency: "On track"
        }
    }

    private var chartFillColor: Color {
        switch metric {
        case .sleepEfficiency: DSColor.Green.green100
        case .hrv: DSColor.Purple.purple100
        case .restingHR: DSColor.Green.green100
        case .consistency: DSColor.Green.green100
        }
    }

    private var chartLineColor: Color {
        switch metric {
        case .sleepEfficiency: DSColor.Green.green500
        case .hrv: DSColor.Purple.purple500
        case .restingHR: DSColor.Green.green500
        case .consistency: DSColor.Green.green500
        }
    }

    private var chartHighlightColor: Color {
        switch metric {
        case .sleepEfficiency: DSColor.Green.green600
        case .hrv: DSColor.Purple.purple600
        case .restingHR: DSColor.Green.green600
        case .consistency: DSColor.Green.green600
        }
    }

    private var contextText: String {
        switch metric {
        case .sleepEfficiency: "Avg: 85% · Best: 91% · Dashed line = your average"
        case .hrv: "Avg: 58ms · Today: 68ms · Trending up"
        case .restingHR: "Avg: 62 bpm · Today: 58 bpm · Getting lower (good)"
        case .consistency: "4.4 avg days/week · Target: 5 days"
        }
    }
}

#Preview {
    NavigationStack {
        TrendsView()
    }
}
