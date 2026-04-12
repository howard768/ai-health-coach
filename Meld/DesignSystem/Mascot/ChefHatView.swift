import SwiftUI

// MARK: - Chef Hat accessory
//
// Tall white poofy chef toque on top of the mascot's head. Earned for
// logging meals consistently. Built from two stacked shapes — a wide
// rounded "puff" at the top and a narrow band at the bottom that meets
// the head.
//
// On the celebrating state, the puff bobs slightly so the hat looks
// alive without being distracting.

struct ChefHatView: View {
    let mascotSize: CGFloat
    let mascotState: MascotState

    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var bob: Bool = false

    var body: some View {
        let hatWidth = mascotSize * 0.55
        let hatHeight = mascotSize * 0.62
        let bandHeight = mascotSize * 0.10

        VStack(spacing: 0) {
            // Puffy top — three bumps using overlapping circles for the
            // classic toque silhouette
            ZStack {
                // Center bump (largest)
                Circle()
                    .fill(.white)
                    .frame(width: hatWidth * 0.62, height: hatWidth * 0.62)
                    .offset(y: 0)
                // Left bump
                Circle()
                    .fill(.white)
                    .frame(width: hatWidth * 0.48, height: hatWidth * 0.48)
                    .offset(x: -hatWidth * 0.27, y: hatWidth * 0.05)
                // Right bump
                Circle()
                    .fill(.white)
                    .frame(width: hatWidth * 0.48, height: hatWidth * 0.48)
                    .offset(x: hatWidth * 0.27, y: hatWidth * 0.05)
            }
            .frame(width: hatWidth, height: hatHeight - bandHeight)
            .shadow(color: .black.opacity(0.15), radius: 3, x: 0, y: 1)
            .scaleEffect(bob ? 1.04 : 1.0, anchor: .bottom)

            // Bottom band — flat white cylinder where the hat meets the head
            RoundedRectangle(cornerRadius: bandHeight * 0.4, style: .continuous)
                .fill(.white)
                .frame(width: hatWidth * 0.78, height: bandHeight)
                .overlay(
                    RoundedRectangle(cornerRadius: bandHeight * 0.4, style: .continuous)
                        .stroke(Color.black.opacity(0.06), lineWidth: 1)
                )
                .shadow(color: .black.opacity(0.10), radius: 2, x: 0, y: 1)
                .offset(y: -bandHeight * 0.15)  // Pull up to overlap puff
        }
        .offset(y: -mascotSize * 0.55)
        .onAppear { startBob() }
        .accessibilityHidden(true)
    }

    private func startBob() {
        guard !reduceMotion else { return }
        bob = false
        withAnimation(.easeInOut(duration: 2.2).repeatForever(autoreverses: true)) {
            bob = true
        }
    }
}

#Preview {
    ZStack {
        SquatBlobIcon(isActive: true, size: 120)
        ChefHatView(mascotSize: 120, mascotState: .idle)
    }
    .padding(40)
    .background(Color(red: 0.95, green: 0.95, blue: 0.97))
}
