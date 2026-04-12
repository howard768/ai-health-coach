import SwiftUI

// MARK: - Shield & Sword accessory
//
// Defensive stance: shield in front of body, sword raised to the side.
// "Welcome to Meld" easy unlock — earned for sending the first chat
// message. Both pieces are SF Symbols ("shield.fill" + a custom rotated
// arrow for the sword) sized relative to the mascot.
//
// On the celebrating state, the sword does a small triumphant raise.

struct ShieldAndSwordView: View {
    let mascotSize: CGFloat
    let mascotState: MascotState

    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var swordRaise: Bool = false

    var body: some View {
        let shieldSize = mascotSize * 0.42
        let swordLength = mascotSize * 0.55

        ZStack {
            // ── Shield: covers chest, slightly offset to the mascot's left ──
            Image(systemName: "shield.fill")
                .resizable()
                .aspectRatio(contentMode: .fit)
                .frame(width: shieldSize, height: shieldSize)
                .foregroundStyle(
                    LinearGradient(
                        colors: [
                            Color(red: 0.55, green: 0.62, blue: 0.78),  // steel
                            Color(red: 0.32, green: 0.38, blue: 0.52),
                        ],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    )
                )
                .overlay(
                    // Cross emblem on the shield
                    Image(systemName: "plus")
                        .resizable()
                        .aspectRatio(contentMode: .fit)
                        .frame(width: shieldSize * 0.4, height: shieldSize * 0.4)
                        .foregroundStyle(Color.white.opacity(0.85))
                        .offset(y: -shieldSize * 0.05)
                )
                .shadow(color: .black.opacity(0.35), radius: 4, x: 1, y: 2)
                .offset(x: -mascotSize * 0.18, y: mascotSize * 0.02)

            // ── Sword: held to mascot's right, blade pointing up-right ──
            // Built from a thin rectangle (blade) + small crossguard +
            // round pommel at the bottom.
            VStack(spacing: 0) {
                // Blade
                Capsule()
                    .fill(
                        LinearGradient(
                            colors: [
                                Color(white: 0.95),
                                Color(white: 0.70),
                            ],
                            startPoint: .leading,
                            endPoint: .trailing
                        )
                    )
                    .frame(width: swordLength * 0.10, height: swordLength * 0.65)
                    .overlay(
                        Capsule()
                            .stroke(Color(white: 0.45), lineWidth: 0.5)
                    )
                // Crossguard
                Rectangle()
                    .fill(Color(red: 0.60, green: 0.45, blue: 0.20))
                    .frame(width: swordLength * 0.30, height: swordLength * 0.05)
                // Hilt
                Capsule()
                    .fill(Color(red: 0.40, green: 0.25, blue: 0.10))
                    .frame(width: swordLength * 0.07, height: swordLength * 0.18)
                // Pommel
                Circle()
                    .fill(Color(red: 0.80, green: 0.65, blue: 0.30))
                    .frame(width: swordLength * 0.10, height: swordLength * 0.10)
            }
            .rotationEffect(.degrees(swordRaise ? -10 : 5))
            .offset(
                x: mascotSize * 0.30,
                y: -mascotSize * 0.10 - (swordRaise ? mascotSize * 0.04 : 0)
            )
            .shadow(color: .black.opacity(0.30), radius: 3, x: 1, y: 2)
        }
        .onAppear { startSwordIdle() }
        .onChange(of: mascotState) { _, _ in
            if mascotState == .celebrating {
                triggerVictoryRaise()
            } else {
                startSwordIdle()
            }
        }
        .accessibilityHidden(true)
    }

    private func startSwordIdle() {
        guard !reduceMotion else { return }
        swordRaise = false
        // Subtle idle sway
        withAnimation(.easeInOut(duration: 2.5).repeatForever(autoreverses: true)) {
            swordRaise = true
        }
    }

    private func triggerVictoryRaise() {
        guard !reduceMotion else { return }
        withAnimation(.spring(response: 0.4, dampingFraction: 0.55).repeatCount(2, autoreverses: true)) {
            swordRaise = true
        }
    }
}

#Preview {
    ZStack {
        SquatBlobIcon(isActive: true, size: 120)
        ShieldAndSwordView(mascotSize: 120, mascotState: .idle)
    }
    .padding(40)
    .background(Color(red: 0.95, green: 0.95, blue: 0.97))
}
