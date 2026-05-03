import SwiftUI

// MARK: - Dashboard Screen (Home Tab)
// Matches Figma "Dashboard v3" spec.
// Greeting → Coach Insight → Today's Metrics → Recovery Readiness
//
// All cards are tappable:
// - Coach insight → Coach tab
// - Metric cards → MetricDetailView
// - Recovery → MetricDetailView (recovery variant)
// Pull-to-refresh reloads all data.

struct DashboardView: View {
    @State private var viewModel = DashboardViewModel()
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    /// Closure to switch tabs (injected from MainTabView)
    var switchToTab: ((Tab) -> Void)? = nil

    var body: some View {
        Group {
            switch viewModel.viewState {
            case .loading:
                ScrollView {
                    DashboardSkeleton()
                }

            case .empty:
                DashboardEmptyState {
                    NotificationCenter.default.post(name: .meldSwitchTab, object: nil, userInfo: ["tab": Tab.you.rawValue])
                    DSHaptic.light()
                }

            case .error(let error):
                FullScreenError(
                    title: "Can't load your data",
                    message: error.localizedDescription,
                    onRetry: { Task { await viewModel.refresh() } }
                )

            case .loaded:
                ScrollView {
                    VStack(alignment: .leading, spacing: DSSpacing.xxl) {
                        // Stale data banner
                        if let lastSynced = viewModel.dashboardData.lastSynced,
                           Date().timeIntervalSince(lastSynced) > 7200 {
                            InlineErrorBanner.staleData()
                        }

                        headerSection

                        // Signal Engine Phase 4 card (shadow-gated server-side).
                        // Falls back to the legacy CoachInsightCard when the
                        // backend reports has_card=false. See SignalInsight.swift.
                        if let signalInsight = viewModel.signalInsight {
                            SignalInsightCard(
                                insight: signalInsight,
                                onContinueInChat: {
                                    switchToTab?(.coach)
                                },
                                onFeedback: { feedback in
                                    Task {
                                        await viewModel.submitInsightFeedback(feedback)
                                    }
                                }
                            )
                        } else {
                            CoachInsightCard(
                                insight: viewModel.dashboardData.coachInsight,
                                onContinueInChat: {
                                    switchToTab?(.coach)
                                }
                            )
                        }

                        todaySection
                    }
                    .padding(.horizontal, DSSpacing.lg)
                    .padding(.top, DSSpacing.md)
                    .padding(.bottom, 120) // Room for tab bar
                }
                .accessibilityIdentifier("dashboard-scroll")
                .refreshable {
                    await viewModel.refresh()
                }
            }
        }
        .background(DSColor.Background.primary)
        .navigationBarHidden(true)
        .onAppear { Analytics.Dashboard.viewed() }
        .task { await viewModel.refresh() }
    }

    // MARK: - Header

    private var headerSection: some View {
        VStack(alignment: .leading, spacing: DSSpacing.xs) {
            // Date + last synced
            HStack {
                Text(viewModel.dateString)
                    .font(DSTypography.caption)
                    .foregroundStyle(DSColor.Text.tertiary)

                Spacer()

                if let syncedString = viewModel.lastSyncedString {
                    Text(syncedString)
                        .font(DSTypography.caption)
                        .foregroundStyle(DSColor.Text.disabled)
                        .accessibilityLabel("Data \(syncedString)")
                }
            }

            Text(viewModel.greeting)
                .font(DSTypography.h1)
                .foregroundStyle(DSColor.Text.primary)
                .accessibilityAddTraits(.isHeader)
        }
    }

    // MARK: - Today Section

    private var todaySection: some View {
        VStack(alignment: .leading, spacing: DSSpacing.lg) {
            Text("Today")
                .font(DSTypography.h2)
                .foregroundStyle(DSColor.Text.primary)
                .accessibilityAddTraits(.isHeader)

            // 2x2 Metric Grid, each card tappable
            LazyVGrid(
                columns: [
                    GridItem(.flexible(), spacing: DSSpacing.md),
                    GridItem(.flexible(), spacing: DSSpacing.md)
                ],
                spacing: DSSpacing.md
            ) {
                ForEach(viewModel.dashboardData.metrics) { metric in
                    NavigationLink(value: metric) {
                        MetricCardView(metric: metric)
                    }
                    .buttonStyle(.plain)
                }
            }

            // Full-width Recovery Readiness, tappable
            NavigationLink(value: viewModel.dashboardData.recoveryReadiness) {
                RecoveryReadinessCard(
                    readiness: viewModel.dashboardData.recoveryReadiness
                )
            }
            .buttonStyle(.plain)
        }
        .navigationDestination(for: HealthMetric.self) { metric in
            MetricDetailView(metric: metric)
        }
        .navigationDestination(for: RecoveryReadiness.self) { readiness in
            RecoveryDetailView(readiness: readiness)
        }
    }
}

// MARK: - Recovery Readiness Card (full-width)

struct RecoveryReadinessCard: View {
    let readiness: RecoveryReadiness

    private var levelColor: Color {
        switch readiness.level {
        case .high: DSColor.Green.green500
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
        // MARK: Accessibility
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Recovery Readiness: \(readiness.level.rawValue). \(readiness.description).")
        .accessibilityHint("Double-tap for details")
        .accessibilityAddTraits(.isButton)
    }
}

// MARK: - Previews

#Preview("Light") {
    NavigationStack {
        DashboardView()
    }
    .preferredColorScheme(.light)
}

#Preview("Dark") {
    NavigationStack {
        DashboardView()
    }
    .preferredColorScheme(.dark)
}
