import SwiftUI
import PhosphorSwift

// MARK: - Meld Custom Tab Bar
// Floating glass pill (per Meld Design System UI kit, 2026-04-19).
// Phosphor Light/Duotone for non-coach tabs, SquatBlob mascot for Coach.
// Active state: purple-600 icon + label, green-500 dot indicator below.
// Every interaction has haptic feedback and spring animation.

struct MeldTabBar: View {
    /// Total bottom inset that content should reserve to clear the floating pill.
    /// Pill height (~64) + bottomInset (28) + a small breathing margin.
    static let contentInset: CGFloat = 100

    @Binding var selectedTab: Tab
    @Environment(\.colorScheme) private var colorScheme

    var body: some View {
        HStack(spacing: 0) {
            ForEach(Tab.allCases, id: \.self) { tab in
                MeldTabItem(
                    tab: tab,
                    isSelected: selectedTab == tab
                ) {
                    withAnimation(DSMotion.snappy) {
                        selectedTab = tab
                    }
                    DSHaptic.selection()
                }
            }
        }
        .padding(.horizontal, DSSpacing.sm)
        .padding(.vertical, DSSpacing.sm)
        .background(pillBackground)
        .padding(.horizontal, 14)
        .padding(.bottom, 28)
    }

    private var pillBackground: some View {
        RoundedRectangle(cornerRadius: 28, style: .continuous)
            .fill(.ultraThinMaterial)
            .overlay(
                RoundedRectangle(cornerRadius: 28, style: .continuous)
                    .strokeBorder(
                        Color.white.opacity(colorScheme == .dark ? 0.12 : 0.6),
                        lineWidth: 0.5
                    )
            )
            .shadow(color: Color.black.opacity(colorScheme == .dark ? 0.0 : 0.08), radius: 16, x: 0, y: 8)
    }
}

// MARK: - Individual Tab Item

private struct MeldTabItem: View {
    let tab: Tab
    let isSelected: Bool
    let action: () -> Void
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        Button(action: action) {
            VStack(spacing: DSSpacing.xs) {
                // Icon: 24pt box for all tabs. Mascot scales into the same box.
                tabIcon
                    .frame(width: 24, height: 24)
                    .scaleEffect(isSelected && !reduceMotion ? 1.06 : 1.0)

                // Label
                Text(tab.title)
                    .font(DSTypography.caption)
                    .foregroundStyle(
                        isSelected ? DSColor.TabBar.active : DSColor.TabBar.inactive
                    )

                // Active dot indicator (below label)
                Circle()
                    .fill(isSelected ? DSColor.TabBar.indicator : Color.clear)
                    .frame(width: 4, height: 4)
            }
            .frame(maxWidth: .infinity)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityIdentifier("tab-\(tab.rawValue)")
    }

    @ViewBuilder
    private var tabIcon: some View {
        let color = isSelected ? DSColor.TabBar.active : DSColor.TabBar.inactive

        if tab == .coach {
            // Mascot scaled to the same 24pt baseline as Phosphor icons so glyphs
            // sit on a single optical line in the tray.
            SquatBlobIcon(isActive: isSelected, size: 24)
        } else {
            tab.phosphorIcon(isSelected: isSelected)
                .resizable()
                .aspectRatio(contentMode: .fit)
                .frame(width: 24, height: 24)
                .foregroundStyle(color)
        }
    }
}

// MARK: - Phosphor Icon Mapping

extension Tab {
    func phosphorIcon(isSelected: Bool) -> Image {
        if isSelected {
            switch self {
            case .home:   return Ph.house.duotone
            case .trends: return Ph.trendUp.duotone
            case .coach:  return Ph.chat.duotone // unused, mascot replaces
            case .log:    return Ph.forkKnife.duotone
            case .you:    return Ph.user.duotone
            }
        } else {
            switch self {
            case .home:   return Ph.house.light
            case .trends: return Ph.trendUp.light
            case .coach:  return Ph.chat.light // unused, mascot replaces
            case .log:    return Ph.forkKnife.light
            case .you:    return Ph.user.light
            }
        }
    }
}

#Preview("Light") {
    VStack {
        Spacer()
        MeldTabBar(selectedTab: .constant(.home))
    }
    .background(DSColor.Background.primary)
}

#Preview("Dark") {
    VStack {
        Spacer()
        MeldTabBar(selectedTab: .constant(.coach))
    }
    .background(DSColor.Background.primary)
    .preferredColorScheme(.dark)
}
