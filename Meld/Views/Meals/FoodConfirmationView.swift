import SwiftUI

// MARK: - Food Confirmation View
// Shows AI-recognized food items for user approval.
// "Good enough" default: one tap to accept all items.
// Individual items can be adjusted or removed.
// Auto-assigned meal type shown as editable chip.

struct FoodConfirmationView: View {
    @Binding var items: [FoodItem]
    @State var mealType: MealType
    @Bindable var viewModel: MealsViewModel
    var image: UIImage?
    @Environment(\.dismiss) private var dismiss
    @State private var isSaving = false
    @State private var editingIndex: Int?

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                ScrollView(showsIndicators: false) {
                    VStack(alignment: .leading, spacing: 0) {
                        // Meal type selector
                        HStack(spacing: DSSpacing.sm) {
                            ForEach(MealType.allCases) { type in
                                DSChip(
                                    title: type.rawValue,
                                    isSelected: mealType == type
                                ) {
                                    mealType = type
                                }
                            }
                        }
                        .padding(.top, DSSpacing.lg)
                        .padding(.horizontal, DSSpacing.xl)

                        Spacer().frame(height: DSSpacing.xxl)

                        if items.isEmpty {
                            // No items recognized
                            VStack(spacing: DSSpacing.md) {
                                AnimatedMascot(state: .concerned, size: 48)
                                Text("Couldn't identify any food")
                                    .font(DSTypography.body)
                                    .foregroundStyle(DSColor.Text.secondary)
                                Text("Try searching by name instead.")
                                    .font(DSTypography.caption)
                                    .foregroundStyle(DSColor.Text.tertiary)
                            }
                            .frame(maxWidth: .infinity)
                            .padding(.top, DSSpacing.xxl)
                        } else {
                            // Recognized items
                            DSSectionHeader(title: "IDENTIFIED ITEMS")
                                .padding(.horizontal, DSSpacing.xl)

                            Spacer().frame(height: DSSpacing.sm)

                            ForEach(Array(items.enumerated()), id: \.element.id) { index, item in
                                foodItemRow(item, index: index)
                                if index < items.count - 1 {
                                    DSDivider()
                                        .padding(.horizontal, DSSpacing.xl)
                                }
                            }

                            Spacer().frame(height: DSSpacing.xxl)

                            // Totals
                            totalsCard
                                .padding(.horizontal, DSSpacing.xl)
                        }

                        Spacer().frame(height: 100)
                    }
                }

                // Log it CTA
                if !items.isEmpty {
                    DSButton(
                        title: isSaving ? "Saving..." : "Log it",
                        style: .primary,
                        size: .lg,
                        isDisabled: isSaving
                    ) {
                        Task { await logMeal() }
                    }
                    .padding(.horizontal, DSSpacing.xl)
                    .padding(.bottom, DSSpacing.lg)
                }
            }
            .background(DSColor.Background.primary)
            .navigationTitle("Confirm Meal")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
            }
        }
    }

    // MARK: - Food Item Row

    @ViewBuilder
    private func foodItemRow(_ item: FoodItem, index: Int) -> some View {
        if editingIndex == index {
            // Editing mode
            editableItemRow(index: index)
        } else {
            // Display mode — tap to edit
            Button {
                editingIndex = index
            } label: {
                HStack(alignment: .top, spacing: DSSpacing.md) {
                    Circle()
                        .fill(item.quality.color)
                        .frame(width: 8, height: 8)
                        .padding(.top, 6)

                    VStack(alignment: .leading, spacing: DSSpacing.xs) {
                        Text(item.name)
                            .font(DSTypography.body)
                            .foregroundStyle(DSColor.Text.primary)
                        Text(item.servingSize)
                            .font(DSTypography.caption)
                            .foregroundStyle(DSColor.Text.secondary)
                        HStack(spacing: DSSpacing.md) {
                            Text("\(item.calories) cal")
                                .font(DSTypography.caption.weight(.medium))
                            Text("P: \(Int(item.protein))g")
                                .font(DSTypography.caption)
                            Text("C: \(Int(item.carbs))g")
                                .font(DSTypography.caption)
                            Text("F: \(Int(item.fat))g")
                                .font(DSTypography.caption)
                        }
                        .foregroundStyle(DSColor.Text.tertiary)
                    }

                    Spacer()

                    if item.confidence < 0.9 {
                        Text("Est.")
                            .font(DSTypography.caption)
                            .foregroundStyle(DSColor.Text.tertiary)
                            .padding(.horizontal, DSSpacing.sm)
                            .padding(.vertical, DSSpacing.xs)
                            .background(DSColor.Background.secondary)
                            .clipShape(Capsule())
                    }

                    Button {
                        items.remove(at: index)
                    } label: {
                        Image(systemName: "xmark.circle")
                            .foregroundStyle(DSColor.Text.tertiary)
                    }
                }
            }
            .buttonStyle(.plain)
            .padding(.horizontal, DSSpacing.xl)
            .padding(.vertical, DSSpacing.sm)
        }
    }

    @ViewBuilder
    private func editableItemRow(index: Int) -> some View {
        VStack(alignment: .leading, spacing: DSSpacing.sm) {
            TextField("Food name", text: Binding(
                get: { items[index].name },
                set: { items[index].name = $0 }
            ))
            .font(DSTypography.body)

            TextField("Serving size", text: Binding(
                get: { items[index].servingSize },
                set: { items[index].servingSize = $0 }
            ))
            .font(DSTypography.caption)

            HStack(spacing: DSSpacing.sm) {
                editField("Cal", value: Binding(
                    get: { Double(items[index].calories) },
                    set: { items[index].calories = Int($0) }
                ))
                editField("P", value: Binding(
                    get: { items[index].protein },
                    set: { items[index].protein = $0 }
                ))
                editField("C", value: Binding(
                    get: { items[index].carbs },
                    set: { items[index].carbs = $0 }
                ))
                editField("F", value: Binding(
                    get: { items[index].fat },
                    set: { items[index].fat = $0 }
                ))
            }

            DSButton(title: "Done", style: .secondary, size: .sm) {
                editingIndex = nil
            }
        }
        .padding(DSSpacing.lg)
        .background(DSColor.Background.secondary)
        .clipShape(RoundedRectangle(cornerRadius: DSRadius.sm))
        .padding(.horizontal, DSSpacing.xl)
    }

    private func editField(_ label: String, value: Binding<Double>) -> some View {
        VStack(spacing: 2) {
            Text(label)
                .font(DSTypography.caption)
                .foregroundStyle(DSColor.Text.tertiary)
            TextField("0", value: value, format: .number)
                .font(DSTypography.bodySM)
                .keyboardType(.decimalPad)
                .multilineTextAlignment(.center)
                .frame(width: 60)
                .padding(.vertical, DSSpacing.xs)
                .background(DSColor.Background.primary)
                .clipShape(RoundedRectangle(cornerRadius: DSRadius.sm))
        }
    }

    // MARK: - Totals Card

    @ViewBuilder
    private var totalsCard: some View {
        let totalCal = items.reduce(0) { $0 + $1.calories }
        let totalP = items.reduce(0.0) { $0 + $1.protein }
        let totalC = items.reduce(0.0) { $0 + $1.carbs }
        let totalF = items.reduce(0.0) { $0 + $1.fat }

        VStack(spacing: DSSpacing.sm) {
            HStack {
                Text("Total")
                    .font(DSTypography.body.weight(.medium))
                Spacer()
                Text("\(totalCal) cal")
                    .font(DSTypography.body.weight(.medium))
            }
            HStack {
                Text("P: \(Int(totalP))g")
                Text("C: \(Int(totalC))g")
                Text("F: \(Int(totalF))g")
                Spacer()
            }
            .font(DSTypography.caption)
            .foregroundStyle(DSColor.Text.secondary)
        }
        .padding(DSSpacing.lg)
        .background(DSColor.Background.secondary)
        .clipShape(RoundedRectangle(cornerRadius: DSRadius.md))
    }

    // MARK: - Save

    private func logMeal() async {
        isSaving = true
        do {
            let meal = Meal(
                mealType: mealType,
                items: items,
                source: .photo
            )
            try await viewModel.saveMeal(meal)
            DSHaptic.success()
            dismiss()
        } catch {
            isSaving = false
            DSHaptic.error()
        }
    }
}
