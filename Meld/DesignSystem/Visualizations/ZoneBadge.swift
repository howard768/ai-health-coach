import SwiftUI

// MARK: - Zone Badge (Recovery Readiness)
// Large circular badge with colored border indicating recovery zone.
// Research: WHOOP's 3-zone system (green/amber/red) maps directly
// to behavioral recommendations. Gas-gauge study (PMC7309237) shows
// 83% comprehension for this pattern.
//
// Triple encoding: color + icon shape + text label.
// "High" = push hard. "Moderate" = go easy. "Low" = rest.

enum RecoveryZone {
    case high      // 67-100%, green
    case moderate  // 34-66%, amber
    case low       // 0-33%, red

    var color: Color {
        switch self {
        case .high: DSColor.Status.success
        case .moderate: DSColor.Status.warning
        case .low: DSColor.Status.error
        }
    }

    var label: String {
        switch self {
        case .high: "High"
        case .moderate: "Moderate"
        case .low: "Low"
        }
    }

    // 4th grade reading level action text
    var actionText: String {
        switch self {
        case .high: "Good for hard training today"
        case .moderate: "Keep it easy today"
        case .low: "Your body needs rest today"
        }
    }

    var iconName: String {
        switch self {
        case .high: "arrow.up.right"
        case .moderate: "minus"
        case .low: "arrow.down.right"
        }
    }

    static func from(score: Double) -> RecoveryZone {
        if score >= 0.67 { return .high }
        if score >= 0.34 { return .moderate }
        return .low
    }
}

struct ZoneBadge: View {
    let zone: RecoveryZone
    var score: Int? = nil // Optional 0-100 score
    var badgeSize: CGFloat = 64

    var body: some View {
        HStack(spacing: DSSpacing.lg) {
            // Badge circle
            ZStack {
                Circle()
                    .fill(zone.color.opacity(0.12))
                    .frame(width: badgeSize, height: badgeSize)

                Circle()
                    .stroke(zone.color, lineWidth: 5)
                    .frame(width: badgeSize, height: badgeSize)

                // Icon inside — shape encoding for colorblind safety
                Image(systemName: zone.iconName)
                    .font(.system(size: badgeSize * 0.3, weight: .semibold))
                    .foregroundStyle(zone.color)
            }

            // Text
            VStack(alignment: .leading, spacing: DSSpacing.xs) {
                Text(zone.label)
                    .font(DSTypography.h2)
                    .foregroundStyle(zone.color)

                Text(zone.actionText)
                    .font(DSTypography.body)
                    .foregroundStyle(DSColor.Text.primary)
                    .lineSpacing(2)

                if let score {
                    Text("\(score)/100")
                        .font(DSTypography.caption)
                        .foregroundStyle(DSColor.Text.tertiary)
                }
            }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Recovery: \(zone.label). \(zone.actionText).")
    }
}

// MARK: - Contributing Factors

struct ContributingFactors: View {
    let factors: [ContributingFactor]

    var body: some View {
        VStack(alignment: .leading, spacing: DSSpacing.lg) {
            Text("What went into this")
                .font(DSTypography.h3)
                .foregroundStyle(DSColor.Text.primary)

            ForEach(factors) { factor in
                HStack(spacing: DSSpacing.md) {
                    VStack(alignment: .leading, spacing: DSSpacing.xs) {
                        Text(factor.name)
                            .font(DSTypography.bodySM)
                            .foregroundStyle(DSColor.Text.primary)

                        DSProgressBar(
                            progress: factor.value,
                            color: factor.status.color,
                            height: 6
                        )
                    }

                    Text(factor.status.label)
                        .font(DSTypography.caption)
                        .foregroundStyle(factor.status.color)
                        .frame(width: 44, alignment: .trailing)
                }
            }
        }
    }
}

struct ContributingFactor: Identifiable {
    let id = UUID()
    let name: String
    let value: Double  // 0-1
    let status: FactorStatus
}

enum FactorStatus {
    case good, watch, rest

    var label: String {
        switch self {
        case .good: "Good"
        case .watch: "Watch"
        case .rest: "Rest"
        }
    }

    var color: Color {
        switch self {
        case .good: DSColor.Status.success
        case .watch: DSColor.Status.warning
        case .rest: DSColor.Status.error
        }
    }
}

// MARK: - Previews

#Preview("High Recovery") {
    ZoneBadge(zone: .high, score: 82)
        .padding()
}

#Preview("Moderate Recovery") {
    ZoneBadge(zone: .moderate, score: 55)
        .padding()
}

#Preview("Low Recovery") {
    ZoneBadge(zone: .low, score: 22)
        .padding()
}

#Preview("Contributing Factors") {
    ContributingFactors(factors: [
        ContributingFactor(name: "Sleep Quality", value: 0.91, status: .good),
        ContributingFactor(name: "HRV vs Baseline", value: 0.78, status: .good),
        ContributingFactor(name: "Resting Heart Rate", value: 0.65, status: .watch),
        ContributingFactor(name: "Training Load", value: 0.45, status: .watch),
    ])
    .padding()
}
