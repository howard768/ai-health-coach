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
        // Start empty — loadHistory() fills from API on appear
        messages = []
        Task { await loadHistory() }
    }

    // MARK: - History Persistence

    func loadHistory() async {
        do {
            let history = try await APIClient.shared.fetchChatHistory()
            if !history.isEmpty {
                // P2-12: Preserve the backend message_id so thumbs up/down still
                // work after a reload. Previously dropped, leaving feedback
                // buttons inert for any historical message.
                messages = history.map { msg in
                    ChatMessage(
                        role: msg.role == "coach" ? .coach : .user,
                        text: msg.content,
                        timestamp: ISO8601DateFormatter().date(from: msg.createdAt) ?? Date(),
                        messageId: msg.id
                    )
                }
            } else {
                // No history — show a welcome message (not fake conversation)
                messages = [
                    ChatMessage(
                        role: .coach,
                        content: [.text("Hey! I'm your health coach. Ask me anything about your sleep, recovery, workouts, or nutrition.")],
                        timestamp: Date()
                    )
                ]
            }
        } catch {
            // Backend unavailable — show welcome message
            messages = [
                ChatMessage(
                    role: .coach,
                    content: [.text("Hey! I'm your health coach. I'm having trouble connecting right now, but ask me anything.")],
                    timestamp: Date()
                )
            ]
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

    func prefill(_ text: String) {
        inputText = text
    }

    func sendQuickAction(_ action: QuickAction) {
        let userMsg = ChatMessage(role: .user, text: action.title)
        messages.append(userMsg)
        DSHaptic.light()
        Analytics.Coach.quickActionTapped(action: action.title)

        simulateCoachResponse(to: action.prompt)
    }

    // MARK: - Feedback

    func submitFeedback(for message: ChatMessage, feedback: String) {
        guard let messageId = message.messageId else { return }
        guard let index = messages.firstIndex(where: { $0.id == message.id }) else { return }
        messages[index].feedback = feedback
        DSHaptic.light()

        Task {
            try? await APIClient.shared.submitFeedback(messageId: messageId, feedback: feedback)
        }
    }

    // MARK: - Coach Response
    //
    // IMPORTANT: No mock/fake fallback. If the backend is unreachable, we show
    // an honest error — never fabricated health data. This is enforced by the
    // eval suite (evidence-bound coaching rule) and was fixed as P0-7 of the
    // 2026-04-10 audit.

    private func simulateCoachResponse(to prompt: String) {
        isTyping = true

        Task {
            // P2-10: Distinguish offline from server error so we give the
            // user a useful nudge instead of a generic "trouble connecting"
            // message. The OfflineBanner at the root is also visible.
            if !NetworkMonitor.shared.isOnline {
                messages.append(ChatMessage(
                    role: .coach,
                    text: "You're offline right now. I'll be here as soon as you're back."
                ))
                isTyping = false
                return
            }

            do {
                let response = try await APIClient.shared.sendMessage(prompt)
                let coachMsg = ChatMessage(role: .coach, text: response.content, messageId: response.messageId)
                messages.append(coachMsg)
            } catch APIError.networkError {
                messages.append(ChatMessage(
                    role: .coach,
                    text: "Looks like the connection dropped. Try again once you're back online."
                ))
            } catch {
                // Honest error — no fabricated data.
                let errorMsg = ChatMessage(
                    role: .coach,
                    text: "I'm having trouble connecting right now. Check your internet connection and try again in a moment."
                )
                messages.append(errorMsg)
            }
            isTyping = false
        }
    }
}
