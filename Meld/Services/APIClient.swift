import Foundation

// MARK: - API Client
// Communicates with the FastAPI backend.
// Fetches real dashboard data and sends coach chat messages.

actor APIClient {
    static let shared = APIClient()

    private let baseURL: URL
    private let decoder: JSONDecoder
    private let session: URLSession

    #if DEBUG
    /// In-memory token for test builds where Keychain is unavailable
    /// (e.g., unsigned simulator builds with CODE_SIGNING_ALLOWED=NO).
    private var testAccessToken: String?

    func setTestToken(_ token: String) {
        testAccessToken = token
    }
    #endif

    private init() {
        // URL resolution priority:
        // 1. Simulator: always localhost (same machine as backend)
        // 2. Device: API_BASE_URL from Info.plist (injected per Debug/Release config)
        // 3. Last-resort fallback: Railway production URL
        #if targetEnvironment(simulator)
        // Use 127.0.0.1 instead of localhost — the simulator resolves
        // localhost to ::1 (IPv6) first, which fails when the backend
        // only listens on 0.0.0.0 (IPv4).
        self.baseURL = URL(string: "http://127.0.0.1:8000/api")!
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
        // P2-11: Custom timeout config. Default URLSession timeouts are 60s
        // (request) / 7 days (resource) which means a hung Opus call would
        // spin the UI indefinitely. We cap the request at 45s (longer than
        // most Claude responses but shorter than user patience) and resource
        // at 90s (covers file uploads like food photos).
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 45  // seconds per request
        config.timeoutIntervalForResource = 90  // seconds per resource (total)
        config.waitsForConnectivity = true     // queue during brief offline periods
        self.session = URLSession(configuration: config)
    }

    /// Build a URL from a path relative to the server root (e.g., "/api/meals").
    /// Handles the baseURL already containing "/api" — strips it to get server root.
    var serverRoot: URL {
        // baseURL is like "http://host:8000/api" — go up one to get "http://host:8000"
        baseURL.deletingLastPathComponent()
    }

    // MARK: - Authed request helpers
    //
    // These wrap URLSession.data(for:) with:
    // 1. Automatic Authorization: Bearer <token> header attachment
    // 2. Single-flight refresh on 401 via AuthManager
    // 3. One retry of the original request with a fresh token
    //
    // On second 401, we throw .unauthorized and AuthManager wipes the session.

    private func attachAuth(_ request: inout URLRequest) async {
        #if DEBUG
        // Prefer in-memory test token (unsigned builds can't access Keychain)
        if let token = testAccessToken {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
            return
        }
        #endif
        // Read token from Keychain directly (AuthManager's validAccessToken also reads it).
        // We don't refresh preemptively — only on 401.
        if let token = try? await KeychainStore.shared.readAccessToken() {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
    }

    /// Send an HTTP request with automatic auth + 401 retry.
    /// On second 401, AuthManager wipes the session and this throws `.unauthorized`.
    private func authedData(for request: URLRequest) async throws -> (Data, URLResponse) {
        var req = request
        await attachAuth(&req)
        let (data, response) = try await session.data(for: req)

        if let http = response as? HTTPURLResponse, http.statusCode == 401 {
            // Try a single refresh + retry
            do {
                _ = try await AuthManager.shared.refresh()
            } catch {
                await AuthManager.shared.handleUnauthorized()
                throw APIError.unauthorized
            }
            // Rebuild request with fresh token
            var retry = request
            await attachAuth(&retry)
            let (retryData, retryResponse) = try await session.data(for: retry)
            if let retryHttp = retryResponse as? HTTPURLResponse, retryHttp.statusCode == 401 {
                await AuthManager.shared.handleUnauthorized()
                throw APIError.unauthorized
            }
            return (retryData, retryResponse)
        }
        return (data, response)
    }

    // MARK: - Generic send helpers
    //
    // P2-1: These helpers dedup the ~20 places that each wrote:
    //   let (data, response) = try await authedData(for: request)
    //   guard let http = response as? HTTPURLResponse, http.statusCode == 200 else {
    //       throw APIError.serverError
    //   }
    //
    // Now endpoints just call send(_:) for fire-and-forget writes or
    // sendDecoding(_:as:) for endpoints that return a Decodable body.
    //
    // NSURLErrorNotConnectedToInternet and friends are mapped to .networkError
    // so offline shows a useful message instead of a generic "server error".

    /// Execute a request where we only care about success — discards the body.
    /// Throws on non-200 or network failure.
    private func send(_ request: URLRequest) async throws {
        let (_, response) = try await authedDataOrNetworkError(for: request)
        try ensureOK(response)
    }

    /// Execute a request and decode the response body as `T`.
    /// Throws `.serverError` on non-200, `.decodingError` on bad payload,
    /// or `.networkError` on offline / transport failures.
    private func sendDecoding<T: Decodable>(
        _ request: URLRequest,
        as type: T.Type = T.self
    ) async throws -> T {
        let (data, response) = try await authedDataOrNetworkError(for: request)
        try ensureOK(response)
        do {
            return try decoder.decode(T.self, from: data)
        } catch {
            throw APIError.decodingError
        }
    }

    /// Variant for endpoints where 404 is a valid "not found" answer (barcode lookup).
    /// Returns nil on 404, decoded `T` on 200, throws on other statuses.
    private func sendDecodingOrNilOn404<T: Decodable>(
        _ request: URLRequest,
        as type: T.Type = T.self
    ) async throws -> T? {
        let (data, response) = try await authedDataOrNetworkError(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw APIError.serverError
        }
        if http.statusCode == 404 { return nil }
        guard http.statusCode == 200 else { throw APIError.serverError }
        do {
            return try decoder.decode(T.self, from: data)
        } catch {
            throw APIError.decodingError
        }
    }

    /// Wrap authedData(for:) with network-error translation so callers see
    /// `APIError.networkError` instead of raw NSError when offline.
    private func authedDataOrNetworkError(for request: URLRequest) async throws -> (Data, URLResponse) {
        do {
            return try await authedData(for: request)
        } catch let apiError as APIError {
            throw apiError
        } catch let urlError as URLError {
            switch urlError.code {
            case .notConnectedToInternet, .networkConnectionLost,
                 .dataNotAllowed, .cannotConnectToHost, .timedOut,
                 .cannotFindHost, .dnsLookupFailed:
                throw APIError.networkError
            default:
                throw APIError.serverError
            }
        } catch {
            throw APIError.serverError
        }
    }

    /// Validate that a URLResponse is HTTPURLResponse with status 200.
    private func ensureOK(_ response: URLResponse) throws {
        guard let http = response as? HTTPURLResponse, http.statusCode == 200 else {
            throw APIError.serverError
        }
    }

    /// Build a URLRequest with the given method, URL, and JSON body.
    private func jsonRequest<Body: Encodable>(
        url: URL,
        method: String,
        body: Body
    ) throws -> URLRequest {
        var request = URLRequest(url: url)
        request.httpMethod = method
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(body)
        return request
    }

    // MARK: - Auth endpoints
    //
    // These hit /auth/* which does NOT go through authedData — they either
    // don't need a bearer token (signInWithApple) or use a different auth
    // mechanism (refreshSession passes refresh_token in the body).

    func signInWithApple(
        identityToken: String,
        rawNonce: String,
        fullName: String?,
        email: String?,
        deviceId: String?
    ) async throws -> AuthManager.TokenPair {
        let url = serverRoot.appendingPathComponent("auth/apple")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let body: [String: Any?] = [
            "identity_token": identityToken,
            "raw_nonce": rawNonce,
            "full_name": fullName,
            "email": email,
            "device_id": deviceId,
        ]
        // Strip nils so the backend's Pydantic validator doesn't get confused
        let cleanBody = body.compactMapValues { $0 }
        request.httpBody = try JSONSerialization.data(withJSONObject: cleanBody)

        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse, http.statusCode == 200 else {
            if let body = String(data: data, encoding: .utf8) {
                Log.auth.error("/auth/apple failed: \(body, privacy: .private)")
            }
            throw APIError.serverError
        }
        return try decodeTokenPair(from: data)
    }

    func refreshSession(refreshToken: String) async throws -> AuthManager.TokenPair {
        let url = serverRoot.appendingPathComponent("auth/refresh")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        let body = ["refresh_token": refreshToken]
        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse, http.statusCode == 200 else {
            throw APIError.unauthorized
        }
        return try decodeTokenPair(from: data)
    }

    func logoutSession(refreshToken: String) async throws {
        let url = serverRoot.appendingPathComponent("auth/logout")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        let body = ["refresh_token": refreshToken]
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        // logout requires bearer token (CurrentUser dependency), so use authedData
        _ = try await authedData(for: request)
    }

    func deleteAccount() async throws {
        let url = serverRoot.appendingPathComponent("auth/delete")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        _ = try await authedData(for: request)
    }

    /// Decode a TokenPair from the backend's JSON response.
    private func decodeTokenPair(from data: Data) throws -> AuthManager.TokenPair {
        guard let json = try JSONSerialization.jsonObject(with: data) as? [String: Any],
              let accessToken = json["access_token"] as? String,
              let refreshToken = json["refresh_token"] as? String,
              let expiresIn = json["expires_in"] as? Int,
              let userDict = json["user"] as? [String: Any],
              let userId = userDict["id"] as? String
        else {
            throw APIError.serverError
        }
        let user = AuthManager.UserInfo(
            id: userId,
            name: userDict["name"] as? String,
            email: userDict["email"] as? String,
            is_private_email: (userDict["is_private_email"] as? Bool) ?? false
        )
        return AuthManager.TokenPair(
            accessToken: accessToken,
            refreshToken: refreshToken,
            expiresIn: expiresIn,
            user: user
        )
    }

    // MARK: - Dev Login (simulator only)

    #if DEBUG
    /// Call /auth/dev-login to get a valid session without Sign in with Apple.
    /// Only available when backend runs in development mode.
    func devLogin() async throws -> AuthManager.TokenPair {
        let url = serverRoot.appendingPathComponent("auth/dev-login")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse, http.statusCode == 200 else {
            throw APIError.serverError
        }
        return try decodeTokenPair(from: data)
    }
    #endif

    // MARK: - Dashboard

    func fetchDashboard() async throws -> APIDashboardResponse {
        let url = baseURL.appendingPathComponent("dashboard")
        return try await sendDecoding(URLRequest(url: url))
    }

    // MARK: - Coach Chat

    func sendMessage(_ message: String) async throws -> APIChatResponse {
        let url = baseURL.appendingPathComponent("coach/chat")
        let request = try jsonRequest(url: url, method: "POST", body: APIChatRequest(message: message))
        return try await sendDecoding(request)
    }

    // MARK: - Feedback

    func submitFeedback(messageId: Int, feedback: String) async throws {
        let url = baseURL.appendingPathComponent("coach/feedback")
        let request = try jsonRequest(
            url: url,
            method: "POST",
            body: APIFeedbackRequest(message_id: messageId, feedback: feedback)
        )
        try await send(request)
    }

    // MARK: - Chat History

    func fetchChatHistory() async throws -> [APIHistoryMessage] {
        let url = baseURL.appendingPathComponent("coach/history")
        let historyResponse: APIHistoryResponse = try await sendDecoding(URLRequest(url: url))
        return historyResponse.messages
    }

    // MARK: - Oura Sync

    func syncOura() async throws {
        let url = serverRoot.appendingPathComponent("api/sync/oura")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        try await send(request)
    }

    // MARK: - Garmin

    func loginGarmin(username: String, password: String) async throws {
        let url = serverRoot.appendingPathComponent("auth/garmin/login")
        let request = try jsonRequest(
            url: url,
            method: "POST",
            body: APICredentialsRequest(username: username, password: password)
        )
        try await send(request)
    }

    // MARK: - Peloton

    func loginPeloton(username: String, password: String) async throws {
        let url = serverRoot.appendingPathComponent("auth/peloton/login")
        let request = try jsonRequest(
            url: url,
            method: "POST",
            body: APICredentialsRequest(username: username, password: password)
        )
        try await send(request)
    }

    // MARK: - HealthKit Sync

    func syncHealthKitMetrics(_ metrics: [HealthKitService.HealthMetricPayload]) async throws {
        let url = serverRoot.appendingPathComponent("api/health/apple-health")
        let request = try jsonRequest(url: url, method: "POST", body: metrics)
        try await send(request)
    }

    // MARK: - Trends

    func fetchTrends(rangeDays: Int = 7) async throws -> APITrendsResponse {
        let url = serverRoot.appendingPathComponent("api/trends")
        var components = URLComponents(url: url, resolvingAgainstBaseURL: false)!
        components.queryItems = [URLQueryItem(name: "range", value: "\(rangeDays)")]
        return try await sendDecoding(URLRequest(url: components.url!))
    }

    // MARK: - Notifications

    func registerDeviceToken(_ token: String) async throws {
        let url = baseURL.deletingLastPathComponent()
            .appendingPathComponent("api/notifications/register")
        let request = try jsonRequest(
            url: url,
            method: "POST",
            body: APIDeviceTokenRegister(device_token: token, platform: "ios")
        )
        try await send(request)
    }

    func fetchNotificationPreferences() async throws -> APINotificationPreferences {
        let url = baseURL.deletingLastPathComponent()
            .appendingPathComponent("api/notifications/preferences")
        return try await sendDecoding(URLRequest(url: url))
    }

    func updateNotificationPreferences(_ prefs: APINotificationPreferences) async throws {
        let url = baseURL.deletingLastPathComponent()
            .appendingPathComponent("api/notifications/preferences")
        let request = try jsonRequest(url: url, method: "PUT", body: prefs)
        try await send(request)
    }

    // MARK: - Meals & Food

    func recognizeFood(imageData: Data) async throws -> [FoodItem] {
        let url = baseURL.deletingLastPathComponent()
            .appendingPathComponent("api/food/recognize")
        let base64 = imageData.base64EncodedString()
        let request = try jsonRequest(
            url: url,
            method: "POST",
            body: APIFoodRecognitionRequest(image_base64: base64, media_type: "image/jpeg")
        )
        let result: APIFoodRecognitionResponse = try await sendDecoding(request)
        return result.items.map { $0.toFoodItem() }
    }

    func logMeal(_ meal: Meal) async throws {
        let url = baseURL.deletingLastPathComponent()
            .appendingPathComponent("api/meals")
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
        let request = try jsonRequest(url: url, method: "POST", body: body)
        try await send(request)
    }

    func fetchMeals(date: String) async throws -> APIDailyMealsResponse {
        let url = baseURL.deletingLastPathComponent()
            .appendingPathComponent("api/meals")
        var components = URLComponents(url: url, resolvingAgainstBaseURL: false)!
        components.queryItems = [URLQueryItem(name: "date", value: date)]
        return try await sendDecoding(URLRequest(url: components.url!))
    }

    func searchFood(_ query: String) async throws -> [FoodItem] {
        let url = baseURL.deletingLastPathComponent()
            .appendingPathComponent("api/food/search")
        let request = try jsonRequest(
            url: url,
            method: "POST",
            body: APIFoodSearchRequest(query: query)
        )
        let result: APIFoodSearchResponse = try await sendDecoding(request)
        return result.results.map { $0.toFoodItem() }
    }

    func lookupBarcode(_ code: String) async throws -> FoodItem? {
        let url = baseURL.deletingLastPathComponent()
            .appendingPathComponent("api/food/barcode/\(code)")
        let item: APIFoodItemResponse? = try await sendDecodingOrNilOn404(URLRequest(url: url))
        return item?.toFoodItem()
    }

    // MARK: - User Profile

    func fetchUserProfile() async throws -> APIUserProfile {
        let url = serverRoot.appendingPathComponent("api/user/profile")
        return try await sendDecoding(URLRequest(url: url))
    }

    func updateUserProfile(_ update: APIUserProfileUpdate) async throws -> APIUserProfile {
        let url = serverRoot.appendingPathComponent("api/user/profile")
        let request = try jsonRequest(url: url, method: "PUT", body: update)
        return try await sendDecoding(request)
    }

    func reportNotificationOpened(notificationId: Int) async throws {
        let url = baseURL.deletingLastPathComponent()
            .appendingPathComponent("api/notifications/opened")
        let request = try jsonRequest(
            url: url,
            method: "POST",
            body: APINotificationOpenedRequest(notification_id: notificationId)
        )
        try await send(request)
    }

    // MARK: - Health Check

    func healthCheck() async -> Bool {
        // Unauthenticated — root endpoint is public
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
    case unauthorized  // 401 — refresh failed, session is dead

    var errorDescription: String? {
        switch self {
        case .serverError: "Something went wrong. Try again in a bit."
        case .networkError: "Can't connect. Check your internet."
        case .decodingError: "Got unexpected data from the server."
        case .unauthorized: "Please sign in again."
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

// P2-1: Small request-body structs used by the generic send helpers. Previously
// these were inline `[String: String]` dictionaries; giving them names lets
// `jsonRequest(url:method:body:)` stay generic-Encodable without resorting to
// Any or JSONSerialization.
struct APICredentialsRequest: Codable {
    let username: String
    let password: String
}

struct APIDeviceTokenRegister: Codable {
    let device_token: String
    let platform: String
}

struct APIFeedbackRequest: Codable {
    let message_id: Int
    let feedback: String
}

struct APIFoodRecognitionRequest: Codable {
    let image_base64: String
    let media_type: String
}

struct APIFoodSearchRequest: Codable {
    let query: String
}

struct APINotificationOpenedRequest: Codable {
    let notification_id: Int
}

struct APIChatResponse: Codable {
    let role: String
    let content: String
    let message_id: Int?
    // P2-18: decode routing/safety/model_used so future debug UI can read them.
    // Backend already returns these — ignoring would silently swallow info.
    let routing: APIChatRouting?
    let safety: APIChatSafety?
    let model_used: String?

    var messageId: Int? { message_id }
    var modelUsed: String? { model_used }
}

struct APIChatRouting: Codable {
    let tier: String?         // "rules" | "sonnet" | "opus"
    let reason: String?
    let confidence: Double?
    let safety_flag: Bool?
}

struct APIChatSafety: Codable {
    let is_concerning: Bool?
    let reasons: [String]?
    let disclaimer_included: Bool?
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
