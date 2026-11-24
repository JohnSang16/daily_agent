import SwiftUI
#if os(iOS)
import WebKit
#endif

/// Spec 13: watch the agent work in the live browser, approve or deny anything that could hand
/// work in, take over at any time, and stop it (which deletes the browser).
struct HomeworkSessionView: View {
    @EnvironmentObject var state: AppState
    @Environment(\.dismiss) private var dismiss
    @Environment(\.scenePhase) private var scenePhase
    @State var session: HomeworkSession
    @State private var note = ""
    @State private var showSteps = true
    @State private var busy = false
    @State private var reloadToken = 0
    @FocusState private var typing: Bool

    var body: some View {
        VStack(spacing: 0) {
            header
            ScrollViewReader { proxy in
                ScrollView {
                    VStack(alignment: .leading, spacing: 20) {
                        liveView
                        if let a = session.approval, session.status == "needs_approval" { approvalCard(a) }
                        if let r = session.reason, !r.isEmpty, session.approval == nil {
                            Text(r).font(.system(size: 14)).foregroundStyle(Theme.body).transition(.opacity)
                        }
                        controls
                        stepLog.id("bottom")
                    }
                    .padding(.horizontal, 20).padding(.top, 8).padding(.bottom, 24)
                    .animation(Theme.spring, value: session)
                }
                .scrollDismissesKeyboard(.interactively)
                .onChange(of: session.steps.count) { _, _ in withAnimation(Theme.spring) { proxy.scrollTo("bottom", anchor: .bottom) } }
            }
            if session.isActive { messageBar }
        }
        .background(Backdrop())
        .preferredColorScheme(.dark)
        .sensoryFeedback(.warning, trigger: session.approval?.id)
        .task(id: session.id) { await poll() }
        .onChange(of: scenePhase) { _, phase in if phase == .active { reloadToken += 1 } }
    }

    // MARK: pieces

    private var header: some View {
        HStack(alignment: .top, spacing: 12) {
            VStack(alignment: .leading, spacing: 4) {
                Text(session.title).font(.system(size: 20)).tracking(-0.3).foregroundStyle(Theme.title).lineLimit(2)
                HStack(spacing: 8) {
                    if session.status == "running" || session.status == "starting" { WorkingDot() }
                    Text(sessionStatusLine(session.status)).font(.system(size: 13)).foregroundStyle(Theme.secondary)
                        .contentTransition(.opacity)
                    Text("· \(session.usage.steps) steps").font(.system(size: 13)).monospacedDigit().foregroundStyle(Theme.tertiary)
                }
            }
            Spacer()
            Button { dismiss() } label: {
                Image(systemName: "chevron.down").font(.system(size: 15)).foregroundStyle(Theme.title)
                    .frame(width: 40, height: 40).glass(Circle())
            }.buttonStyle(PressStyle()).accessibilityLabel("minimize")
        }
        .padding(.horizontal, 20).padding(.top, 16).padding(.bottom, 10)
    }

    @ViewBuilder
    private var liveView: some View {
        let shape = RoundedRectangle(cornerRadius: 20, style: .continuous)
        ZStack {
            if let s = session.liveViewUrl, let url = URL(string: s) {
                LiveBrowser(url: url, reloadToken: reloadToken)
            } else {
                Text(session.isActive ? "connecting to the browser." : "the browser was deleted.")
                    .font(.system(size: 13.5)).foregroundStyle(Theme.secondary)
            }
        }
        .frame(maxWidth: .infinity).aspectRatio(1280.0 / 800.0, contentMode: .fit)
        .background(Theme.surface).clipShape(shape)
        .overlay(shape.strokeBorder(Color.white.opacity(session.status == "takeover" ? 0.5 : 0.12), lineWidth: 1))
        .animation(Theme.ease, value: session.status)
        .accessibilityLabel("live view of the agent's browser")
    }

    private func approvalCard(_ a: PendingApproval) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            sectionLabel("needs your approval")
            Text("\"\(a.label)\"").font(.system(size: 20)).tracking(-0.3).foregroundStyle(Theme.title)
            Text(session.reason ?? "this could hand in or send something.").font(.system(size: 13.5)).foregroundStyle(Theme.secondary)
            Text("check the live view first. approving runs this one action once.").font(.system(size: 12.5)).foregroundStyle(Theme.tertiary)
            HStack(spacing: 10) {
                PillButton(label: "approve", primary: true, enabled: !busy, feedback: .success) { decide(a, true) }
                PillButton(label: "deny", enabled: !busy) { decide(a, false) }
            }
        }
        .padding(18).frame(maxWidth: .infinity, alignment: .leading)
        .glass(RoundedRectangle(cornerRadius: 22, style: .continuous))
        .transition(.opacity.combined(with: .scale(scale: 0.97)))
    }

    @ViewBuilder
    private var controls: some View {
        if session.isActive {
            HStack(spacing: 10) {
                if session.status == "takeover" || session.status == "paused" {
                    PillButton(label: "hand back", primary: true, enabled: !busy) { control("handback") }
                } else if session.status != "needs_approval" {
                    PillButton(label: "take over", enabled: !busy) { control("takeover") }
                    PillButton(label: "pause", enabled: !busy) { control("pause") }
                }
                Spacer()
                PillButton(label: "stop", enabled: !busy, feedback: .warning) { control("stop") }
            }
        } else {
            PillButton(label: "close", primary: true) { dismiss() }
        }
    }

    private var stepLog: some View {
        VStack(alignment: .leading, spacing: 10) {
            Button { withAnimation(Theme.spring) { showSteps.toggle() } } label: {
                HStack(spacing: 6) {
                    sectionLabel("what it did")
                    Image(systemName: "chevron.down").font(.system(size: 10)).foregroundStyle(Theme.tertiary)
                        .rotationEffect(.degrees(showSteps ? 0 : -90))
                }.frame(minHeight: 32)
            }.buttonStyle(PressStyle())
            if showSteps {
                ForEach(session.steps) { s in
                    HStack(alignment: .firstTextBaseline, spacing: 10) {
                        Text(clock(s.at)).font(.system(size: 11.5)).monospacedDigit().foregroundStyle(Theme.tertiary)
                            .frame(width: 58, alignment: .leading)
                        Text(s.summary).font(.system(size: 13.5)).foregroundStyle(s.kind == "you" ? Theme.secondary : Theme.body)
                    }
                    .transition(.opacity.combined(with: .move(edge: .bottom)))
                }
            }
        }
    }

    private var messageBar: some View {
        HStack(spacing: 8) {
            TextField("tell the agent something", text: $note, axis: .vertical)
                .font(.system(size: 15.5)).foregroundStyle(Theme.title).lineLimit(1...3)
                .focused($typing).submitLabel(.send).onSubmit(send)
                .padding(.leading, 18).padding(.vertical, 11)
            Button(action: send) {
                Image(systemName: "arrow.up").font(.system(size: 16, weight: .medium)).foregroundStyle(Color.black)
                    .frame(width: 40, height: 40)
                    .background(Circle().fill(LinearGradient(colors: [.white, Color(white: 0.82)], startPoint: .top, endPoint: .bottom)))
            }
            .buttonStyle(PressStyle()).disabled(note.trimmingCharacters(in: .whitespaces).isEmpty)
            .opacity(note.trimmingCharacters(in: .whitespaces).isEmpty ? 0.4 : 1)
            .padding(.trailing, 5).accessibilityLabel("send")
        }
        .glass(Capsule()).padding(.horizontal, 14).padding(.bottom, 10)
    }

    // MARK: actions

    private func poll() async {
        while !Task.isCancelled && session.isActive {
            try? await Task.sleep(nanoseconds: 2_000_000_000)
            if let s = await state.homeworkSession(session.id) { withAnimation(Theme.spring) { session = s } }
        }
    }

    private func control(_ action: String) {
        busy = true
        Task {
            if let s = await state.homeworkControl(session.id, action) { withAnimation(Theme.spring) { session = s } }
            busy = false
        }
    }

    private func decide(_ a: PendingApproval, _ approve: Bool) {
        busy = true
        Task {
            if let s = await state.homeworkDecide(session.id, approval: a.id, approve: approve) {
                withAnimation(Theme.spring) { session = s }
            } else if let s = await state.homeworkSession(session.id) {
                session = s  // an expired approval comes back as an error: show the fresh state
            }
            busy = false
        }
    }

    private func send() {
        let t = note.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !t.isEmpty else { return }
        note = ""
        Task { if let s = await state.homeworkMessage(session.id, t) { session = s } }
    }
}

/// Kernel's live view page. You can watch, or tap into it to drive the browser yourself.
#if os(iOS)
struct LiveBrowser: UIViewRepresentable {
    let url: URL
    var reloadToken = 0  // backgrounding the app kills the live view's connection; bump this to reconnect

    final class Coordinator {
        var lastToken = 0
    }

    func makeCoordinator() -> Coordinator { Coordinator() }

    func makeUIView(context: Context) -> WKWebView {
        _ = WKWebView.focusRaisesKeyboard
        let config = WKWebViewConfiguration()
        config.allowsInlineMediaPlayback = true
        config.websiteDataStore = .nonPersistent()  // the live view link is a credential: keep nothing
        let v = WKWebView(frame: .zero, configuration: config)
        v.isOpaque = false
        v.backgroundColor = .black
        v.scrollView.isScrollEnabled = false
        v.load(URLRequest(url: url))
        context.coordinator.lastToken = reloadToken
        return v
    }
    func updateUIView(_ v: WKWebView, context: Context) {
        if v.url?.host != url.host || context.coordinator.lastToken != reloadToken {
            context.coordinator.lastToken = reloadToken
            v.load(URLRequest(url: url))
        }
    }
}

/// WKWebView only raises the keyboard for a focus() it counts as a user tap. Kernel's keyboard
/// button focuses a hidden input from script, so nothing pops up. This marks every focus as
/// user driven. Private WebKit selector (fine for a personal app, not App Store safe); if Apple
/// renames it, the lookup fails and nothing changes.
extension WKWebView {
    static let focusRaisesKeyboard: Void = {
        guard let cls = NSClassFromString("WKContentView") else { return }
        let sel = sel_getUid("_elementDidFocus:userIsInteracting:blurPreviousNode:activityStateChanges:userObject:")
        guard let method = class_getInstanceMethod(cls, sel) else { return }
        typealias Original = @convention(c) (AnyObject, Selector, UnsafeRawPointer, Bool, Bool, UInt64, AnyObject?) -> Void
        let original = unsafeBitCast(method_getImplementation(method), to: Original.self)
        let patched: @convention(block) (AnyObject, UnsafeRawPointer, Bool, Bool, UInt64, AnyObject?) -> Void = {
            me, node, _, blur, changes, obj in original(me, sel, node, true, blur, changes, obj)
        }
        method_setImplementation(method, imp_implementationWithBlock(patched))
    }()
}
#else
struct LiveBrowser: View {
    let url: URL
    var reloadToken = 0
    var body: some View { Text("live view runs on the phone.").foregroundStyle(Theme.secondary) }
}
#endif
