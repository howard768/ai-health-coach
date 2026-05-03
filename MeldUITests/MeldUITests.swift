import XCTest

// Swift 6: XCUIApplication is @MainActor-isolated, so any test method that
// constructs or drives it must run on the main actor. Mark the class
// @MainActor (rather than each method) to keep future tests simple.
@MainActor
final class MeldUITests: XCTestCase {
    /// Smoke check: the app builds and can be launched on a simulator.
    ///
    /// Intentionally minimal. `XCUIApplication.launch()` records a test
    /// failure itself if the simulator cannot start the app; if the call
    /// returns normally we have verified the smoke invariant (app boots).
    ///
    /// Everything richer, specific UI elements, navigation, state
    /// transitions, is owned by Maestro (`maestro/flows/`). Maestro
    /// uses the same `-uitesting-skip-auth` bypass, has a backend-less
    /// harness, and is much less flaky than XCUITest against a SwiftUI
    /// app whose rendering depends on network state.
    ///
    /// Prior attempts here used `app.wait(for: .runningForeground)` and
    /// `app.buttons["tab-home"].waitForExistence`, which failed on CI
    /// with "Failed to get background assertion", an XCUITest
    /// infrastructure flake on macos-15 runners, not an app bug (the
    /// app was launching with a valid pid). Keeping this test minimal.
    func testAppLaunches() throws {
        let app = XCUIApplication()
        // Same auth-bypass arg Maestro uses. MeldApp reads both the
        // `-uitesting-skip-auth` CLI arg and the MELD_UI_TESTING env var.
        app.launchArguments = ["-uitesting-skip-auth"]
        app.launchEnvironment["MELD_UI_TESTING"] = "1"
        app.launch()
    }
}
