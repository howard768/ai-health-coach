import SwiftUI
import Charts

// MARK: - Sparkline Visualizations (Swift Charts)
// Compact trend visualizations using Apple's Charts framework.
// Used inside metric cards and detail views.
// No axes, no labels — pure data ink.

// MARK: - Bar Sparkline (7-day mini bars)

struct BarSparkline: View {
    let values: [Double]
    var highlightLast: Bool = true
    var barColor: Color = DSColor.Purple.purple300
    var highlightColor: Color = DSColor.Purple.purple500

    var body: some View {
        Chart(Array(values.enumerated()), id: \.offset) { index, value in
            BarMark(
                x: .value("Day", index),
                y: .value("Value", value)
            )
            .foregroundStyle(
                highlightLast && index == values.count - 1
                    ? highlightColor
                    : barColor
            )
            .cornerRadius(2)
        }
        .chartXAxis(.hidden)
        .chartYAxis(.hidden)
        .chartLegend(.hidden)
    }
}

// MARK: - Area Sparkline (trend with baseline)

struct AreaSparkline: View {
    let values: [Double]
    var baseline: Double? = nil
    var fillColor: Color = DSColor.Purple.purple100
    var lineColor: Color = DSColor.Purple.purple400
    var baselineColor: Color = DSColor.Text.disabled
    var highlightColor: Color = DSColor.Purple.purple600

    var body: some View {
        Chart {
            // Area fill
            ForEach(Array(values.enumerated()), id: \.offset) { index, value in
                AreaMark(
                    x: .value("Day", index),
                    y: .value("Value", value)
                )
                .foregroundStyle(
                    LinearGradient(
                        colors: [fillColor, fillColor.opacity(0.3)],
                        startPoint: .top,
                        endPoint: .bottom
                    )
                )

                // Line on top
                LineMark(
                    x: .value("Day", index),
                    y: .value("Value", value)
                )
                .foregroundStyle(lineColor)
                .lineStyle(StrokeStyle(lineWidth: 2))
            }

            // Today's point (last value highlighted)
            if let last = values.last {
                PointMark(
                    x: .value("Day", values.count - 1),
                    y: .value("Value", last)
                )
                .foregroundStyle(highlightColor)
                .symbolSize(36)
            }

            // Baseline average (dashed horizontal line)
            if let baseline {
                RuleMark(y: .value("Baseline", baseline))
                    .foregroundStyle(baselineColor)
                    .lineStyle(StrokeStyle(lineWidth: 1, dash: [4, 3]))
            }
        }
        .chartXAxis(.hidden)
        .chartYAxis(.hidden)
        .chartLegend(.hidden)
    }
}

// MARK: - Previews

#Preview("Bar Sparkline") {
    BarSparkline(values: [0.6, 0.8, 0.7, 0.9, 0.85, 0.88, 0.95])
        .frame(width: 150, height: 40)
        .padding()
}

#Preview("Area Sparkline") {
    AreaSparkline(
        values: [52, 58, 55, 62, 68, 64, 68],
        baseline: 58
    )
    .frame(width: 320, height: 60)
    .padding()
}

#Preview("Area Sparkline - RHR") {
    AreaSparkline(
        values: [62, 60, 61, 58, 59, 57, 58],
        baseline: 60,
        fillColor: DSColor.Green.green100,
        lineColor: DSColor.Green.green500,
        highlightColor: DSColor.Green.green600
    )
    .frame(width: 320, height: 60)
    .padding()
}
