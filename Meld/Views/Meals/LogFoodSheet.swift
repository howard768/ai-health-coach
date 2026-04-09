import SwiftUI

// MARK: - Unified Food Input Sheet
// Half-sheet for logging food. Phase 1: text search + suggestions.
// Phase 2: camera viewfinder + barcode + voice.
// Smart suggestions by time of day + recent meals.
// 3 taps to log (vs MFP's 8-10).

struct LogFoodSheet: View {
    @Bindable var viewModel: MealsViewModel
    @Environment(\.dismiss) private var dismiss
    private let M: CGFloat = 20

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                // Search bar
                HStack(spacing: DSSpacing.sm) {
                    Image(systemName: "magnifyingglass")
                        .foregroundStyle(DSColor.Text.tertiary)

                    TextField("What did you eat?", text: $viewModel.searchText)
                        .font(DSTypography.body)
                        .foregroundStyle(DSColor.Text.primary)
                        .onSubmit {
                            viewModel.searchFood(viewModel.searchText)
                        }
                        .onChange(of: viewModel.searchText) { _, newValue in
                            viewModel.searchFood(newValue)
                        }

                    if !viewModel.searchText.isEmpty {
                        Button(action: {
                            viewModel.searchText = ""
                            viewModel.searchResults = []
                        }) {
                            Image(systemName: "xmark.circle.fill")
                                .foregroundStyle(DSColor.Text.disabled)
                        }
                    }
                }
                .padding(.vertical, DSSpacing.md)
                .padding(.horizontal, DSSpacing.lg)
                .background(DSColor.Surface.secondary)
                .dsCornerRadius(DSRadius.md)
                .padding(.horizontal, M)
                .padding(.top, DSSpacing.md)

                // Smart suggestions (when not searching)
                if viewModel.searchText.isEmpty {
                    suggestionsSection
                } else if viewModel.isSearching {
                    // Loading
                    ProgressView()
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                } else if viewModel.searchResults.isEmpty && !viewModel.searchText.isEmpty {
                    // No results
                    VStack(spacing: DSSpacing.md) {
                        Spacer()
                        Text("No foods found")
                            .font(DSTypography.body)
                            .foregroundStyle(DSColor.Text.secondary)
                        Text("Try a different name, or describe what you ate.")
                            .font(DSTypography.bodySM)
                            .foregroundStyle(DSColor.Text.tertiary)
                            .multilineTextAlignment(.center)
                        Spacer()
                    }
                    .padding(.horizontal, M)
                } else {
                    // Search results
                    searchResultsList
                }
            }
            .background(DSColor.Background.primary)
            .navigationTitle("Log Food")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                        .foregroundStyle(DSColor.Text.secondary)
                }
            }
        }
    }

    // MARK: - Smart Suggestions

    private var suggestionsSection: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: DSSpacing.xxl) {
                // Time-based suggestion
                if let suggestion = viewModel.timeBasedSuggestion {
                    VStack(alignment: .leading, spacing: DSSpacing.sm) {
                        Text("Quick add")
                            .font(DSTypography.h3)
                            .foregroundStyle(DSColor.Text.primary)

                        Button(action: {
                            // Re-log saved meal
                            DSHaptic.light()
                        }) {
                            HStack {
                                Image(systemName: "clock.arrow.circlepath")
                                    .foregroundStyle(DSColor.Green.green500)
                                Text(suggestion)
                                    .font(DSTypography.body)
                                    .foregroundStyle(DSColor.Text.primary)
                                Spacer()
                                DSListChevron()
                            }
                            .padding(DSSpacing.lg)
                            .background(DSColor.Surface.primary)
                            .dsCornerRadius(DSRadius.md)
                            .dsElevation(.low)
                        }
                    }
                }

                // Recent meals
                VStack(alignment: .leading, spacing: DSSpacing.sm) {
                    Text("Recent")
                        .font(DSTypography.h3)
                        .foregroundStyle(DSColor.Text.primary)

                    ForEach(viewModel.recentMeals, id: \.self) { meal in
                        Button(action: {
                            DSHaptic.light()
                            // Log recent meal
                        }) {
                            HStack {
                                Image(systemName: "arrow.counterclockwise")
                                    .font(.system(size: 14))
                                    .foregroundStyle(DSColor.Text.tertiary)
                                Text(meal)
                                    .font(DSTypography.body)
                                    .foregroundStyle(DSColor.Text.primary)
                                Spacer()
                                DSListChevron()
                            }
                            .padding(.vertical, DSSpacing.md)
                        }
                        DSDivider(inset: 0)
                    }
                }

                // Quick log methods
                VStack(alignment: .leading, spacing: DSSpacing.sm) {
                    Text("Quick log")
                        .font(DSTypography.h3)
                        .foregroundStyle(DSColor.Text.primary)

                    HStack(spacing: DSSpacing.xl) {
                        Button {
                            viewModel.showInputSheet = false
                            DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
                                viewModel.showCamera = true
                            }
                        } label: {
                            quickLogButton(icon: "camera.fill", title: "Photo")
                        }

                        Button {
                            viewModel.showInputSheet = false
                            DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
                                viewModel.showBarcodeScanner = true
                            }
                        } label: {
                            quickLogButton(icon: "barcode.viewfinder", title: "Barcode")
                        }

                        Button {
                            viewModel.showInputSheet = false
                            DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
                                viewModel.showVoiceCapture = true
                            }
                        } label: {
                            quickLogButton(icon: "mic.fill", title: "Voice")
                        }
                    }
                    .frame(maxWidth: .infinity)
                }
            }
            .padding(.horizontal, M)
            .padding(.top, DSSpacing.xxl)
        }
    }

    private func quickLogButton(icon: String, title: String) -> some View {
        VStack(spacing: DSSpacing.sm) {
            Image(systemName: icon)
                .font(.system(size: 22))
                .foregroundStyle(DSColor.Purple.purple500)
                .frame(width: 56, height: 56)
                .background(DSColor.Purple.purple50)
                .clipShape(Circle())

            Text(title)
                .font(DSTypography.caption)
                .foregroundStyle(DSColor.Text.secondary)
        }
    }

    private func featureTeaser(icon: String, title: String) -> some View {
        VStack(spacing: DSSpacing.sm) {
            Image(systemName: icon)
                .font(.system(size: 24))
                .foregroundStyle(DSColor.Text.disabled)
                .frame(width: 56, height: 56)
                .background(DSColor.Surface.secondary)
                .clipShape(Circle())

            Text(title)
                .font(DSTypography.caption)
                .foregroundStyle(DSColor.Text.disabled)
        }
    }

    // MARK: - Search Results

    private var searchResultsList: some View {
        ScrollView {
            LazyVStack(spacing: 0) {
                ForEach(viewModel.searchResults) { item in
                    Button(action: {
                        viewModel.logFoodItem(item)
                    }) {
                        HStack(spacing: DSSpacing.md) {
                            // Quality dot
                            Circle()
                                .fill(item.quality.color)
                                .frame(width: 8, height: 8)

                            VStack(alignment: .leading, spacing: DSSpacing.xxs) {
                                Text(item.name)
                                    .font(DSTypography.body)
                                    .foregroundStyle(DSColor.Text.primary)

                                Text("\(item.servingSize) · \(item.calories) cal")
                                    .font(DSTypography.caption)
                                    .foregroundStyle(DSColor.Text.tertiary)
                            }

                            Spacer()

                            // Macro preview
                            VStack(alignment: .trailing, spacing: DSSpacing.xxs) {
                                Text("P: \(Int(item.protein))g")
                                    .font(.system(size: 10))
                                    .foregroundStyle(DSColor.Green.green500)
                                Text("C: \(Int(item.carbs))g  F: \(Int(item.fat))g")
                                    .font(.system(size: 10))
                                    .foregroundStyle(DSColor.Text.tertiary)
                            }

                            // Source badge
                            Text(item.dataSource.rawValue)
                                .font(.system(size: 8, weight: .medium))
                                .foregroundStyle(DSColor.Text.disabled)
                                .padding(.horizontal, 4)
                                .padding(.vertical, 2)
                                .background(DSColor.Surface.secondary)
                                .dsCornerRadius(DSRadius.xs)
                        }
                        .padding(.vertical, DSSpacing.md)
                        .padding(.horizontal, M)
                    }
                    DSDivider(inset: M + 20)
                }
            }
        }
    }
}

#Preview {
    MealsView()
}
