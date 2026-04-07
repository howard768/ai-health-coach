import Testing
@testable import Meld

@Test func dashboardViewModelLoadsMockData() async throws {
    let viewModel = DashboardViewModel()
    #expect(viewModel.dashboardData.metrics.count == 4)
    #expect(viewModel.dashboardData.recoveryReadiness.level == .high)
}
