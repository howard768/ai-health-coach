import SwiftUI
import PhosphorSwift

// MARK: - Meld Custom Tab Bar
// Glassmorphic background with Phosphor Duotone icons.
// Coach tab features the custom mascot blob.
// Every interaction has haptic feedback and spring animation.

struct MeldTabBar: View {
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
        .padding(.top, DSSpacing.md)
        .padding(.bottom, DSSpacing.xxl)
        .background(tabBarBackground)
    }

    private var tabBarBackground: some View {
        Rectangle()
            .fill(.ultraThinMaterial)
            .overlay(alignment: .top) {
                Rectangle()
                    .fill(Color.white.opacity(colorScheme == .dark ? 0.06 : 0.5))
                    .frame(height: 0.5)
            }
            .ignoresSafeArea(.all, edges: .bottom)
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
                // Active dot indicator
                Circle()
                    .fill(isSelected ? DSColor.Green.green500 : Color.clear)
                    .frame(width: 5, height: 5)

                // Icon
                tabIcon
                    .scaleEffect(isSelected && !reduceMotion ? 1.08 : 1.0)
                    .frame(width: 28, height: 28)

                // Label
                Text(tab.title)
                    .font(DSTypography.caption)
                    .foregroundStyle(
                        isSelected ? DSColor.Green.green500 : DSColor.Text.tertiary
                    )
            }
            .frame(maxWidth: .infinity)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
    }

    @ViewBuilder
    private var tabIcon: some View {
        let color = isSelected ? DSColor.Green.green500 : DSColor.Text.tertiary

        if tab == .coach {
            // Mascot blob — custom drawn, not a Phosphor icon
            SquatBlobIcon(isActive: isSelected)
        } else {
            // Phosphor Duotone icons for everything else
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
            case .home:    return Ph.house.duotone
            case .coach:   return Ph.chat.duotone // unused, mascot replaces
            case .trends:  return Ph.trendUp.duotone
            case .meals:   return Ph.forkKnife.duotone
            case .profile: return Ph.user.duotone
            }
        } else {
            switch self {
            case .home:    return Ph.house.light
            case .coach:   return Ph.chat.light // unused, mascot replaces
            case .trends:  return Ph.trendUp.light
            case .meals:   return Ph.forkKnife.light
            case .profile: return Ph.user.light
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
