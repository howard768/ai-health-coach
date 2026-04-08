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
        // Local development — use Mac's local IP so physical devices can connect
        // Switch to Railway URL for production
        self.baseURL = URL(string: "http://192.168.86.47:8000/api")!
        self.decoder = JSONDecoder()
        self.session = URLSession.shared
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
