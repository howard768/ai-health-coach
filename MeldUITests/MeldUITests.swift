import XCTest

// Swift 6: XCUIApplication is @MainActor-isolated, so any test method that
// constructs or drives it must run on the main actor. Mark the class
// @MainActor (rather than each method) to keep future tests simple.
@MainActor
final class MeldUITests: XCTestCase {
    func testAppLaunches() throws {
        let app = XCUIApplication()
        // MeldApp reads -uitesting-skip-auth and fast-paths past onboarding
        // + signs in synthetically (see MeldApp.init). Without this, launch
        // hangs on the auth / onboarding flow and the test reports
        // "pid 0, failed to get background assertion" because the app
        // never finishes boot within XCTest's timeout.
        app.launchArguments = ["-uitesting-skip-auth"]
        app.launch()

        // Wait for the home tab to appear — mirrors the Maestro smoke flow.
        // The tab-home identifier is set by MeldTabBar via
        // `.accessibilityIdentifier("tab-\(tab.rawValue)")`.
        XCTAssertTrue(
            app.buttons["tab-home"].waitForExistence(timeout: 15),
            "Home tab should appear within 15s of launch"
        )
    }
}
