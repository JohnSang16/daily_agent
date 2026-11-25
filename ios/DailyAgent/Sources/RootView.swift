import SwiftUI

enum Screen: String, CaseIterable, Identifiable {
    case dashboard, calendar, agent, money, settings
    var id: String { rawValue }
}

struct RootView: View {
    @EnvironmentObject var state: AppState
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.scenePhase) private var scenePhase
    @State private var screen: Screen = .dashboard
    @State private var drawerOpen = false
    @State private var drag: CGFloat = 0  // live finger offset while the drawer is being pulled

    private let width: CGFloat = 250
    private var motion: Animation { reduceMotion ? .easeOut(duration: 0.2) : Theme.spring }
    /// 0 closed, 1 open, anything between while a finger is on it.
    private var progress: CGFloat { min(max((drawerOpen ? width : 0) + drag, 0), width) / width }

    var body: some View {
        ZStack(alignment: .topLeading) {
            Theme.bg.ignoresSafeArea()
            drawer

            // the screen leans back, rounds its corners and slides over as the drawer opens
            ZStack(alignment: .top) {
                Backdrop()
                Group {
                    switch screen {
                    case .dashboard: DashboardView()
                    case .calendar: CalendarView()
                    case .agent: AgentView()
                    case .money: MoneyView()
                    case .settings: SettingsView()
                    }
                }
                .transition(.opacity.combined(with: .scale(scale: 0.985)))
                .id(screen)
                // content scrolls softly under the menu button instead of hitting a hard edge
                LinearGradient(colors: [Color.black.opacity(0.92), Color.black.opacity(0)], startPoint: .top, endPoint: .bottom)
                    .frame(height: 64).ignoresSafeArea(edges: .top).allowsHitTesting(false)
            }
            .allowsHitTesting(progress == 0)
            .overlay {
                // while open, a tap or a leftward pull on the screen closes the drawer (it rides along with the screen)
                if drawerOpen {
                    Color.clear.contentShape(Rectangle())
                        .onTapGesture { close() }
                        .gesture(pull)
                }
            }
            // a mask that ignores the safe area rounds the corners without cutting the page off under the status bar
            .mask { RoundedRectangle(cornerRadius: 34 * progress, style: .continuous).ignoresSafeArea() }
            .overlay {
                RoundedRectangle(cornerRadius: 34 * progress, style: .continuous)
                    .strokeBorder(Color.white.opacity(0.14 * progress), lineWidth: 0.8).ignoresSafeArea().allowsHitTesting(false)
            }
            .shadow(color: .black.opacity(0.6 * progress), radius: 30, x: -8)
            .scaleEffect(reduceMotion ? 1 : 1 - 0.08 * progress, anchor: .trailing)
            .offset(x: width * progress)

            // a thin strip on the left edge pulls the drawer out with the finger, under the menu button
            if !drawerOpen {
                Color.clear.frame(width: 18).frame(maxHeight: .infinity).contentShape(Rectangle())
                    .gesture(pull).ignoresSafeArea()
            }

            Button { drawerOpen ? close() : open() } label: {
                Image(systemName: drawerOpen ? "xmark" : "line.3.horizontal")
                    .font(.system(size: 16, weight: .regular)).foregroundStyle(Theme.title)
                    .contentTransition(.symbolEffect(.replace))
                    .frame(width: 44, height: 44).glass(Circle())
            }
            .buttonStyle(PressStyle()).accessibilityLabel(drawerOpen ? "close menu" : "menu")
            .padding(.leading, 12).padding(.top, 4)
            .offset(x: width * progress)

        }
        .overlay(alignment: .top) {
            if let t = state.toast {
                WinToast(toast: t).padding(.top, 6)
                    .transition(.move(edge: .top).combined(with: .opacity))
                    .onTapGesture { withAnimation(Theme.ease) { state.toast = nil } }
            }
        }
        .sensoryFeedback(.impact(weight: .light), trigger: drawerOpen)
        .onChange(of: state.configured) { _, ok in if !ok { screen = .settings } }
        .onChange(of: state.jumpTo) { _, s in
            guard let s else { return }
            withAnimation(motion) { screen = s }
            state.jumpTo = nil
        }
        .onChange(of: scenePhase) { _, p in
            if p == .active, state.configured, state.isStale { Task { await state.refresh() } }
        }
        .onAppear { if !state.configured { screen = .settings } }
        .preferredColorScheme(.dark)
    }

    private func open() { withAnimation(motion) { drawerOpen = true; drag = 0 } }
    private func close() { withAnimation(motion) { drawerOpen = false; drag = 0 } }

    /// Follows the finger, then settles open or shut from where a flick would have landed.
    private var pull: some Gesture {
        DragGesture(minimumDistance: 8)
            .onChanged { v in drag = v.translation.width }
            .onEnded { v in
                let landing = (drawerOpen ? width : 0) + v.predictedEndTranslation.width
                landing > width / 2 ? open() : close()
            }
    }

    private var drawer: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("js ai").font(.system(size: 22, weight: .light)).tracking(-0.3).foregroundStyle(Theme.title).padding(.bottom, 26)
            ForEach(Array(Screen.allCases.enumerated()), id: \.element) { i, s in
                Button {
                    withAnimation(motion) { screen = s; drawerOpen = false; drag = 0 }
                } label: {
                    HStack(spacing: 12) {
                        Circle().fill(Color.white).frame(width: 6, height: 6).opacity(screen == s ? 1 : 0)
                        Text(s.rawValue).font(.system(size: 18)).foregroundStyle(screen == s ? Theme.title : Theme.secondary)
                    }
                    .frame(maxWidth: .infinity, minHeight: 44, alignment: .leading)
                    .contentShape(Rectangle())
                }
                .buttonStyle(PressStyle())
                // rows slide in one after another as the drawer opens
                .offset(x: reduceMotion ? 0 : -24 * (1 - progress) * CGFloat(i + 1) / 3)
                .opacity(progress)
            }
            Spacer()
        }
        .sensoryFeedback(.selection, trigger: screen)
        .padding(.horizontal, 24).padding(.top, 72)
        .frame(width: width, alignment: .leading).frame(maxHeight: .infinity)
        .background {
            Rectangle().fill(.ultraThinMaterial).ignoresSafeArea()
                .overlay(alignment: .trailing) {
                    Rectangle().fill(LinearGradient(colors: [Color.white.opacity(0.22), Color.white.opacity(0.02)], startPoint: .top, endPoint: .bottom))
                        .frame(width: 0.8).ignoresSafeArea()
                }
        }
        .opacity(progress)
        .gesture(pull)
        .accessibilityHidden(!drawerOpen)
    }
}


/// Self talk after a win, in glass at the top: the line, then one identity line under it.
struct WinToast: View {
    let toast: Toast
    var body: some View {
        VStack(spacing: 3) {
            Text(toast.title).font(.system(size: 15, weight: .medium)).foregroundStyle(Theme.title)
            if let l = toast.line { Text(l).font(.system(size: 13)).foregroundStyle(Theme.secondary) }
        }
        .multilineTextAlignment(.center)
        .padding(.horizontal, 22).padding(.vertical, 12)
        .glass(Capsule())
        .shadow(color: .black.opacity(0.4), radius: 20, y: 8)
        .accessibilityElement(children: .combine)
        .accessibilityAddTraits(.isStaticText)
    }
}
