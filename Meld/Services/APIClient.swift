import Foundation

// MARK: - API Client Stub
// Will communicate with the FastAPI backend.
// Stubbed for Cycle 1 — Dashboard uses mock data initially.

actor APIClient {
    static let shared = APIClient()

    private let baseURL: URL

    private init() {
        // Local development
        self.baseURL = URL(string: "http://localhost:8000/api")!
    }

    // MARK: - Dashboard

    /// Fetch pre-computed dashboard data from backend
    func fetchDashboard() async throws -> DashboardData {
        // TODO: Implement when backend is ready
        fatalError("Not implemented — using mock data via DashboardViewModel")
    }
}
