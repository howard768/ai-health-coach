import SwiftUI

// MARK: - Armothy Arms — the centerpiece accessory
//
// Comically organic muscle arms grafted onto the chunky pixel-art body.
// Inspired by the Armothy character (Dribbble #6589148) — exaggerated
// biceps, smug curves, NOT pixelated. The contrast between the blocky
// SquatBlob torso and the fluid Path-rendered arms is the entire joke.
//
// DESIGN DECISIONS
//
// - Arms attach at the body's "shoulder" level. The base mascot grid
//   is 10×7; the body's widest row is row 3 (zero-indexed), columns 0-9.
//   So shoulders anchor at (0.0, 3.5/7) on the left and (1.0, 3.5/7)
//   on the right, in fractional coordinates of the mascot bounds.
//
// - Each arm is one filled Path with a darker stroke outline (cartoon
//   punch). The bicep is the dominant volume; the forearm + fist are
//   smaller. Arms hang in a "ready to flex" pose by default and snap
//   into a hard flex when mascot state goes to .celebrating.
//
// - Color: matches the body Warm Amber (#E5A84B) so the arms read as
//   part of the same character, not stuck-on. Outline is a darker
//   shade of the same hue (#A87527) for definition without going black.
//
// - Size: arms extend ~50% of mascot width past each side. So a 100pt
//   mascot has arms reaching to about ±50pt — a 200pt total bounding
//   box. The wrapper component (MeldMascot) is responsible for
//   reserving enough horizontal padding so arms don't get clipped.

struct ArmothyArmsView: View {
    let mascotSize: CGFloat
    let mascotState: MascotState

    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var flexPhase: Bool = false

    // Body color tokens (must match SquatBlobIcon.bodyColor + a darker outline)
    private static let armColor = Color(red: 0xE5/255, green: 0xA8/255, blue: 0x4B/255)
    private static let armOutline = Color(red: 0xA8/255, green: 0x75/255, blue: 0x27/255)

    // Geometry tuning. All values are fractions of mascotSize so the
    // arms scale correctly from the 28pt chat avatar to the 96pt
    // dashboard hero.
    private struct G {
        static let shoulderY: CGFloat = 0.45      // 45% down from top
        static let armReach: CGFloat = 0.50       // arms extend 50% past each side
        static let bicepRadius: CGFloat = 0.18    // bicep is 18% of mascot wide
        static let forearmThickness: CGFloat = 0.13
        static let fistRadius: CGFloat = 0.10
        static let outlineWidth: CGFloat = 0.025
    }

    var body: some View {
        Canvas { context, canvasSize in
            // canvasSize includes the arm overflow because MeldMascot
            // gives us a frame wider than the base mascot.
            let s = mascotSize
            let centerX = canvasSize.width / 2
            let shoulderY = canvasSize.height * G.shoulderY

            // Compute the flex amount: 0.0 = relaxed, 1.0 = fully flexed
            let flex: CGFloat = {
                guard !reduceMotion else {
                    return mascotState == .celebrating ? 1.0 : 0.0
                }
                switch mascotState {
                case .celebrating: return flexPhase ? 1.0 : 0.6
                case .greeting:    return 0.4
                default:           return flexPhase ? 0.05 : 0.0
                }
            }()

            // Draw both arms — left first so right composites cleanly.
            for side in [-1.0, 1.0] {
                let sideX = centerX + CGFloat(side) * (s * 0.42)
                drawArm(
                    context: context,
                    shoulderX: sideX,
                    shoulderY: shoulderY,
                    direction: CGFloat(side),
                    flex: flex,
                    scale: s
                )
            }
        }
        .onAppear { startBreathing() }
        .onChange(of: mascotState) { _, newState in
            startBreathing()
            if newState == .celebrating {
                triggerFlex()
            }
        }
        .accessibilityHidden(true)  // Decorative
    }

    // MARK: - Arm geometry

    /// Draws one organic arm starting from the shoulder and curving out
    /// + down into a bicep, forearm, and fist.
    private func drawArm(
        context: GraphicsContext,
        shoulderX: CGFloat,
        shoulderY: CGFloat,
        direction: CGFloat,  // -1 left, +1 right
        flex: CGFloat,
        scale: CGFloat
    ) {
        let bicepR = scale * G.bicepRadius
        let forearmW = scale * G.forearmThickness
        let fistR = scale * G.fistRadius
        let reach = scale * G.armReach

        // Bicep center: out and slightly up from shoulder
        let bicepCenter = CGPoint(
            x: shoulderX + direction * (reach * 0.40),
            y: shoulderY - bicepR * 0.3 - flex * (scale * 0.08)  // rises when flexing
        )

        // Forearm tip: continues outward, then sharply UP when flexed
        // (this is the classic muscle-flex pose)
        let forearmTip = CGPoint(
            x: bicepCenter.x + direction * (bicepR * 0.6) - flex * direction * (scale * 0.08),
            y: bicepCenter.y + bicepR * 1.2 - flex * (scale * 0.50)
        )

        // Fist: just past forearm tip
        let fistCenter = CGPoint(
            x: forearmTip.x,
            y: forearmTip.y - flex * (scale * 0.04)
        )

        // ── Arm outline (organic blob: shoulder → bicep → forearm → fist) ──
        var path = Path()

        // Start at shoulder, top edge
        path.move(to: CGPoint(x: shoulderX, y: shoulderY - bicepR * 0.5))

        // Top of bicep — round bulge
        path.addQuadCurve(
            to: CGPoint(x: bicepCenter.x, y: bicepCenter.y - bicepR * 1.1),
            control: CGPoint(x: shoulderX + direction * (bicepR * 0.4),
                             y: shoulderY - bicepR * 1.4 - flex * (scale * 0.10))
        )

        // Bicep peak → forearm outer edge (this is where the flex shows)
        path.addQuadCurve(
            to: CGPoint(x: forearmTip.x + direction * forearmW * 0.7,
                        y: forearmTip.y - fistR),
            control: CGPoint(x: bicepCenter.x + direction * bicepR * 1.3,
                             y: bicepCenter.y - bicepR * 0.2 - flex * (scale * 0.05))
        )

        // Around the fist (top → outer → bottom)
        path.addArc(
            center: fistCenter,
            radius: fistR,
            startAngle: .degrees(direction > 0 ? -90 : 90),
            endAngle: .degrees(direction > 0 ? 90 : -90 + 180),
            clockwise: direction < 0
        )

        // Forearm inner edge back toward bicep underside
        path.addQuadCurve(
            to: CGPoint(x: bicepCenter.x - direction * bicepR * 0.4,
                        y: bicepCenter.y + bicepR * 0.7),
            control: CGPoint(x: forearmTip.x - direction * forearmW * 0.4,
                             y: forearmTip.y + fistR * 0.3)
        )

        // Bicep underside → back to shoulder
        path.addQuadCurve(
            to: CGPoint(x: shoulderX, y: shoulderY + bicepR * 0.5),
            control: CGPoint(x: shoulderX + direction * bicepR * 0.5,
                             y: shoulderY + bicepR * 0.4)
        )

        // Close along shoulder edge
        path.addLine(to: CGPoint(x: shoulderX, y: shoulderY - bicepR * 0.5))
        path.closeSubpath()

        // Fill + outline
        context.fill(path, with: .color(Self.armColor))
        context.stroke(
            path,
            with: .color(Self.armOutline),
            style: StrokeStyle(lineWidth: scale * G.outlineWidth, lineJoin: .round)
        )

        // ── Bicep highlight line — the muscle definition crescent ──
        // Only visible when flexed (flex > 0.3) so relaxed arms stay
        // smooth and the flex feels earned.
        if flex > 0.3 {
            var highlight = Path()
            highlight.move(to: CGPoint(
                x: bicepCenter.x - direction * bicepR * 0.5,
                y: bicepCenter.y - bicepR * 0.3
            ))
            highlight.addQuadCurve(
                to: CGPoint(
                    x: bicepCenter.x + direction * bicepR * 0.5,
                    y: bicepCenter.y + bicepR * 0.1
                ),
                control: CGPoint(
                    x: bicepCenter.x + direction * bicepR * 0.7,
                    y: bicepCenter.y - bicepR * 0.5
                )
            )
            context.stroke(
                highlight,
                with: .color(Self.armOutline.opacity(flex)),
                style: StrokeStyle(
                    lineWidth: scale * 0.018,
                    lineCap: .round
                )
            )
        }
    }

    // MARK: - Animation triggers

    private func startBreathing() {
        guard !reduceMotion else { return }
        flexPhase = false
        withAnimation(.easeInOut(duration: 1.8).repeatForever(autoreverses: true)) {
            flexPhase = true
        }
    }

    private func triggerFlex() {
        guard !reduceMotion else { return }
        flexPhase = false
        withAnimation(.spring(response: 0.35, dampingFraction: 0.55).repeatCount(3, autoreverses: true)) {
            flexPhase = true
        }
    }
}

#Preview("Armothy Arms — all states") {
    VStack(spacing: 32) {
        ForEach([MascotState.idle, .greeting, .celebrating, .concerned], id: \.self) { state in
            VStack(spacing: 8) {
                ZStack {
                    SquatBlobIcon(isActive: true, size: 96)
                    ArmothyArmsView(mascotSize: 96, mascotState: state)
                        .frame(width: 200, height: 96)
                }
                .frame(width: 200, height: 110)
                Text(state.rawValue.capitalized)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        }
    }
    .padding()
    .background(Color(red: 0.95, green: 0.95, blue: 0.97))
}
