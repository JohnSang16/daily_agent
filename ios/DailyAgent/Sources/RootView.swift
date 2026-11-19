import SwiftUI

enum Screen: String, CaseIterable, Identifiable {
    case dashboard, calendar, money, settings
    var id: String { rawValue }
}

struct RootView: View {
    @EnvironmentObject var state: AppState
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var screen: Screen = .dashboard
    @State private var drawerOpen = false

    private var motion: Animation { reduceMotion ? .easeOut(duration: 0.2) : Theme.spring }

    var body: some View {
        ZStack(alignment: .topLeading) {
            Theme.bg.ignoresSafeArea()

            // the screen leans back and slides over when the drawer opens
            ZStack {
                switch screen {
                case .dashboard: DashboardView().transition(.opacity.combined(with: .scale(scale: 0.98)))
                case .calendar: CalendarView().transition(.opacity.combined(with: .scale(scale: 0.98)))
                case .money: MoneyView().transition(.opacity.combined(with: .scale(scale: 0.98)))
                case .settings: SettingsView().transition(.opacity.combined(with: .scale(scale: 0.98)))
                }
            }
            .animation(motion, value: screen)
            .background(Theme.bg)
            .clipShape(RoundedRectangle(cornerRadius: drawerOpen ? 32 : 0, style: .continuous))
            .scaleEffect(drawerOpen && !reduceMotion ? 0.92 : 1, anchor: .trailing)
            .offset(x: drawerOpen ? 250 : 0)
            .opacity(drawerOpen ? 0.6 : 1)
            .allowsHitTesting(!drawerOpen)
            .overlay {
                // tapping the dimmed screen closes the drawer
                if drawerOpen {
                    Color.clear.contentShape(Rectangle())
                        .onTapGesture { withAnimation(motion) { drawerOpen = false } }
                }
            }

            Button { withAnimation(motion) { drawerOpen.toggle() } } label: {
                Image(systemName: "line.3.horizontal").font(.system(size: 17, weight: .regular)).foregroundStyle(Theme.title)
                    .frame(width: 44, height: 44).glass(Circle())
            }
            .buttonStyle(PressStyle()).accessibilityLabel("menu")
            .padding(.leading, 12).padding(.top, 4)
            .offset(x: drawerOpen ? 250 : 0)

            if drawerOpen { drawer.transition(.move(edge: .leading).combined(with: .opacity)) }
        }
        .sensoryFeedback(.impact(weight: .light), trigger: drawerOpen)
        .sensoryFeedback(.selection, trigger: screen)
        .simultaneousGesture(DragGesture(minimumDistance: 30).onEnded { v in
            if !drawerOpen, v.startLocation.x < 28, v.translation.width > 60 { withAnimation(motion) { drawerOpen = true } }
            if drawerOpen, v.translation.width < -60 { withAnimation(motion) { drawerOpen = false } }
        })
        .task { if screen == .dashboard { await state.refresh() } }
        .onChange(of: state.configured) { _, ok in if !ok { screen = .settings } }
        .onAppear { if !state.configured { screen = .settings } }
        .preferredColorScheme(.dark)
    }

    private var drawer: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("js ai").font(.system(size: 22, weight: .light)).foregroundStyle(Theme.title).padding(.bottom, 26)
            ForEach(Array(Screen.allCases.enumerated()), id: \.element) { i, s in
                Button {
                    withAnimation(motion) { screen = s; drawerOpen = false }
                } label: {
                    HStack(spacing: 12) {
                        Circle().fill(screen == s ? Color.white : Color.clear).frame(width: 6, height: 6)
                        Text(s.rawValue).font(.system(size: 18)).foregroundStyle(screen == s ? Theme.title : Theme.secondary)
                    }
                    .frame(maxWidth: .infinity, minHeight: 44, alignment: .leading)
                }
                .buttonStyle(PressStyle())
                .reveal(i)
            }
            Spacer()
        }
        .padding(.horizontal, 24).padding(.top, 72)
        .frame(width: 250, alignment: .leading).frame(maxHeight: .infinity)
        .background {
            Rectangle().fill(.ultraThinMaterial).ignoresSafeArea()
                .overlay(alignment: .trailing) {
                    Rectangle().fill(LinearGradient(colors: [Color.white.opacity(0.22), Color.white.opacity(0.02)], startPoint: .top, endPoint: .bottom))
                        .frame(width: 0.8).ignoresSafeArea()
                }
        }
    }
}
