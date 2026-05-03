import SwiftUI

// MARK: - Offline Banner
//
// P2-10: A slim banner that slides in from the top whenever NetworkMonitor
// reports the device is offline, and slides out automatically when
// connectivity returns. Drop into any root view via `.offlineBanner()`.
//
// Design:
// - Uses our subtle warning color from the design system
// - Fixed 36pt height so it doesn't reflow content
// - Animated via default .easeInOut transition on opacity + offset
// - Does NOT block interaction, the underlying request still queues via
//   URLSession.waitsForConnectivity when the network returns
//
// Why a modifier and not a standalone view: we want this banner to attach
// once at the tab root so every screen gets it for free without each
// ViewModel having to surface its own offline state.

struct OfflineBanner: View {
    var body: some View {
        HStack(spacing: DSSpacing.sm) {
            Image(systemName: "wifi.slash")
                .font(.system(size: 13, weight: .semibold))
                .foregroundStyle(Color.white)
            Text("You're offline. Changes will sync when you're back.")
                .font(DSTypography.caption)
                .foregroundStyle(Color.white)
                .lineLimit(1)
                .minimumScaleFactor(0.8)
        }
        .frame(maxWidth: .infinity)
        .frame(height: 36)
        .background(DSColor.Status.warning)
        .accessibilityElement(children: .combine)
        .accessibilityLabel("Offline. Changes will sync when connectivity returns.")
    }
}

// MARK: - Attach modifier

extension View {
    /// Attach the app-wide offline banner. Observes NetworkMonitor and
    /// slides the banner in/out on the `.isOnline` transition.
    func offlineBanner() -> some View {
        modifier(OfflineBannerModifier())
    }
}

private struct OfflineBannerModifier: ViewModifier {
    @State private var monitor = NetworkMonitor.shared

    func body(content: Content) -> some View {
        content
            .safeAreaInset(edge: .top, spacing: 0) {
                if !monitor.isOnline {
                    OfflineBanner()
                        .transition(.move(edge: .top).combined(with: .opacity))
                }
            }
            .animation(.easeInOut(duration: 0.25), value: monitor.isOnline)
    }
}
