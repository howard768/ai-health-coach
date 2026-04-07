import SwiftUI

@main
struct MeldApp: App {

    init() {
        #if DEBUG
        DSFontDebug.verifyFonts()
        #endif
    }

    var body: some Scene {
        WindowGroup {
            MainTabView()
        }
    }
}
