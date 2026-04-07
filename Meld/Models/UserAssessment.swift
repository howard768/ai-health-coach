import Foundation

// MARK: - User Assessment Model
// Captures onboarding assessment data. Goal-adaptive:
// fields required depend on which goals the user selected.

struct UserAssessment {
    var goals: Set<HealthGoal> = []
    var customGoalText: String = ""
    var age: Int? = nil
    var heightInches: Int? = nil
    var weightLbs: Double? = nil
    var targetWeightLbs: Double? = nil
    var trainingExperience: TrainingExperience? = nil
    var trainingDaysPerWeek: Int? = nil
    var chronotype: Chronotype? = nil
    var sleepChallenge: SleepChallenge? = nil
    var connectedSources: Set<DataSourceType> = []

    // MARK: - Computed

    var bmi: Double? {
        guard let h = heightInches, let w = weightLbs, h > 0 else { return nil }
        return (w / Double(h * h)) * 703.0
    }

    var needsHeight: Bool { goals.contains(.loseWeight) || goals.contains(.buildMuscle) }
    var needsWeight: Bool { goals.contains(.loseWeight) || goals.contains(.buildMuscle) }
    var needsTargetWeight: Bool { goals.contains(.loseWeight) }
    var needsExperience: Bool { goals.contains(.buildMuscle) }
    var needsTrainingDays: Bool { goals.contains(.buildMuscle) }
    var needsChronotype: Bool { goals.contains(.sleepBetter) }
    var needsSleepChallenge: Bool { goals.contains(.sleepBetter) }

    var isProfileComplete: Bool {
        guard age != nil else { return false }
        if needsHeight && heightInches == nil { return false }
        if needsWeight && weightLbs == nil { return false }
        if needsTargetWeight && targetWeightLbs == nil { return false }
        if needsExperience && trainingExperience == nil { return false }
        if needsTrainingDays && trainingDaysPerWeek == nil { return false }
        return true
    }

    var hasDataSource: Bool { !connectedSources.isEmpty }
}

// MARK: - Enums

enum HealthGoal: String, CaseIterable, Identifiable {
    case loseWeight = "Lose weight"
    case buildMuscle = "Build muscle"
    case sleepBetter = "Sleep better"
    case recoverFaster = "Recover faster"
    case moreEnergy = "More energy"
    case feelBest = "Feel my best"

    var id: String { rawValue }
}

enum TrainingExperience: String, CaseIterable, Identifiable {
    case beginner = "Just starting"
    case intermediate = "A while"
    case advanced = "Years"

    var id: String { rawValue }
}

enum Chronotype: String, CaseIterable, Identifiable {
    case earlyBird = "Early bird"
    case nightOwl = "Night owl"
    case varies = "Varies"

    var id: String { rawValue }
}

enum SleepChallenge: String, CaseIterable, Identifiable {
    case fallingAsleep = "Falling asleep"
    case stayingAsleep = "Staying asleep"
    case wakingRested = "Waking rested"
    case consistency = "Consistency"

    var id: String { rawValue }
}

enum DataSourceType: String, CaseIterable, Identifiable {
    case oura = "Oura Ring"
    case appleHealth = "Apple Health"
    case eightSleep = "Eight Sleep"
    case garmin = "Garmin"

    var id: String { rawValue }

    var subtitle: String {
        switch self {
        case .oura: "Sleep, HRV, readiness, activity"
        case .appleHealth: "Steps, workouts, heart rate"
        case .eightSleep: "Sleep tracking, bed temperature"
        case .garmin: "Activity, HR, body battery"
        }
    }

    var isAvailable: Bool {
        switch self {
        case .oura, .appleHealth: true
        case .eightSleep, .garmin: false // Coming soon
        }
    }
}
