import Speech
import SwiftUI
#if canImport(UIKit)
import UIKit
#else
import AppKit
#endif
#if os(iOS)
import AVFoundation
#endif

enum AgentMode: String, CaseIterable, Identifiable {
    case ask, homework
    var id: String { rawValue }
}

struct ChatTurn: Identifiable, Equatable, Codable {
    var id = UUID()
    let question: String
    var reply: AskReply?
    var failed = false
}

/// Spec 19: one box for questions. Ask reads your notes and tasks, homework reads only your school
/// notes for one course. Nothing here drives a browser or submits anything.
struct AgentView: View {
    @EnvironmentObject var state: AppState
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @StateObject private var dictation = Dictation()
    @State private var mode: AgentMode = .ask
    @State private var context: AskContext = .all
    @State private var course: String?
    @State private var draft = ""
    @State private var draftBeforeDictation = ""
    @State private var askTurns: [ChatTurn] = []
    @State private var hwTurns: [ChatTurn] = []
    @State private var chats: [Chat] = ChatStore.load()
    @State private var chatId = UUID()
    @State private var showChats = false
    @FocusState private var typing: Bool
    @Namespace private var pick
    @State private var session: HomeworkSession?  // the open homework agent session
    @State private var starting: Int?  // assignment id while its browser starts
    @State private var startNote: String?
    @State private var showing = false

    private var turns: [ChatTurn] { mode == .ask ? askTurns : hwTurns }
    private var waiting: Bool { turns.last.map { $0.reply == nil && !$0.failed } ?? false }
    private var canSend: Bool { !waiting && !draft.trimmingCharacters(in: .whitespaces).isEmpty && (mode == .ask || course != nil) }
    private var selectedCourse: Course? { state.courses.first { $0.course == course } }

    var body: some View {
        VStack(spacing: 0) {
            ZStack(alignment: .trailing) {
                modeSwitch
                if mode == .ask {
                    Button { showChats = true } label: {
                        Image(systemName: "bubble.left.and.text.bubble.right").font(.system(size: 16))
                            .foregroundStyle(Theme.body).frame(width: 44, height: 44)
                    }
                    .buttonStyle(PressStyle()).accessibilityLabel("chats")
                    .padding(.trailing, 12).transition(.opacity)
                }
            }
            .padding(.top, 6)
            ScrollViewReader { proxy in
                ScrollView {
                    VStack(alignment: .leading, spacing: 28) {
                        if mode == .homework && turns.isEmpty { homeworkHome }
                        if mode == .ask && turns.isEmpty { askHome }
                        ForEach(turns) { t in TurnView(turn: t).id(t.id) }
                        if waiting { WorkingDot().padding(.leading, 2).id("working") }
                    }
                    .padding(.horizontal, 24).padding(.top, 28).padding(.bottom, 16)
                    .frame(maxWidth: .infinity, alignment: .leading)
                }
                .scrollDismissesKeyboard(.interactively)
                .onChange(of: turns) { _, t in
                    let target: AnyHashable? = waiting ? AnyHashable("working") : t.last.map { AnyHashable($0.id) }
                    if let target { withAnimation(Theme.spring) { proxy.scrollTo(target, anchor: .bottom) } }
                }
            }
            composer
        }
        .task {
            if state.courses.isEmpty { await state.loadCourses() }
            if course == nil { course = state.courses.first?.course }
            if session == nil { session = await state.activeHomeworkSession() }
        }
        .onChange(of: state.courses) { _, cs in if course == nil { course = cs.first?.course } }
        .onChange(of: dictation.text) { _, t in if dictation.listening { draft = Self.joined(draftBeforeDictation, t) } }
        .onChange(of: askTurns) { _, t in
            guard !t.isEmpty else { return }
            chats.removeAll { $0.id == chatId }
            chats.insert(Chat(id: chatId, turns: t, updated: Date()), at: 0)
            ChatStore.save(chats)
        }
        .sheet(isPresented: $showChats) {
            ChatsSheet(chats: $chats, current: chatId, open: { c in
                chatId = c.id; askTurns = c.turns; showChats = false
            }, new: {
                chatId = UUID(); askTurns = []; showChats = false
            })
        }
        .onChange(of: showing) { _, open in
            if !open, let s = session { Task { if let fresh = await state.homeworkSession(s.id) { session = fresh } } }
        }
        #if os(iOS)
        .fullScreenCover(isPresented: $showing) {
            if let s = session { HomeworkSessionView(session: s).environmentObject(state) }
        }
        #else
        .sheet(isPresented: $showing) {
            if let s = session { HomeworkSessionView(session: s).environmentObject(state) }
        }
        #endif
    }

    // MARK: pieces

    private var modeSwitch: some View {
        HStack(spacing: 4) {
            ForEach(AgentMode.allCases) { m in
                Button { withAnimation(reduceMotion ? Theme.ease : Theme.spring) { mode = m } } label: {
                    Text(m.rawValue).font(.system(size: 15, weight: mode == m ? .medium : .regular))
                        .foregroundStyle(mode == m ? Theme.title : Theme.secondary)
                        .frame(width: 104, height: 40)
                        .background {
                            if mode == m {
                                Capsule().fill(Color.white.opacity(0.12))
                                    .overlay(Capsule().strokeBorder(Color.white.opacity(0.14), lineWidth: 0.6))
                                    .matchedGeometryEffect(id: "agent-mode", in: pick)
                            }
                        }
                }.buttonStyle(PressStyle())
            }
        }
        .padding(4).glass(Capsule())
        .sensoryFeedback(.selection, trigger: mode)
        .frame(maxWidth: .infinity)
        .padding(.leading, 40)  // clear of the menu button
    }

    private var askHome: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("ask anything").font(.system(size: 28, weight: .light)).tracking(-0.5).foregroundStyle(Theme.title)
            Text("connected to your vault, calendar, deadlines and money.")
                .font(.system(size: 14)).foregroundStyle(Theme.secondary)
        }.reveal()
    }

    @ViewBuilder
    private var homeworkHome: some View {
        VStack(alignment: .leading, spacing: 18) {
            VStack(alignment: .leading, spacing: 8) {
                Text(course.map { courseLabel($0, max: 40) } ?? "homework").font(.system(size: 28, weight: .light))
                    .tracking(-0.5).foregroundStyle(Theme.title)
                Text("connected to your school notes, iCollege and Pearson, always with you watching.")
                    .font(.system(size: 14)).foregroundStyle(Theme.secondary)
            }
            if let c = selectedCourse {
                VStack(alignment: .leading, spacing: 14) {
                    sectionLabel("coming up")
                    ForEach(c.assignments.prefix(5)) { a in
                        HStack(alignment: .center, spacing: 10) {
                            Button { draft = "what does \(a.title) cover?"; typing = true } label: {
                                VStack(alignment: .leading, spacing: 3) {
                                    Text(a.title).font(.system(size: 16)).foregroundStyle(Theme.title).multilineTextAlignment(.leading)
                                    Text(dueLine(a.dueAt)).font(.system(size: 12.5)).foregroundStyle(Theme.secondary)
                                }
                                .frame(maxWidth: .infinity, minHeight: 44, alignment: .leading).contentShape(Rectangle())
                            }
                            .buttonStyle(PressStyle())
                            .accessibilityHint("asks what it covers")
                            Menu {
                                Button("on iCollege") { work(a, site: "icollege") }
                                Button("on Pearson") { work(a, site: "pearson") }
                            } label: {
                                HStack(spacing: 6) {
                                    if starting == a.id { WorkingDot() }
                                    Text(starting == a.id ? "starting" : "work on it")
                                }
                                .font(.system(size: 13.5)).foregroundStyle(Theme.title)
                                .padding(.horizontal, 14).frame(minHeight: 36).glass(Capsule()).frame(minHeight: 44)
                            }
                            .disabled(starting != nil)
                        }
                    }
                    if let n = startNote { Text(n).font(.system(size: 13)).foregroundStyle(Theme.secondary) }
                    if let s = session, s.isActive {
                        Button { showing = true } label: {
                            Label("back to \(s.title)", systemImage: "play.circle").font(.system(size: 14)).foregroundStyle(Theme.title)
                                .padding(.horizontal, 14).frame(minHeight: 40).glass(Capsule())
                        }.buttonStyle(PressStyle())
                    }
                }
            } else {
                Text(state.courses.isEmpty ? "no iCollege assignments synced yet." : "pick a course below.")
                    .font(.system(size: 14)).foregroundStyle(Theme.secondary)
            }
        }.reveal()
    }

    private var composer: some View {
        VStack(alignment: .leading, spacing: 12) {
            scopeChip.padding(.horizontal, 24)
            HStack(spacing: 8) {
                TextField(mode == .ask ? "ask anything" : "ask about this course", text: $draft, axis: .vertical)
                    .font(.system(size: 16)).foregroundStyle(Theme.title).lineLimit(1...4)
                    .focused($typing).submitLabel(.send).onSubmit { send(draft) }
                    .padding(.leading, 20).padding(.vertical, 12)
                Button {
                    if !dictation.listening { draftBeforeDictation = draft }
                    dictation.toggle()
                } label: {
                    Image(systemName: dictation.listening ? "waveform" : "mic")
                        .font(.system(size: 17)).foregroundStyle(dictation.listening ? Theme.title : Theme.secondary)
                        .symbolEffect(.variableColor.iterative, isActive: dictation.listening)
                        .frame(width: 40, height: 44)
                }
                .buttonStyle(PressStyle())
                .accessibilityLabel(dictation.listening ? "stop dictation" : "dictate")
                Button { send(draft) } label: {
                    Image(systemName: "arrow.up").font(.system(size: 17, weight: .medium)).foregroundStyle(Color.black)
                        .frame(width: 44, height: 44)
                        .background(Circle().fill(LinearGradient(colors: [.white, Color(white: 0.82)], startPoint: .top, endPoint: .bottom)))
                }
                .buttonStyle(PressStyle()).disabled(!canSend).opacity(canSend ? 1 : 0.4)
                .animation(Theme.ease, value: canSend)
                .accessibilityLabel("send")
                .padding(.trailing, 5)
            }
            .glass(Capsule())
            .padding(.horizontal, 16)
            if let note = dictation.note {
                Text(note).font(.system(size: 12.5)).foregroundStyle(Theme.secondary).padding(.horizontal, 24)
            }
        }
        .padding(.bottom, 10)
        .animation(Theme.spring, value: typing)
    }

    /// "context: all" in ask, the course in homework.
    private var scopeChip: some View {
        Menu {
            if mode == .ask {
                Picker("context", selection: $context) {
                    Text("all: notes, deadlines, schedule and money").tag(AskContext.all)
                    Text("notes only").tag(AskContext.notes)
                    Text("deadlines and schedule only").tag(AskContext.tasks)
                }
            } else {
                Picker("course", selection: Binding(get: { course ?? "" }, set: { course = $0 })) {
                    ForEach(state.courses) { c in Text(courseLabel(c.course, max: 40)).tag(c.course) }
                }
            }
        } label: {
            HStack(spacing: 6) {
                Text(mode == .ask ? "context: \(context.rawValue)" : "course: " + (course.map { courseLabel($0, max: 22) } ?? "none"))
                Image(systemName: "chevron.down").font(.system(size: 11))
            }
            .font(.system(size: 13.5)).foregroundStyle(Theme.body)
            .padding(.horizontal, 14).frame(minHeight: 36)
            .overlay(Capsule().strokeBorder(Theme.line, lineWidth: 1))
            .frame(minHeight: 44)
        }
        .sensoryFeedback(.selection, trigger: context)
    }

    // MARK: homework agent

    private func work(_ a: CourseAssignment, site: String) {
        starting = a.id
        startNote = nil
        Task {
            if let s = await state.startHomework(taskId: a.id, site: site) {
                session = s
                showing = true
            } else if state.problem?.contains("already running") == true, let s = await state.activeHomeworkSession() {
                session = s  // the 409 case: don't dead end, open the one that's already going
                showing = true
            } else {
                startNote = state.problem ?? (state.offline ? "offline. can't reach the agent." : "the browser couldn't start.")
            }
            starting = nil
        }
    }

    /// Dictation adds to what's already typed instead of replacing it.
    static func joined(_ typed: String, _ spoken: String) -> String {
        typed.isEmpty || spoken.isEmpty || typed.last?.isWhitespace == true ? typed + spoken : typed + " " + spoken
    }

    // MARK: sending

    private func send(_ text: String) {
        let q = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !q.isEmpty, !waiting, mode == .ask || course != nil else { return }
        if dictation.listening { dictation.toggle() }
        draft = ""
        let turn = ChatTurn(question: q)
        let m = mode, ctx = context, crs = mode == .homework ? course : nil
        let history = Self.history(m == .ask ? askTurns : hwTurns)
        withAnimation(Theme.spring) { append(turn, to: m) }
        Task {
            let r = await state.ask(q, context: ctx, course: crs, history: history)
            withAnimation(Theme.spring) { finish(turn.id, in: m, with: r) }
        }
    }

    /// The last 6 answered turns as user/assistant pairs, so follow ups make sense to the backend.
    static func history(_ turns: [ChatTurn]) -> [[String: String]] {
        turns.filter { $0.reply != nil }.suffix(6).flatMap { t in
            [["role": "user", "text": t.question],
             ["role": "assistant", "text": String(t.reply!.answer.prefix(2000))]]
        }
    }

    private func append(_ t: ChatTurn, to m: AgentMode) {
        if m == .ask { askTurns.append(t) } else { hwTurns.append(t) }
    }

    private func finish(_ id: UUID, in m: AgentMode, with r: AskReply?) {
        func apply(_ list: inout [ChatTurn]) {
            guard let i = list.firstIndex(where: { $0.id == id }) else { return }
            if let r { list[i].reply = r } else { list[i].failed = true }
        }
        if m == .ask { apply(&askTurns) } else { apply(&hwTurns) }
    }
}

/// The question in a bubble on the right, the answer as markdown, then copy and sources under it.
struct TurnView: View {
    @EnvironmentObject var state: AppState
    let turn: ChatTurn
    @State private var showSources = false
    @State private var copied = false

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(turn.question).font(.system(size: 16)).foregroundStyle(Theme.title)
                .textSelection(.enabled)
                .padding(.horizontal, 16).padding(.vertical, 10)
                .background(RoundedRectangle(cornerRadius: 20, style: .continuous).fill(Color.white.opacity(0.09)))
                .frame(maxWidth: 300, alignment: .trailing).frame(maxWidth: .infinity, alignment: .trailing)
            if let r = turn.reply {
                Text(markdown(r.answer)).font(.system(size: 17)).foregroundStyle(Theme.title).lineSpacing(5)
                    .textSelection(.enabled).transition(.opacity)
                    .contextMenu { Button { copy(r.answer) } label: { Label("copy", systemImage: "doc.on.doc") } }
                HStack(spacing: 4) {
                    Button { copy(r.answer) } label: {
                        Image(systemName: copied ? "checkmark" : "doc.on.doc").font(.system(size: 13))
                            .foregroundStyle(Theme.secondary).frame(width: 36, height: 32).contentTransition(.symbolEffect(.replace))
                    }
                    .buttonStyle(PressStyle()).accessibilityLabel(copied ? "copied" : "copy reply")
                    .sensoryFeedback(.success, trigger: copied) { _, now in now }
                    if !r.sources.isEmpty {
                        Button { withAnimation(Theme.spring) { showSources.toggle() } } label: {
                            Text(showSources ? "hide sources" : "sources")
                                .font(.system(size: 12.5)).foregroundStyle(Theme.tertiary).frame(minHeight: 32)
                        }.buttonStyle(PressStyle())
                    }
                }
                .padding(.leading, -10)
                if showSources {
                    VStack(alignment: .leading, spacing: 12) {
                        ForEach(r.sources) { s in
                            VStack(alignment: .leading, spacing: 3) {
                                Text(noteName(s.path) + (s.heading.isEmpty ? "" : " · " + s.heading.lowercased()))
                                    .font(.system(size: 13)).foregroundStyle(Theme.body)
                                Text(s.excerpt).font(.system(size: 12.5)).foregroundStyle(Theme.tertiary).lineLimit(3)
                            }
                        }
                    }
                    .padding(14).frame(maxWidth: .infinity, alignment: .leading)
                    .glass(RoundedRectangle(cornerRadius: 18, style: .continuous))
                    .transition(.opacity.combined(with: .move(edge: .top)))
                }
            } else if turn.failed {
                Text(state.offline ? "offline. can't reach the agent." : (state.problem ?? "that didn't go through. try again."))
                    .font(.system(size: 14.5)).foregroundStyle(Theme.secondary)
            }
        }
    }

    private func copy(_ text: String) {
        #if canImport(UIKit)
        UIPasteboard.general.string = text
        #else
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(text, forType: .string)
        #endif
        withAnimation(Theme.ease) { copied = true }
        Task {
            try? await Task.sleep(for: .seconds(1.5))
            withAnimation(Theme.ease) { copied = false }
        }
    }
}

/// Bold, italics, code and links from the model's markdown; line breaks and "- " lists kept as is.
func markdown(_ s: String) -> AttributedString {
    (try? AttributedString(markdown: s, options: .init(interpretedSyntax: .inlineOnlyPreservingWhitespace)))
        ?? AttributedString(s)
}

/// Past ask chats, newest first. Tap to reopen and keep going, swipe to delete.
struct ChatsSheet: View {
    @Binding var chats: [Chat]
    let current: UUID
    let open: (Chat) -> Void
    let new: () -> Void

    var body: some View {
        NavigationStack {
            List {
                Button { new() } label: {
                    Label("new chat", systemImage: "square.and.pencil").foregroundStyle(Theme.title)
                }
                ForEach(chats) { c in
                    Button { open(c) } label: {
                        VStack(alignment: .leading, spacing: 3) {
                            Text(c.title).font(.system(size: 16)).foregroundStyle(Theme.title).lineLimit(1)
                            Text(c.updated.formatted(.relative(presentation: .named)) + (c.id == current ? " · open" : ""))
                                .font(.system(size: 12.5)).foregroundStyle(Theme.secondary)
                        }
                    }
                }
                .onDelete { i in chats.remove(atOffsets: i); ChatStore.save(chats) }
            }
            .navigationTitle("chats")
        }
        .presentationDetents([.medium, .large])
    }
}

/// The one ambient motion in the design: a small dot that breathes while the agent works.
struct WorkingDot: View {
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var on = false
    var body: some View {
        Circle().fill(Color.white).frame(width: 8, height: 8)
            .opacity(on ? 1 : 0.3).scaleEffect(on || reduceMotion ? 1 : 0.7)
            .animation(.easeInOut(duration: 0.8).repeatForever(autoreverses: true), value: on)
            .onAppear { on = true }
            .accessibilityLabel("working")
    }
}

/// Dictation on the device only: nothing is sent to Apple, and nothing is sent to the agent until you tap send.
@MainActor
final class Dictation: ObservableObject {
    @Published var text = ""
    @Published var listening = false
    @Published var note: String?
    private let recognizer = SFSpeechRecognizer(locale: Locale(identifier: "en-US"))
    private var task: SFSpeechRecognitionTask?
    #if os(iOS)
    private let engine = AVAudioEngine()
    #endif

    func toggle() {
        listening ? stop() : start()
    }

    private func start() {
        note = nil
        SFSpeechRecognizer.requestAuthorization { status in
            Task { @MainActor in
                guard status == .authorized else { self.note = "speech recognition is off for js ai. turn it on in iOS settings."; return }
                self.begin()
            }
        }
    }

    private func begin() {
        #if os(iOS)
        guard let recognizer, recognizer.isAvailable, recognizer.supportsOnDeviceRecognition else {
            note = "on device dictation isn't available here. use the keyboard mic instead."
            return
        }
        let request = SFSpeechAudioBufferRecognitionRequest()
        request.requiresOnDeviceRecognition = true
        request.shouldReportPartialResults = true
        do {
            let session = AVAudioSession.sharedInstance()
            try session.setCategory(.record, mode: .measurement, options: .duckOthers)
            try session.setActive(true, options: .notifyOthersOnDeactivation)
            let input = engine.inputNode
            input.installTap(onBus: 0, bufferSize: 1024, format: input.outputFormat(forBus: 0)) { buf, _ in request.append(buf) }
            engine.prepare()
            try engine.start()
        } catch {
            note = "the microphone couldn't start."
            return
        }
        text = ""
        listening = true
        task = recognizer.recognitionTask(with: request) { result, error in
            Task { @MainActor in
                if let result { self.text = result.bestTranscription.formattedString }
                if error != nil || result?.isFinal == true { self.stop() }
            }
        }
        #else
        note = "dictation runs on the phone."
        #endif
    }

    func stop() {
        #if os(iOS)
        if engine.isRunning {
            engine.stop()
            engine.inputNode.removeTap(onBus: 0)
        }
        try? AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation)
        #endif
        task?.cancel()
        task = nil
        listening = false
    }
}
