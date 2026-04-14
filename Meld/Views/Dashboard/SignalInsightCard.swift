import SwiftUI

// MARK: - Signal Insight Card
//
// Phase 4 of the Signal Engine (~/.claude/plans/golden-floating-creek.md).
// Renders the daily top-1 ranked finding from the backend heuristic ranker:
// correlation, anomaly, forecast_warning, etc. Mirrors CoachInsightCard
// visually so the swap is seamless; coexists with CoachInsightCard until
// the backend flips `ml_shadow_insight_card` off for a user.
//
// Voice compliance (from feedback_no_em_dashes + feedback_onboarding): no
// em dashes, no emoji, short sentences, 4th-grade reading level. All
// user-facing strings originate either from the backend's narrator
// (``payload.effectDescription``) or from the plain-language
// ``SignalInsight.body`` computed property.

struct SignalInsightCard: View {
    let insight: SignalInsight
    var onContinueInChat: () -> Void = {}
    var onFeedback: (SignalInsightFeedback) -> Void = { _ in }

    @State private var submittedFeedback: SignalInsightFeedback?

    var body: some View {
        DSCard(style: .insight) {
            VStack(alignment: .leading, spacing: DSSpacing.md) {

                // Header: mascot + kind-specific headline + confidence badge
                HStack(alignment: .top, spacing: DSSpacing.sm) {
                    MeldMascot(state: .idle, size: 32)

                    VStack(alignment: .leading, spacing: DSSpacing.xxs) {
                        Text(insight.headline)
                            .font(DSTypography.bodyEmphasis)
                            .foregroundStyle(DSColor.Purple.purple600)

                        Text(insight.confidenceLabel)
                            .font(DSTypography.caption)
                            .foregroundStyle(DSColor.Text.tertiary)
                    }

                    Spacer()
                }

                // Body: plain-language description
                Text(insight.body)
                    .font(DSTypography.body)
                    .foregroundStyle(DSColor.Text.primary)
                    .lineSpacing(4)
                    .multilineTextAlignment(.leading)
                    .frame(maxWidth: .infinity, alignment: .leading)

                // Feedback + continue-in-chat footer. Feedback row first
                // so users can react without interrupting the primary flow.
                if submittedFeedback == nil {
                    feedbackRow
                } else {
                    feedbackConfirmation
                }

                continueInChatButton
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .accessibilityIdentifier("dashboard-signal-card")
    }

    // MARK: - Feedback row

    private var feedbackRow: some View {
        HStack(spacing: DSSpacing.sm) {
            Text("Helpful?")
                .font(DSTypography.caption)
                .foregroundStyle(DSColor.Text.tertiary)

            feedbackButton(.thumbsUp, systemName: "hand.thumbsup", label: "Thumbs up")
            feedbackButton(.thumbsDown, systemName: "hand.thumbsdown", label: "Thumbs down")

            Spacer()

            Button(action: {
                DSHaptic.light()
                submit(.alreadyKnew)
            }) {
                Text("I knew that")
                    .font(DSTypography.caption)
                    .foregroundStyle(DSColor.Text.tertiary)
                    .padding(.vertical, DSSpacing.xs)
                    .padding(.horizontal, DSSpacing.sm)
            }
            .buttonStyle(.plain)
            .accessibilityLabel("I already knew that")
        }
        .frame(height: 44) // Minimum 44pt touch target for every control.
    }

    private func feedbackButton(
        _ kind: SignalInsightFeedback,
        systemName: String,
        label: String
    ) -> some View {
        Button(action: {
            DSHaptic.light()
            submit(kind)
        }) {
            Image(systemName: systemName)
                .font(.system(size: 16, weight: .semibold))
                .foregroundStyle(DSColor.Purple.purple600)
                .frame(width: 44, height: 44)
        }
        .buttonStyle(.plain)
        .accessibilityLabel(label)
        .accessibilityIdentifier("signal-feedback-\(kind.rawValue)")
    }

    private var feedbackConfirmation: some View {
        HStack(spacing: DSSpacing.xs) {
            Image(systemName: "checkmark")
                .font(.system(size: 13, weight: .semibold))
                .foregroundStyle(DSColor.Text.tertiary)
            Text("Thanks. We will use this to surface better patterns.")
                .font(DSTypography.caption)
                .foregroundStyle(DSColor.Text.tertiary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .frame(minHeight: 44)
    }

    private func submit(_ feedback: SignalInsightFeedback) {
        submittedFeedback = feedback
        onFeedback(feedback)
    }

    // MARK: - Continue in chat CTA

    private var continueInChatButton: some View {
        Button(action: {
            DSHaptic.light()
            onContinueInChat()
        }) {
            HStack(spacing: DSSpacing.xs) {
                Text("Tell me more")
                    .font(DSTypography.bodyEmphasis)
                    .foregroundStyle(DSColor.Accessible.greenText)

                Image(systemName: "arrow.right")
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundStyle(DSColor.Accessible.greenText)
            }
            .frame(height: 44)
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .buttonStyle(.plain)
        .accessibilityLabel("Tell me more in chat")
        .accessibilityIdentifier("signal-continue-cta")
    }
}

// MARK: - Previews

#Preview("Correlation, literature-backed") {
    SignalInsightCard(insight: SignalInsight(
        id: 1,
        candidateID: "abc123",
        kind: .correlation,
        subjectMetrics: ["protein_intake", "deep_sleep_seconds"],
        effectSize: 0.55,
        confidence: 0.95,
        score: 0.82,
        rankerVersion: "heuristic-1.0.0",
        literatureSupport: true,
        payload: SignalInsightPayload(
            sourceMetric: "protein_intake",
            targetMetric: "deep_sleep_seconds",
            lagDays: 0,
            direction: "positive",
            pearsonR: 0.55,
            spearmanR: 0.5,
            sampleSize: 60,
            effectDescription: "When your protein intake is higher, your deep sleep tends to be longer.",
            confidenceTier: "literature_supported",
            literatureRef: "10.1007/s40279-014-0260-0",
            metricKey: nil,
            observationDate: nil,
            observedValue: nil,
            forecastedValue: nil,
            residual: nil,
            zScore: nil,
            confirmedByBocpd: nil
        )
    ))
    .padding()
    .background(DSColor.Background.primary)
}

#Preview("Anomaly, BOCPD-confirmed") {
    SignalInsightCard(insight: SignalInsight(
        id: 2,
        candidateID: "def456",
        kind: .anomaly,
        subjectMetrics: ["hrv"],
        effectSize: 0.8,
        confidence: 0.80,
        score: 0.61,
        rankerVersion: "heuristic-1.0.0",
        literatureSupport: false,
        payload: SignalInsightPayload(
            sourceMetric: nil,
            targetMetric: nil,
            lagDays: nil,
            direction: "low",
            pearsonR: nil,
            spearmanR: nil,
            sampleSize: nil,
            effectDescription: nil,
            confidenceTier: nil,
            literatureRef: nil,
            metricKey: "hrv",
            observationDate: "2026-04-13",
            observedValue: 22.0,
            forecastedValue: 42.0,
            residual: -20.0,
            zScore: -4.0,
            confirmedByBocpd: true
        )
    ))
    .padding()
    .background(DSColor.Background.primary)
}
