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

    init(id: UUID = UUID(), role: ChatRole, content: [ChatContent], timestamp: Date = Date()) {
        self.id = id
        self.role = role
        self.content = content
        self.timestamp = timestamp
    }

    // Convenience: simple text message
    init(role: ChatRole, text: String, timestamp: Date = Date()) {
        self.init(role: role, content: [.text(text)], timestamp: timestamp)
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
    let metricType: MetricCategory
    let title: String
    let value: String
    let unit: String
    let subtitle: String
    let trendValues: [Double]?
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
