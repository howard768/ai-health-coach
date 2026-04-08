import Foundation

// MARK: - Coach Chat View Model
// Manages chat state, message history, and mock AI responses.
// Will integrate with Claude API in Cycle 2 backend work.

@Observable @MainActor
final class CoachViewModel {

    var messages: [ChatMessage] = []
    var inputText: String = ""
    var isTyping: Bool = false
    var quickActions: [QuickAction] = QuickAction.defaults

    init() {
        // Try loading history from backend, fall back to seed messages
        messages = Self.seedMessages()
        Task { await loadHistory() }
    }

    // MARK: - History Persistence

    func loadHistory() async {
        do {
            let history = try await APIClient.shared.fetchChatHistory()
            if !history.isEmpty {
                messages = history.map { msg in
                    ChatMessage(
                        role: msg.role == "coach" ? .coach : .user,
                        text: msg.content,
                        timestamp: ISO8601DateFormatter().date(from: msg.createdAt) ?? Date()
                    )
                }
            }
        } catch {
            // Backend unavailable — keep seed messages
        }
    }

    // MARK: - Actions

    func sendMessage() {
        let text = inputText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return }

        // Add user message
        let userMsg = ChatMessage(role: .user, text: text)
        messages.append(userMsg)
        inputText = ""
        DSHaptic.light()
        Analytics.Coach.messageSent()

        // Simulate coach response
        simulateCoachResponse(to: text)
    }

    func sendQuickAction(_ action: QuickAction) {
        let userMsg = ChatMessage(role: .user, text: action.title)
        messages.append(userMsg)
        DSHaptic.light()
        Analytics.Coach.quickActionTapped(action: action.title)

        simulateCoachResponse(to: action.prompt)
    }

    // MARK: - Simulated Response

    private func simulateCoachResponse(to prompt: String) {
        isTyping = true

        Task {
            // Try real backend first
            do {
                let response = try await APIClient.shared.sendMessage(prompt)
                let coachMsg = ChatMessage(role: .coach, text: response.content)
                messages.append(coachMsg)
                isTyping = false
                return
            } catch {
                // Backend not available — fall back to mock
            }

            // Fallback: mock response
            try? await Task.sleep(for: .seconds(1.5))
            let response = generateMockResponse(for: prompt)
            messages.append(response)
            isTyping = false
        }
    }

    private func generateMockResponse(for prompt: String) -> ChatMessage {
        let lowered = prompt.lowercased()

        if lowered.contains("sleep") {
            return ChatMessage(
                role: .coach,
                content: [
                    .text("Good morning, Brock. Your sleep was great last night. Here's what I see:"),
                    .dataCard(ChatDataCard(
                        metricType: .sleepEfficiency,
                        title: "Sleep Summary",
                        value: "91",
                        unit: "%",
                        subtitle: "7h 12m total",
                        trendValues: [0.82, 0.88, 0.85, 0.91, 0.87, 0.90, 0.91]
                    )),
                    .text("Your deep sleep was longer than usual. Today is a good day for a hard workout."),
                ]
            )
        } else if lowered.contains("workout") || lowered.contains("plan") {
            return ChatMessage(
                role: .coach,
                content: [
                    .text("Based on your recovery and last week's volume, here's your session. I added 5lbs to your working sets:"),
                    .workoutPlan([
                        WorkoutExercise(name: "Squats", prescription: "4×5 @ 230lb"),
                        WorkoutExercise(name: "RDL", prescription: "3×8 @ 190lb"),
                        WorkoutExercise(name: "Leg Press", prescription: "3×10"),
                        WorkoutExercise(name: "Walking Lunges", prescription: "2×12"),
                    ]),
                    .text("Your HRV is high today, so push for those extra reps."),
                ]
            )
        } else if lowered.contains("eat") || lowered.contains("food") || lowered.contains("dinner") {
            return ChatMessage(
                role: .coach,
                content: [
                    .text("Your goal is to lose weight and build muscle. Here's what I'd aim for today:"),
                    .text("Protein: 140-150g\nCarbs: 180-200g\nFat: 50-60g\nTotal: ~1,800 cal"),
                    .citation(
                        text: "Higher protein helps keep muscle while losing fat.",
                        source: "Phillips, S.M. (2014). A Brief Review of Higher Dietary Protein Diets."
                    ),
                ]
            )
        } else if lowered.contains("recovery") || lowered.contains("recover") {
            return ChatMessage(
                role: .coach,
                content: [
                    .text("Your recovery looks strong today."),
                    .dataCard(ChatDataCard(
                        metricType: .hrv,
                        title: "HRV Status",
                        value: "68",
                        unit: "ms",
                        subtitle: "↑ 14% vs baseline",
                        trendValues: [52, 58, 55, 62, 68, 64, 68]
                    )),
                    .text("Your body is handling stress well. You can push hard today."),
                ]
            )
        } else {
            return ChatMessage(
                role: .coach,
                content: [
                    .text("That's a great question. Based on your data, here's what I think: your overall trend is positive. Your sleep and HRV are improving, and you've been consistent with training. Keep it up."),
                ]
            )
        }
    }

    // MARK: - Seed Messages

    private static func seedMessages() -> [ChatMessage] {
        [
            ChatMessage(
                role: .coach,
                content: [
                    .text("Good morning, Brock. Your sleep was 91% and HRV is 14% above your baseline. Great recovery night."),
                    .dataCard(ChatDataCard(
                        metricType: .sleepEfficiency,
                        title: "Sleep Summary",
                        value: "91",
                        unit: "%",
                        subtitle: "7h 12m total",
                        trendValues: [0.82, 0.88, 0.85, 0.91, 0.87, 0.90, 0.91]
                    )),
                    .text("Today is ideal for progressive overload. I'd prioritize squats and deadlifts. Want me to outline your session?"),
                ],
                timestamp: Date().addingTimeInterval(-3600)
            ),
            ChatMessage(
                role: .user,
                text: "Yes, outline leg day for me",
                timestamp: Date().addingTimeInterval(-3500)
            ),
            ChatMessage(
                role: .coach,
                content: [
                    .text("Here's your session. Based on your recovery and last week's volume, I've added 5lbs to your working sets:"),
                    .workoutPlan([
                        WorkoutExercise(name: "Squats", prescription: "4×5 @ 225lb"),
                        WorkoutExercise(name: "RDL", prescription: "3×8 @ 185lb"),
                        WorkoutExercise(name: "Leg Press", prescription: "3×10"),
                        WorkoutExercise(name: "Walking Lunges", prescription: "2×12"),
                    ]),
                ],
                timestamp: Date().addingTimeInterval(-3400)
            ),
        ]
    }
}
