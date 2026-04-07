import SwiftUI

// MARK: - Meld Design System Chip Component
// Horizontal scrollable quick-action pills for coach chat.
// Green text, subtle border, pill radius.

struct DSChip: View {
    let title: String
    var isSelected: Bool = false
    let action: () -> Void

    var body: some View {
        Button(action: {
            DSHaptic.selection()
            action()
        }) {
            Text(title)
                .font(DSTypography.bodySM)
                .foregroundStyle(isSelected ? DSColor.Text.onGreen : DSColor.Green.green500)
                .padding(.vertical, DSSpacing.sm)
                .padding(.horizontal, DSSpacing.lg)
                .background(isSelected ? DSColor.Green.green500 : Color.clear)
                .clipShape(Capsule())
                .overlay(
                    Capsule()
                        .stroke(
                            isSelected ? Color.clear : DSColor.Text.disabled,
                            lineWidth: 1
                        )
                )
        }
    }
}

// MARK: - Chip Row (horizontal scrollable)

struct DSChipRow: View {
    let chips: [String]
    var onTap: (String) -> Void = { _ in }

    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: DSSpacing.sm) {
                ForEach(chips, id: \.self) { chip in
                    DSChip(title: chip) {
                        onTap(chip)
                    }
                }
            }
            .padding(.horizontal, DSSpacing.lg)
        }
    }
}
