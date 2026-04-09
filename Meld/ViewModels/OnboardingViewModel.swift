import SwiftUI

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

    func connectSource(_ source: DataSourceType) {
        assessment.connectedSources.insert(source)
        DSHaptic.success()

        // Analytics
        switch source {
        case .oura: Analytics.Onboarding.ouraConnected()
        case .appleHealth:
            Analytics.Onboarding.healthKitGranted()
            // Request HealthKit authorization and prefill profile data
            Task {
                let granted = await HealthKitService.shared.requestAuthorization()
                if granted {
                    prefilledAge = HealthKitService.shared.getAge()
                    if let weight = await HealthKitService.shared.getLatestWeight() {
                        prefilledWeightLbs = weight
                    }
                    if let height = await HealthKitService.shared.getLatestHeight() {
                        prefilledHeightInches = Int(height)
                    }
                    applyPrefill()
                    // Trigger background sync to backend
                    await HealthKitService.shared.syncToBackend()
                }
            }
        default: break
        }
    }

    func startSync() async {
        isSyncing = true
        syncProgress = 0
        Analytics.Onboarding.syncStarted()

        // Simulate sync steps
        let steps = [
            "Connecting to your data...",
            "Reading your sleep patterns...",
            "Computing your baseline...",
            "Getting your first insight ready..."
        ]

        for (i, _) in steps.enumerated() {
            try? await Task.sleep(for: .seconds(0.8))
            withAnimation(DSMotion.standard) {
                syncProgress = Double(i + 1) / Double(steps.count)
            }
        }

        try? await Task.sleep(for: .seconds(0.5))
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
