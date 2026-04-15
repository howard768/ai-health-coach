import XCTest

// Swift 6: XCUIApplication is @MainActor-isolated, so any test method that
// constructs or drives it must run on the main actor. Mark the class
// @MainActor (rather than each method) to keep future tests simple.
@MainActor
final class MeldUITests: XCTestCase {
    /// Smoke check: the app boots and reaches the foreground.
    ///
    /// Intentionally minimal. Specific UI element and navigation coverage
    /// is owned by Maestro (see `maestro/flows/`), which tests against
    /// the same `-uitesting-skip-auth` bypass and has a full backend-less
    /// harness for element assertions. Here we just verify that a build
    /// which ships off CI can actually launch in the simulator; probing
    /// specific SwiftUI-rendered elements from XCUITest is flaky against
    /// an app that depends on network state for rendering.
    func testAppLaunches() throws {
        let app = XCUIApplication()
        // Same auth-bypass arg Maestro uses. MeldApp reads both the
        // `-uitesting-skip-auth` CLI arg and the MELD_UI_TESTING env var.
        app.launchArguments = ["-uitesting-skip-auth"]
        app.launchEnvironment["MELD_UI_TESTING"] = "1"
        app.launch()

        XCTAssertTrue(
            app.wait(for: .runningForeground, timeout: 20),
            "App should reach foreground within 20s of launch"
        )
    }
}
