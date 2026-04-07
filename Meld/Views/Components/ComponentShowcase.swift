import SwiftUI
import Shimmer

// MARK: - Component Showcase
// Temporary screen to preview all new DS components.
// Access via Profile tab during development.

struct ComponentShowcase: View {
    @State private var toggleA = true
    @State private var toggleB = false
    @State private var currentStep = 2
    @State private var progress = 0.6

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: DSSpacing.xxxl) {

                    // MARK: Empty States
                    emptyStatesSection

                    // MARK: Avatars
                    avatarsSection

                    // MARK: Progress Indicators
                    progressSection

                    // MARK: Data Cards
                    dataCardsSection

                    // MARK: List Components
                    listSection

                    // MARK: Skeleton Loading
                    skeletonSection

                    // MARK: Existing Components
                    existingSection
                }
                .padding(.horizontal, DSSpacing.lg)
                .padding(.vertical, DSSpacing.xl)
            }
            .background(DSColor.Background.primary)
            .navigationTitle("Components")
            .navigationBarTitleDisplayMode(.large)
        }
    }

    // MARK: - Empty States

    private var emptyStatesSection: some View {
        VStack(alignment: .leading, spacing: DSSpacing.lg) {
            sectionTitle("Empty States")

            DSEmptyState(
                title: "No health data yet",
                message: "Connect your Oura Ring to start seeing your metrics here.",
                actionTitle: "Connect a wearable"
            )
            .frame(height: 300)
            .background(DSColor.Surface.primary)
            .dsCornerRadius(DSRadius.xl)
            .dsElevation(.low)
        }
    }

    // MARK: - Avatars

    private var avatarsSection: some View {
        VStack(alignment: .leading, spacing: DSSpacing.lg) {
            sectionTitle("Avatars")

            HStack(spacing: DSSpacing.lg) {
                VStack(spacing: DSSpacing.xs) {
                    DSAvatar(size: .sm, initials: "BH")
                    Text("SM").font(DSTypography.caption).foregroundStyle(DSColor.Text.tertiary)
                }
                VStack(spacing: DSSpacing.xs) {
                    DSAvatar(size: .md, initials: "BH")
                    Text("MD").font(DSTypography.caption).foregroundStyle(DSColor.Text.tertiary)
                }
                VStack(spacing: DSSpacing.xs) {
                    DSAvatar(size: .lg, initials: "BH")
                    Text("LG").font(DSTypography.caption).foregroundStyle(DSColor.Text.tertiary)
                }
                VStack(spacing: DSSpacing.xs) {
                    DSAvatar(size: .xl, initials: "BH")
                    Text("XL").font(DSTypography.caption).foregroundStyle(DSColor.Text.tertiary)
                }
            }

            HStack(spacing: DSSpacing.lg) {
                VStack(spacing: DSSpacing.xs) {
                    DSMascotAvatar(size: .sm)
                    Text("SM").font(DSTypography.caption).foregroundStyle(DSColor.Text.tertiary)
                }
                VStack(spacing: DSSpacing.xs) {
                    DSMascotAvatar(size: .md)
                    Text("MD").font(DSTypography.caption).foregroundStyle(DSColor.Text.tertiary)
                }
                VStack(spacing: DSSpacing.xs) {
                    DSMascotAvatar(size: .lg)
                    Text("LG").font(DSTypography.caption).foregroundStyle(DSColor.Text.tertiary)
                }
                VStack(spacing: DSSpacing.xs) {
                    DSMascotAvatar(size: .xl)
                    Text("XL").font(DSTypography.caption).foregroundStyle(DSColor.Text.tertiary)
                }
            }
        }
    }

    // MARK: - Progress

    private var progressSection: some View {
        VStack(alignment: .leading, spacing: DSSpacing.lg) {
            sectionTitle("Progress Indicators")

            Text("Step Dots").font(DSTypography.bodySM).foregroundStyle(DSColor.Text.secondary)
            DSStepDots(totalSteps: 5, currentStep: currentStep)
            Button("Next Step") {
                withAnimation { currentStep = (currentStep + 1) % 5 }
            }
            .font(DSTypography.caption)
            .foregroundStyle(DSColor.Purple.purple500)

            Text("Progress Bar").font(DSTypography.bodySM).foregroundStyle(DSColor.Text.secondary)
            DSProgressBar(progress: progress)
            DSProgressBar(progress: 1.0, color: DSColor.Status.success)

            Text("Circular").font(DSTypography.bodySM).foregroundStyle(DSColor.Text.secondary)
            HStack(spacing: DSSpacing.xxl) {
                VStack(spacing: DSSpacing.xs) {
                    DSCircularProgress(progress: nil, size: 40)
                    Text("Loading").font(DSTypography.caption).foregroundStyle(DSColor.Text.tertiary)
                }
                VStack(spacing: DSSpacing.xs) {
                    DSCircularProgress(progress: 0.65, size: 40)
                    Text("65%").font(DSTypography.caption).foregroundStyle(DSColor.Text.tertiary)
                }
                VStack(spacing: DSSpacing.xs) {
                    DSCircularProgress(progress: 1.0, size: 40, color: DSColor.Status.success)
                    Text("Done").font(DSTypography.caption).foregroundStyle(DSColor.Text.tertiary)
                }
            }
        }
    }

    // MARK: - Data Cards

    private var dataCardsSection: some View {
        VStack(alignment: .leading, spacing: DSSpacing.lg) {
            sectionTitle("Data Cards (for Coach Chat)")

            Text("Summary Card").font(DSTypography.bodySM).foregroundStyle(DSColor.Text.secondary)
            DSSummaryDataCard(
                title: "Sleep Summary",
                value: "91",
                unit: "%",
                subtitle: "7h 12m total",
                onTap: {}
            )

            Text("Workout Card").font(DSTypography.bodySM).foregroundStyle(DSColor.Text.secondary)
            DSWorkoutCard(exercises: [
                WorkoutExercise(name: "Squats", prescription: "4\u{00D7}5 @ 225lb"),
                WorkoutExercise(name: "RDL", prescription: "3\u{00D7}8 @ 185lb"),
                WorkoutExercise(name: "Leg Press", prescription: "3\u{00D7}10"),
                WorkoutExercise(name: "Walking Lunges", prescription: "2\u{00D7}12"),
            ])

            Text("Citation Card").font(DSTypography.bodySM).foregroundStyle(DSColor.Text.secondary)
            DSCitationCard(
                text: "Dietary protein supports sleep quality through tryptophan availability and muscle recovery demands.",
                source: "Halson, S.L. (2014). Sleep in Elite Athletes. Sports Medicine."
            )
        }
    }

    // MARK: - List Components

    private var listSection: some View {
        VStack(alignment: .leading, spacing: 0) {
            sectionTitle("List & Settings")
                .padding(.bottom, DSSpacing.md)

            VStack(spacing: 0) {
                DSSectionHeader(title: "Data Sources")

                DSListRow(title: "Oura Ring", subtitle: "Synced 2 min ago", leading: {
                    Image(systemName: "circle.hexagongrid.fill")
                        .foregroundStyle(DSColor.Green.green500)
                }, trailing: {
                    DSListStatusDot(isConnected: true)
                })

                DSDivider()

                DSListRow(title: "Eight Sleep", subtitle: "Not connected", leading: {
                    Image(systemName: "bed.double.fill")
                        .foregroundStyle(DSColor.Text.disabled)
                }, trailing: {
                    DSListStatusDot(isConnected: false)
                })

                DSDivider()

                DSSectionHeader(title: "Preferences")

                DSToggle(title: "Push Notifications", isOn: $toggleA, subtitle: "Proactive coaching alerts")

                DSDivider()

                DSToggle(title: "Dark Mode Override", isOn: $toggleB)
            }
            .background(DSColor.Surface.primary)
            .dsCornerRadius(DSRadius.lg)
            .dsElevation(.low)
        }
    }

    // MARK: - Skeleton Loading

    private var skeletonSection: some View {
        VStack(alignment: .leading, spacing: DSSpacing.lg) {
            sectionTitle("Skeleton Loading (Shimmer)")

            Text("Dashboard skeleton:").font(DSTypography.bodySM).foregroundStyle(DSColor.Text.secondary)

            // Skeleton card mimicking MetricCardView shape
            HStack(spacing: DSSpacing.md) {
                skeletonCard
                skeletonCard
            }

            // Skeleton insight card
            VStack(alignment: .leading, spacing: DSSpacing.md) {
                HStack(spacing: DSSpacing.sm) {
                    Circle().fill(DSColor.Surface.secondary).frame(width: 32, height: 32)
                    VStack(alignment: .leading, spacing: 4) {
                        RoundedRectangle(cornerRadius: 4).fill(DSColor.Surface.secondary).frame(width: 80, height: 12)
                        RoundedRectangle(cornerRadius: 4).fill(DSColor.Surface.secondary).frame(width: 50, height: 10)
                    }
                }
                RoundedRectangle(cornerRadius: 4).fill(DSColor.Surface.secondary).frame(height: 14)
                RoundedRectangle(cornerRadius: 4).fill(DSColor.Surface.secondary).frame(height: 14)
                RoundedRectangle(cornerRadius: 4).fill(DSColor.Surface.secondary).frame(width: 200, height: 14)
            }
            .padding(DSSpacing.xl)
            .background(DSColor.Purple.purple50)
            .dsCornerRadius(DSRadius.xl)
            .shimmering()
        }
    }

    private var skeletonCard: some View {
        VStack(alignment: .leading, spacing: DSSpacing.sm) {
            RoundedRectangle(cornerRadius: 4).fill(DSColor.Surface.secondary).frame(width: 80, height: 10)
            RoundedRectangle(cornerRadius: 4).fill(DSColor.Surface.secondary).frame(width: 60, height: 32)
            RoundedRectangle(cornerRadius: 4).fill(DSColor.Surface.secondary).frame(width: 90, height: 10)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(DSSpacing.xl)
        .background(DSColor.Surface.primary)
        .dsCornerRadius(DSRadius.lg)
        .dsElevation(.medium)
        .shimmering()
    }

    // MARK: - Existing Components

    private var existingSection: some View {
        VStack(alignment: .leading, spacing: DSSpacing.lg) {
            sectionTitle("Buttons & Chips")

            DSButton(title: "Primary Action", style: .primary) {}
            DSButton(title: "Secondary Action", style: .secondary) {}
            DSButton(title: "Ghost Action", style: .ghost) {}
            DSButton(title: "Loading...", style: .primary, isLoading: true) {}

            Text("Quick Actions").font(DSTypography.bodySM).foregroundStyle(DSColor.Text.secondary)
            DSChipRow(chips: [
                "How did my session go?",
                "Log dinner",
                "Recovery check"
            ])
        }
    }

    // MARK: - Helper

    private func sectionTitle(_ text: String) -> some View {
        Text(text)
            .font(DSTypography.h2)
            .foregroundStyle(DSColor.Text.primary)
    }
}

#Preview("Light") {
    ComponentShowcase()
}

#Preview("Dark") {
    ComponentShowcase()
        .preferredColorScheme(.dark)
}
