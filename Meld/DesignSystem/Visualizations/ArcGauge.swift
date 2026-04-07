import SwiftUI

// MARK: - Arc Gauge Visualization
// 180° semicircular gauge with 3 colored range band segments.
// Research: gas gauge analogies achieve 83% comprehension vs 60% for line graphs
// (JAMIA study, PMC7309237). Works equally well across all cognitive levels.
//
// Used for: Sleep Efficiency (percentage metrics with known good ranges)
// Triple encoding: color + position + text label for accessibility.

struct ArcGauge: View {
    let value: Double        // 0.0 to 1.0
    let displayValue: String // e.g., "91"
    let unit: String         // e.g., "%"
    let label: String        // e.g., "SLEEP"
    let subtitle: String     // e.g., "7h 12m total"

    // Zone thresholds (as fractions of 0-1)
    var lowThreshold: Double = 0.74   // Below this = red
    var midThreshold: Double = 0.85   // Below this = amber, above = green

    // Zone labels (4th grade reading level)
    var lowLabel: String = "Not enough sleep"
    var midLabel: String = "Could be better"
    var highLabel: String = "Great sleep"

    private let strokeWidth: CGFloat = 12
    private let startAngle: Angle = .degrees(180)
    private let endAngle: Angle = .degrees(0)

    private var zone: Zone {
        if value >= midThreshold { return .high }
        if value >= lowThreshold { return .mid }
        return .low
    }

    private enum Zone {
        case low, mid, high

        var color: Color {
            switch self {
            case .low: DSColor.Status.error
            case .mid: DSColor.Status.warning
            case .high: DSColor.Status.success
            }
        }
    }

    var body: some View {
        VStack(spacing: DSSpacing.sm) {
            // The gauge
            GeometryReader { geo in
                let width = geo.size.width
                let radius = (width - strokeWidth) / 2
                let center = CGPoint(x: width / 2, y: radius + strokeWidth / 2)

                ZStack {
                    // Range band segments (background arcs at 20% opacity)
                    arcSegment(center: center, radius: radius, from: 0, to: lowThreshold, color: DSColor.Status.error.opacity(0.15))
                    arcSegment(center: center, radius: radius, from: lowThreshold, to: midThreshold, color: DSColor.Status.warning.opacity(0.15))
                    arcSegment(center: center, radius: radius, from: midThreshold, to: 1.0, color: DSColor.Status.success.opacity(0.15))

                    // Active fill arc
                    arcSegment(center: center, radius: radius, from: 0, to: min(value, 1.0), color: zone.color)

                    // Diamond marker at current position
                    diamondMarker(center: center, radius: radius, value: value)

                    // Value label centered inside the arc
                    VStack(spacing: 0) {
                        HStack(alignment: .firstTextBaseline, spacing: DSSpacing.xxs) {
                            Text(displayValue)
                                .font(DSTypography.metricLG)
                                .foregroundStyle(DSColor.Text.primary)
                            Text(unit)
                                .font(DSTypography.caption)
                                .foregroundStyle(DSColor.Text.secondary)
                        }
                    }
                    .position(x: center.x, y: center.y - 8)
                }
            }
            .aspectRatio(2, contentMode: .fit) // 2:1 for semicircle

            // Label
            Text(label)
                .dsLabel()
                .foregroundStyle(DSColor.Text.tertiary)

            // Subtitle
            Text(subtitle)
                .font(DSTypography.caption)
                .foregroundStyle(DSColor.Text.secondary)

            // Zone verdict
            Text(zoneLabel)
                .font(DSTypography.bodySM)
                .foregroundStyle(zone.color)
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(label): \(displayValue)\(unit). \(subtitle). \(zoneLabel).")
    }

    private var zoneLabel: String {
        switch zone {
        case .low: lowLabel
        case .mid: midLabel
        case .high: highLabel
        }
    }

    // MARK: - Drawing Helpers

    private func arcSegment(center: CGPoint, radius: CGFloat, from: Double, to: Double, color: Color) -> some View {
        Path { path in
            let fromAngle = Angle.degrees(180 + from * 180)
            let toAngle = Angle.degrees(180 + to * 180)
            path.addArc(center: center, radius: radius, startAngle: fromAngle, endAngle: toAngle, clockwise: false)
        }
        .stroke(color, style: StrokeStyle(lineWidth: strokeWidth, lineCap: .round))
    }

    private func diamondMarker(center: CGPoint, radius: CGFloat, value: Double) -> some View {
        let angle = Angle.degrees(180 + value * 180)
        let x = center.x + radius * cos(angle.radians)
        let y = center.y + radius * sin(angle.radians)
        let markerSize: CGFloat = 10

        return Path { path in
            path.move(to: CGPoint(x: x, y: y - markerSize / 2))
            path.addLine(to: CGPoint(x: x + markerSize / 2, y: y))
            path.addLine(to: CGPoint(x: x, y: y + markerSize / 2))
            path.addLine(to: CGPoint(x: x - markerSize / 2, y: y))
            path.closeSubpath()
        }
        .fill(DSColor.Text.primary)
    }
}

// MARK: - Previews

#Preview("Sleep - Great") {
    ArcGauge(value: 0.91, displayValue: "91", unit: "%", label: "SLEEP", subtitle: "7h 12m total")
        .frame(width: 177)
        .padding()
}

#Preview("Sleep - Okay") {
    ArcGauge(value: 0.78, displayValue: "78", unit: "%", label: "SLEEP", subtitle: "6h 20m total")
        .frame(width: 177)
        .padding()
}

#Preview("Sleep - Low") {
    ArcGauge(value: 0.62, displayValue: "62", unit: "%", label: "SLEEP", subtitle: "4h 50m total")
        .frame(width: 177)
        .padding()
}

#Preview("Full Width") {
    ArcGauge(value: 0.91, displayValue: "91", unit: "%", label: "SLEEP EFFICIENCY", subtitle: "7h 12m total")
        .frame(width: 300)
        .padding()
}
