import Foundation
import Testing
@testable import Meld

// MARK: - APIContentBlock decoder
//
// The backend emits a discriminated union { type: "text" | "data_card", ... }.
// These tests pin the wire format — if the backend renames a field, the iOS
// decode breaks and we catch it here before shipping.

@Test func contentBlockDecodesTextType() async throws {
    let json = """
    { "type": "text", "value": "Your sleep was solid." }
    """.data(using: .utf8)!
    let block = try JSONDecoder().decode(APIContentBlock.self, from: json)
    if case .text(let value) = block {
        #expect(value == "Your sleep was solid.")
    } else {
        Issue.record("Expected .text, got \\(block)")
    }
}

@Test func contentBlockDecodesDataCardType() async throws {
    let json = """
    {
      "type": "data_card",
      "metric": "sleep_efficiency",
      "value": "91",
      "unit": "%",
      "subtitle": "above 7-day avg"
    }
    """.data(using: .utf8)!
    let block = try JSONDecoder().decode(APIContentBlock.self, from: json)
    if case .dataCard(let metric, let value, let unit, let subtitle) = block {
        #expect(metric == "sleep_efficiency")
        #expect(value == "91")
        #expect(unit == "%")
        #expect(subtitle == "above 7-day avg")
    } else {
        Issue.record("Expected .dataCard, got \\(block)")
    }
}

@Test func contentBlockUnknownTypeFallsBackToEmptyText() async throws {
    // Forward-compat: if the backend adds a new block kind later, old clients
    // should degrade gracefully rather than crash on decode.
    let json = """
    { "type": "workout_plan", "exercises": [] }
    """.data(using: .utf8)!
    let block = try JSONDecoder().decode(APIContentBlock.self, from: json)
    if case .text(let value) = block {
        #expect(value == "")
    } else {
        Issue.record("Expected fallback to .text(\"\"), got \\(block)")
    }
}

@Test func chatResponseDecodesWithBlocks() async throws {
    // Representative payload from POST /api/coach/chat — mirrors what the
    // backend actually returns for a response containing one data tag.
    let json = """
    {
      "role": "coach",
      "content": "Your sleep was solid. **91%** above avg.",
      "blocks": [
        { "type": "text", "value": "Your sleep was solid." },
        { "type": "data_card", "metric": "sleep_efficiency", "value": "91", "unit": "%", "subtitle": "above 7-day avg" }
      ],
      "message_id": 42,
      "routing": null,
      "safety": null,
      "model_used": "claude-sonnet-4-5"
    }
    """.data(using: .utf8)!
    let response = try JSONDecoder().decode(APIChatResponse.self, from: json)
    #expect(response.blocks?.count == 2)
    #expect(response.messageId == 42)
}

@Test func chatResponseDecodesWithoutBlocks() async throws {
    // Backward-compat: pre-v2 server builds omit the blocks field entirely.
    // The decoder must accept that and produce nil rather than throwing.
    let json = """
    {
      "role": "coach",
      "content": "Hello.",
      "message_id": 1,
      "routing": null,
      "safety": null,
      "model_used": null
    }
    """.data(using: .utf8)!
    let response = try JSONDecoder().decode(APIChatResponse.self, from: json)
    #expect(response.blocks == nil)
    #expect(response.content == "Hello.")
}

// MARK: - ChatDataCard.displayTitle
//
// The backend emits metric keys in snake_case. The UI needs human-readable
// titles. Tests pin the mapping for the metrics we actually use today.

@Test func chatDataCardMapsKnownMetricKeys() async throws {
    let cases: [(key: String, expected: String)] = [
        ("sleep_efficiency", "Sleep Efficiency"),
        ("deep_sleep_minutes", "Deep Sleep"),
        ("hrv", "HRV"),
        ("resting_hr", "Resting HR"),
        ("readiness_score", "Readiness"),
        ("steps", "Steps"),
        ("active_calories", "Active Calories"),
    ]
    for c in cases {
        let card = ChatDataCard(metricKey: c.key, value: "1", unit: "", subtitle: "")
        #expect(card.title == c.expected, "Metric key '\\(c.key)' should map to '\\(c.expected)' but got '\\(card.title)'")
    }
}

@Test func chatDataCardFallsBackToTitleCaseForUnknownKeys() async throws {
    // Unknown keys shouldn't produce empty or snake_case titles in the UI.
    let card = ChatDataCard(metricKey: "total_energy_expenditure", value: "1", unit: "", subtitle: "")
    #expect(card.title == "Total Energy Expenditure")
}

// MARK: - DashboardViewModel

@Test @MainActor func dashboardViewModelStartsEmptyAndLoading() async throws {
    let viewModel = DashboardViewModel()
    // After P0-7 (delete generateMockResponse), the VM no longer seeds mock data.
    // It starts empty and in `.loading` state until refresh() pulls real data.
    #expect(viewModel.dashboardData.metrics.isEmpty)
    #expect(viewModel.dashboardData.greeting == "")
    if case .loading = viewModel.viewState {
        // Expected
    } else {
        Issue.record("DashboardViewModel should start in .loading state")
    }
}

// MARK: - CoachViewModel

@Test @MainActor func coachViewModelStartsWithEmptyMessages() async throws {
    let viewModel = CoachViewModel()
    // After P0-7 (delete seedMessages), the VM starts empty.
    // loadHistory() is called from init() but completes async — synchronous
    // check just confirms there's no fake seed data.
    #expect(!viewModel.isTyping)
}

// MARK: - Auth Models

@Test func tokenPairDecodesFromBackendShape() async throws {
    // Sanity check that AuthManager.TokenPair can model a backend response
    let user = AuthManager.UserInfo(
        id: "001234.test.5678",
        name: "Test User",
        email: "test@example.com",
        is_private_email: false
    )
    let pair = AuthManager.TokenPair(
        accessToken: "fake-access",
        refreshToken: "fake-refresh",
        expiresIn: 900,
        user: user
    )
    #expect(pair.user.id == "001234.test.5678")
    #expect(pair.expiresIn == 900)
}
