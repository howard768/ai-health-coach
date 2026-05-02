import SwiftUI

// MARK: - What We Collect
//
// Plain-language summary of every category of data Meld stores about a user.
// Anti-dark-pattern: shows what we collect at the same depth as the
// privacy policy, in language a 4th-grader can read. The full Privacy
// Policy on heymeld.com is the legal document; this screen is the
// human-readable companion that lives in the app for fast review.

struct WhatWeCollectView: View {
    @Environment(\.dismiss) private var dismiss
    @Environment(\.openURL) private var openURL
    private let M: CGFloat = 20

    private struct Category: Identifiable {
        let id = UUID()
        let title: String
        let what: String
        let why: String
        let source: String
    }

    private let categories: [Category] = [
        Category(
            title: "Account",
            what: "Your name, email, and Apple user ID.",
            why: "So you can sign in and we can send you the morning brief.",
            source: "Sign in with Apple"
        ),
        Category(
            title: "Health metrics",
            what: "Sleep efficiency, HRV, resting heart rate, readiness, and workout history.",
            why: "These are the inputs your coach reads to give you advice.",
            source: "Oura, Apple Health, Peloton, or Garmin (only the ones you connect)"
        ),
        Category(
            title: "Meals",
            what: "Foods, portions, calories, protein, and the time of each meal.",
            why: "To match nutrition with how you sleep and recover.",
            source: "Meals you log in the app"
        ),
        Category(
            title: "Coaching messages",
            what: "Every chat between you and your coach.",
            why: "So your coach remembers context and gets more useful over time.",
            source: "Conversations in the Coach tab"
        ),
        Category(
            title: "App usage",
            what: "Anonymous, aggregated counts of which screens you visit and which features you use.",
            why: "So we know what to fix or build next. No personal data is included.",
            source: "TelemetryDeck (privacy-first analytics)"
        ),
        Category(
            title: "Crash logs",
            what: "Stack traces and device model when the app crashes.",
            why: "So we can fix bugs.",
            source: "Sentry"
        ),
    ]

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: DSSpacing.xl) {
                    Text("Here's everything Meld stores about you, in plain language. Tap “Privacy Policy” for the full legal version.")
                        .font(DSTypography.bodySM)
                        .foregroundStyle(DSColor.Text.secondary)
                        .padding(.horizontal, M)
                        .padding(.top, DSSpacing.md)

                    VStack(spacing: DSSpacing.md) {
                        ForEach(categories) { category in
                            VStack(alignment: .leading, spacing: DSSpacing.sm) {
                                Text(category.title)
                                    .font(DSTypography.h3)
                                    .foregroundStyle(DSColor.Text.primary)

                                row(label: "What", body: category.what)
                                row(label: "Why", body: category.why)
                                row(label: "Source", body: category.source)
                            }
                            .padding(DSSpacing.lg)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .background(DSColor.Surface.primary)
                            .dsCornerRadius(DSRadius.lg)
                        }
                    }
                    .padding(.horizontal, M)

                    Button {
                        openURL(URL(string: "https://heymeld.com/privacy")!)
                    } label: {
                        Text("Read the full Privacy Policy")
                            .font(DSTypography.bodyEmphasis)
                            .foregroundStyle(DSColor.Purple.purple500)
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, DSSpacing.md)
                    }
                    .padding(.horizontal, M)
                    .padding(.bottom, DSSpacing.xxl)
                }
            }
            .background(DSColor.Background.primary)
            .navigationTitle("What We Collect")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done") { dismiss() }
                }
            }
        }
    }

    @ViewBuilder
    private func row(label: String, body: String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(label.uppercased())
                .font(DSTypography.caption)
                .foregroundStyle(DSColor.Text.tertiary)
            Text(body)
                .font(DSTypography.bodySM)
                .foregroundStyle(DSColor.Text.secondary)
        }
    }
}

#Preview {
    WhatWeCollectView()
}
