import SwiftUI

// MARK: - Range Band Indicator
// Horizontal capsule bar showing a user's personal min-to-max range
// with a positioned diamond marker for today's value.
// Research: personal baseline context is critical for metrics like HRV
// where absolute values are meaningless without individual context.
//
// Used for: HRV (ms), Resting Heart Rate (bpm)
// Triple encoding: position + color gradient + text context.

struct RangeBand: View {
    let currentValue: Double
    let personalMin: Double
    let personalMax: Double
    let personalAverage: Double
    let displayValue: String   // e.g., "68"
    let unit: String           // e.g., "ms"
    let label: String          // e.g., "HRV"

    /// Whether higher values are better (true for HRV, false for RHR)
    var higherIsBetter: Bool = true

    var height: CGFloat = 12

    private var normalizedPosition: CGFloat {
        guard personalMax > personalMin else { return 0.5 }
        return CGFloat((currentValue - personalMin) / (personalMax - personalMin)).clamped(to: 0...1)
    }

    private var contextText: String {
        let diff = currentValue - personalAverage
        let pct = abs(diff / personalAverage) * 100
        let direction = diff > 0 ? "above" : "below"

        if abs(diff / personalAverage) < 0.05 {
            return "Right in your range"
        } else if (diff > 0 && higherIsBetter) || (diff < 0 && !higherIsBetter) {
            return "\(Int(pct))% \(direction) your normal"
        } else {
            return "\(Int(pct))% \(direction) your normal"
        }
    }

    private var contextColor: Color {
        let diff = currentValue - personalAverage
        if abs(diff / personalAverage) < 0.05 {
            return DSColor.Purple.purple500
        } else if (diff > 0 && higherIsBetter) || (diff < 0 && !higherIsBetter) {
            return DSColor.Status.success
        } else {
            return DSColor.Status.warning
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: DSSpacing.sm) {
            // Value
            HStack(alignment: .firstTextBaseline, spacing: DSSpacing.xxs) {
                Text(displayValue)
                    .font(DSTypography.metricLG)
                    .foregroundStyle(DSColor.Text.primary)
                Text(unit)
                    .font(DSTypography.caption)
                    .foregroundStyle(DSColor.Text.secondary)
            }

            // Range band
            GeometryReader { geo in
                let width = geo.size.width

                ZStack(alignment: .leading) {
                    // Track
                    Capsule()
                        .fill(DSColor.Surface.secondary)
                        .frame(height: height)

                    // Personal range gradient fill
                    Capsule()
                        .fill(
                            LinearGradient(
                                colors: [DSColor.Purple.purple200, DSColor.Purple.purple500],
                                startPoint: .leading,
                                endPoint: .trailing
                            )
                        )
                        .frame(height: height)

                    // Diamond marker for today's value
                    diamond
                        .offset(x: normalizedPosition * (width - 12))
                }
            }
            .frame(height: height + 8) // Extra for diamond overshoot

            // Min/max labels
            HStack {
                Text("\(Int(personalMin))")
                    .font(.system(size: 9))
                    .foregroundStyle(DSColor.Text.disabled)
                Spacer()
                Text("\(Int(personalMax))")
                    .font(.system(size: 9))
                    .foregroundStyle(DSColor.Text.disabled)
            }

            // Label
            Text(label)
                .dsLabel()
                .foregroundStyle(DSColor.Text.tertiary)

            // Context
            Text(contextText)
                .font(DSTypography.caption)
                .foregroundStyle(contextColor)
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(label): \(displayValue) \(unit). \(contextText).")
    }

    private var diamond: some View {
        Path { path in
            let size: CGFloat = 10
            path.move(to: CGPoint(x: 6, y: 0))
            path.addLine(to: CGPoint(x: 12, y: size / 2 + 4))
            path.addLine(to: CGPoint(x: 6, y: size + 8))
            path.addLine(to: CGPoint(x: 0, y: size / 2 + 4))
            path.closeSubpath()
        }
        .fill(DSColor.Text.primary)
        .frame(width: 12, height: 18)
        .offset(y: -3)
    }
}

// MARK: - Clamping Helper

private extension Comparable {
    func clamped(to range: ClosedRange<Self>) -> Self {
        min(max(self, range.lowerBound), range.upperBound)
    }
}

// MARK: - Previews

#Preview("HRV - Above Average") {
    RangeBand(
        currentValue: 68,
        personalMin: 42,
        personalMax: 82,
        personalAverage: 58,
        displayValue: "68",
        unit: "ms",
        label: "HRV",
        higherIsBetter: true
    )
    .frame(width: 177)
    .padding()
}

#Preview("RHR - Good") {
    RangeBand(
        currentValue: 58,
        personalMin: 52,
        personalMax: 72,
        personalAverage: 62,
        displayValue: "58",
        unit: "bpm",
        label: "RESTING HR",
        higherIsBetter: false
    )
    .frame(width: 177)
    .padding()
}
