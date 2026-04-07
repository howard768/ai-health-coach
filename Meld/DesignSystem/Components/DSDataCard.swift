import SwiftUI

// MARK: - Meld Design System Data Card
// Rich inline data card for embedding health data visualizations
// within coach chat messages and metric detail screens.
//
// Per Vision doc: "Inline rich cards that really visualize the data
// with rich data and context. Not a link to a dashboard — the insight
// is right there in the conversation."
//
// Variants:
// - Summary: compact metric + mini visualization + tap to expand
// - Workout: structured exercise list with sets/reps/weight
// - Citation: literature reference with source

enum DSDataCardVariant {
    case summary
    case workout
    case citation
}

// MARK: - Summary Data Card (compact metric in chat)

struct DSSummaryDataCard: View {
    let title: String
    let value: String
    let unit: String
    let subtitle: String
    var trendColor: Color = DSColor.Green.green500
    var onTap: (() -> Void)? = nil

    var body: some View {
        Button(action: { onTap?(); DSHaptic.light() }) {
            HStack(spacing: DSSpacing.lg) {
                // Metric
                VStack(alignment: .leading, spacing: DSSpacing.xxs) {
                    Text(title)
                        .dsLabel()
                        .foregroundStyle(DSColor.Text.tertiary)

                    HStack(alignment: .firstTextBaseline, spacing: DSSpacing.xxs) {
                        Text(value)
                            .font(DSTypography.metricLG)
                            .foregroundStyle(DSColor.Text.primary)

                        Text(unit)
                            .font(DSTypography.caption)
                            .foregroundStyle(DSColor.Text.secondary)
                    }

                    Text(subtitle)
                        .font(DSTypography.caption)
                        .foregroundStyle(trendColor)
                }

                Spacer()

                // Mini visualization placeholder
                // This will be replaced with actual sparklines, gauges, etc.
                VStack(spacing: DSSpacing.xxs) {
                    MiniBarChart()
                        .frame(width: 60, height: 40)

                    if onTap != nil {
                        Text("Tap to expand")
                            .font(.system(size: 9, weight: .medium))
                            .foregroundStyle(DSColor.Text.disabled)
                    }
                }
            }
            .padding(DSSpacing.lg)
            .background(DSColor.Surface.secondary)
            .dsCornerRadius(DSRadius.lg)
        }
        .buttonStyle(.plain)
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(title): \(value) \(unit). \(subtitle)")
        .accessibilityHint(onTap != nil ? "Double-tap to expand" : "")
    }
}

// MARK: - Mini Bar Chart (placeholder visualization)

private struct MiniBarChart: View {
    let bars: [CGFloat] = [0.5, 0.7, 0.6, 0.9, 0.8, 0.85, 0.95]

    var body: some View {
        HStack(alignment: .bottom, spacing: 2) {
            ForEach(bars.indices, id: \.self) { index in
                RoundedRectangle(cornerRadius: 1.5, style: .continuous)
                    .fill(index == bars.count - 1
                        ? DSColor.Purple.purple500
                        : DSColor.Purple.purple200
                    )
                    .frame(width: 6, height: bars[index] * 40)
            }
        }
    }
}

// MARK: - Workout Plan Card (structured exercise list)

struct DSWorkoutCard: View {
    let exercises: [WorkoutExercise]

    var body: some View {
        VStack(alignment: .leading, spacing: DSSpacing.sm) {
            ForEach(exercises) { exercise in
                HStack {
                    Text(exercise.name)
                        .font(DSTypography.bodySM)
                        .foregroundStyle(DSColor.Text.primary)

                    Spacer()

                    Text(exercise.prescription)
                        .font(DSTypography.bodySM)
                        .foregroundStyle(DSColor.Text.secondary)
                }
                .padding(.vertical, DSSpacing.xxs)
            }
        }
        .padding(DSSpacing.lg)
        .background(DSColor.Surface.secondary)
        .dsCornerRadius(DSRadius.lg)
        .accessibilityElement(children: .combine)
        .accessibilityLabel("Workout plan: \(exercises.map { $0.name }.joined(separator: ", "))")
    }
}

struct WorkoutExercise: Identifiable {
    let id = UUID()
    let name: String
    let prescription: String // e.g., "4×5 @ 225lb"
}

// MARK: - Citation Card (literature reference)

struct DSCitationCard: View {
    let text: String
    let source: String

    var body: some View {
        VStack(alignment: .leading, spacing: DSSpacing.sm) {
            Text(text)
                .font(DSTypography.bodySM)
                .foregroundStyle(DSColor.Text.primary)
                .italic()
                .lineSpacing(3)

            HStack(spacing: DSSpacing.xs) {
                Image(systemName: "book.closed")
                    .font(.system(size: 10))
                    .foregroundStyle(DSColor.Text.disabled)

                Text(source)
                    .font(DSTypography.caption)
                    .foregroundStyle(DSColor.Text.tertiary)
            }
        }
        .padding(DSSpacing.lg)
        .background(DSColor.Surface.secondary)
        .dsCornerRadius(DSRadius.md)
        .overlay(
            RoundedRectangle(cornerRadius: DSRadius.md, style: .continuous)
                .stroke(DSColor.Purple.purple200, lineWidth: 1)
        )
    }
}

// MARK: - Previews

#Preview("Summary Card") {
    DSSummaryDataCard(
        title: "Sleep Summary",
        value: "91",
        unit: "%",
        subtitle: "7h 12m total",
        onTap: {}
    )
    .padding()
    .background(DSColor.Background.primary)
}

#Preview("Workout Card") {
    DSWorkoutCard(exercises: [
        WorkoutExercise(name: "Squats", prescription: "4×5 @ 225lb"),
        WorkoutExercise(name: "RDL", prescription: "3×8 @ 185lb"),
        WorkoutExercise(name: "Leg Press", prescription: "3×10"),
        WorkoutExercise(name: "Walking Lunges", prescription: "2×12"),
    ])
    .padding()
    .background(DSColor.Background.primary)
}

#Preview("Citation Card") {
    DSCitationCard(
        text: "Dietary protein supports sleep quality through tryptophan availability and muscle recovery demands.",
        source: "Halson, S.L. (2014). Sleep in Elite Athletes. Sports Medicine."
    )
    .padding()
    .background(DSColor.Background.primary)
}

#Preview("Dark") {
    VStack(spacing: DSSpacing.lg) {
        DSSummaryDataCard(
            title: "HRV Status",
            value: "68",
            unit: "ms",
            subtitle: "↑ 14% vs baseline",
            onTap: {}
        )
        DSWorkoutCard(exercises: [
            WorkoutExercise(name: "Squats", prescription: "4×5 @ 225lb"),
            WorkoutExercise(name: "RDL", prescription: "3×8 @ 185lb"),
        ])
        DSCitationCard(
            text: "HRV recovery correlates with sleep quality in trained individuals.",
            source: "Buchheit, M. (2014). Monitoring training status."
        )
    }
    .padding()
    .background(DSColor.Background.primary)
    .preferredColorScheme(.dark)
}
