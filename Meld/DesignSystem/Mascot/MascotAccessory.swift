import SwiftUI

// MARK: - Mascot Accessory System
//
// Users earn accessories (Armothy muscle arms, pounding heart, shield/sword,
// crown, chef hat, glasses) as they hit milestones. Each accessory is a
// distinct visual layer that overlays on top of (or behind) the base
// SquatBlob mascot. The contrast between the chunky pixel-art body and
// fluid organic accessories is the visual joke that anchors the system.
//
// ARCHITECTURE
//
// 1. `MascotAccessory` enum — the catalog. rawValue strings match the
//    backend `accessory_id` column. Adding a new accessory means adding
//    one enum case + one render struct.
//
// 2. `MascotAccessoryRenderer` — the runtime dispatch. Given an accessory
//    case + base size + animation state, it returns the SwiftUI view for
//    that accessory.
//
// 3. Each individual accessory file (e.g. `ArmothyArmsView.swift`) is a
//    self-contained SwiftUI view that knows how to draw itself relative
//    to the 10×7 mascot grid. They take a `mascotSize: CGFloat` and
//    compute their own positions from there.
//
// 4. `MeldMascot` (separate file) is the single component every call
//    site uses. It composes the base + accessories + animations.
//
// ANCHORING
//
// The base mascot is rendered in a Canvas with a 10-column × 7-row grid.
// Accessories anchor by fractional position: (0.5, 0.0) is top-center,
// (0.0, 0.5) is left-middle, etc. This stays correct across mascot
// sizes from 24pt (chat avatar) to 1024pt (app icon source).
//
// Z-ORDER
//
// Each accessory declares whether it draws BEHIND the body (.under,
// e.g. cape, halo, aura) or ON TOP of the body (.over, e.g. crown, arms,
// sword). MeldMascot composites them in the right order.

// MARK: - Catalog

enum MascotAccessory: String, CaseIterable, Codable, Identifiable, Sendable {
    /// Comically organic muscle arms — the centerpiece. Pixel-art body
    /// + fluid Path-based biceps. Flexes when mascot is celebrating.
    case armothyArms = "armothy_arms"

    /// Animated heart pulsing on the chest. Beats faster when mascot
    /// is in concerned/error states (sympathetic nervous system bit).
    case poundingHeart = "pounding_heart"

    /// Defensive stance — shield in front of body, sword raised.
    /// "First chat sent" welcome unlock.
    case shieldAndSword = "shield_and_sword"

    /// Crown with flickering flame on top. The "you are committed" tier
    /// for long activity streaks.
    case fireCrown = "fire_crown"

    /// Tall white chef hat. For meal-logging engagement.
    case chefHat = "chef_hat"

    /// Round wireframe spectacles. For coach-conversation engagement.
    case scholarGlasses = "scholar_glasses"

    var id: String { rawValue }

    /// Display name for the wardrobe screen.
    var displayName: String {
        switch self {
        case .armothyArms: "Armothy Arms"
        case .poundingHeart: "Pounding Heart"
        case .shieldAndSword: "Shield & Sword"
        case .fireCrown: "Fire Crown"
        case .chefHat: "Chef Hat"
        case .scholarGlasses: "Scholar Glasses"
        }
    }

    /// Short flavor text shown in the wardrobe + unlock celebration.
    var flavorText: String {
        switch self {
        case .armothyArms:
            "You showed up. Your coach noticed. Now you have biceps."
        case .poundingHeart:
            "Your recovery is trending up. Your mascot can feel it."
        case .shieldAndSword:
            "You opened the chat. The coach is ready."
        case .fireCrown:
            "Seven days in a row. You're on fire."
        case .chefHat:
            "You logged enough meals to earn the hat."
        case .scholarGlasses:
            "You and the coach have been talking. A lot."
        }
    }

    /// Plain-language unlock criteria — shown on locked accessories
    /// in the wardrobe so the user knows what to do.
    var unlockHint: String {
        switch self {
        case .armothyArms: "3 days of activity in a row"
        case .poundingHeart: "1 high-recovery day this week"
        case .shieldAndSword: "Send your first chat to the coach"
        case .fireCrown: "7 days of activity in a row"
        case .chefHat: "Log 5 meals total"
        case .scholarGlasses: "Send 10 chat messages to the coach"
        }
    }
}

// MARK: - Z-order

enum MascotAccessoryZOrder {
    /// Drawn BEFORE the body — appears behind the mascot.
    /// Use for: capes, halos, ambient aura effects.
    case under
    /// Drawn AFTER the body — appears on top of the mascot.
    /// Use for: crowns, hats, arms, weapons, glasses, hearts.
    case over
}

extension MascotAccessory {
    /// Where this accessory sits in the render stack relative to the
    /// base mascot body.
    var zOrder: MascotAccessoryZOrder {
        switch self {
        case .armothyArms: .over
        case .poundingHeart: .over
        case .shieldAndSword: .over
        case .fireCrown: .over
        case .chefHat: .over
        case .scholarGlasses: .over
        }
    }
}

// MARK: - Runtime renderer
//
// Single dispatch point that takes an accessory case + the base mascot
// size + the current animation state and returns the right SwiftUI view.
// MeldMascot calls this once per equipped accessory.

struct MascotAccessoryRenderer: View {
    let accessory: MascotAccessory
    let mascotSize: CGFloat
    let state: MascotState

    var body: some View {
        switch accessory {
        case .armothyArms:
            ArmothyArmsView(mascotSize: mascotSize, mascotState: state)
        case .poundingHeart:
            PoundingHeartView(mascotSize: mascotSize, mascotState: state)
        case .shieldAndSword:
            ShieldAndSwordView(mascotSize: mascotSize, mascotState: state)
        case .fireCrown:
            FireCrownView(mascotSize: mascotSize, mascotState: state)
        case .chefHat:
            ChefHatView(mascotSize: mascotSize, mascotState: state)
        case .scholarGlasses:
            ScholarGlassesView(mascotSize: mascotSize, mascotState: state)
        }
    }
}
