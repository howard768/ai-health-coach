import Foundation
import Network
import Observation

// MARK: - Network Monitor
//
// P2-10: Provides app-wide reachability state so ViewModels can distinguish
// "offline" from "server error" and show a dedicated offline banner instead
// of a generic "something went wrong". URLSession already handles
// waitsForConnectivity + timeouts (set in APIClient.swift) — this adds the
// observable state layer on top.
//
// Usage:
//   if !NetworkMonitor.shared.isOnline { show offline UI; return }
//   try await APIClient.shared.fetchDashboard()
//
// And for SwiftUI banners:
//   @Bindable var monitor = NetworkMonitor.shared
//   if !monitor.isOnline { OfflineBanner() }
//
// Uses NWPathMonitor on a background queue; publishes updates on the
// main actor so SwiftUI can observe without Task hops.

@Observable @MainActor
final class NetworkMonitor {
    static let shared = NetworkMonitor()

    /// True when the device has at least one usable network interface.
    /// Starts optimistic (true) so we don't show "offline" before the first
    /// path update lands.
    private(set) var isOnline: Bool = true

    /// Current connection type — useful for "using cellular" UX or metered-
    /// data decisions. Mirrors NWInterface.InterfaceType.
    enum ConnectionType {
        case wifi
        case cellular
        case wired
        case other
        case none
    }
    private(set) var connectionType: ConnectionType = .other

    /// True while actively using an expensive connection (usually cellular).
    /// Read from NWPath.isExpensive — used to suppress large background syncs.
    private(set) var isExpensive: Bool = false

    /// True while using a constrained connection (Low Data Mode).
    private(set) var isConstrained: Bool = false

    // Non-observable backing infra so SwiftUI doesn't try to track the monitor itself
    @ObservationIgnored private let monitor = NWPathMonitor()
    @ObservationIgnored private let queue = DispatchQueue(label: "com.heymeld.NetworkMonitor")
    @ObservationIgnored private var started = false

    private init() {
        start()
    }

    private func start() {
        guard !started else { return }
        started = true
        monitor.pathUpdateHandler = { [weak self] path in
            guard let self else { return }
            Task { @MainActor in
                self.apply(path)
            }
        }
        monitor.start(queue: queue)
    }

    private func apply(_ path: NWPath) {
        let newOnline = path.status == .satisfied
        if newOnline != isOnline {
            isOnline = newOnline
        }
        isExpensive = path.isExpensive
        isConstrained = path.isConstrained

        let newType: ConnectionType
        if path.usesInterfaceType(.wifi) {
            newType = .wifi
        } else if path.usesInterfaceType(.cellular) {
            newType = .cellular
        } else if path.usesInterfaceType(.wiredEthernet) {
            newType = .wired
        } else if path.status == .satisfied {
            newType = .other
        } else {
            newType = .none
        }
        if newType != connectionType {
            connectionType = newType
        }
    }

    /// Await the next transition back online. Returns immediately if already
    /// online. ViewModels can use this to defer a retry until connectivity
    /// returns instead of spinning.
    func waitUntilOnline() async {
        if isOnline { return }
        await withCheckedContinuation { continuation in
            // Poll at 1Hz — cheap and robust to missed path updates.
            Task { @MainActor in
                while !isOnline {
                    try? await Task.sleep(nanoseconds: 1_000_000_000)
                }
                continuation.resume()
            }
        }
    }
}
