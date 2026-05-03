import SwiftUI
import UIKit

// MARK: - Onboarding View Model
// State machine for the 5-screen onboarding flow.
// Tracks assessment data, validation, and step progression.
// Critical path: Goals + Age + ≥1 data source must be completed.

enum OnboardingStep: Int, CaseIterable {
    case welcome = 0
    case goals = 1
    case profile = 2
    case connect = 3
    case notifications = 4
    case sync = 5

    var progressIndex: Int { rawValue - 1 } // -1 for welcome (no dots)
    var totalSteps: Int { 5 } // Steps shown in progress dots (excludes welcome)
}

@Observable @MainActor
final class OnboardingViewModel {

    // MARK: - State

    var currentStep: OnboardingStep = .welcome
    var assessment = UserAssessment()
    var isComplete = false
    var isSyncing = false
    var syncProgress: Double = 0

    // Metrics fetched after sync completes (nil = no data yet → show "--")
    var fetchedSleepScore: String? = nil
    var fetchedHRV: String? = nil

    // Connection flow state
    // `pendingOuraConnect` flips true when the user taps Connect on Oura (we
    // open Safari). When the app comes back to foreground, the Connect view
    // polls /api/user/profile to see if the backend received a token and then
    // clears this flag.
    var pendingOuraConnect: Bool = false
    var healthKitAuthInFlight: Bool = false

    // Pre-filled data from HealthKit (nil until HealthKit is integrated)
    var prefilledAge: Int? = nil
    var prefilledHeightInches: Int? = nil
    var prefilledWeightLbs: Double? = nil

    // MARK: - Computed

    var canProceedFromGoals: Bool {
        !assessment.goals.isEmpty
    }

    var canProceedFromProfile: Bool {
        assessment.isProfileComplete
    }

    var canProceedFromConnect: Bool {
        assessment.hasDataSource
    }

    // MARK: - Actions

    func next() {
        guard let nextStep = OnboardingStep(rawValue: currentStep.rawValue + 1) else { return }
        withAnimation(DSMotion.standard) {
            currentStep = nextStep
        }
        DSHaptic.light()
    }

    func applyPrefill() {
        if let age = prefilledAge { assessment.age = age }
        if let h = prefilledHeightInches { assessment.heightInches = h }
        if let w = prefilledWeightLbs {
            assessment.weightLbs = w
            // Set default target weight if weight loss goal
            if assessment.goals.contains(.loseWeight) && assessment.targetWeightLbs == nil {
                assessment.targetWeightLbs = max(w - 15, 100) // Default: 15lbs less
            }
        }
    }

    func toggleGoal(_ goal: HealthGoal) {
        if assessment.goals.contains(goal) {
            assessment.goals.remove(goal)
        } else {
            assessment.goals.insert(goal)
        }
        DSHaptic.selection()
    }

    /// Connect a data source. Replaces the old "insert into set and call it
    /// connected" pattern that silently faked success without running OAuth
    /// or asking for HealthKit authorization. Now: runs the real permission
    /// flow and only marks `connectedSources` on actual success.
    func connectSource(_ source: DataSourceType) async {
        DSHaptic.light()

        switch source {
        case .appleHealth:
            // Real HealthKit auth prompt. If the user approves, pull prefill
            // data and sync to backend before marking as connected.
            guard !healthKitAuthInFlight else { return }
            healthKitAuthInFlight = true
            let granted = await HealthKitService.shared.requestAuthorization()
            healthKitAuthInFlight = false
            guard granted else {
                DSHaptic.error()
                return
            }
            assessment.connectedSources.insert(.appleHealth)
            Analytics.Onboarding.healthKitGranted()
            DSHaptic.success()

            // Prefill profile data from HealthKit + background-sync to backend.
            prefilledAge = HealthKitService.shared.getAge()
            if let weight = await HealthKitService.shared.getLatestWeight() {
                prefilledWeightLbs = weight
            }
            if let height = await HealthKitService.shared.getLatestHeight() {
                prefilledHeightInches = Int(height)
            }
            applyPrefill()
            await HealthKitService.shared.syncToBackend()

        case .oura:
            // Open the backend's Oura OAuth redirect in Safari. The backend
            // bounces to Oura, the user authorizes, Oura redirects back to
            // the backend callback, and the token lands on the user's row.
            // When the app returns to foreground, ConnectDataView polls
            // /api/user/profile.data_sources to see whether the token
            // attached, then inserts .oura into connectedSources.
            guard let appleUserId = try? await KeychainStore.shared.readAppleUserId() else {
                Log.onboarding.error("Oura connect: no apple_user_id in Keychain")
                DSHaptic.error()
                return
            }
            var components = URLComponents(
                url: APIClient.shared.serverRoot.appendingPathComponent("auth/oura"),
                resolvingAgainstBaseURL: false
            )
            components?.queryItems = [URLQueryItem(name: "state", value: appleUserId)]
            guard let authURL = components?.url else {
                Log.onboarding.error("Oura connect: failed to build auth URL")
                DSHaptic.error()
                return
            }
            pendingOuraConnect = true
            Analytics.Onboarding.ouraConnected()
            await UIApplication.shared.open(authURL)

        case .peloton, .garmin:
            // Marked "Soon" in the UI, taps should never reach here, but
            // no-op defensively so we don't insert them into connectedSources.
            break
        }
    }

    /// Poll the backend to refresh connection status for sources that need a
    /// server-side round trip to confirm (Oura OAuth). Call this when the
    /// Connect view appears and when the scene returns to foreground after
    /// the user bounced out to Safari.
    func refreshConnectionStatus() async {
        guard let profile = try? await APIClient.shared.fetchUserProfile() else { return }
        let ouraConnected = profile.data_sources.contains { source in
            source.name.lowercased().contains("oura") && source.connected
        }
        if ouraConnected {
            assessment.connectedSources.insert(.oura)
            if pendingOuraConnect {
                DSHaptic.success()
            }
        }
        pendingOuraConnect = false
    }

    func startSync() async {
        isSyncing = true
        syncProgress = 0
        Analytics.Onboarding.syncStarted()

        // Step 1: Persist the assessment to the backend. This creates the
        // User record that coach greetings, goals, and personalization read from.
        // Failing silently is OK, the user can retry from Profile settings
        // later. But we log it so we can spot repeated failures.
        do {
            // Normalize the free-form goal text: trim whitespace, collapse empty
            // to nil so the backend clears the column. Anything meaningful gets
            // persisted on the users row and flows into the coach system prompt.
            let normalizedCustomGoal: String? = {
                let trimmed = assessment.customGoalText.trimmingCharacters(in: .whitespacesAndNewlines)
                return trimmed.isEmpty ? nil : trimmed
            }()

            let update = APIUserProfileUpdate(
                name: AuthSessionState.shared.userDisplayName,
                email: AuthSessionState.shared.userEmail,
                age: assessment.age,
                height_inches: assessment.heightInches,
                weight_lbs: assessment.weightLbs,
                target_weight_lbs: assessment.targetWeightLbs,
                goals: assessment.goals.map(\.rawValue),
                custom_goal_text: normalizedCustomGoal,
                training_experience: assessment.trainingExperience?.rawValue,
                training_days_per_week: assessment.trainingDaysPerWeek,
                onboarding_complete: true
            )
            _ = try await APIClient.shared.updateUserProfile(update)
        } catch {
            // Non-fatal, continue the sync flow. User can retry from settings.
            Log.onboarding.error("Profile save failed: \(error.localizedDescription)")
        }

        // Step 1b: Try to load real metrics for the summary card.
        // Silently ignored, if data isn't ready yet the card shows "--".
        //
        // Reject obviously bogus values. Zero sleep efficiency means the
        // backend has no reconciled sleep record yet (not that the user
        // slept 0%), and single-digit HRV usually means an uninitialized
        // buffer rather than a real reading. Surfacing "Sleep Score 0%" in
        // the "You're all set!" summary looked real to Stephanie in build 3
        // feedback and made the scores feel broken.
        if let dashboard = try? await APIClient.shared.fetchDashboard() {
            for metric in dashboard.metrics {
                switch metric.category {
                case "sleepEfficiency":
                    if let value = Int(metric.value), value > 0 {
                        fetchedSleepScore = "\(metric.value)\(metric.unit)"
                    }
                case "hrv":
                    if let value = Int(metric.value), value >= 10 {
                        fetchedHRV = "\(metric.value) \(metric.unit)"
                    }
                default:
                    break
                }
            }
        }

        withAnimation(DSMotion.standard) { syncProgress = 0.25 }

        // Step 2: Animate the remaining progress so the user sees forward motion
        // while their data syncs in the background (Oura webhooks, HealthKit, etc.).
        let remainingSteps = 3
        for i in 0..<remainingSteps {
            try? await Task.sleep(for: .seconds(0.6))
            withAnimation(DSMotion.standard) {
                syncProgress = 0.25 + Double(i + 1) / Double(remainingSteps) * 0.75
            }
        }

        try? await Task.sleep(for: .seconds(0.3))
        isSyncing = false
        Analytics.Onboarding.syncCompleted()

        withAnimation(DSMotion.emphasis) {
            isComplete = true
        }
        DSHaptic.success()
    }

    // MARK: - Formatting

    func heightString(_ inches: Int) -> String {
        let feet = inches / 12
        let remaining = inches % 12
        return "\(feet)'\(remaining)\""
    }
}
