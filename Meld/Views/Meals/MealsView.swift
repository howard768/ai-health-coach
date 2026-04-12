import SwiftUI

// MARK: - Meals Tab
// Daily nutrition summary + meal timeline + cross-domain insight.
// Phase 1: text search logging. Phase 2: photo + barcode.
// Research: consistency beats accuracy (PMC5568610).
// 3 taps to log vs MFP's 8-10.
// Grid: 20pt margins, 8pt vertical rhythm.

struct MealsView: View {
    @State private var viewModel = MealsViewModel()
    private let M: CGFloat = 20

    var body: some View {
        ZStack(alignment: .bottomTrailing) {
            ScrollView {
                VStack(alignment: .leading, spacing: DSSpacing.xxl) {
                    // Error banner
                    if viewModel.loadError {
                        InlineErrorBanner.syncFailed {
                            Task { await viewModel.loadMeals() }
                        }
                    }

                    // Daily summary card
                    dailySummaryCard

                    // Meal timeline
                    if viewModel.dailyNutrition.meals.isEmpty {
                        MealsEmptyState {
                            viewModel.showInputSheet = true
                        }
                    } else {
                        mealTimeline
                    }

                    // Cross-domain insight (when available)
                    foodInsightCard

                    // Streak
                    streakSection
                }
                .padding(.horizontal, M)
                .padding(.top, DSSpacing.md)
                .padding(.bottom, 160) // Room for FAB + tab bar
            }
            .background(DSColor.Background.primary)

            // Floating Action Button
            fab
        }
        .sheet(isPresented: $viewModel.showInputSheet) {
            LogFoodSheet(viewModel: viewModel)
                .presentationDetents([.medium, .large])
                .presentationDragIndicator(.visible)
        }
        .sheet(isPresented: $viewModel.showCamera) {
            CameraView(viewModel: viewModel)
        }
        .sheet(isPresented: $viewModel.showBarcodeScanner) {
            BarcodeScannerView(viewModel: viewModel)
        }
        .sheet(isPresented: $viewModel.showVoiceCapture) {
            VoiceCaptureView(viewModel: viewModel)
        }
        .task { await viewModel.loadMeals() }
    }

    // MARK: - Daily Summary Card

    private var dailySummaryCard: some View {
        DSCard(style: .glass) {
            VStack(spacing: DSSpacing.lg) {
                // Macro arcs row
                HStack(spacing: DSSpacing.xl) {
                    macroArc(
                        label: "Protein",
                        current: viewModel.dailyNutrition.totalProtein,
                        target: viewModel.dailyNutrition.proteinTarget,
                        unit: "g",
                        color: DSColor.Green.green500
                    )
                    macroArc(
                        label: "Carbs",
                        current: viewModel.dailyNutrition.totalCarbs,
                        target: viewModel.dailyNutrition.carbTarget,
                        unit: "g",
                        color: DSColor.Purple.purple500
                    )
                    macroArc(
                        label: "Fat",
                        current: viewModel.dailyNutrition.totalFat,
                        target: viewModel.dailyNutrition.fatTarget,
                        unit: "g",
                        color: DSColor.Status.warning
                    )
                }

                // Calorie budget bar
                VStack(spacing: DSSpacing.xs) {
                    DSProgressBar(
                        progress: min(1.0, Double(viewModel.dailyNutrition.totalCalories) / Double(viewModel.dailyNutrition.calorieTarget)),
                        color: viewModel.dailyNutrition.caloriesRemaining > 0 ? DSColor.Green.green500 : DSColor.Status.error
                    )

                    HStack {
                        Text("\(viewModel.dailyNutrition.totalCalories) cal eaten")
                            .font(DSTypography.caption)
                            .foregroundStyle(DSColor.Text.secondary)
                        Spacer()
                        Text(viewModel.dailyNutrition.calorieStatusText)
                            .font(DSTypography.caption)
                            .foregroundStyle(DSColor.Accessible.greenText)
                    }
                }

                // Food quality indicator
                HStack(spacing: DSSpacing.sm) {
                    Circle()
                        .fill(viewModel.dailyNutrition.overallQuality.color)
                        .frame(width: 8, height: 8)
                    Text(viewModel.dailyNutrition.qualityText)
                        .font(DSTypography.caption)
                        .foregroundStyle(DSColor.Text.tertiary)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
    }

    private func macroArc(label: String, current: Double, target: Double, unit: String, color: Color) -> some View {
        VStack(spacing: DSSpacing.xs) {
            // Mini arc
            ZStack {
                Circle()
                    .stroke(DSColor.Surface.secondary, lineWidth: 5)
                    .frame(width: 56, height: 56)

                Circle()
                    .trim(from: 0, to: min(1.0, current / target))
                    .stroke(color, style: StrokeStyle(lineWidth: 5, lineCap: .round))
                    .frame(width: 56, height: 56)
                    .rotationEffect(.degrees(-90))

                Text("\(Int(current))")
                    .font(DSTypography.bodySM)
                    .foregroundStyle(DSColor.Text.primary)
            }

            Text(label)
                .font(DSTypography.caption)
                .foregroundStyle(DSColor.Text.tertiary)
        }
    }

    // MARK: - Meal Timeline

    private var mealTimeline: some View {
        VStack(alignment: .leading, spacing: DSSpacing.lg) {
            Text("Today")
                .font(DSTypography.h2)
                .foregroundStyle(DSColor.Text.primary)

            ForEach(viewModel.dailyNutrition.meals) { meal in
                MealCard(meal: meal)
            }
        }
    }

    // MARK: - Food → Health Insight

    private var foodInsightCard: some View {
        DSCard(style: .insight) {
            VStack(alignment: .leading, spacing: DSSpacing.md) {
                HStack(spacing: DSSpacing.sm) {
                    MeldMascot(state: .idle, size: 24)
                    Text("Food Insight")
                        .font(DSTypography.bodySM)
                        .foregroundStyle(DSColor.Purple.purple600)
                }

                Text("Your deep sleep was 22 min longer on days you ate dinner before 7pm this week.")
                    .font(DSTypography.body)
                    .foregroundStyle(DSColor.Text.primary)
                    .lineSpacing(4)

                DSChip(title: "Ask coach about this") {
                    NotificationCenter.default.post(name: .init("MeldSwitchTab"), object: nil, userInfo: ["tab": "coach"])
                    DSHaptic.light()
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    // MARK: - Streak

    private var streakSection: some View {
        HStack(spacing: DSSpacing.md) {
            DotArrayMini(trainedDays: min(viewModel.dailyNutrition.streak, 7), totalDays: 7)

            VStack(alignment: .leading, spacing: DSSpacing.xxs) {
                Text("\(viewModel.dailyNutrition.streak)-day streak")
                    .font(DSTypography.h3)
                    .foregroundStyle(DSColor.Text.primary)
                Text("Keep logging to help your coach.")
                    .font(DSTypography.caption)
                    .foregroundStyle(DSColor.Text.tertiary)
            }
        }
        .padding(DSSpacing.lg)
        .background(DSColor.Surface.secondary)
        .dsCornerRadius(DSRadius.md)
    }

    // MARK: - FAB

    private var fab: some View {
        Button(action: {
            viewModel.showInputSheet = true
            DSHaptic.medium()
        }) {
            Image(systemName: "plus")
                .font(.system(size: 22, weight: .semibold))
                .foregroundStyle(.white)
                .frame(width: 56, height: 56)
                .background(DSColor.Green.green500)
                .clipShape(Circle())
                .dsElevation(.high)
        }
        .padding(.trailing, M)
        .padding(.bottom, 96) // Above tab bar
        .accessibilityLabel("Log a meal")
        .accessibilityHint("Opens the meal logging sheet")
    }
}

// MARK: - Meal Card

private struct MealCard: View {
    let meal: Meal

    var body: some View {
        DSCard(style: .metric) {
            VStack(alignment: .leading, spacing: DSSpacing.sm) {
                // Header: time + meal type
                HStack {
                    Text(meal.mealType.rawValue)
                        .font(DSTypography.bodyEmphasis)
                        .foregroundStyle(DSColor.Text.primary)

                    Spacer()

                    Text(timeString)
                        .font(DSTypography.caption)
                        .foregroundStyle(DSColor.Text.tertiary)
                }

                // Food items
                ForEach(meal.items) { item in
                    HStack {
                        Circle()
                            .fill(item.quality.color)
                            .frame(width: 6, height: 6)

                        Text(item.name)
                            .font(DSTypography.bodySM)
                            .foregroundStyle(DSColor.Text.primary)

                        Spacer()

                        Text("\(item.calories) cal")
                            .font(DSTypography.caption)
                            .foregroundStyle(DSColor.Text.secondary)
                    }
                }

                // Macro badges
                HStack(spacing: DSSpacing.sm) {
                    macroBadge("P", value: meal.totalProtein, color: DSColor.Green.green500)
                    macroBadge("C", value: meal.totalCarbs, color: DSColor.Purple.purple500)
                    macroBadge("F", value: meal.totalFat, color: DSColor.Status.warning)

                    Spacer()

                    Text("\(meal.totalCalories) cal")
                        .font(DSTypography.bodySM)
                        .foregroundStyle(DSColor.Text.primary)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    private func macroBadge(_ letter: String, value: Double, color: Color) -> some View {
        HStack(spacing: DSSpacing.xxs) {
            Text(letter)
                .font(.system(size: 10, weight: .bold))
                .foregroundStyle(color)
            Text("\(Int(value))g")
                .font(DSTypography.caption)
                .foregroundStyle(DSColor.Text.secondary)
        }
        .padding(.horizontal, DSSpacing.sm)
        .padding(.vertical, DSSpacing.xxs)
        .background(color.opacity(0.1))
        .dsCornerRadius(DSRadius.xs)
    }

    private var timeString: String {
        let formatter = DateFormatter()
        formatter.dateFormat = "h:mm a"
        return formatter.string(from: meal.date)
    }
}

// MARK: - DotArrayMini (reused from MetricCardView, made public)

struct DotArrayMini: View {
    let trainedDays: Int
    let totalDays: Int

    var body: some View {
        HStack(spacing: 4) {
            ForEach(0..<totalDays, id: \.self) { day in
                Circle()
                    .fill(day < trainedDays ? DSColor.Green.green500 : DSColor.Text.disabled.opacity(0.4))
                    .frame(width: 8, height: 8)
            }
        }
    }
}

#Preview {
    MealsView()
}
