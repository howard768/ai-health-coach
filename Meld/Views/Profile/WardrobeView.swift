import SwiftUI

// MARK: - Wardrobe — Mascot Accessory Gallery
//
// Browse, unlock, equip, and unequip mascot accessories. Shows the full
// catalog of MascotAccessory cases with their current state:
//
//   • Locked — grayed out, shows unlock hint
//   • Unlocked — full color, can toggle equipped
//   • Equipped — full color + checkmark badge
//
// A large preview of the current mascot with all equipped accessories
// sits at the top of the screen. Tapping a row toggles equip (if unlocked)
// or triggers an unlock attempt (if locked + in debug mode).
//
// IMPORTANT: in this build, the wardrobe also serves as the DEBUG
// surface for unlocking accessories. Tap a locked accessory to unlock
// it via POST /api/user/mascot/unlock. This will be replaced by the
// achievement detection system in a later cycle.

struct WardrobeView: View {
    @Bindable private var wardrobe = MascotWardrobe.shared
    @State private var celebratingAccessory: MascotAccessory? = nil
    @State private var showCelebration: Bool = false

    var body: some View {
        ScrollView(showsIndicators: false) {
            VStack(spacing: DSSpacing.xxl) {
                // Live preview of the mascot with current accessories
                mascotPreview

                // Accessory catalog
                VStack(spacing: DSSpacing.sm) {
                    DSSectionHeader(title: "WARDROBE")
                    ForEach(MascotAccessory.allCases) { accessory in
                        accessoryRow(accessory)
                    }
                }
                .padding(.horizontal, DSSpacing.xl)

                Spacer(minLength: 100)
            }
        }
        .background(DSColor.Background.primary)
        .navigationTitle("Wardrobe")
        .navigationBarTitleDisplayMode(.large)
        .task { await wardrobe.refresh() }
        .overlay {
            if showCelebration, let accessory = celebratingAccessory {
                UnlockCelebrationOverlay(
                    accessory: accessory,
                    onDismiss: { showCelebration = false }
                )
                .transition(.opacity.combined(with: .scale(scale: 0.8)))
            }
        }
        .animation(.spring(response: 0.35), value: showCelebration)
    }

    // MARK: - Mascot preview

    private var mascotPreview: some View {
        VStack(spacing: DSSpacing.md) {
            MeldMascot(
                state: showCelebration ? .celebrating : .idle,
                size: 120,
                accessories: wardrobe.equipped
            )
            .frame(height: 240)
            .frame(maxWidth: .infinity)

            if wardrobe.equipped.isEmpty {
                Text("No accessories equipped. Tap one below to try it on.")
                    .font(DSTypography.bodySM)
                    .foregroundStyle(DSColor.Text.tertiary)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, DSSpacing.xl)
            }
        }
        .padding(.top, DSSpacing.xl)
    }

    // MARK: - Accessory rows

    @ViewBuilder
    private func accessoryRow(_ accessory: MascotAccessory) -> some View {
        let isUnlocked = wardrobe.unlocked.contains(accessory)
        let isEquipped = wardrobe.equipped.contains(accessory)

        Button {
            Task {
                if isUnlocked {
                    // Toggle equip
                    await wardrobe.setEquipped(accessory, equipped: !isEquipped)
                } else {
                    // Debug unlock — tap locked accessory to unlock it.
                    // In production this path would be gated by achievement
                    // detection, but for now the wardrobe is the unlock surface.
                    let isNew = await wardrobe.unlock(accessory)
                    if isNew {
                        celebratingAccessory = accessory
                        showCelebration = true
                        DSHaptic.heavy()
                    }
                }
            }
        } label: {
            HStack(spacing: DSSpacing.lg) {
                // Thumbnail: mini mascot with just this accessory
                MeldMascot(
                    state: .idle,
                    size: 28,
                    accessories: isUnlocked ? [accessory] : []
                )
                .frame(width: 44, height: 44)
                .background(
                    isUnlocked
                        ? Color.hex(0xFAF0DA)
                        : DSColor.Surface.secondary
                )
                .clipShape(RoundedRectangle(cornerRadius: DSRadius.md, style: .continuous))
                .opacity(isUnlocked ? 1.0 : 0.5)

                // Text
                VStack(alignment: .leading, spacing: DSSpacing.xxs) {
                    Text(accessory.displayName)
                        .font(DSTypography.bodyEmphasis)
                        .foregroundStyle(isUnlocked ? DSColor.Text.primary : DSColor.Text.disabled)

                    Text(isUnlocked ? accessory.flavorText : accessory.unlockHint)
                        .font(DSTypography.caption)
                        .foregroundStyle(isUnlocked ? DSColor.Text.tertiary : DSColor.Text.disabled)
                        .lineLimit(2)
                }

                Spacer()

                // Status badge
                if isEquipped {
                    Image(systemName: "checkmark.circle.fill")
                        .font(.system(size: 22))
                        .foregroundStyle(DSColor.Green.green500)
                } else if isUnlocked {
                    Image(systemName: "circle")
                        .font(.system(size: 22))
                        .foregroundStyle(DSColor.Text.disabled)
                } else {
                    Image(systemName: "lock.fill")
                        .font(.system(size: 18))
                        .foregroundStyle(DSColor.Text.disabled)
                }
            }
            .padding(DSSpacing.md)
            .background(DSColor.Surface.primary)
            .dsCornerRadius(DSRadius.lg)
            .overlay(
                RoundedRectangle(cornerRadius: DSRadius.lg, style: .continuous)
                    .stroke(
                        isEquipped ? DSColor.Green.green400.opacity(0.5) : DSColor.Background.tertiary,
                        lineWidth: isEquipped ? 2 : 1
                    )
            )
        }
        .buttonStyle(.plain)
        .accessibilityLabel("\(accessory.displayName), \(isEquipped ? "equipped" : isUnlocked ? "unlocked" : "locked")")
        .accessibilityHint(isUnlocked ? "Double-tap to \(isEquipped ? "unequip" : "equip")" : "Double-tap to unlock")
    }
}

// MARK: - Unlock Celebration Overlay

private struct UnlockCelebrationOverlay: View {
    let accessory: MascotAccessory
    let onDismiss: () -> Void

    var body: some View {
        ZStack {
            // Dim background
            Color.black.opacity(0.55)
                .ignoresSafeArea()
                .onTapGesture { onDismiss() }

            VStack(spacing: DSSpacing.xxl) {
                // Mascot with the new accessory, celebrating
                MeldMascot(
                    state: .celebrating,
                    size: 120,
                    accessories: [accessory]
                )
                .frame(height: 240)

                Text("New unlock")
                    .font(DSTypography.h3)
                    .foregroundStyle(DSColor.Text.onPurple)

                Text(accessory.displayName)
                    .font(DSTypography.h1)
                    .foregroundStyle(DSColor.Green.green400)

                Text(accessory.flavorText)
                    .font(DSTypography.body)
                    .foregroundStyle(DSColor.Text.onPurple.opacity(0.8))
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, DSSpacing.xl)

                DSButton(title: "Equip now", style: .primary) {
                    Task {
                        await MascotWardrobe.shared.setEquipped(accessory, equipped: true)
                    }
                    onDismiss()
                }
                .padding(.horizontal, DSSpacing.huge)

                Button("Maybe later") {
                    onDismiss()
                }
                .font(DSTypography.bodySM)
                .foregroundStyle(DSColor.Text.onPurple.opacity(0.6))
            }
            .padding(DSSpacing.xxl)
        }
    }
}

#Preview {
    NavigationStack {
        WardrobeView()
    }
}
