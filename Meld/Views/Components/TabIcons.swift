import SwiftUI

// MARK: - Squat Blob Mascot Icon (Pixel Art)
// Exact recreation from Figma node data (frame 25:2, B variant).
// Grid: 10 columns x 7 rows of 14x14 rounded rectangles.
// Corner radius: 2px (proportional ~14% of cell size).
// Cells are edge-to-edge on a 14px grid, NO explicit gaps.
// Visual spacing comes solely from the rounded corners.
// Body: #E5A84B (Warm Amber) | Eyes: #6B4B1A (Dark Brown)
// Changed from green (#33BA99) to avoid Android mascot association.
// Amber creates triadic harmony with purple (brand) and green (accent).

struct SquatBlobIcon: View {
    var isActive: Bool = false
    var size: CGFloat = 26

    // Exact pixel grid from Figma metadata
    // 0 = empty, 1 = body (#E5A84B), 2 = eye (#6B4B1A)
    private static let grid: [[Int]] = [
        [0, 0, 1, 1, 1, 1, 1, 1, 0, 0],  // row 0
        [0, 1, 1, 1, 1, 1, 1, 1, 1, 0],  // row 1
        [1, 1, 1, 2, 1, 1, 2, 1, 1, 1],  // row 2 (eyes at col 3, 6)
        [1, 1, 1, 1, 1, 1, 1, 1, 1, 1],  // row 3
        [1, 1, 1, 1, 1, 1, 1, 1, 1, 1],  // row 4
        [0, 1, 1, 1, 1, 1, 1, 1, 1, 0],  // row 5
        [0, 0, 1, 1, 0, 0, 1, 1, 0, 0],  // row 6 (feet)
    ]

    private static let cols = 10
    private static let rows = 7

    // Mascot colors: Warm Amber (triadic with purple brand + green accent)
    private static let bodyColor = Color.hex(0xE5A84B)
    private static let eyeColor = Color.hex(0x6B4B1A)

    var body: some View {
        Canvas { context, canvasSize in
            let cellW = canvasSize.width / CGFloat(Self.cols)
            let cellH = canvasSize.height / CGFloat(Self.rows)
            // Corner radius proportional to cell size (~14% of cell, matching 2/14 from Figma)
            let cr = min(cellW, cellH) * 0.14

            for row in 0..<Self.rows {
                for col in 0..<Self.cols {
                    let cell = Self.grid[row][col]
                    guard cell != 0 else { continue }

                    let rect = CGRect(
                        x: CGFloat(col) * cellW,
                        y: CGFloat(row) * cellH,
                        width: cellW,
                        height: cellH
                    )

                    var path = Path()
                    path.addRoundedRect(
                        in: rect,
                        cornerSize: CGSize(width: cr, height: cr),
                        style: .continuous
                    )

                    let color: Color = cell == 2 ? Self.eyeColor : Self.bodyColor
                    context.fill(path, with: .color(isActive ? color : color.opacity(0.45)))
                }
            }
        }
        .frame(width: size, height: size)
        .accessibilityLabel("Meld coach mascot")
        .accessibilityHidden(!isActive) // Only announce when active
    }
}

#Preview("Sizes") {
    HStack(spacing: 24) {
        VStack {
            SquatBlobIcon(isActive: true, size: 26)
            Text("26pt").font(.caption2)
        }
        VStack {
            SquatBlobIcon(isActive: false, size: 26)
            Text("26pt off").font(.caption2)
        }
        VStack {
            SquatBlobIcon(isActive: true, size: 48)
            Text("48pt").font(.caption2)
        }
        VStack {
            SquatBlobIcon(isActive: true, size: 128)
            Text("128pt").font(.caption2)
        }
    }
    .padding()
}
