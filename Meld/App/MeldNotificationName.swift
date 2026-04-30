import Foundation

/// Centralized `Notification.Name` constants for in-app cross-component
/// signalling. Pre-PR-H, every site that posted or observed a notification
/// used `.init("MeldSwitchTab")` directly — six call sites, each with its
/// own potential typo, and no compiler help finding stale references when
/// the name changes.
///
/// One enum-of-strings keystone per audit finding: a typo in any one site
/// silently became a no-op (no listener fired) without any warning.
extension Notification.Name {

    /// Posted by views that want to switch the bottom tab. Carries
    /// `userInfo: ["tab": <Tab.rawValue>]` and optionally
    /// `["message": <String>]` to prefill the coach input.
    static let meldSwitchTab = Notification.Name("MeldSwitchTab")
}
