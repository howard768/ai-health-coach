import SwiftUI

// MARK: - Pounding Heart accessory
//
// Animated heart pulses on the mascot's chest. Uses an SF Symbol for the
// heart shape (rendered with the system filled glyph for crispness at any
// size) wrapped in a scale-pulse animation. The pulse rate is faster when
// the mascot is in a concerned/error state — visualizing the sympathetic
// nervous system bit.

struct PoundingHeartView: View {
    let mascotSize: CGFloat
    let mascotState: MascotState

    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var beat: Bool = false

    var body: some View {
        // Heart sits center-chest, slightly above the mascot's optical
        // middle so it reads as "on the body" not "in front of."
        let heartSize = mascotSize * 0.32

        Image(systemName: "heart.fill")
            .resizable()
            .aspectRatio(contentMode: .fit)
            .frame(width: heartSize, height: heartSize)
            .foregroundStyle(
                LinearGradient(
                    colors: [
                        Color(red: 0.95, green: 0.30, blue: 0.40),
                        Color(red: 0.85, green: 0.18, blue: 0.30),
                    ],
                    startPoint: .top,
                    endPoint: .bottom
                )
            )
            .shadow(color: Color.red.opacity(0.5), radius: heartSize * 0.15, x: 0, y: 0)
            // Center on the mascot's chest area (shifted slightly up)
            .offset(y: -mascotSize * 0.05)
            .scaleEffect(beat ? 1.18 : 0.92)
            .onAppear { startPulse() }
            .onChange(of: mascotState) { _, _ in startPulse() }
            .accessibilityHidden(true)
    }

    private func startPulse() {
        guard !reduceMotion else { return }
        beat = false
        // Concerned/error states beat faster (panicked heart);
        // everything else is a calm steady rhythm.
        let duration: Double = switch mascotState {
        case .concerned, .error: 0.35
        case .celebrating: 0.45
        default: 0.75
        }
        withAnimation(.easeInOut(duration: duration).repeatForever(autoreverses: true)) {
            beat = true
        }
    }
}

#Preview {
    ZStack {
        SquatBlobIcon(isActive: true, size: 96)
        PoundingHeartView(mascotSize: 96, mascotState: .idle)
    }
    .padding()
    .background(Color(red: 0.95, green: 0.95, blue: 0.97))
}
