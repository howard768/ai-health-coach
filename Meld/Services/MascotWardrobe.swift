import Foundation
import Observation

// MARK: - MascotWardrobe — global mascot accessory state
//
// Single source of truth for which accessories the user has unlocked
// and which are currently equipped on the home-screen mascot. Backed by
// the GET /api/user/mascot endpoint; mutated via PATCH and POST /unlock.
//
// USAGE
//
//   // Read (synchronously, from any view):
//   if MascotWardrobe.shared.equipped.contains(.armothyArms) { ... }
//
//   // Refresh from backend (call from app lifecycle / pull-to-refresh):
//   await MascotWardrobe.shared.refresh()
//
//   // Equip / unequip:
//   try await MascotWardrobe.shared.setEquipped(.armothyArms, equipped: true)
//
//   // Manually unlock (used by the wardrobe debug toggle today; later
//   // replaced by server-side achievement detectors):
//   try await MascotWardrobe.shared.unlock(.armothyArms)
//
// MeldMascot reads from this singleton by default. Pass an explicit
// `accessories:` parameter to override (useful for thumbnails + previews
// in the wardrobe screen itself).
//
// THREADING
//
// @MainActor + @Observable. All mutations happen on the main actor so
// SwiftUI can observe the published properties without bridging.

@MainActor
@Observable
final class MascotWardrobe {
    static let shared = MascotWardrobe()

    /// Every accessory the user has ever earned. Superset of `equipped`.
    private(set) var unlocked: Set<MascotAccessory> = []

    /// Currently equipped accessories — what shows up on MeldMascot.
    /// A user can equip multiple at once; ordering is fixed by enum case.
    private(set) var equipped: Set<MascotAccessory> = []

    /// True when an API call is in flight, so the wardrobe screen can
    /// show a spinner.
    private(set) var isLoading: Bool = false

    /// Most recent newly-unlocked accessory — wired to the celebration
    /// banner. Set by `unlock(_:)` when the backend reports it was the
    /// first time. Caller is responsible for clearing this once shown.
    var lastUnlocked: MascotAccessory? = nil

    private init() {}

    // MARK: - Backend sync

    /// Pull the latest state from /api/user/mascot. Call on app launch
    /// and when the user opens the wardrobe screen.
    func refresh() async {
        isLoading = true
        defer { isLoading = false }
        do {
            let state = try await APIClient.shared.fetchMascotState()
            apply(state)
        } catch {
            Log.api.error("MascotWardrobe.refresh failed: \(error.localizedDescription)")
        }
    }

    /// Equip or unequip an already-unlocked accessory. Optimistic — the
    /// local state updates immediately and the backend write is fire-and-
    /// confirm. On error, refreshes from backend to restore consistency.
    func setEquipped(_ accessory: MascotAccessory, equipped newValue: Bool) async {
        guard unlocked.contains(accessory) else {
            Log.api.warning("Tried to equip un-unlocked accessory: \(accessory.rawValue)")
            return
        }

        // Optimistic update
        if newValue {
            equipped.insert(accessory)
        } else {
            equipped.remove(accessory)
        }

        do {
            let state = try await APIClient.shared.updateMascotEquip(
                accessoryId: accessory.rawValue,
                equipped: newValue
            )
            apply(state)
        } catch {
            Log.api.error("setEquipped failed for \(accessory.rawValue): \(error.localizedDescription)")
            await refresh()  // Restore consistency
        }
    }

    /// Manually unlock an accessory. Idempotent: returns true the FIRST
    /// time, false on subsequent calls. Caller can use the return value
    /// to decide whether to show the celebration UI.
    @discardableResult
    func unlock(_ accessory: MascotAccessory) async -> Bool {
        do {
            let response = try await APIClient.shared.unlockMascotAccessory(
                accessoryId: accessory.rawValue
            )
            apply(response.state)
            if response.newly_unlocked {
                lastUnlocked = accessory
            }
            return response.newly_unlocked
        } catch {
            Log.api.error("unlock failed for \(accessory.rawValue): \(error.localizedDescription)")
            return false
        }
    }

    // MARK: - Internal

    /// Apply a fresh APIMascotState snapshot to local properties.
    /// Unknown accessory_id strings (e.g. shipped on a newer iOS build
    /// than what's installed) are silently ignored.
    private func apply(_ state: APIMascotState) {
        unlocked = Set(state.unlocked.compactMap { MascotAccessory(rawValue: $0) })
        equipped = Set(state.equipped.compactMap { MascotAccessory(rawValue: $0) })
    }
}
