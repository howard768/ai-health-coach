import SwiftUI

// MARK: - Open Source Licenses
//
// Static list of the third-party Swift packages bundled in Meld plus a one-line
// pointer to each project's license. We don't ship the full license text inline
// (would balloon the bundle and require constant updates); we link out to the
// canonical source so the displayed list stays correct as long as the package
// repos themselves don't move.
//
// Adding a new SPM dependency? Append it here in alphabetical order.

struct OpenSourceLicensesView: View {
    @Environment(\.dismiss) private var dismiss
    @Environment(\.openURL) private var openURL

    private struct License: Identifiable {
        let id: String  // package name = stable id
        let name: String
        let license: String  // SPDX identifier
        let homepageURL: URL
        let licenseURL: URL
    }

    private let licenses: [License] = [
        License(
            id: "MijickPopups",
            name: "MijickPopups",
            license: "MIT",
            homepageURL: URL(string: "https://github.com/Mijick/Popups")!,
            licenseURL: URL(string: "https://github.com/Mijick/Popups/blob/main/LICENSE")!
        ),
        License(
            id: "PhosphorSwift",
            name: "PhosphorSwift",
            license: "MIT",
            homepageURL: URL(string: "https://github.com/phosphor-icons/swift")!,
            licenseURL: URL(string: "https://github.com/phosphor-icons/swift/blob/main/LICENSE")!
        ),
        License(
            id: "Shimmer",
            name: "SwiftUI Shimmer",
            license: "MIT",
            homepageURL: URL(string: "https://github.com/markiv/SwiftUI-Shimmer")!,
            licenseURL: URL(string: "https://github.com/markiv/SwiftUI-Shimmer/blob/main/LICENSE")!
        ),
        License(
            id: "SwiftGlass",
            name: "SwiftGlass",
            license: "MIT",
            homepageURL: URL(string: "https://github.com/1998code/SwiftGlass")!,
            licenseURL: URL(string: "https://github.com/1998code/SwiftGlass/blob/main/LICENSE")!
        ),
        License(
            id: "SwiftUIIntrospect",
            name: "SwiftUI Introspect",
            license: "MIT",
            homepageURL: URL(string: "https://github.com/siteline/swiftui-introspect")!,
            licenseURL: URL(string: "https://github.com/siteline/swiftui-introspect/blob/main/LICENSE")!
        ),
        License(
            id: "SwiftUIX",
            name: "SwiftUIX",
            license: "MIT",
            homepageURL: URL(string: "https://github.com/SwiftUIX/SwiftUIX")!,
            licenseURL: URL(string: "https://github.com/SwiftUIX/SwiftUIX/blob/main/LICENSE")!
        ),
        License(
            id: "swift-snapshot-testing",
            name: "swift-snapshot-testing",
            license: "MIT",
            homepageURL: URL(string: "https://github.com/pointfreeco/swift-snapshot-testing")!,
            licenseURL: URL(string: "https://github.com/pointfreeco/swift-snapshot-testing/blob/main/LICENSE")!
        ),
        License(
            id: "TelemetryDeck",
            name: "TelemetryDeck",
            license: "MIT",
            homepageURL: URL(string: "https://github.com/TelemetryDeck/SwiftSDK")!,
            licenseURL: URL(string: "https://github.com/TelemetryDeck/SwiftSDK/blob/main/LICENSE")!
        ),
    ]

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: DSSpacing.lg) {
                    Text("Meld is built with these open-source projects. Tap a name to view the project; tap “View license” for the full license text.")
                        .font(DSTypography.bodySM)
                        .foregroundStyle(DSColor.Text.secondary)
                        .padding(.horizontal, DSSpacing.lg)
                        .padding(.top, DSSpacing.md)

                    VStack(spacing: 0) {
                        ForEach(licenses) { license in
                            VStack(alignment: .leading, spacing: DSSpacing.xs) {
                                Button {
                                    openURL(license.homepageURL)
                                } label: {
                                    HStack {
                                        Text(license.name)
                                            .font(DSTypography.bodyEmphasis)
                                            .foregroundStyle(DSColor.Text.primary)
                                        Spacer()
                                        Text(license.license)
                                            .font(DSTypography.caption)
                                            .foregroundStyle(DSColor.Text.tertiary)
                                    }
                                }
                                .buttonStyle(.plain)

                                Button("View license") {
                                    openURL(license.licenseURL)
                                }
                                .font(DSTypography.caption)
                                .foregroundStyle(DSColor.Purple.purple500)
                            }
                            .padding(.vertical, DSSpacing.md)
                            .padding(.horizontal, DSSpacing.lg)

                            if license.id != licenses.last?.id {
                                DSDivider()
                            }
                        }
                    }
                    .background(DSColor.Surface.primary)
                    .dsCornerRadius(DSRadius.lg)
                    .padding(.horizontal, DSSpacing.md)
                }
                .padding(.bottom, DSSpacing.xxl)
            }
            .background(DSColor.Background.primary)
            .navigationTitle("Open Source Licenses")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done") { dismiss() }
                }
            }
        }
    }
}

#Preview {
    OpenSourceLicensesView()
}
