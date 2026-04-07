import SwiftUI

// MARK: - Dashboard Screen (Home Tab)
// Matches Figma "Dashboard v3" spec.
// Greeting → Coach Insight → Today's Metrics → Recovery Readiness

struct DashboardView: View {
    @State private var viewModel = DashboardViewModel()

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: DSSpacing.xxl) {

                // MARK: Header
                headerSection

                // MARK: Coach Insight
                CoachInsightCard(insight: viewModel.dashboardData.coachInsight)

                // MARK: Today's Metrics
                todaySection

                // Bottom padding for tab bar
                Spacer().frame(height: DSSpacing.huge)
            }
            .padding(.horizontal, DSSpacing.lg)
            .padding(.top, DSSpacing.md)
        }
        .background(DSColor.Background.primary)
    }

    // MARK: - Header

    private var headerSection: some View {
        VStack(alignment: .leading, spacing: DSSpacing.xs) {
            Text(viewModel.dateString)
                .font(DSTypography.caption)
                .foregroundStyle(DSColor.Text.tertiary)

            Text(viewModel.greeting)
                .font(DSTypography.h1)
                .foregroundStyle(DSColor.Text.primary)
        }
    }

    // MARK: - Today Section

    private var todaySection: some View {
        VStack(alignment: .leading, spacing: DSSpacing.lg) {
            Text("Today")
                .font(DSTypography.h2)
                .foregroundStyle(DSColor.Text.primary)

            // 2x2 Metric Grid
            LazyVGrid(
                columns: [
                    GridItem(.flexible(), spacing: DSSpacing.md),
                    GridItem(.flexible(), spacing: DSSpacing.md)
                ],
                spacing: DSSpacing.md
            ) {
                ForEach(viewModel.dashboardData.metrics) { metric in
                    MetricCardView(metric: metric)
                }
            }

            // Full-width Recovery Readiness
            RecoveryReadinessCard(
                readiness: viewModel.dashboardData.recoveryReadiness
            )
        }
    }
}

// MARK: - Recovery Readiness Card (full-width)

private struct RecoveryReadinessCard: View {
    let readiness: RecoveryReadiness

    private var levelColor: Color {
        switch readiness.level {
        case .high: DSColor.Status.success
        case .moderate: DSColor.Status.warning
        case .low: DSColor.Status.error
        }
    }

    var body: some View {
        DSCard(style: .metric) {
            VStack(alignment: .leading, spacing: DSSpacing.sm) {
                Text("RECOVERY READINESS")
                    .dsLabel()
                    .foregroundStyle(DSColor.Text.tertiary)

                HStack(alignment: .firstTextBaseline, spacing: DSSpacing.md) {
                    Text(readiness.level.rawValue)
                        .font(DSTypography.metricLG)
                        .foregroundStyle(levelColor)

                    Text(readiness.description)
                        .font(DSTypography.bodySM)
                        .foregroundStyle(DSColor.Text.tertiary)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }
}

// MARK: - Previews

#Preview("Light") {
    DashboardView()
        .preferredColorScheme(.light)
}

#Preview("Dark") {
    DashboardView()
        .preferredColorScheme(.dark)
}
