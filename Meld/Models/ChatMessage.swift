import Foundation

// MARK: - Chat Message Models
// Structured content format supporting mixed content:
// text, embedded data cards, workout plans, and citations.
// This mirrors the API response format so the backend can return
// rich, typed content blocks within a single message.

struct ChatMessage: Identifiable {
    let id: UUID
    let role: ChatRole
    let content: [ChatContent]
    let timestamp: Date
    var messageId: Int?  // Backend DB ID — used for feedback
    var feedback: String?  // "up", "down", or nil

    init(id: UUID = UUID(), role: ChatRole, content: [ChatContent], timestamp: Date = Date(), messageId: Int? = nil) {
        self.id = id
        self.role = role
        self.content = content
        self.timestamp = timestamp
        self.messageId = messageId
    }

    // Convenience: simple text message
    init(role: ChatRole, text: String, timestamp: Date = Date(), messageId: Int? = nil) {
        self.init(role: role, content: [.text(text)], timestamp: timestamp, messageId: messageId)
    }
}

enum ChatRole {
    case coach
    case user
}

// MARK: - Content Blocks (mixed content within a message)

enum ChatContent: Identifiable {
    case text(String)
    case dataCard(ChatDataCard)
    case workoutPlan([WorkoutExercise])
    case citation(text: String, source: String)

    var id: String {
        switch self {
        case .text(let s): "text_\(s.prefix(20).hashValue)"
        case .dataCard(let c): "card_\(c.id)"
        case .workoutPlan: "workout_\(UUID().uuidString)"
        case .citation(let t, _): "cite_\(t.prefix(20).hashValue)"
        }
    }
}

struct ChatDataCard: Identifiable {
    let id = UUID()
    let title: String
    let value: String
    let unit: String
    let subtitle: String

    /// Construct from a backend metric key. Backend emits keys like
    /// "sleep_efficiency", "deep_sleep_minutes", "hrv", "steps" — broader
    /// than our 4-case MetricCategory enum. We derive a display title from
    /// the key rather than requiring the enum to know about every metric.
    init(metricKey: String, value: String, unit: String, subtitle: String) {
        self.title = Self.displayTitle(for: metricKey)
        self.value = value
        self.unit = unit
        self.subtitle = subtitle
    }

    /// Map backend metric keys to human-readable card titles.
    /// Unknown keys get a sensible default (snake_case → Title Case).
    private static func displayTitle(for key: String) -> String {
        switch key {
        case "sleep_efficiency": return "Sleep Efficiency"
        case "sleep_duration_hours": return "Sleep Duration"
        case "deep_sleep_minutes": return "Deep Sleep"
        case "rem_sleep_minutes": return "REM Sleep"
        case "hrv", "hrv_average": return "HRV"
        case "resting_hr": return "Resting HR"
        case "readiness_score": return "Readiness"
        case "steps": return "Steps"
        case "active_calories": return "Active Calories"
        default:
            // snake_case → Title Case fallback
            return key
                .split(separator: "_")
                .map { $0.prefix(1).uppercased() + $0.dropFirst() }
                .joined(separator: " ")
        }
    }
}

// MARK: - Quick Actions

struct QuickAction: Identifiable {
    let id = UUID()
    let title: String
    let prompt: String // The actual prompt sent to Claude

    static let defaults: [QuickAction] = [
        QuickAction(title: "How's my sleep?", prompt: "Analyze my sleep data from last night and tell me what it means."),
        QuickAction(title: "Plan my workout", prompt: "Based on my recovery and training history, plan today's workout."),
        QuickAction(title: "What should I eat?", prompt: "Based on my goals and activity today, what should I eat?"),
        QuickAction(title: "Recovery check", prompt: "How is my recovery looking? Should I push hard or take it easy?"),
    ]
}
