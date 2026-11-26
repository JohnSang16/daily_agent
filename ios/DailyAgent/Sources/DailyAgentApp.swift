import SwiftUI

@main
struct DailyAgentApp: App {
    @StateObject private var state = AppState()
    @State private var splash = true

    var body: some Scene {
        WindowGroup {
            ZStack {
                RootView().environmentObject(state)
                if splash { Splash { splash = false }.zIndex(1) }
            }
        }
    }
}

/// Picks up where the launch screen leaves off: same logo, same spot, holds a beat, then fades into the app.
struct Splash: View {
    let done: () -> Void
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var leaving = false

    var body: some View {
        ZStack {
            Theme.bg
            Image("Logo")
                .scaleEffect(leaving && !reduceMotion ? 1.12 : 1)
                .opacity(leaving ? 0 : 1)
        }
        .ignoresSafeArea()
        .opacity(leaving ? 0 : 1)
        .allowsHitTesting(!leaving)
        .accessibilityHidden(true)
        .task {
            try? await Task.sleep(for: .seconds(0.9))
            withAnimation(.easeInOut(duration: 0.5)) { leaving = true }
            try? await Task.sleep(for: .seconds(0.5))
            done()
        }
    }
}
