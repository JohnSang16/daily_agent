import SwiftUI

@main
struct DailyAgentApp: App {
    @StateObject private var state = AppState()

    var body: some Scene {
        WindowGroup {
            RootView().environmentObject(state)
        }
    }
}
