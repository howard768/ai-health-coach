import SwiftUI

// MARK: - Coach Chat Screen
// Full chat interface with embedded data cards, workout plans,
// quick action chips, and streaming response indicator.
// Inspired by Exyte Chat but built from DS components for full design control.
//
// Features recreated from Exyte Chat:
// - Message bubbles (left coach, right user) with avatar
// - Message grouping with timestamps
// - Quick action chips above input
// - Typing indicator with animated mascot
// - Embedded rich content (data cards, workouts, citations)
// - Keyboard-aware input bar fixed at bottom
//
// Grid: 20pt margins, 8pt vertical rhythm.

struct CoachChatView: View {
    @Bindable var viewModel: CoachViewModel
    private let M: CGFloat = 20

    @FocusState private var isInputFocused: Bool

    var body: some View {
        VStack(spacing: 0) {
            // Navigation title
            Text("Coach")
                .font(DSTypography.h2)
                .foregroundStyle(DSColor.Text.primary)
                .frame(maxWidth: .infinity)
                .padding(.vertical, DSSpacing.md)
                .background(DSColor.Background.primary)

            // Message list
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(spacing: DSSpacing.lg) {
                        ForEach(viewModel.messages) { message in
                            MessageView(message: message) { feedback in
                                viewModel.submitFeedback(for: message, feedback: feedback)
                            }
                            .id(message.id)
                        }

                        // Typing indicator
                        if viewModel.isTyping {
                            TypingIndicator()
                                .padding(.horizontal, M)
                                .id("typing")
                        }
                    }
                    .padding(.vertical, DSSpacing.md)
                }
                .scrollDismissesKeyboard(.interactively)
                .onChange(of: viewModel.messages.count) { _, _ in
                    scrollToBottom(proxy: proxy)
                }
                .onChange(of: viewModel.isTyping) { _, _ in
                    scrollToBottom(proxy: proxy)
                }
                .onChange(of: isInputFocused) { _, focused in
                    if focused { scrollToBottom(proxy: proxy) }
                }
            }

            // Quick action chips — use opacity instead of if/else to prevent layout jitter
            DSChipRow(chips: viewModel.quickActions.map(\.title)) { title in
                if let action = viewModel.quickActions.first(where: { $0.title == title }) {
                    viewModel.sendQuickAction(action)
                }
            }
            .accessibilityIdentifier("coach-quick-actions")
            .padding(.vertical, DSSpacing.sm)
            .opacity(viewModel.isTyping ? 0 : 1)
            .allowsHitTesting(!viewModel.isTyping)

            // Input bar
            chatInputBar
        }
        .background(DSColor.Background.primary)
        .onAppear { Analytics.Coach.chatOpened() }
    }

    private func scrollToBottom(proxy: ScrollViewProxy) {
        withAnimation(DSMotion.standard) {
            if viewModel.isTyping {
                proxy.scrollTo("typing", anchor: .bottom)
            } else if let last = viewModel.messages.last {
                proxy.scrollTo(last.id, anchor: .bottom)
            }
        }
    }

    // MARK: - Input Bar

    private var chatInputBar: some View {
        HStack(spacing: DSSpacing.sm) {
            TextField("Ask anything about your health", text: $viewModel.inputText)
                .font(DSTypography.body)
                .foregroundStyle(DSColor.Text.primary)
                .padding(.vertical, DSSpacing.md)
                .padding(.horizontal, DSSpacing.lg)
                .background(DSColor.Surface.secondary)
                .clipShape(Capsule())
                .focused($isInputFocused)
                .onSubmit {
                    viewModel.sendMessage()
                }
                .accessibilityLabel("Message your coach")
                .accessibilityIdentifier("coach-input")
                .accessibilityHint("Type a question about your sleep, recovery, food, or training")

            if !viewModel.inputText.isEmpty {
                Button(action: { viewModel.sendMessage() }) {
                    MeldMascot(state: .idle, size: 36)
                        .frame(width: 44, height: 44)
                        .background(Color.hex(0xFAF0DA))
                        .clipShape(Circle())
                }
                .transition(.scale.combined(with: .opacity))
                .accessibilityLabel("Send message")
                .accessibilityIdentifier("coach-send")
                .accessibilityHint("Sends your message to the coach")
            }
        }
        .padding(.horizontal, M)
        .padding(.vertical, DSSpacing.sm)
        .background(DSColor.Background.primary)
        .animation(DSMotion.snappy, value: viewModel.inputText.isEmpty)
    }
}

// MARK: - Message View (coach or user)

private struct MessageView: View {
    let message: ChatMessage
    var onFeedback: ((String) -> Void)?
    private let M: CGFloat = 20

    var body: some View {
        HStack(alignment: .top, spacing: DSSpacing.sm) {
            if message.role == .coach {
                coachBubble
            } else {
                userBubble
            }
        }
        .padding(.horizontal, M)
    }

    // MARK: - Coach Bubble (left-aligned with avatar)

    private var coachBubble: some View {
        HStack(alignment: .top, spacing: DSSpacing.sm) {
            MeldMascot(state: .idle, size: 28)
                .padding(.top, DSSpacing.xs)

            VStack(alignment: .leading, spacing: DSSpacing.sm) {
                // Timestamp
                Text(timeString)
                    .font(DSTypography.caption)
                    .foregroundStyle(DSColor.Text.tertiary)

                // Content blocks
                ForEach(message.content) { block in
                    contentView(for: block)
                }

                // Feedback buttons (only for coach messages with a backend ID)
                if message.messageId != nil {
                    HStack(spacing: DSSpacing.md) {
                        Button {
                            onFeedback?("up")
                        } label: {
                            Image(systemName: message.feedback == "up" ? "hand.thumbsup.fill" : "hand.thumbsup")
                                .font(.system(size: 14))
                                .foregroundStyle(message.feedback == "up" ? DSColor.Purple.purple500 : DSColor.Text.tertiary)
                        }
                        .accessibilityLabel(message.feedback == "up" ? "Helpful, selected" : "Mark helpful")
                        .accessibilityAddTraits(message.feedback == "up" ? .isSelected : [])

                        Button {
                            onFeedback?("down")
                        } label: {
                            Image(systemName: message.feedback == "down" ? "hand.thumbsdown.fill" : "hand.thumbsdown")
                                .font(.system(size: 14))
                                .foregroundStyle(message.feedback == "down" ? DSColor.Status.error : DSColor.Text.tertiary)
                        }
                        .accessibilityLabel(message.feedback == "down" ? "Not helpful, selected" : "Mark not helpful")
                        .accessibilityAddTraits(message.feedback == "down" ? .isSelected : [])
                    }
                    .padding(.top, DSSpacing.xs)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)

            Spacer(minLength: 40) // Right margin for coach messages
        }
    }

    // MARK: - User Bubble (right-aligned, purple)

    private var userBubble: some View {
        HStack {
            Spacer(minLength: 80) // Left margin for user messages

            VStack(alignment: .trailing, spacing: DSSpacing.xs) {
                Text(timeString)
                    .font(DSTypography.caption)
                    .foregroundStyle(DSColor.Text.tertiary)

                // User messages are always text
                if case .text(let text) = message.content.first {
                    Text(text)
                        .font(DSTypography.body)
                        .foregroundStyle(DSColor.Text.onPurple)
                        .padding(.horizontal, DSSpacing.lg)
                        .padding(.vertical, DSSpacing.md)
                        .background(DSColor.Purple.purple500)
                        .dsCornerRadius(DSRadius.xl)
                }
            }
        }
    }

    // MARK: - Content Block Rendering

    @ViewBuilder
    private func contentView(for block: ChatContent) -> some View {
        switch block {
        case .text(let text):
            MarkdownText(raw: text)

        case .dataCard(let card):
            DSSummaryDataCard(
                title: card.title,
                value: card.value,
                unit: card.unit,
                subtitle: card.subtitle,
                onTap: { /* Navigate to metric detail */ }
            )

        case .workoutPlan(let exercises):
            DSWorkoutCard(exercises: exercises)

        case .citation(let text, let source):
            DSCitationCard(text: text, source: source)
        }
    }

    // MARK: - Time Formatting

    private var timeString: String {
        let formatter = DateFormatter()
        formatter.dateFormat = "h:mm a"
        return formatter.string(from: message.timestamp)
    }
}

// MARK: - Markdown Text
//
// Renders the coach's markdown-ish text with inline **bold** / *italic* and
// bulleted lists (lines starting with "- "). SwiftUI's AttributedString
// markdown parser handles inline formatting but not lists, so we split on
// newlines and render bullets as separate rows with a DS purple glyph.
//
// Supported:
//   **bold**, *italic*, `code`, and [links](url)
//   - bullet lines
//   blank lines between paragraphs
//
// Unsupported (coach prompt forbids them): headers, tables, numbered lists.

private struct MarkdownText: View {
    let raw: String

    var body: some View {
        VStack(alignment: .leading, spacing: DSSpacing.sm) {
            ForEach(Array(paragraphs.enumerated()), id: \.offset) { _, paragraph in
                paragraphView(paragraph)
            }
        }
    }

    /// Split the raw text into "paragraphs", where consecutive non-bullet
    /// lines merge into one paragraph and each bullet line is its own unit.
    /// Blank lines act as paragraph breaks.
    private var paragraphs: [Paragraph] {
        var result: [Paragraph] = []
        var textBuffer: [String] = []

        func flushText() {
            if !textBuffer.isEmpty {
                let joined = textBuffer.joined(separator: " ")
                if !joined.isEmpty {
                    result.append(.text(joined))
                }
                textBuffer.removeAll()
            }
        }

        for line in raw.components(separatedBy: "\n") {
            let trimmed = line.trimmingCharacters(in: .whitespaces)
            if trimmed.isEmpty {
                flushText()
            } else if trimmed.hasPrefix("- ") {
                flushText()
                result.append(.bullet(String(trimmed.dropFirst(2))))
            } else if trimmed.hasPrefix("* ") {
                flushText()
                result.append(.bullet(String(trimmed.dropFirst(2))))
            } else {
                textBuffer.append(trimmed)
            }
        }
        flushText()
        return result
    }

    @ViewBuilder
    private func paragraphView(_ paragraph: Paragraph) -> some View {
        switch paragraph {
        case .text(let value):
            Text(attributed(value))
                .font(DSTypography.body)
                .foregroundStyle(DSColor.Text.primary)
                .lineSpacing(4)
                .fixedSize(horizontal: false, vertical: true)
        case .bullet(let value):
            HStack(alignment: .firstTextBaseline, spacing: DSSpacing.sm) {
                Text("•")
                    .font(DSTypography.body)
                    .foregroundStyle(DSColor.Purple.purple500)
                Text(attributed(value))
                    .font(DSTypography.body)
                    .foregroundStyle(DSColor.Text.primary)
                    .lineSpacing(4)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
    }

    /// Parse inline markdown (**bold**, *italic*, `code`, [link](url)) into
    /// an AttributedString. Falls back to plain text if parsing fails.
    private func attributed(_ string: String) -> AttributedString {
        var options = AttributedString.MarkdownParsingOptions()
        options.interpretedSyntax = .inlineOnlyPreservingWhitespace
        if let parsed = try? AttributedString(markdown: string, options: options) {
            return parsed
        }
        return AttributedString(string)
    }

    private enum Paragraph {
        case text(String)
        case bullet(String)
    }
}

// MARK: - Previews

#Preview {
    CoachChatView(viewModel: CoachViewModel())
}
