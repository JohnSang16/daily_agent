import SwiftUI

enum Screen: String, CaseIterable, Identifiable {
    case dashboard, money, settings
    var id: String { rawValue }
}

struct RootView: View {
    @EnvironmentObject var state: AppState
    @State private var screen: Screen = .dashboard
    @State private var drawerOpen = false

    var body: some View {
        ZStack(alignment: .topLeading) {
            Theme.bg.ignoresSafeArea()
            Group {
                switch screen {
                case .dashboard: DashboardView()
                case .money: MoneyView()
                case .settings: SettingsView()
                }
            }
            .offset(x: drawerOpen ? 260 : 0)
            .opacity(drawerOpen ? 0.4 : 1)
            .allowsHitTesting(!drawerOpen)

            Button { withAnimation(Theme.ease) { drawerOpen.toggle() } } label: {
                Image(systemName: "line.3.horizontal").font(.system(size: 18, weight: .light)).foregroundStyle(Theme.title)
                    .frame(width: 44, height: 44)
            }
            .buttonStyle(.plain).accessibilityLabel("menu").padding(.leading, 12).padding(.top, 4)
            .offset(x: drawerOpen ? 260 : 0)

            if drawerOpen { drawer.transition(.move(edge: .leading)) }
        }
        .gesture(DragGesture(minimumDistance: 30).onEnded { v in
            if !drawerOpen, v.startLocation.x < 28, v.translation.width > 60 { withAnimation(Theme.ease) { drawerOpen = true } }
            if drawerOpen, v.translation.width < -60 { withAnimation(Theme.ease) { drawerOpen = false } }
        })
        .task {
            if screen == .dashboard { await state.refresh() }
        }
        .onChange(of: state.configured) { _, ok in if !ok { screen = .settings } }
        .onAppear { if !state.configured { screen = .settings } }
        .preferredColorScheme(.dark)
    }

    private var drawer: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("js ai").font(.system(size: 22, weight: .light)).foregroundStyle(Theme.title).padding(.bottom, 26)
            ForEach(Screen.allCases) { s in
                Button {
                    withAnimation(Theme.ease) { screen = s; drawerOpen = false }
                } label: {
                    Text(s.rawValue).font(.system(size: 18)).foregroundStyle(screen == s ? Theme.title : Theme.secondary)
                        .frame(maxWidth: .infinity, minHeight: 44, alignment: .leading)
                }.buttonStyle(.plain)
            }
            Spacer()
        }
        .padding(.horizontal, 24).padding(.top, 72)
        .frame(width: 260, alignment: .leading).frame(maxHeight: .infinity)
        .background(Theme.surface.ignoresSafeArea())
    }
}
