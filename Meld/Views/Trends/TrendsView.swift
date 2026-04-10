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
        .task { await loadTrends() }
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
        guard let data = trendsData else {
            // Pre-load fallback
            switch selectedRange {
            case .week:
                return "Your sleep and HRV are both trending up. Resting heart rate is stable. You trained 5 of 7 days. Strong week."
            case .month:
                return "Your sleep got better over the last 30 days. HRV is up 8% from where you started. Your body is adapting to your training."
            case .quarter:
                return "Big picture: your fitness is improving. Resting HR dropped 4 bpm, HRV is up 15%, and you've been consistent 80% of the time."
            }
        }
        var parts: [String] = []
        if let sleep = data.metrics["sleep_efficiency"], sleep.values.count >= 2,
           let first = sleep.values.first, first > 0 {
            let last = sleep.values.last!
            let pct = Int((last - first) / first * 100)
            if pct > 0 { parts.append("Sleep is up \(pct)%.") }
            else if pct < 0 { parts.append("Sleep is down \(abs(pct))%.") }
            else { parts.append("Sleep is stable.") }
        }
        if let hrv = data.metrics["hrv"], hrv.values.count >= 2,
           let first = hrv.values.first, first > 0 {
            let last = hrv.values.last!
            let pct = Int((last - first) / first * 100)
            if pct > 0 { parts.append("HRV is up \(pct)%.") }
            else if pct < 0 { parts.append("HRV is down \(abs(pct))%.") }
            else { parts.append("HRV is stable.") }
        }
        if let hr = data.metrics["resting_hr"], hr.values.count >= 2 {
            let first = hr.values.first!, last = hr.values.last!
            let diff = Int(first - last)
            if diff > 0 { parts.append("Resting HR dropped \(diff) bpm.") }
            else if diff < 0 { parts.append("Resting HR is up \(abs(diff)) bpm.") }
            else { parts.append("Resting heart rate is stable.") }
        }
        return parts.isEmpty ? "Loading your trends..." : parts.joined(separator: " ")
    }

    // MARK: - Cross-Domain Trend
    // TODO: Blocked on backend — needs GET /api/trends/patterns returning correlation text.
    //       Hardcoded until that endpoint exists.

    private var crossDomainTrendInsight: some View {
        DSCard(style: .data) {
            VStack(alignment: .leading, spacing: DSSpacing.md) {
                Text("Pattern Found")
                    .font(DSTypography.h3)
                    .foregroundStyle(DSColor.Text.primary)

                Text("Your HRV tends to be higher on days after you eat dinner before 7pm. This pattern showed up 5 out of the last 7 times.")
                    .font(DSTypography.body)
                    .foregroundStyle(DSColor.Text.secondary)
                    .lineSpacing(4)

                DSChip(title: "Ask coach about this") {
                    NotificationCenter.default.post(name: .init("MeldSwitchTab"), object: nil, userInfo: ["tab": "coach"])
                    DSHaptic.light()
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    // MARK: - Nutrition Trend
    // TODO: Blocked on backend — needs GET /api/trends/nutrition (or nutrition keys added
    //       to the existing /api/trends response) returning avg protein, avg calories, days logged.
    //       Values below are hardcoded until that endpoint exists.

    private var nutritionTrendCard: some View {
        DSCard(style: .metric) {
            VStack(alignment: .leading, spacing: DSSpacing.md) {
                Text("NUTRITION")
                    .dsLabel()
                    .foregroundStyle(DSColor.Text.tertiary)

                HStack(spacing: DSSpacing.xxl) {
                    VStack(alignment: .leading, spacing: DSSpacing.xxs) {
                        Text("Avg Protein")
                            .font(DSTypography.caption)
                            .foregroundStyle(DSColor.Text.tertiary)
                        Text("138g")
                            .font(DSTypography.h3)
                            .foregroundStyle(DSColor.Text.primary)
                        Text("Target: 150g")
                            .font(DSTypography.caption)
                            .foregroundStyle(DSColor.Status.warning)
                    }

                    VStack(alignment: .leading, spacing: DSSpacing.xxs) {
                        Text("Avg Calories")
                            .font(DSTypography.caption)
                            .foregroundStyle(DSColor.Text.tertiary)
                        Text("2,050")
                            .font(DSTypography.h3)
                            .foregroundStyle(DSColor.Text.primary)
                        Text("Target: 2,200")
                            .font(DSTypography.caption)
                            .foregroundStyle(DSColor.Accessible.greenText)
                    }

                    VStack(alignment: .leading, spacing: DSSpacing.xxs) {
                        Text("Logged")
                            .font(DSTypography.caption)
                            .foregroundStyle(DSColor.Text.tertiary)
                        Text("12/14")
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
        let key: String
        switch metric {
        case .sleepEfficiency: key = "sleep_efficiency"
        case .hrv: key = "hrv"
        case .restingHR: key = "resting_hr"
        case .consistency: key = "readiness"
        }
        if let last = apiData?.metrics[key]?.values.last {
            return "\(Int(last))"
        }
        switch metric {
        case .sleepEfficiency: return "91"
        case .hrv: return "68"
        case .restingHR: return "58"
        case .consistency: return "5"
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
        let key: String
        switch metric {
        case .sleepEfficiency: key = "sleep_efficiency"
        case .hrv: key = "hrv"
        case .restingHR: key = "resting_hr"
        case .consistency: key = "readiness"
        }
        if let values = apiData?.metrics[key]?.values, values.count >= 2,
           let first = values.first, first > 0, let last = values.last {
            switch metric {
            case .sleepEfficiency, .hrv:
                let pct = Int((last - first) / first * 100)
                let sign = pct >= 0 ? "+" : ""
                return "\(sign)\(pct)% this \(range.label.lowercased())"
            case .restingHR:
                let diff = Int(first - last)
                if diff == 0 { return "Stable this \(range.label.lowercased())" }
                let sign = diff > 0 ? "-" : "+"
                return "\(sign)\(abs(diff)) bpm this \(range.label.lowercased())"
            case .consistency:
                let avg = values.reduce(0, +) / Double(values.count)
                return String(format: "%.1f avg/week", avg)
            }
        }
        switch metric {
        case .sleepEfficiency: return "+6% this \(range.label.lowercased())"
        case .hrv: return "+17% this \(range.label.lowercased())"
        case .restingHR: return "-4 bpm this \(range.label.lowercased())"
        case .consistency: return "On track"
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
        let key: String
        switch metric {
        case .sleepEfficiency: key = "sleep_efficiency"
        case .hrv: key = "hrv"
        case .restingHR: key = "resting_hr"
        case .consistency: key = "readiness"
        }
        if let m = apiData?.metrics[key], let last = m.values.last {
            let avg = Int(m.personal_average)
            switch metric {
            case .sleepEfficiency:
                return "Avg: \(avg)% · Today: \(Int(last))% · Dashed line = your average"
            case .hrv:
                return "Avg: \(avg)ms · Today: \(Int(last))ms · Dashed line = your average"
            case .restingHR:
                return "Avg: \(avg) bpm · Today: \(Int(last)) bpm · Getting lower (good)"
            case .consistency:
                return String(format: "%.1f avg days/week · Target: 5 days", m.personal_average)
            }
        }
        switch metric {
        case .sleepEfficiency: return "Avg: 85% · Best: 91% · Dashed line = your average"
        case .hrv: return "Avg: 58ms · Today: 68ms · Trending up"
        case .restingHR: return "Avg: 62 bpm · Today: 58 bpm · Getting lower (good)"
        case .consistency: return "4.4 avg days/week · Target: 5 days"
        }
    }
}

#Preview {
    NavigationStack {
        TrendsView()
    }
}
