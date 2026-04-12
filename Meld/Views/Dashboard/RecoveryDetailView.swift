import SwiftUI

// MARK: - Recovery Detail View
// Uses ZoneBadge with contributing factors.
// Research: WHOOP 3-zone system with factor decomposition.
// Triple encoding: color + icon + text for accessibility.

struct RecoveryDetailView: View {
    let readiness: RecoveryReadiness
    private let M: CGFloat = 20

    private var zone: RecoveryZone {
        switch readiness.level {
        case .high: .high
        case .moderate: .moderate
        case .low: .low
        }
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: DSSpacing.xxl) {

                // Zone badge — the hero
                DSCard(style: .metric) {
                    ZoneBadge(zone: zone, score: 82, badgeSize: 72)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }

                // Contributing factors
                DSCard(style: .data) {
                    ContributingFactors(factors: [
                        ContributingFactor(name: "Sleep Quality", value: 0.91, status: .good),
                        ContributingFactor(name: "HRV vs Baseline", value: 0.78, status: .good),
                        ContributingFactor(name: "Resting Heart Rate", value: 0.65, status: .watch),
                        ContributingFactor(name: "Training Load", value: 0.45, status: .watch),
                    ])
                    .frame(maxWidth: .infinity, alignment: .leading)
                }

                // Coach recommendation
                DSCard(style: .insight) {
                    VStack(alignment: .leading, spacing: DSSpacing.md) {
                        HStack(spacing: DSSpacing.sm) {
                            MeldMascot(state: .idle, size: 24)
                            Text("What to do today")
                                .font(DSTypography.h3)
                                .foregroundStyle(DSColor.Purple.purple600)
                        }

                        Text(coachAdvice)
                            .font(DSTypography.body)
                            .foregroundStyle(DSColor.Text.primary)
                            .lineSpacing(4)

                        DSChip(title: "Plan my workout") {
                            NotificationCenter.default.post(name: .init("MeldSwitchTab"), object: nil, userInfo: ["tab": "coach"])
                            DSHaptic.light()
                        }
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                }

                // Source
                HStack(spacing: DSSpacing.xs) {
                    Circle()
                        .fill(DSColor.Green.green400)
                        .frame(width: 6, height: 6)
                    Text("From: Oura Ring + training log")
                        .font(DSTypography.caption)
                        .foregroundStyle(DSColor.Text.disabled)
                }
            }
            .padding(.horizontal, M)
            .padding(.top, DSSpacing.md)
            .padding(.bottom, DSSpacing.xxxl)
        }
        .background(DSColor.Background.primary)
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .principal) {
                Text("Recovery")
                    .font(DSTypography.h3)
                    .foregroundStyle(DSColor.Text.primary)
            }
        }
    }

    private var coachAdvice: String {
        switch zone {
        case .high:
            "You slept well and your heart rate is low. Your body can handle a hard workout. Try adding weight to your main lifts today."
        case .moderate:
            "Your body is okay but not at its best. Stick to your plan but don't push for new records today."
        case .low:
            "Your body needs rest. Skip the heavy lifting and do a light walk or stretching instead."
        }
    }
}

#Preview {
    NavigationStack {
        RecoveryDetailView(readiness: RecoveryReadiness(
            level: .high,
            description: "Good for intensity today"
        ))
    }
}
