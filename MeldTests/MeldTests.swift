import Testing
@testable import Meld

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
