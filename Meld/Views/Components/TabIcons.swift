import SwiftUI

// MARK: - Squat Blob Mascot Icon (Pixel Art)
// Exact recreation from Figma node data (frame 25:2, B variant).
// Grid: 10 columns x 7 rows of 14x14 rounded rectangles.
// Corner radius: 2px (proportional ~14% of cell size).
// Cells are edge-to-edge on a 14px grid — NO explicit gaps.
// Visual spacing comes solely from the rounded corners.
// Body: #33BA99 | Eyes: #0F382E (row 2, cols 3 & 6)

struct SquatBlobIcon: View {
    var isActive: Bool = false
    var size: CGFloat = 26

    // Exact pixel grid from Figma metadata
    // 0 = empty, 1 = body (#33BA99), 2 = eye (#0F382E)
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

    // Figma exact colors
    private static let bodyColor = Color.hex(0x33BA99)
    private static let eyeColor = Color.hex(0x0F382E)

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
