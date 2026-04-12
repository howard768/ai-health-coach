import SwiftUI

// MARK: - MeldMascot — the one mascot every call site uses
//
// Composes:
//   1. Base body (SquatBlobIcon)
//   2. Animation envelope (state-driven scale/offset/rotation/opacity)
//   3. Equipped accessories (rendered behind or on top of the body)
//
// CALL SITES
//
// 36 places in the app render the mascot. They all go through this
// component. Existing call sites that used `SquatBlobIcon` or
// `AnimatedMascot` directly are migrated to `MeldMascot` so a future
// accessory rollout doesn't require touching every file again.
//
// The `accessories` parameter defaults to reading from `MascotWardrobe.shared`,
// the global @Observable that tracks what the user has equipped. Pass a
// custom set explicitly only for previews / wardrobe row thumbnails.
//
// SIZING
//
// Some accessories (notably ArmothyArms) extend BEYOND the base mascot
// bounds. MeldMascot reserves enough horizontal padding for them by
// rendering inside a frame that's 2× the mascot size. The base body
// is rendered centered. Call sites that need exact sizing can still
// pass `size:` and the wrapper will add the overflow padding internally.
//
// REDUCE MOTION
//
// Both the body envelope and the accessory animations respect
// `accessibilityReduceMotion`. The wrapper itself does no animation
// logic — it just composes child views that handle their own motion.

struct MeldMascot: View {
    let state: MascotState
    let size: CGFloat
    /// Explicit override; if nil, body reads from `MascotWardrobe.shared`.
    /// Stored as a `let` (not @State) so it's truly initializer-supplied
    /// and re-renders when the parent passes a different set.
    let explicitAccessories: Set<MascotAccessory>?

    @State private var phase: Bool = false
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    init(
        state: MascotState = .idle,
        size: CGFloat = 48,
        accessories: Set<MascotAccessory>? = nil
    ) {
        self.state = state
        self.size = size
        self.explicitAccessories = accessories
    }

    /// Read-side accessor that prefers the explicit override and falls
    /// back to the global wardrobe singleton.
    private var resolvedAccessories: Set<MascotAccessory> {
        if let explicit = explicitAccessories {
            return explicit
        }
        return MascotWardrobe.shared.equipped
    }

    var body: some View {
        // Frame is 2× the base size so accessories that overflow (Armothy
        // arms, fire crown flames, hat puff) have room. The base body
        // renders centered within this larger frame.
        let frameSize = size * 2

        ZStack {
            // 1. Under-layer accessories (capes, halos, etc.)
            ForEach(Array(orderedAccessories(zOrder: .under)), id: \.rawValue) { accessory in
                MascotAccessoryRenderer(
                    accessory: accessory,
                    mascotSize: size,
                    state: state
                )
            }

            // 2. Base body, with the existing animation envelope
            SquatBlobIcon(isActive: true, size: size)
                .scaleEffect(scaleValue)
                .offset(x: offsetX, y: offsetY)
                .rotationEffect(.degrees(rotation))
                .opacity(opacityValue)

            // 3. Over-layer accessories (arms, crown, hat, glasses, etc.)
            ForEach(Array(orderedAccessories(zOrder: .over)), id: \.rawValue) { accessory in
                MascotAccessoryRenderer(
                    accessory: accessory,
                    mascotSize: size,
                    state: state
                )
            }
        }
        .frame(width: frameSize, height: frameSize)
        .onAppear { startAnimation() }
        .onChange(of: state) { _, _ in startAnimation() }
        .accessibilityLabel(accessibilitySummary)
    }

    // MARK: - Accessory ordering

    /// Stable rendering order for accessories so the same set always
    /// composites the same way. Sorted by enum case order.
    private func orderedAccessories(zOrder: MascotAccessoryZOrder) -> [MascotAccessory] {
        MascotAccessory.allCases.filter {
            resolvedAccessories.contains($0) && $0.zOrder == zOrder
        }
    }

    // MARK: - Animation envelope (lifted from the old AnimatedMascot)

    private var scaleValue: CGFloat {
        guard !reduceMotion else { return 1.0 }
        switch state {
        case .idle: return phase ? 1.03 : 1.0
        case .thinking: return 1.0
        case .celebrating: return phase ? 1.15 : 0.95
        case .concerned: return phase ? 0.92 : 1.0
        case .greeting: return phase ? 1.0 : 0.3
        case .error: return 1.0
        }
    }

    private var offsetX: CGFloat {
        guard !reduceMotion else { return 0 }
        switch state {
        case .error: return phase ? -4 : 4
        default: return 0
        }
    }

    private var offsetY: CGFloat {
        guard !reduceMotion else { return 0 }
        switch state {
        case .idle: return phase ? -1.5 : 1.5
        case .celebrating: return phase ? -8 : 0
        case .greeting: return phase ? 0 : 20
        default: return 0
        }
    }

    private var rotation: Double {
        guard !reduceMotion else { return 0 }
        switch state {
        case .thinking: return phase ? 3 : -3
        case .celebrating: return phase ? 5 : -5
        default: return 0
        }
    }

    private var opacityValue: Double {
        guard !reduceMotion else { return 1.0 }
        switch state {
        case .thinking: return phase ? 0.7 : 1.0
        case .greeting: return phase ? 1.0 : 0.0
        default: return 1.0
        }
    }

    private func startAnimation() {
        guard !reduceMotion else { return }
        phase = false
        let animation: Animation = switch state {
        case .idle:
            .easeInOut(duration: 2.0).repeatForever(autoreverses: true)
        case .thinking:
            .easeInOut(duration: 0.8).repeatForever(autoreverses: true)
        case .celebrating:
            DSMotion.bouncy.repeatCount(3, autoreverses: true)
        case .concerned, .greeting:
            DSMotion.emphasis
        case .error:
            DSMotion.snappy.repeatCount(4, autoreverses: true)
        }
        withAnimation(animation) {
            phase = true
        }
    }

    // MARK: - Accessibility

    private var accessibilitySummary: String {
        let stateLabel = state.accessibilityLabel
        if resolvedAccessories.isEmpty {
            return "Coach mascot, \(stateLabel)"
        }
        let accessoryNames = resolvedAccessories
            .sorted { $0.rawValue < $1.rawValue }
            .map(\.displayName)
            .joined(separator: ", ")
        return "Coach mascot, \(stateLabel), wearing \(accessoryNames)"
    }
}

// MARK: - Convenience initializer for explicit-no-accessories rendering

extension MeldMascot {
    /// Render the mascot with NO accessories regardless of wardrobe state.
    /// Use for thumbnails / locked accessory previews / system-level chrome
    /// where you want the bare body.
    static func bare(state: MascotState = .idle, size: CGFloat = 48) -> MeldMascot {
        MeldMascot(state: state, size: size, accessories: [])
    }
}

#Preview("Idle, no accessories") {
    MeldMascot(state: .idle, size: 96, accessories: [])
        .padding()
}

#Preview("Idle, all accessories") {
    MeldMascot(
        state: .idle,
        size: 120,
        accessories: Set(MascotAccessory.allCases)
    )
    .padding()
    .background(Color(red: 0.95, green: 0.95, blue: 0.97))
}

#Preview("Celebrating, Armothy + crown") {
    MeldMascot(
        state: .celebrating,
        size: 120,
        accessories: [.armothyArms, .fireCrown]
    )
    .padding()
    .background(Color(red: 0.95, green: 0.95, blue: 0.97))
}
