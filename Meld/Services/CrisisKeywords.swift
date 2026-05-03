import Foundation

// MARK: - Crisis Keywords (client-side defense in depth)
//
// The backend's coach_engine.check_message_content() already detects crisis
// phrases and, when the Anthropic API fails, returns a safety fallback with
// 988/741741. But that only catches anthropic.APIError. If the request fails
// for any other reason, network timeout, TLS error, 500/502 from the host,
// an unhandled exception before the Claude call, iOS shows a generic
// "trouble connecting" message and the user's crisis signal is lost.
//
// This helper mirrors the backend's phrase list so we can surface crisis
// resources from the client even when the server never responded. The lists
// MUST stay in sync: if you add a phrase in coach_engine.py, add it here too.
// The backend list lives at backend/app/services/coach_engine.py:123-135.

enum CrisisKeywords {

    /// Phrases that indicate a mental health crisis. Match is case-insensitive
    /// substring on the user's input, same as the backend.
    static let phrases: [String] = [
        "want to die", "want to end it", "kill myself", "end my life",
        "no reason to live", "better off without me",
        "can't go on", "cant go on",
        "hurt myself", "self-harm", "self harm", "suicide", "suicidal",
        "don't want to be here", "dont want to be here",
        "not worth living",
        "no point in living", "want it to be over",
        "feeling like a burden", "everyone would be better off",
        "don't want to live", "dont want to live",
        "can't take it anymore", "cant take it anymore",
        "i don't want to be alive", "i dont want to be alive",
    ]

    /// True if any crisis phrase appears in `text`. Case-insensitive.
    static func detect(in text: String) -> Bool {
        let lowered = text.lowercased()
        return phrases.contains { lowered.contains($0) }
    }

    /// Resource message shown when the server didn't return a coach response
    /// but the user's input contained crisis language. Uses markdown links so
    /// MarkdownText renders tappable `tel:` / `sms:` deep links that dial or
    /// open the Messages app.
    ///
    /// Keep the content tight and action-first: verdict, numbers to call, one
    /// short closing line. Matches the BLUF structure used elsewhere.
    static let fallbackMessage: String = """
    **I'm having trouble connecting right now, but I want to make sure you're safe.**

    If you're in crisis, please reach out:
    - [Call or text 988](tel:988) for the Suicide & Crisis Lifeline
    - [Text HOME to 741741](sms:741741&body=HOME) for the Crisis Text Line
    - If you're in immediate danger, call 911

    You're not alone. Please talk to someone.
    """
}
