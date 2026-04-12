import SwiftUI

// MARK: - Fire Crown accessory
//
// Gold crown with three flickering flame tips on top of the mascot's
// head. The "you are committed" tier — earned for hitting a 7-day
// activity streak.
//
// Crown is built from a Path (5-point crenellation shape) so it scales
// cleanly. Flames are three small Path-based teardrops that flicker
// (random scale + opacity) on a fast loop.

struct FireCrownView: View {
    let mascotSize: CGFloat
    let mascotState: MascotState

    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var flicker: Bool = false

    private static let goldFill = LinearGradient(
        colors: [
            Color(red: 1.00, green: 0.86, blue: 0.30),
            Color(red: 0.85, green: 0.62, blue: 0.10),
        ],
        startPoint: .top,
        endPoint: .bottom
    )
    private static let goldStroke = Color(red: 0.55, green: 0.38, blue: 0.05)

    private static let flameFill = LinearGradient(
        colors: [
            Color(red: 1.00, green: 0.92, blue: 0.30),
            Color(red: 1.00, green: 0.45, blue: 0.05),
            Color(red: 0.85, green: 0.10, blue: 0.05),
        ],
        startPoint: .top,
        endPoint: .bottom
    )

    var body: some View {
        let crownWidth = mascotSize * 0.55
        let crownHeight = mascotSize * 0.22
        let flameSize = mascotSize * 0.14

        VStack(spacing: 0) {
            // Three flames above the crown
            HStack(spacing: crownWidth * 0.08) {
                FlameShape()
                    .fill(Self.flameFill)
                    .frame(width: flameSize * 0.85, height: flameSize)
                    .scaleEffect(flicker ? 0.92 : 1.05, anchor: .bottom)
                    .opacity(flicker ? 0.85 : 1.0)
                FlameShape()
                    .fill(Self.flameFill)
                    .frame(width: flameSize, height: flameSize * 1.2)
                    .scaleEffect(flicker ? 1.08 : 0.94, anchor: .bottom)
                FlameShape()
                    .fill(Self.flameFill)
                    .frame(width: flameSize * 0.85, height: flameSize)
                    .scaleEffect(flicker ? 0.95 : 1.08, anchor: .bottom)
                    .opacity(flicker ? 0.95 : 0.88)
            }
            .shadow(color: Color.orange.opacity(0.5), radius: flameSize * 0.4, y: 0)

            // Crown body — crenellated top with a flat band at bottom
            CrownShape()
                .fill(Self.goldFill)
                .overlay(
                    CrownShape()
                        .stroke(Self.goldStroke, lineWidth: 1.2)
                )
                .frame(width: crownWidth, height: crownHeight)
                .shadow(color: .black.opacity(0.30), radius: 2, x: 0, y: 1)
        }
        // Sit on top of the head
        .offset(y: -mascotSize * 0.50)
        .onAppear { startFlicker() }
        .accessibilityHidden(true)
    }

    private func startFlicker() {
        guard !reduceMotion else { return }
        flicker = false
        withAnimation(.easeInOut(duration: 0.18).repeatForever(autoreverses: true)) {
            flicker = true
        }
    }
}

// MARK: - Shapes

private struct CrownShape: Shape {
    func path(in rect: CGRect) -> Path {
        var p = Path()
        let w = rect.width
        let h = rect.height

        // 5 spikes on top, 4 valleys between them, flat band on bottom
        // Bottom-left → up to first spike → valley → second spike → ... → bottom-right
        p.move(to: CGPoint(x: 0, y: h))
        p.addLine(to: CGPoint(x: 0, y: h * 0.45))               // left edge
        p.addLine(to: CGPoint(x: w * 0.10, y: 0))               // spike 1 (left)
        p.addLine(to: CGPoint(x: w * 0.20, y: h * 0.40))        // valley 1
        p.addLine(to: CGPoint(x: w * 0.30, y: h * 0.05))        // spike 2
        p.addLine(to: CGPoint(x: w * 0.42, y: h * 0.40))        // valley 2
        p.addLine(to: CGPoint(x: w * 0.50, y: 0))               // spike 3 (center, tallest)
        p.addLine(to: CGPoint(x: w * 0.58, y: h * 0.40))        // valley 3
        p.addLine(to: CGPoint(x: w * 0.70, y: h * 0.05))        // spike 4
        p.addLine(to: CGPoint(x: w * 0.80, y: h * 0.40))        // valley 4
        p.addLine(to: CGPoint(x: w * 0.90, y: 0))               // spike 5 (right)
        p.addLine(to: CGPoint(x: w, y: h * 0.45))               // right edge
        p.addLine(to: CGPoint(x: w, y: h))                      // bottom-right
        p.closeSubpath()
        return p
    }
}

private struct FlameShape: Shape {
    func path(in rect: CGRect) -> Path {
        var p = Path()
        let w = rect.width
        let h = rect.height

        // Teardrop pointing up: round bottom, narrowing top with a slight S curve
        p.move(to: CGPoint(x: w / 2, y: 0))                              // top tip
        p.addQuadCurve(
            to: CGPoint(x: w, y: h * 0.55),
            control: CGPoint(x: w * 0.95, y: h * 0.20)
        )
        p.addQuadCurve(
            to: CGPoint(x: w / 2, y: h),
            control: CGPoint(x: w, y: h)
        )
        p.addQuadCurve(
            to: CGPoint(x: 0, y: h * 0.55),
            control: CGPoint(x: 0, y: h)
        )
        p.addQuadCurve(
            to: CGPoint(x: w / 2, y: 0),
            control: CGPoint(x: w * 0.05, y: h * 0.20)
        )
        p.closeSubpath()
        return p
    }
}

#Preview {
    ZStack {
        SquatBlobIcon(isActive: true, size: 120)
        FireCrownView(mascotSize: 120, mascotState: .idle)
    }
    .padding(40)
    .background(Color(red: 0.95, green: 0.95, blue: 0.97))
}
