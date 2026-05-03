import SwiftUI

// MARK: - Meld Design System Motion / Animation Tokens
// Spring-based animations for natural, physical feel.
// Organized by intent, not technical parameters.

enum DSMotion {

    /// Fast spring for toggles, checkmarks, micro-interactions
    /// Response: 0.2s, Damping: 0.9 (minimal bounce)
    static let micro = Animation.spring(response: 0.2, dampingFraction: 0.9)

    /// Default spring for standard transitions, card reveals
    /// Response: 0.35s, Damping: 0.85 (subtle bounce)
    static let standard = Animation.spring(response: 0.35, dampingFraction: 0.85)

    /// Emphasis spring for modals, sheets, important reveals
    /// Response: 0.5s, Damping: 0.8 (noticeable bounce)
    static let emphasis = Animation.spring(response: 0.5, dampingFraction: 0.8)

    /// Playful spring for mascot animations, celebrations
    /// Response: 0.5s, Damping: 0.65 (bouncy)
    static let bouncy = Animation.spring(response: 0.5, dampingFraction: 0.65)

    /// Quick spring for selections, tab switches, chip taps
    /// Response: 0.25s, Damping: 0.9 (snappy, minimal overshoot)
    static let snappy = Animation.spring(response: 0.25, dampingFraction: 0.9)

    /// Smooth ease for background gradients, ambient effects
    /// Duration: 0.4s, EaseInOut
    static let smooth = Animation.easeInOut(duration: 0.4)

    /// Slow ambient animation for background orbs, breathing effects
    /// Duration: 2.0s, EaseInOut
    static let ambient = Animation.easeInOut(duration: 2.0)

    // MARK: - Duration Constants

    enum Duration {
        /// 0.15s, Instant feedback
        static let instant: Double = 0.15
        /// 0.25s, Quick transitions
        static let quick: Double = 0.25
        /// 0.35s, Standard transitions
        static let standard: Double = 0.35
        /// 0.5s, Emphasis transitions
        static let emphasis: Double = 0.5
        /// 1.0s, Slow reveals
        static let slow: Double = 1.0
    }
}
