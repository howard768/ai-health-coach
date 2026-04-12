import SwiftUI

// MARK: - Scholar Glasses accessory
//
// Round wireframe spectacles centered over the mascot's eyes. The
// SquatBlob's eyes live at row 2, columns 3 and 6 of the 10×7 grid, so
// each lens centers at fractional X = 0.35 and 0.65 respectively, with
// the bridge connecting them at row-2 vertical center (~0.30 down).
//
// Built from two stroked Circles + a small Path bridge. No animation —
// glasses just sit there. The point is the visual joke of the studious
// look on the chunky body.

struct ScholarGlassesView: View {
    let mascotSize: CGFloat
    let mascotState: MascotState

    var body: some View {
        let lensRadius = mascotSize * 0.13
        let bridgeWidth = mascotSize * 0.06
        let frameStroke = max(1.5, mascotSize * 0.025)

        Canvas { context, canvasSize in
            let centerX = canvasSize.width / 2
            // Eye row in the 10x7 grid is row 2 (zero-indexed), so vertical
            // center is at (2 + 0.5) / 7 = ~0.357 down. Offset slightly
            // up so the glasses sit ON the eyes rather than below them.
            let eyeY = canvasSize.height * 0.35
            let lensSeparation = mascotSize * 0.30  // distance between lens centers

            let leftLensX = centerX - lensSeparation / 2
            let rightLensX = centerX + lensSeparation / 2

            // ── Left lens ──
            var leftPath = Path()
            leftPath.addArc(
                center: CGPoint(x: leftLensX, y: eyeY),
                radius: lensRadius,
                startAngle: .degrees(0),
                endAngle: .degrees(360),
                clockwise: false
            )
            context.stroke(
                leftPath,
                with: .color(.black.opacity(0.85)),
                style: StrokeStyle(lineWidth: frameStroke)
            )
            // Subtle lens shine
            context.fill(
                Path(ellipseIn: CGRect(
                    x: leftLensX - lensRadius * 0.85,
                    y: eyeY - lensRadius * 0.85,
                    width: lensRadius * 1.7,
                    height: lensRadius * 1.7
                )),
                with: .color(.white.opacity(0.18))
            )

            // ── Right lens ──
            var rightPath = Path()
            rightPath.addArc(
                center: CGPoint(x: rightLensX, y: eyeY),
                radius: lensRadius,
                startAngle: .degrees(0),
                endAngle: .degrees(360),
                clockwise: false
            )
            context.stroke(
                rightPath,
                with: .color(.black.opacity(0.85)),
                style: StrokeStyle(lineWidth: frameStroke)
            )
            context.fill(
                Path(ellipseIn: CGRect(
                    x: rightLensX - lensRadius * 0.85,
                    y: eyeY - lensRadius * 0.85,
                    width: lensRadius * 1.7,
                    height: lensRadius * 1.7
                )),
                with: .color(.white.opacity(0.18))
            )

            // ── Bridge ──
            var bridge = Path()
            bridge.move(to: CGPoint(x: leftLensX + lensRadius * 0.95, y: eyeY))
            bridge.addLine(to: CGPoint(x: rightLensX - lensRadius * 0.95, y: eyeY))
            context.stroke(
                bridge,
                with: .color(.black.opacity(0.85)),
                style: StrokeStyle(lineWidth: frameStroke, lineCap: .round)
            )

            // ── Temple arms (small lines extending past each lens) ──
            var leftTemple = Path()
            leftTemple.move(to: CGPoint(x: leftLensX - lensRadius * 0.95, y: eyeY))
            leftTemple.addLine(to: CGPoint(x: leftLensX - lensRadius * 1.4, y: eyeY + lensRadius * 0.15))
            context.stroke(
                leftTemple,
                with: .color(.black.opacity(0.85)),
                style: StrokeStyle(lineWidth: frameStroke, lineCap: .round)
            )

            var rightTemple = Path()
            rightTemple.move(to: CGPoint(x: rightLensX + lensRadius * 0.95, y: eyeY))
            rightTemple.addLine(to: CGPoint(x: rightLensX + lensRadius * 1.4, y: eyeY + lensRadius * 0.15))
            context.stroke(
                rightTemple,
                with: .color(.black.opacity(0.85)),
                style: StrokeStyle(lineWidth: frameStroke, lineCap: .round)
            )
        }
        .frame(width: mascotSize, height: mascotSize)
        .accessibilityHidden(true)
    }
}

#Preview {
    ZStack {
        SquatBlobIcon(isActive: true, size: 120)
        ScholarGlassesView(mascotSize: 120, mascotState: .idle)
    }
    .padding(40)
    .background(Color(red: 0.95, green: 0.95, blue: 0.97))
}
