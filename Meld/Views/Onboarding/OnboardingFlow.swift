import SwiftUI

// MARK: - Onboarding Flow Coordinator
// Manages the 5-screen onboarding flow with state machine.
// Transitions between screens with spring animation.
// Passes completion handler to MainTabView.

struct OnboardingFlow: View {
    @State private var viewModel = OnboardingViewModel()
    var onComplete: () -> Void = {}

    var body: some View {
        ZStack {
            switch viewModel.currentStep {
            case .welcome:
                WelcomeView(viewModel: viewModel)
                    .transition(.move(edge: .trailing))
            case .goals:
                GoalsView(viewModel: viewModel)
                    .transition(.move(edge: .trailing))
            case .profile:
                QuickProfileView(viewModel: viewModel)
                    .transition(.move(edge: .trailing))
            case .connect:
                ConnectDataView(viewModel: viewModel)
                    .transition(.move(edge: .trailing))
            case .notifications:
                NotificationPrimingView(viewModel: viewModel)
                    .transition(.move(edge: .trailing))
            case .sync:
                FirstSyncView(viewModel: viewModel, onComplete: onComplete)
                    .transition(.move(edge: .trailing))
            }
        }
        .animation(DSMotion.standard, value: viewModel.currentStep.rawValue)
    }
}

// MARK: - Shared Layout Constants (Grid Spec)
// 402×874pt frame, 20pt margins, 362pt content width
// All onboarding screens use these constants.

enum OnboardingLayout {
    static let margin: CGFloat = 20  // Apple standard side margin
    static let contentWidth: CGFloat = 362

    // Vertical positions
    static let statusBarY: CGFloat = 16
    static let dotsY: CGFloat = 68
    static let titleY: CGFloat = 96

    // CTA anchored at bottom: 34pt safe + 16pt padding + 48pt button
    static let ctaBottomPadding: CGFloat = 50 // from screen bottom to CTA bottom edge
}

#Preview {
    OnboardingFlow()
}
