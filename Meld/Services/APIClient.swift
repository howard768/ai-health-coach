import Foundation

// MARK: - API Client
// Communicates with the FastAPI backend.
// Fetches real dashboard data and sends coach chat messages.

actor APIClient {
    static let shared = APIClient()

    private let baseURL: URL
    private let decoder: JSONDecoder
    private let session: URLSession

    private init() {
        // URL resolution priority:
        // 1. Simulator: always localhost (same machine as backend)
        // 2. Device: API_BASE_URL from Info.plist (injected per Debug/Release config)
        // 3. Last-resort fallback: Railway production URL
        #if targetEnvironment(simulator)
        self.baseURL = URL(string: "http://localhost:8000/api")!
        #else
        let plistURL = Bundle.main.object(forInfoDictionaryKey: "API_BASE_URL") as? String
        let resolvedURL: String = {
            if let plistURL, !plistURL.isEmpty, let _ = URL(string: plistURL) {
                return plistURL
            }
            // Fallback — should never hit in a properly configured build
            return "https://zippy-forgiveness-production-0704.up.railway.app/api"
        }()
        self.baseURL = URL(string: resolvedURL)!
        #endif
        self.decoder = JSONDecoder()
        self.session = URLSession.shared
    }

    /// Build a URL from a path relative to the server root (e.g., "/api/meals").
    /// Handles the baseURL already containing "/api" — strips it to get server root.
    /// nonisolated: only reads the immutable `let baseURL`, safe across actor boundaries.
    nonisolated var serverRoot: URL {
        // baseURL is like "http://host:8000/api" — go up one to get "http://host:8000"
        baseURL.deletingLastPathComponent()
    }

    // MARK: - Dashboard

    func fetchDashboard() async throws -> APIDashboardResponse {
        let url = baseURL.appendingPathComponent("dashboard")
        let (data, response) = try await session.data(from: url)

        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw APIError.serverError
        }

        return try decoder.decode(APIDashboardResponse.self, from: data)
    }

    // MARK: - Coach Chat

    func sendMessage(_ message: String) async throws -> APIChatResponse {
        let url = baseURL.appendingPathComponent("coach/chat")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let body = APIChatRequest(message: message)
        request.httpBody = try JSONEncoder().encode(body)

        let (data, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw APIError.serverError
        }

        return try decoder.decode(APIChatResponse.self, from: data)
    }

    // MARK: - Feedback

    func submitFeedback(messageId: Int, feedback: String) async throws {
        let url = baseURL.appendingPathComponent("coach/feedback")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let body = ["message_id": messageId, "feedback": feedback] as [String: Any]
        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (_, response) = try await session.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw APIError.serverError
        }
    }

    // MARK: - Chat History

    func fetchChatHistory() async throws -> [APIHistoryMessage] {
        let url = baseURL.appendingPathComponent("coach/history")
        let (data, response) = try await session.data(from: url)

        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw APIError.serverError
        }

        let historyResponse = try decoder.decode(APIHistoryResponse.self, from: data)
        return historyResponse.messages
    }

    // MARK: - Oura Sync

    func syncOura() async throws {
        let url = serverRoot.appendingPathComponent("api/sync/oura")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"

        let (_, response) = try await session.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw APIError.serverError
        }
    }

    // MARK: - Garmin

    func loginGarmin(username: String, password: String) async throws {
        let url = serverRoot.appendingPathComponent("auth/garmin/login")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let body = ["username": username, "password": password]
        request.httpBody = try JSONEncoder().encode(body)

        let (_, response) = try await session.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw APIError.serverError
        }
    }

    // MARK: - Peloton

    func loginPeloton(username: String, password: String) async throws {
        let url = serverRoot.appendingPathComponent("auth/peloton/login")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let body = ["username": username, "password": password]
        request.httpBody = try JSONEncoder().encode(body)

        let (_, response) = try await session.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw APIError.serverError
        }
    }

    // MARK: - HealthKit Sync

    func syncHealthKitMetrics(_ metrics: [HealthKitService.HealthMetricPayload]) async throws {
        let url = serverRoot.appendingPathComponent("api/health/apple-health")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(metrics)

        let (_, response) = try await session.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw APIError.serverError
        }
    }

    // MARK: - Trends

    func fetchTrends(rangeDays: Int = 7) async throws -> APITrendsResponse {
        let url = serverRoot.appendingPathComponent("api/trends")
        var components = URLComponents(url: url, resolvingAgainstBaseURL: false)!
        components.queryItems = [URLQueryItem(name: "range", value: "\(rangeDays)")]

        let (data, response) = try await session.data(from: components.url!)
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw APIError.serverError
        }
        return try decoder.decode(APITrendsResponse.self, from: data)
    }

    // MARK: - Notifications

    func registerDeviceToken(_ token: String) async throws {
        let url = baseURL.deletingLastPathComponent()
            .appendingPathComponent("api/notifications/register")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let body = ["device_token": token, "platform": "ios"]
        request.httpBody = try JSONEncoder().encode(body)

        let (_, response) = try await session.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw APIError.serverError
        }
    }

    func fetchNotificationPreferences() async throws -> APINotificationPreferences {
        let url = baseURL.deletingLastPathComponent()
            .appendingPathComponent("api/notifications/preferences")
        let (data, response) = try await session.data(from: url)
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw APIError.serverError
        }
        return try decoder.decode(APINotificationPreferences.self, from: data)
    }

    func updateNotificationPreferences(_ prefs: APINotificationPreferences) async throws {
        let url = baseURL.deletingLastPathComponent()
            .appendingPathComponent("api/notifications/preferences")
        var request = URLRequest(url: url)
        request.httpMethod = "PUT"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(prefs)

        let (_, response) = try await session.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw APIError.serverError
        }
    }

    // MARK: - Meals & Food

    func recognizeFood(imageData: Data) async throws -> [FoodItem] {
        let url = baseURL.deletingLastPathComponent()
            .appendingPathComponent("api/food/recognize")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let base64 = imageData.base64EncodedString()
        let body: [String: String] = ["image_base64": base64, "media_type": "image/jpeg"]
        request.httpBody = try JSONEncoder().encode(body)

        let (data, response) = try await session.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw APIError.serverError
        }

        let result = try decoder.decode(APIFoodRecognitionResponse.self, from: data)
        return result.items.map { $0.toFoodItem() }
    }

    func logMeal(_ meal: Meal) async throws {
        let url = baseURL.deletingLastPathComponent()
            .appendingPathComponent("api/meals")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let body = APIMealCreate(
            meal_type: meal.mealType.rawValue.lowercased(),
            source: meal.source.rawValue,
            items: meal.items.map { item in
                APIFoodItemCreate(
                    name: item.name,
                    serving_size: item.servingSize,
                    serving_count: Double(item.servingCount),
                    calories: item.calories,
                    protein: item.protein,
                    carbs: item.carbs,
                    fat: item.fat,
                    quality: item.quality.rawValue,
                    data_source: item.dataSource.rawValue,
                    confidence: item.confidence
                )
            }
        )
        request.httpBody = try JSONEncoder().encode(body)

        let (_, response) = try await session.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw APIError.serverError
        }
    }

    func fetchMeals(date: String) async throws -> APIDailyMealsResponse {
        let url = baseURL.deletingLastPathComponent()
            .appendingPathComponent("api/meals")
        var components = URLComponents(url: url, resolvingAgainstBaseURL: false)!
        components.queryItems = [URLQueryItem(name: "date", value: date)]

        let (data, response) = try await session.data(from: components.url!)
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw APIError.serverError
        }

        return try decoder.decode(APIDailyMealsResponse.self, from: data)
    }

    func searchFood(_ query: String) async throws -> [FoodItem] {
        let url = baseURL.deletingLastPathComponent()
            .appendingPathComponent("api/food/search")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let body = ["query": query]
        request.httpBody = try JSONEncoder().encode(body)

        let (data, response) = try await session.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw APIError.serverError
        }

        let result = try decoder.decode(APIFoodSearchResponse.self, from: data)
        return result.results.map { $0.toFoodItem() }
    }

    func lookupBarcode(_ code: String) async throws -> FoodItem? {
        let url = baseURL.deletingLastPathComponent()
            .appendingPathComponent("api/food/barcode/\(code)")
        let (data, response) = try await session.data(from: url)
        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.serverError
        }
        if httpResponse.statusCode == 404 { return nil }
        guard httpResponse.statusCode == 200 else { throw APIError.serverError }

        let item = try decoder.decode(APIFoodItemResponse.self, from: data)
        return item.toFoodItem()
    }

    // MARK: - User Profile

    func fetchUserProfile() async throws -> APIUserProfile {
        let url = serverRoot.appendingPathComponent("api/user/profile")
        let (data, response) = try await session.data(from: url)
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw APIError.serverError
        }
        return try decoder.decode(APIUserProfile.self, from: data)
    }

    func updateUserProfile(_ update: APIUserProfileUpdate) async throws -> APIUserProfile {
        let url = serverRoot.appendingPathComponent("api/user/profile")
        var request = URLRequest(url: url)
        request.httpMethod = "PUT"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(update)

        let (data, response) = try await session.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw APIError.serverError
        }
        return try decoder.decode(APIUserProfile.self, from: data)
    }

    func disconnectOura() async throws {
        let url = serverRoot.appendingPathComponent("api/user/oura")
        var request = URLRequest(url: url)
        request.httpMethod = "DELETE"

        let (_, response) = try await session.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 204 else {
            throw APIError.serverError
        }
    }

    func reportNotificationOpened(notificationId: Int) async throws {
        let url = baseURL.deletingLastPathComponent()
            .appendingPathComponent("api/notifications/opened")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let body = ["notification_id": notificationId]
        request.httpBody = try JSONEncoder().encode(body)

        let (_, response) = try await session.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw APIError.serverError
        }
    }

    // MARK: - Health Check

    func healthCheck() async -> Bool {
        let url = baseURL.deletingLastPathComponent()
        do {
            let (_, response) = try await session.data(from: url)
            return (response as? HTTPURLResponse)?.statusCode == 200
        } catch {
            return false
        }
    }
}

// MARK: - API Errors

enum APIError: Error, LocalizedError {
    case serverError
    case networkError
    case decodingError

    var errorDescription: String? {
        switch self {
        case .serverError: "Something went wrong. Try again in a bit."
        case .networkError: "Can't connect. Check your internet."
        case .decodingError: "Got unexpected data from the server."
        }
    }
}

// MARK: - API Response Models

struct APIMetricResponse: Codable {
    let category: String
    let label: String
    let value: String
    let unit: String
    let subtitle: String
    let trend: String
}

struct APIRecoveryResponse: Codable {
    let level: String
    let description: String
}

struct APICoachInsightResponse: Codable {
    let message: String
    let timestamp: String
}

struct APIDashboardResponse: Codable {
    let greeting: String
    let date: String
    let metrics: [APIMetricResponse]
    let recovery: APIRecoveryResponse
    let coach_insight: APICoachInsightResponse
    let last_synced: String?

    // Convert to app model
    func toDashboardData() -> DashboardData {
        DashboardData(
            date: Date(),
            greeting: greeting,
            metrics: metrics.map { m in
                HealthMetric(
                    category: MetricCategory(rawValue: m.category) ?? .sleepEfficiency,
                    label: m.label,
                    value: m.value,
                    unit: m.unit,
                    subtitle: m.subtitle,
                    trend: m.trend == "positive" ? .positive : m.trend == "negative" ? .negative : .neutral
                )
            },
            recoveryReadiness: RecoveryReadiness(
                level: ReadinessLevel(rawValue: recovery.level) ?? .high,
                description: recovery.description
            ),
            coachInsight: CoachInsight(
                message: coach_insight.message,
                timestamp: ISO8601DateFormatter().date(from: coach_insight.timestamp) ?? Date()
            ),
            lastSynced: Date()
        )
    }
}

struct APIChatRequest: Codable {
    let message: String
}

struct APIChatResponse: Codable {
    let role: String
    let content: String
    let message_id: Int?

    var messageId: Int? { message_id }
}

struct APIHistoryMessage: Codable {
    let id: Int
    let role: String
    let content: String
    let model_used: String?
    let routing_tier: String?
    let created_at: String

    var createdAt: String { created_at }
}

struct APIHistoryResponse: Codable {
    let messages: [APIHistoryMessage]
    let conversation_id: Int
}

// MARK: - Meal/Food API Models

struct APIFoodItemResponse: Codable {
    let name: String
    let serving_size: String
    let serving_count: Double?
    let calories: Int
    let protein: Double
    let carbs: Double
    let fat: Double
    let quality: String
    let data_source: String
    let confidence: Double

    func toFoodItem() -> FoodItem {
        FoodItem(
            name: name,
            servingSize: serving_size,
            servingCount: serving_count ?? 1.0,
            calories: calories,
            protein: protein,
            carbs: carbs,
            fat: fat,
            quality: FoodQuality(rawValue: quality) ?? .mixed,
            dataSource: FoodDataSource(rawValue: data_source) ?? .aiEstimate,
            confidence: confidence
        )
    }
}

struct APIFoodItemCreate: Codable {
    let name: String
    let serving_size: String
    let serving_count: Double
    let calories: Int
    let protein: Double
    let carbs: Double
    let fat: Double
    let quality: String
    let data_source: String
    let confidence: Double
}

struct APIMealCreate: Codable {
    let meal_type: String
    let source: String
    let items: [APIFoodItemCreate]
}

struct APIFoodRecognitionResponse: Codable {
    let items: [APIFoodItemResponse]
    let meal_type: String
}

struct APIFoodSearchResponse: Codable {
    let results: [APIFoodItemResponse]
}

struct APIDailyMealsResponse: Codable {
    let date: String
    let meals: [APIMealResponse]
    let total_calories: Int
    let total_protein: Double
    let total_carbs: Double
    let total_fat: Double
}

struct APIMealResponse: Codable {
    let id: Int
    let date: String
    let meal_type: String
    let source: String
    let items: [APIFoodItemResponse]
    let total_calories: Int
    let total_protein: Double
    let total_carbs: Double
    let total_fat: Double
    let created_at: String
}

struct APITrendsResponse: Codable {
    let range_days: Int
    let metrics: [String: APIMetricTrend]
}

struct APIMetricTrend: Codable {
    let values: [Double]
    let dates: [String]?
    let baseline: Double
    let personal_min: Double
    let personal_max: Double
    let personal_average: Double
}

struct APIUserProfile: Codable {
    let name: String?
    let email: String?
    let age: Int?
    let height_inches: Int?
    let weight_lbs: Double?
    let target_weight_lbs: Double?
    let goals: [String]
    let training_experience: String?
    let training_days_per_week: Int?
    let member_since: String?
    let data_sources: [APIDataSource]

    var heightString: String {
        guard let inches = height_inches else { return "--" }
        return "\(inches / 12)'\(inches % 12)\""
    }

    var weightString: String {
        guard let lbs = weight_lbs else { return "--" }
        return "\(Int(lbs)) lbs"
    }

    var goalsString: String {
        goals.isEmpty ? "--" : goals.joined(separator: " · ")
    }

    var initials: String {
        guard let name else { return "?" }
        let parts = name.split(separator: " ")
        return parts.prefix(2).map { String($0.prefix(1)) }.joined()
    }
}

struct APIDataSource: Codable {
    let name: String
    let connected: Bool
    let last_synced: String?
}

/// Payload for PUT /api/user/profile. Mirrors backend UserProfileUpdate schema.
/// All fields optional — the backend merges onto the existing record.
struct APIUserProfileUpdate: Codable {
    var name: String?
    var email: String?
    var age: Int?
    var height_inches: Int?
    var weight_lbs: Double?
    var target_weight_lbs: Double?
    var goals: [String]?
    var training_experience: String?
    var training_days_per_week: Int?
}

struct APINotificationPreferences: Codable {
    var morning_brief: Bool
    var coaching_nudge: Bool
    var bedtime_coaching: Bool
    var streak_alerts: Bool
    var weekly_review: Bool
    var workout_reminders: Bool
    var health_alerts: Bool
    var nudge_frequency: String
    var quiet_hours_start: String
    var quiet_hours_end: String

    static let defaults = APINotificationPreferences(
        morning_brief: true,
        coaching_nudge: true,
        bedtime_coaching: true,
        streak_alerts: true,
        weekly_review: true,
        workout_reminders: false,
        health_alerts: true,
        nudge_frequency: "2x_week",
        quiet_hours_start: "22:00",
        quiet_hours_end: "07:00"
    )
}
