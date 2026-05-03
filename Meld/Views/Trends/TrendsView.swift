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
    @State private var isLoading = false
    @State private var loadError: String? = nil
    @State private var patterns: [APIPatternInsight] = []
    private let M: CGFloat = 20

    // Show empty state when we've loaded but the response is empty
    private var isEmpty: Bool {
        guard let data = trendsData else { return false }
        return data.metrics.isEmpty || data.metrics.values.allSatisfy { $0.values.isEmpty }
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: DSSpacing.xxl) {

                // Time range selector (always visible so the user can retry a different range)
                timeRangeSelector

                if isLoading && trendsData == nil {
                    // First-load spinner
                    loadingCard
                } else if let loadError {
                    // Error with retry
                    errorCard(message: loadError)
                } else if isEmpty {
                    // No data yet, prompt to connect a source
                    emptyCard
                } else {
                    // Trend summary (headline insight)
                    trendSummaryCard

                    // Per-metric trend cards
                    ForEach(MetricCategory.allCases, id: \.self) { metric in
                        TrendCard(metric: metric, range: selectedRange, apiData: trendsData)
                    }

                    // Cross-domain and nutrition, only shown when backed by real data
                    // (pattern detection and nutrition APIs not yet wired)
                }
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
        .onChange(of: selectedRange) { _, _ in
            // Refetch BOTH trends and patterns: previously only trendsData
            // refreshed on range change, so the "Pattern Found" coach insight
            // card stayed pinned to whatever the first 30-day fetch returned.
            Task {
                await loadTrends()
                await loadPatterns()
            }
        }
    }

    private var rangeDays: Int {
        switch selectedRange {
        case .week: return 7
        case .month: return 30
        case .quarter: return 90
        }
    }

    private func loadTrends() async {
        isLoading = true
        loadError = nil
        do {
            trendsData = try await APIClient.shared.fetchTrends(rangeDays: rangeDays)
        } catch {
            loadError = "Couldn't load trends. Pull to refresh."
        }
        isLoading = false
    }

    // MARK: - Empty / Loading / Error cards

    private var loadingCard: some View {
        VStack(spacing: DSSpacing.md) {
            ProgressView()
                .scaleEffect(1.2)
            Text("Loading your trends...")
                .font(DSTypography.bodySM)
                .foregroundStyle(DSColor.Text.secondary)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, DSSpacing.huge)
    }

    private var emptyCard: some View {
        VStack(spacing: DSSpacing.md) {
            MeldMascot(state: .idle, size: 48)
            Text("No trend data yet")
                .font(DSTypography.h3)
                .foregroundStyle(DSColor.Text.primary)
            Text("Connect your Oura Ring or Apple Health to start seeing your patterns.")
                .font(DSTypography.bodySM)
                .foregroundStyle(DSColor.Text.secondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, DSSpacing.xl)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, DSSpacing.huge)
    }

    private func errorCard(message: String) -> some View {
        VStack(spacing: DSSpacing.md) {
            MeldMascot(state: .concerned, size: 48)
            Text("Something went wrong")
                .font(DSTypography.h3)
                .foregroundStyle(DSColor.Text.primary)
            Text(message)
                .font(DSTypography.bodySM)
                .foregroundStyle(DSColor.Text.secondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, DSSpacing.xl)
            Button("Retry") {
                Task { await loadTrends() }
            }
            .font(DSTypography.bodyEmphasis)
            .foregroundStyle(DSColor.Purple.purple500)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, DSSpacing.huge)
    }

    private func loadPatterns() async {
        do {
            let result = try await APIClient.shared.fetchTrendPatterns(rangeDays: rangeDays)
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
                    MeldMascot(state: .idle, size: 24)
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
        guard let data = trendsData, !data.metrics.isEmpty else {
            return "Keep tracking, more data means better insights."
        }
        var parts: [String] = []

        if let sleep = data.metrics["sleep_efficiency"], sleep.values.count >= 2 {
            let diff = (sleep.values.last ?? 0) - (sleep.values.first ?? 0)
            if diff > 2 { parts.append("Your sleep efficiency is trending up") }
            else if diff < -2 { parts.append("Your sleep efficiency dipped a bit") }
            else { parts.append("Your sleep efficiency is holding steady") }
        }
        if let hrv = data.metrics["hrv"], hrv.values.count >= 2 {
            let diff = (hrv.values.last ?? 0) - (hrv.values.first ?? 0)
            if diff > 2 { parts.append("HRV is improving") }
            else if diff < -2 { parts.append("HRV dropped a bit") }
            else { parts.append("HRV is stable") }
        }
        if let rhr = data.metrics["resting_hr"], rhr.values.count >= 2 {
            let diff = (rhr.values.last ?? 0) - (rhr.values.first ?? 0)
            if diff < -1 { parts.append("Resting heart rate is dropping, good sign") }
            else if diff > 1 { parts.append("Resting heart rate is up a bit") }
            else { parts.append("Resting heart rate is stable") }
        }
        if parts.isEmpty { return "Keep tracking, more data means better insights." }
        return parts.joined(separator: ". ") + "."
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
                    // MainTabView's onReceive(.meldSwitchTab) calls
                    // coachViewModel.prefill(_:) only when the userInfo
                    // contains a `message` key. Pass the pattern text as the
                    // prompt so the coach tab opens with the question already
                    // teed up. Falls back to a generic prompt when patterns
                    // haven't loaded yet.
                    let prompt: String
                    if let p = topPattern {
                        prompt = "Tell me more about this pattern: \(p.pattern_text)"
                    } else {
                        prompt = "What patterns are you seeing in my data?"
                    }
                    NotificationCenter.default.post(
                        name: .meldSwitchTab,
                        object: nil,
                        userInfo: [
                            "tab": Tab.coach.rawValue,
                            "message": prompt,
                        ]
                    )
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
                        Text(avgProtein.map { "\($0)g" } ?? "--")
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
                        Text(avgCalories.map { $0.formatted() } ?? "--")
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
                        Text(daysLogged.map { "\($0)/\(rangeDays)" } ?? "--")
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
                .accessibilityLabel("\(metric.accessibilityName) trend chart")
                .accessibilityValue("\(trendText). Current value \(currentValue) \(currentUnit).")

                // Context line
                Text(contextText)
                    .font(DSTypography.caption)
                    .foregroundStyle(DSColor.Text.tertiary)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    // MARK: - Per-Metric Data

    private var apiKey: String {
        switch metric {
        case .sleepEfficiency: "sleep_efficiency"
        case .hrv: "hrv"
        case .restingHR: "resting_hr"
        case .consistency: "readiness"
        }
    }

    private var metricData: APIMetricTrend? {
        apiData?.metrics[apiKey]
    }

    private var currentValue: String {
        guard let data = metricData, let latest = data.values.last else { return "--" }
        return "\(Int(latest))"
    }

    private var currentUnit: String {
        switch metric {
        case .sleepEfficiency: "%"
        case .hrv: "ms"
        case .restingHR: "bpm"
        case .consistency: "score"
        }
    }

    private var trendData: [Double] {
        if let values = metricData?.values, !values.isEmpty { return values }
        return []
    }

    private var baselineValue: Double {
        if let baseline = metricData?.baseline, baseline > 0 { return baseline }
        return 0
    }

    private var trendDirection: Double {
        guard let data = metricData, data.values.count >= 2,
              let first = data.values.first, let last = data.values.last else { return 0 }
        return last - first
    }

    private var trendIcon: String {
        let diff = trendDirection
        if abs(diff) < 1 { return "minus" }
        if metric == .restingHR { return diff < 0 ? "arrow.down.right" : "arrow.up.right" }
        return diff > 0 ? "arrow.up.right" : "arrow.down.right"
    }

    private var trendColor: Color {
        let diff = trendDirection
        if abs(diff) < 1 { return DSColor.Text.secondary }
        if metric == .restingHR {
            return diff < 0 ? DSColor.Status.success : DSColor.Status.warning
        }
        return diff > 0 ? DSColor.Status.success : DSColor.Status.warning
    }

    private var trendText: String {
        guard let data = metricData, data.values.count >= 2,
              let first = data.values.first, let last = data.values.last else {
            return "No trend yet"
        }
        let diff = last - first
        if metric == .restingHR {
            if abs(diff) < 1 { return "Stable this \(range.label.lowercased())" }
            let sign = diff < 0 ? "" : "+"
            return "\(sign)\(Int(diff)) bpm this \(range.label.lowercased())"
        }
        let pctChange = first > 0 ? Int(abs(diff) / first * 100) : 0
        if pctChange < 1 { return "Stable this \(range.label.lowercased())" }
        let sign = diff > 0 ? "+" : "-"
        return "\(sign)\(pctChange)% this \(range.label.lowercased())"
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
        guard let data = metricData else { return "Dashed line = your average" }
        let avg = Int(data.personal_average)
        let best = Int(data.personal_max)
        switch metric {
        case .sleepEfficiency:
            return "Avg: \(avg)% · Best: \(best)% · Dashed line = your average"
        case .hrv:
            guard let latest = data.values.last else { return "Avg: \(avg)ms" }
            let dir = latest > data.personal_average ? "Trending up" : latest < data.personal_average ? "Trending down" : "Stable"
            return "Avg: \(avg)ms · Latest: \(Int(latest))ms · \(dir)"
        case .restingHR:
            guard let latest = data.values.last else { return "Avg: \(avg) bpm" }
            let dir = latest < data.personal_average ? "Getting lower (good)" : latest > data.personal_average ? "Trending up" : "Stable"
            return "Avg: \(avg) bpm · Latest: \(Int(latest)) bpm · \(dir)"
        case .consistency:
            return "Avg: \(avg) · Dashed line = your average"
        }
    }
}

#Preview {
    NavigationStack {
        TrendsView()
    }
}
