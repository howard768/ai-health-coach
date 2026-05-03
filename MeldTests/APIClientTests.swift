import Foundation
import Testing
@testable import Meld

// MARK: - APIClientTests
//
// APIClient is an actor wrapping URLSession, so the network path can't be
// driven from XCTest without dependency injection. What CAN be pinned here
// is the deterministic data layer the rest of the app depends on:
//
//   - APIError text (shown to users in toast banners on every error case)
//   - Request body encoding (every backend rename or field-removal breaks here)
//   - Response model decoding for endpoints not already covered by
//     MeldTests / SignalInsightTests
//   - The derived-state properties on APIUserProfile (label strings rendered
//     across the You tab and onboarding screens)
//   - APINotificationPreferences.defaults (used by the Settings UI on first
//     load before the backend round-trips)
//
// Wire-shape tests for APIChatResponse, APIContentBlock, APIDailyInsightResponse,
// and ChatDataCard live in MeldTests.swift and SignalInsightTests.swift.

// MARK: - APIError text contract

@Test func apiErrorServerHasUserFacingText() async throws {
    // These strings are surfaced by the toast banner on every failed request.
    // Renaming the cases without updating the copy ships unhelpful messages
    // to users, so the test pins both the case set and the visible text.
    #expect(APIError.serverError.errorDescription == "Something went wrong. Try again in a bit.")
}

@Test func apiErrorNetworkSuggestsConnectivityCheck() async throws {
    #expect(APIError.networkError.errorDescription == "Can't connect. Check your internet.")
}

@Test func apiErrorDecodingFlagsUnexpectedPayload() async throws {
    #expect(APIError.decodingError.errorDescription == "Got unexpected data from the server.")
}

@Test func apiErrorUnauthorizedAsksUserToSignInAgain() async throws {
    // After a failed refresh, AuthManager wipes the session and the UI shows
    // this. The text must NOT include any internal token/expiry detail.
    #expect(APIError.unauthorized.errorDescription == "Please sign in again.")
}

// MARK: - Request body encoding
//
// These structs sit on the iOS side of the wire and must encode to the exact
// snake_case / camelCase shapes the FastAPI routers parse. A field rename
// here would silently 422 on the backend.

@Test func chatRequestEncodesMessageField() async throws {
    let req = APIChatRequest(message: "How was my sleep?")
    let data = try JSONEncoder().encode(req)
    let json = try #require(try JSONSerialization.jsonObject(with: data) as? [String: Any])
    #expect(json["message"] as? String == "How was my sleep?")
    #expect(json.count == 1)
}

@Test func credentialsRequestEncodesUsernamePassword() async throws {
    // Used for Garmin + Peloton login. Backend reads keys exactly as named.
    let req = APICredentialsRequest(username: "user@example.com", password: "secret")
    let data = try JSONEncoder().encode(req)
    let json = try #require(try JSONSerialization.jsonObject(with: data) as? [String: Any])
    #expect(json["username"] as? String == "user@example.com")
    #expect(json["password"] as? String == "secret")
}

@Test func deviceTokenRegisterEncodesSnakeCaseAndPlatformIos() async throws {
    let req = APIDeviceTokenRegister(device_token: "abc123", platform: "ios")
    let data = try JSONEncoder().encode(req)
    let json = try #require(try JSONSerialization.jsonObject(with: data) as? [String: Any])
    #expect(json["device_token"] as? String == "abc123", "key must be snake_case for FastAPI")
    #expect(json["platform"] as? String == "ios")
}

@Test func feedbackRequestEncodesMessageIdAsInt() async throws {
    let req = APIFeedbackRequest(message_id: 42, feedback: "thumbs_up")
    let data = try JSONEncoder().encode(req)
    let json = try #require(try JSONSerialization.jsonObject(with: data) as? [String: Any])
    #expect(json["message_id"] as? Int == 42, "must encode as Int, not String")
    #expect(json["feedback"] as? String == "thumbs_up")
}

@Test func notificationOpenedRequestEncodesNotificationId() async throws {
    let req = APINotificationOpenedRequest(notification_id: 77)
    let data = try JSONEncoder().encode(req)
    let json = try #require(try JSONSerialization.jsonObject(with: data) as? [String: Any])
    #expect(json["notification_id"] as? Int == 77)
}

// MARK: - APIDashboardResponse.toDashboardData mapping

@Test func dashboardMapsAllMetricFieldsAndTrendDirection() async throws {
    let response = APIDashboardResponse(
        greeting: "Good morning",
        date: "2026-05-03",
        metrics: [
            APIMetricResponse(
                category: "sleepEfficiency", label: "Sleep",
                value: "91", unit: "%", subtitle: "above avg", trend: "positive"
            ),
            APIMetricResponse(
                category: "hrv", label: "HRV",
                value: "55", unit: "ms", subtitle: "stable", trend: "negative"
            ),
            APIMetricResponse(
                category: "restingHR", label: "RHR",
                value: "60", unit: "bpm", subtitle: "ok", trend: "neutral"
            ),
        ],
        recovery: APIRecoveryResponse(level: "High", description: "Rested"),
        coach_insight: APICoachInsightResponse(
            message: "Take it easy",
            timestamp: "2026-05-03T08:00:00Z"
        ),
        last_synced: nil
    )
    let dash = response.toDashboardData()
    #expect(dash.greeting == "Good morning")
    #expect(dash.metrics.count == 3)
    #expect(dash.metrics[0].category == .sleepEfficiency)
    #expect(dash.metrics[0].trend == .positive)
    #expect(dash.metrics[1].category == .hrv)
    #expect(dash.metrics[1].trend == .negative)
    #expect(dash.metrics[2].category == .restingHR)
    #expect(dash.metrics[2].trend == .neutral)
    #expect(dash.recoveryReadiness.level == .high)
}

@Test func dashboardFallsBackToSleepEfficiencyOnUnknownCategory() async throws {
    // Forward-compat: backend may add a new metric category before the
    // app gains a UI for it. Falling back instead of crashing keeps the
    // dashboard renderable.
    let response = APIDashboardResponse(
        greeting: "", date: "",
        metrics: [APIMetricResponse(
            category: "future_metric_kind", label: "X",
            value: "1", unit: "", subtitle: "", trend: "positive"
        )],
        recovery: APIRecoveryResponse(level: "Moderate", description: ""),
        coach_insight: APICoachInsightResponse(message: "", timestamp: ""),
        last_synced: nil
    )
    let dash = response.toDashboardData()
    #expect(dash.metrics[0].category == .sleepEfficiency)
}

@Test func dashboardFallsBackToHighReadinessOnUnknownLevel() async throws {
    let response = APIDashboardResponse(
        greeting: "", date: "", metrics: [],
        recovery: APIRecoveryResponse(level: "futureLevel", description: ""),
        coach_insight: APICoachInsightResponse(message: "", timestamp: ""),
        last_synced: nil
    )
    let dash = response.toDashboardData()
    #expect(dash.recoveryReadiness.level == .high, "must keep dashboard renderable")
}

@Test func dashboardCoachInsightFallsBackToNowOnInvalidTimestamp() async throws {
    let response = APIDashboardResponse(
        greeting: "", date: "", metrics: [],
        recovery: APIRecoveryResponse(level: "High", description: ""),
        coach_insight: APICoachInsightResponse(message: "Hello", timestamp: "not-a-date"),
        last_synced: nil
    )
    let dash = response.toDashboardData()
    #expect(dash.coachInsight.message == "Hello")
    // Timestamp falls back to "now": within a few seconds of test runtime.
    #expect(abs(dash.coachInsight.timestamp.timeIntervalSinceNow) < 5)
}

@Test func dashboardTrendStringMapsToPositiveOrNeutral() async throws {
    // Anything that's not "positive" or "negative" should land on .neutral.
    let response = APIDashboardResponse(
        greeting: "", date: "",
        metrics: [APIMetricResponse(
            category: "hrv", label: "HRV",
            value: "55", unit: "ms", subtitle: "", trend: "sideways"
        )],
        recovery: APIRecoveryResponse(level: "High", description: ""),
        coach_insight: APICoachInsightResponse(message: "", timestamp: ""),
        last_synced: nil
    )
    let dash = response.toDashboardData()
    #expect(dash.metrics[0].trend == .neutral)
}

// MARK: - APIFoodItemResponse.toFoodItem mapping

@Test func foodItemPreservesScalarFields() async throws {
    let item = APIFoodItemResponse(
        name: "Chicken Breast", serving_size: "6oz", serving_count: 1.5,
        calories: 280, protein: 52, carbs: 0, fat: 6,
        quality: "Whole", data_source: "USDA", confidence: 0.95
    )
    let f = item.toFoodItem()
    #expect(f.name == "Chicken Breast")
    #expect(f.servingSize == "6oz")
    #expect(f.servingCount == 1.5)
    #expect(f.calories == 280)
    #expect(f.protein == 52)
    #expect(f.quality == .whole)
    #expect(f.dataSource == .usda)
    #expect(f.confidence == 0.95)
}

@Test func foodItemDefaultsServingCountToOneWhenNil() async throws {
    let item = APIFoodItemResponse(
        name: "Apple", serving_size: "1 medium", serving_count: nil,
        calories: 95, protein: 0.5, carbs: 25, fat: 0.3,
        quality: "Whole", data_source: "USDA", confidence: 0.9
    )
    #expect(item.toFoodItem().servingCount == 1.0)
}

@Test func foodItemFallsBackOnUnknownEnumValues() async throws {
    // Backend can send a future quality tier or a new data source ahead of
    // the iOS enum gaining the case. Fallback to safe defaults so the food
    // log still renders.
    let item = APIFoodItemResponse(
        name: "X", serving_size: "1", serving_count: 1,
        calories: 0, protein: 0, carbs: 0, fat: 0,
        quality: "future_tier", data_source: "future_db", confidence: 0
    )
    let f = item.toFoodItem()
    #expect(f.quality == .mixed, "unknown quality must default to .mixed")
    #expect(f.dataSource == .aiEstimate, "unknown data_source must default to .aiEstimate")
}

// MARK: - APIUserProfile derived properties
//
// These power the You tab summary cards; if they break the user sees garbled
// labels like "0'0\"" or "lbs" on a numeric weight field.

@Test func userProfileHeightFormatsAsFeetInches() async throws {
    let p = makeProfile(height: 70)
    #expect(p.heightString == "5'10\"")
}

@Test func userProfileHeightReturnsDashWhenNil() async throws {
    let p = makeProfile(height: nil)
    #expect(p.heightString == "--")
}

@Test func userProfileWeightRoundsToInteger() async throws {
    let p = makeProfile(weight: 178.6)
    #expect(p.weightString == "178 lbs", "Int(Double) truncates, no rounding")
}

@Test func userProfileWeightReturnsDashWhenNil() async throws {
    let p = makeProfile(weight: nil)
    #expect(p.weightString == "--")
}

@Test func userProfileGoalsJoinWithMiddleDot() async throws {
    let p = makeProfile(goals: ["Strength", "Sleep"])
    #expect(p.goalsString == "Strength \u{00B7} Sleep")
}

@Test func userProfileGoalsReturnDashWhenEmpty() async throws {
    let p = makeProfile(goals: [])
    #expect(p.goalsString == "--")
}

@Test func userProfileInitialsTakeFirstLetterOfFirstTwoWords() async throws {
    #expect(makeProfile(name: "Brock Howard").initials == "BH")
    #expect(makeProfile(name: "Jane Q. Public").initials == "JQ", "stops at 2 words")
    #expect(makeProfile(name: "Cher").initials == "C", "single word still works")
}

@Test func userProfileInitialsReturnQuestionMarkWhenNameNil() async throws {
    #expect(makeProfile(name: nil).initials == "?")
}

// MARK: - APINotificationPreferences defaults
//
// First-launch users see these toggle states before the backend round-trips.
// The Settings screen reads `.defaults` directly. Pinning ensures a refactor
// doesn't accidentally flip a default-on toggle to off (e.g. morning_brief).

@Test func notificationPreferencesDefaultsMatchSettingsScreen() async throws {
    let d = APINotificationPreferences.defaults
    #expect(d.morning_brief == true)
    #expect(d.coaching_nudge == true)
    #expect(d.bedtime_coaching == true)
    #expect(d.streak_alerts == true)
    #expect(d.weekly_review == true)
    #expect(d.workout_reminders == false, "off by default, opt-in only")
    #expect(d.health_alerts == true)
    #expect(d.nudge_frequency == "2x_week")
    #expect(d.quiet_hours_start == "22:00")
    #expect(d.quiet_hours_end == "07:00")
}

// MARK: - Wire-format decode for response models not yet covered

@Test func dailyMealsResponseDecodesTotalsAsExpectedTypes() async throws {
    // Total fields are computed server-side. Pin the type contract so a
    // future backend change to e.g. `total_calories: float` is caught here.
    let json = """
    {
      "date": "2026-05-03",
      "meals": [],
      "total_calories": 1850,
      "total_protein": 145.5,
      "total_carbs": 180.0,
      "total_fat": 60.2
    }
    """.data(using: .utf8)!
    let r = try JSONDecoder().decode(APIDailyMealsResponse.self, from: json)
    #expect(r.date == "2026-05-03")
    #expect(r.meals.isEmpty)
    #expect(r.total_calories == 1850)
    #expect(r.total_protein == 145.5)
}

@Test func trendsResponseDecodesNestedMetricAndOptionalNutrition() async throws {
    let json = """
    {
      "range_days": 7,
      "metrics": {
        "sleep_efficiency": {
          "values": [88, 90, 91],
          "dates": ["2026-05-01", "2026-05-02", "2026-05-03"],
          "baseline": 87.5,
          "personal_min": 80,
          "personal_max": 95,
          "personal_average": 89.6
        }
      },
      "nutrition": null
    }
    """.data(using: .utf8)!
    let r = try JSONDecoder().decode(APITrendsResponse.self, from: json)
    #expect(r.range_days == 7)
    let trend = try #require(r.metrics["sleep_efficiency"])
    #expect(trend.values.count == 3)
    #expect(trend.baseline == 87.5)
    #expect(r.nutrition == nil)
}

@Test func dataSourceDecodesConnectedAndLastSynced() async throws {
    let json = """
    { "name": "Oura", "connected": true, "last_synced": "2026-05-03T07:30:00Z" }
    """.data(using: .utf8)!
    let s = try JSONDecoder().decode(APIDataSource.self, from: json)
    #expect(s.name == "Oura")
    #expect(s.connected == true)
    #expect(s.last_synced == "2026-05-03T07:30:00Z")
}

@Test func dataSourceDecodesNeverSynced() async throws {
    // last_synced is null when the user has connected but a sync hasn't run.
    let json = """
    { "name": "Garmin", "connected": true, "last_synced": null }
    """.data(using: .utf8)!
    let s = try JSONDecoder().decode(APIDataSource.self, from: json)
    #expect(s.last_synced == nil)
}

@Test func chatResponseDecodesRoutingSafetyAndModelUsedForDebugUI() async throws {
    // P2-18: backend always returns these. Pinning the decode keeps them
    // available to a future debug overlay without a follow-up wire change.
    let json = """
    {
      "role": "coach",
      "content": "ok",
      "blocks": null,
      "message_id": 7,
      "routing": { "tier": "sonnet", "reason": "general", "confidence": 0.8, "safety_flag": false },
      "safety": { "is_concerning": false, "reasons": [], "disclaimer_included": false },
      "model_used": "claude-sonnet-4-5"
    }
    """.data(using: .utf8)!
    let r = try JSONDecoder().decode(APIChatResponse.self, from: json)
    #expect(r.routing?.tier == "sonnet")
    #expect(r.safety?.is_concerning == false)
    #expect(r.modelUsed == "claude-sonnet-4-5")
}

// MARK: - Helpers

private func makeProfile(
    name: String? = "Test User",
    height: Int? = 70,
    weight: Double? = 170,
    goals: [String] = ["Sleep"]
) -> APIUserProfile {
    APIUserProfile(
        name: name,
        email: "test@example.com",
        age: 35,
        height_inches: height,
        weight_lbs: weight,
        onboarding_complete: true,
        target_weight_lbs: nil,
        goals: goals,
        training_experience: nil,
        training_days_per_week: nil,
        member_since: "2026-01-01",
        data_sources: []
    )
}
