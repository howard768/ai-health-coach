import SwiftUI
import UIKit

// MARK: - Meld Design System Haptic Feedback
// Wraps UIKit feedback generators in a SwiftUI-friendly API.
// Use sparingly — haptics should feel intentional, not noisy.

@MainActor
enum DSHaptic {

    /// Light tap — card taps, subtle confirmations
    static func light() {
        let generator = UIImpactFeedbackGenerator(style: .light)
        generator.prepare()
        generator.impactOccurred()
    }

    /// Medium tap — button presses, meaningful selections
    static func medium() {
        let generator = UIImpactFeedbackGenerator(style: .medium)
        generator.prepare()
        generator.impactOccurred()
    }

    /// Heavy tap — important actions, destructive confirmations
    static func heavy() {
        let generator = UIImpactFeedbackGenerator(style: .heavy)
        generator.prepare()
        generator.impactOccurred()
    }

    /// Selection tick — tab changes, picker scrolls, chip selection
    static func selection() {
        let generator = UISelectionFeedbackGenerator()
        generator.prepare()
        generator.selectionChanged()
    }

    /// Success — positive feedback, goal reached, insight delivered
    static func success() {
        let generator = UINotificationFeedbackGenerator()
        generator.prepare()
        generator.notificationOccurred(.success)
    }

    /// Warning — caution moment, approaching limit
    static func warning() {
        let generator = UINotificationFeedbackGenerator()
        generator.prepare()
        generator.notificationOccurred(.warning)
    }

    /// Error — failure, invalid input
    static func error() {
        let generator = UINotificationFeedbackGenerator()
        generator.prepare()
        generator.notificationOccurred(.error)
    }
}

// MARK: - Sensory Feedback View Modifier (iOS 17+)

extension View {
    /// Add haptic feedback triggered by a value change
    func dsHaptic<T: Equatable>(_ style: SensoryFeedback, trigger: T) -> some View {
        self.sensoryFeedback(style, trigger: trigger)
    }
}
