import XCTest

// Swift 6: XCUIApplication is @MainActor-isolated, so any test method that
// constructs or drives it must run on the main actor. Mark the class
// @MainActor (rather than each method) to keep future tests simple.
@MainActor
final class MeldUITests: XCTestCase {
    func testAppLaunches() throws {
        let app = XCUIApplication()
        app.launch()
    }
}
