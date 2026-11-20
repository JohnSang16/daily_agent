import SwiftUI

struct DashboardView: View {
    @EnvironmentObject var state: AppState
    @State private var editingGoal = false
    @State private var draft = ""
    @State private var picked: RankedTask?
    @State private var eodForced = false
    @FocusState private var goalFocused: Bool

    private func f(_ p: String) -> String {
        let d = DateFormatter(); d.locale = Locale(identifier: "en_US_POSIX"); d.dateFormat = p
        return d.string(from: Date())
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 30) {
                VStack(alignment: .leading, spacing: 4) {
                    BigTitle(text: f("EEEE"))
                    Text(f("MMMM d").lowercased()).font(.system(size: 14.5)).foregroundStyle(Theme.secondary)
                }
                if checkinDue(Date(), answered: state.checkin?.today.didTop != nil), state.checkin != nil {
                    CheckinCard(topTitle: state.today?.ranked.first?.title).reveal(1)
                }
                yesterdayLine.reveal(1)
                if let d = state.digest {
                    if let m = d.mantra { line("mantra", m).reveal(1) }
                    if let v = d.vision { line("vision", v).reveal(2) }
                }
                // right under the vision: what is most likely to get in the way, and the plan for it
                if state.checkin != nil { ObstaclePlan().reveal(2) }
                if let d = state.digest {
                    if let w = d.why { line("why, \(w.date)", w.text).reveal(3) }
                    if let id = d.identity, !id.isEmpty { identity(id).reveal(4) }
                }
                if let t = state.today {
                    Text(t.explanation.text).font(.system(size: 14.5)).foregroundStyle(Theme.body).lineSpacing(3)
                        .contentTransition(.opacity).reveal(5)
                }
                goalSection.reveal(6)
                plan(state.digest?.plan).reveal(7)
                deadlines.reveal(8)
                RepsSection().reveal(9)
                schedule.reveal(10)
                MailboxSection().reveal(11)
                eodSection.reveal(12)
                footer.reveal(13)
            }
            .page()
            .animation(Theme.spring, value: state.today)
            .animation(Theme.spring, value: state.checkin)
            .animation(Theme.spring, value: eodForced)
        }
        .scrollDismissesKeyboard(.interactively)
        .refreshable { await state.refresh() }
        .task { if state.isStale { await state.refresh() } }
        .sheet(item: $picked) { t in TaskSheet(task: t).environmentObject(state) }
    }

    /// Pops open by itself from 9 pm until answered. Before that, a quiet manual trigger.
    @ViewBuilder
    private var eodSection: some View {
        if let e = state.eod, !e.answered {
            if checkinDue(Date(), answered: false) || eodForced {
                EodCard(eod: e)
            } else {
                Button("log today") { eodForced = true }
                    .font(.system(size: 13)).foregroundStyle(Theme.secondary).frame(minHeight: 44)
            }
        }
    }

    private func line(_ label: String, _ text: String) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            sectionLabel(label)
            Text(text).font(.system(size: 15)).foregroundStyle(Theme.body).lineSpacing(3)
        }
    }

    private func identity(_ lines: [String]) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            sectionLabel("identity, say it out loud, repeat each twice")
            if let s = state.checkin?.sayDo, !sayDoLine(s).isEmpty {
                Text(sayDoLine(s)).font(.system(size: 13)).monospacedDigit().foregroundStyle(Theme.secondary)
            }
            ForEach(Array(lines.enumerated()), id: \.offset) { _, l in
                Text(l).font(.system(size: 15)).foregroundStyle(Theme.title)
            }
        }
    }

    @ViewBuilder
    private func plan(_ p: DigestPlan?) -> some View {
        if let p {
            VStack(alignment: .leading, spacing: 8) {
                sectionLabel("today's plan")
                if p.logged {
                    ForEach(Array(p.items.enumerated()), id: \.offset) { _, i in
                        HStack(alignment: .firstTextBaseline, spacing: 10) {
                            Image(systemName: i.done ? "checkmark.circle.fill" : "circle")
                                .font(.system(size: 13)).foregroundStyle(i.done ? Theme.tertiary : Theme.secondary)
                            Text(i.text).font(.system(size: 15))
                                .foregroundStyle(i.done ? Theme.tertiary : Theme.body)
                                .strikethrough(i.done, color: Theme.tertiary)
                        }
                        .accessibilityElement(children: .combine)
                        .accessibilityValue(i.done ? "done" : "not done")
                    }
                } else {
                    Text("no plan logged, what's the schedule today?").font(.system(size: 14.5)).foregroundStyle(Theme.secondary)
                }
            }
        }
    }

    private var goalSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            sectionLabel("today's goal")
            if let g = state.goal, !g.isEmpty, !editingGoal {
                Button { draft = g; editingGoal = true; goalFocused = true } label: {
                    Text(g).font(.system(size: 26)).tracking(-0.4).foregroundStyle(Theme.title)
                        .multilineTextAlignment(.leading).frame(maxWidth: .infinity, alignment: .leading)
                }
                .buttonStyle(PressStyle()).accessibilityHint("edit the goal")
                .transition(.opacity)
            } else {
                HStack(spacing: 12) {
                    TextField("one line", text: $draft).font(.system(size: 18)).foregroundStyle(Theme.title)
                        .focused($goalFocused).submitLabel(.done).onSubmit(saveGoal)
                        .onChange(of: draft) { _, v in if v.count > 90 { draft = String(v.prefix(90)) } }
                    if editingGoal {
                        Button("cancel") { withAnimation(Theme.spring) { editingGoal = false } }
                            .font(.system(size: 14)).foregroundStyle(Theme.secondary).frame(minHeight: 44)
                    }
                    PillButton(label: "save", primary: true, enabled: !draft.trimmingCharacters(in: .whitespaces).isEmpty,
                               action: saveGoal)
                }
                .transition(.opacity)
            }
        }
        .animation(Theme.spring, value: editingGoal)
    }

    private func saveGoal() {
        let text = draft
        guard !text.trimmingCharacters(in: .whitespaces).isEmpty else { return }
        goalFocused = false
        editingGoal = false
        Task { await state.saveGoal(text) }
    }

    /// #1 is a card with its deep work block and if-then plan, #2 and #3 are quiet rows under it.
    private var deadlines: some View {
        VStack(alignment: .leading, spacing: 18) {
            HStack {
                sectionLabel("deadlines")
                Spacer()
                if let n = state.today?.doneToday, n > 0 {
                    Text("\(n) done today").font(.system(size: 13)).monospacedDigit().foregroundStyle(Theme.secondary)
                        .contentTransition(.numericText())
                }
            }
            if let t = state.today, let first = t.ranked.first {
                FocusCard(task: first, block: t.topTask?.id == first.id ? t.topTask?.suggestedBlock : nil,
                          ifThen: state.checkin?.today.ifThen) { picked = first }
                    .transition(.asymmetric(insertion: .opacity, removal: .opacity.combined(with: .move(edge: .leading))))
                ForEach(Array(t.ranked.dropFirst().prefix(2).enumerated()), id: \.element.id) { i, r in
                    Button { picked = r } label: {
                        HStack(alignment: .top, spacing: 14) {
                            Text("\(i + 2)").font(.system(size: 15)).monospacedDigit().foregroundStyle(Theme.tertiary)
                                .frame(width: 18, alignment: .leading)
                            VStack(alignment: .leading, spacing: 3) {
                                Text(r.title).font(.system(size: 15)).foregroundStyle(Theme.body).multilineTextAlignment(.leading)
                                Text(dueLine(r.dueAt)).font(.system(size: 12.5)).foregroundStyle(Theme.tertiary)
                            }
                            Spacer(minLength: 0)
                        }
                        .frame(maxWidth: .infinity, minHeight: 44, alignment: .leading)
                        .contentShape(Rectangle())
                    }
                    .buttonStyle(PressStyle())
                    .padding(.leading, 4)
                    .transition(.asymmetric(insertion: .opacity, removal: .opacity.combined(with: .move(edge: .leading))))
                }
            } else {
                Text(state.today == nil ? state.waitingText : "nothing due.").font(.system(size: 14.5)).foregroundStyle(Theme.secondary)
            }
        }
    }

    /// Yesterday's #1 slipped: say it once, plainly, and point at today.
    @ViewBuilder
    private var yesterdayLine: some View {
        if let y = state.checkin?.yesterday, y.didTop == false {
            VStack(alignment: .leading, spacing: 4) {
                sectionLabel("yesterday")
                Text("#1 slipped" + ((y.whyNot ?? "").isEmpty ? "." : ": " + (y.whyNot ?? "")))
                    .font(.system(size: 14.5)).foregroundStyle(Theme.body)
                Text("never miss twice. today counts.").font(.system(size: 13)).foregroundStyle(Theme.secondary)
            }
        }
    }

    private var schedule: some View {
        VStack(alignment: .leading, spacing: 14) {
            if let t = state.today, !t.events.isEmpty {
                sectionLabel("today's schedule")
                ForEach(t.events) { e in
                    HStack(alignment: .firstTextBaseline, spacing: 12) {
                        Text(e.allDay ? "all day" : clock(e.start)).font(.system(size: 12.5)).monospacedDigit()
                            .foregroundStyle(Theme.secondary).frame(width: 64, alignment: .leading)
                        Text(e.title).font(.system(size: 15)).foregroundStyle(Theme.body)
                    }
                }
            }
        }
    }

    private var footer: some View {
        VStack(alignment: .leading, spacing: 6) {
            if let t = state.today {
                ForEach(t.warnings) { w in
                    Text(warningLine(w)).font(.system(size: 12.5)).foregroundStyle(Theme.secondary)
                }
            }
            if let p = state.problem, state.today != nil { Text(p).font(.system(size: 12.5)).foregroundStyle(Theme.secondary) }
            ForEach(Array((state.digest?.notes ?? []).enumerated()), id: \.offset) { _, n in
                Text(n).font(.system(size: 12.5)).foregroundStyle(Theme.secondary)
            }
            if let at = state.lastUpdated {
                Text((state.offline ? "offline. last updated " : "updated ") + timeText(at))
                    .font(.system(size: 12.5)).foregroundStyle(Theme.tertiary)
            }
        }
    }

    private func timeText(_ d: Date) -> String {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.dateFormat = Calendar.current.isDateInToday(d) ? "h:mm a" : "MMM d, h:mm a"
        return f.string(from: d).lowercased()
    }
}

struct TaskSheet: View {
    @EnvironmentObject var state: AppState
    @Environment(\.dismiss) private var dismiss
    let task: RankedTask

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                VStack(alignment: .leading, spacing: 8) {
                    sheetTitle(task.title)
                    Text("due " + dueLine(task.dueAt)).font(.system(size: 14.5)).foregroundStyle(Theme.secondary)
                    if !task.reasons.isEmpty {
                        Text(task.reasons.joined(separator: ", ").lowercased().replacingOccurrences(of: "_", with: " "))
                            .font(.system(size: 13.5)).foregroundStyle(Theme.secondary)
                    }
                    if task.atRisk { Text("at risk. give it your first free block.").font(.system(size: 13.5)).foregroundStyle(Theme.body) }
                }
                // the sheet closes at once, the agent catches up behind it
                PillButton(label: "mark done", primary: true, feedback: .success) {
                    dismiss(); Task { await state.done(task.id) }
                }
                sectionLabel("snooze")
                ForEach(SnoozeOption.allCases) { o in
                    PillButton(label: o.rawValue) { dismiss(); Task { await state.snooze(task.id, o) } }
                }
            }
            .padding(24).padding(.top, 8).frame(maxWidth: .infinity, alignment: .leading)
        }
        .sheetChrome()
    }
}


/// The #1 task: heavier than the rest, with when to do it and the plan for what gets in the way.
struct FocusCard: View {
    let task: RankedTask
    let block: TimeBlock?
    let ifThen: String?
    let open: () -> Void

    var body: some View {
        Button(action: open) {
            VStack(alignment: .leading, spacing: 10) {
                HStack(spacing: 8) {
                    FirstTag()
                    if task.atRisk { Text("at risk").font(.system(size: 11)).foregroundStyle(Theme.title) }
                    Spacer()
                    Image(systemName: "chevron.right").font(.system(size: 12)).foregroundStyle(Theme.tertiary)
                }
                Text(task.title).font(.system(size: 22)).tracking(-0.3).foregroundStyle(Theme.title)
                    .multilineTextAlignment(.leading)
                Text(dueLine(task.dueAt)).font(.system(size: 13)).foregroundStyle(Theme.secondary)
                let b = blockLine(block)
                if !b.isEmpty {
                    Label(b, systemImage: "clock").font(.system(size: 13.5)).foregroundStyle(Theme.body)
                }
                if let p = ifThen, !p.isEmpty {
                    Text("if it gets hard: " + p).font(.system(size: 13)).foregroundStyle(Theme.secondary)
                }
            }
            .padding(18).frame(maxWidth: .infinity, alignment: .leading)
            .glass(RoundedRectangle(cornerRadius: 22, style: .continuous))
            .contentShape(RoundedRectangle(cornerRadius: 22, style: .continuous))
        }
        .buttonStyle(PressStyle())
        .accessibilityHint("snooze or mark done")
    }
}

/// From 9 pm until answered: did #1 happen, why not, and one thing to let go of.
struct CheckinCard: View {
    @EnvironmentObject var state: AppState
    let topTitle: String?
    @State private var answer: Bool?
    @State private var whyNot = ""
    @State private var letGo = ""

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            sectionLabel("tonight")
            Text("did #1 happen?").font(.system(size: 22)).tracking(-0.3).foregroundStyle(Theme.title)
            if let t = topTitle { Text(t).font(.system(size: 13)).foregroundStyle(Theme.secondary) }
            HStack(spacing: 10) {
                PillButton(label: "yes", primary: answer == true, feedback: .success) { withAnimation(Theme.spring) { answer = true } }
                PillButton(label: "no", primary: answer == false) { withAnimation(Theme.spring) { answer = false } }
            }
            if answer == false {
                field("what got in the way?", $whyNot)
            }
            if answer != nil {
                field("one thing outside your control to let go of", $letGo)
                PillButton(label: "done for today", primary: true) { save() }
            }
        }
        .padding(18).frame(maxWidth: .infinity, alignment: .leading)
        .glass(RoundedRectangle(cornerRadius: 22, style: .continuous))
    }

    private func field(_ prompt: String, _ text: Binding<String>) -> some View {
        TextField(prompt, text: text, axis: .vertical).font(.system(size: 15)).foregroundStyle(Theme.title)
            .lineLimit(1...3).padding(.horizontal, 16).padding(.vertical, 12)
            .glass(RoundedRectangle(cornerRadius: 18, style: .continuous))
            .onChange(of: text.wrappedValue) { _, v in if v.count > 200 { text.wrappedValue = String(v.prefix(200)) } }
    }

    private func save() {
        guard let a = answer else { return }
        var body: [String: Any] = ["did_top": a]
        if let t = topTitle { body["top_task_title"] = String(t.prefix(200)) }
        if !a, !whyNot.isEmpty { body["why_not"] = whyNot }
        if !letGo.isEmpty { body["let_go"] = letGo }
        if a { state.celebrate("you did what you said.") }
        Task { await state.saveCheckin(body) }
    }
}

/// Closes the day: a few bullets in my own words, written into the vault alongside
/// what the app already knows (tasks finished, today's goal).
struct EodCard: View {
    @EnvironmentObject var state: AppState
    let eod: Eod
    @State private var bullets = ""
    @State private var saving = false

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            sectionLabel("log today")
            Text("how'd it go?").font(.system(size: 22)).tracking(-0.3).foregroundStyle(Theme.title)
            Text("\(eod.tasksDoneToday) task\(eod.tasksDoneToday == 1 ? "" : "s") done" + (eod.goal.map { ", goal: \($0)" } ?? ""))
                .font(.system(size: 13)).foregroundStyle(Theme.secondary)
            TextField("a few bullets, high level", text: $bullets, axis: .vertical)
                .font(.system(size: 15)).foregroundStyle(Theme.title)
                .lineLimit(3...8).padding(.horizontal, 16).padding(.vertical, 12)
                .glass(RoundedRectangle(cornerRadius: 18, style: .continuous))
                .onChange(of: bullets) { _, v in if v.count > 4000 { bullets = String(v.prefix(4000)) } }
            PillButton(label: saving ? "logging" : "log it", primary: true,
                       enabled: !saving && !bullets.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty) {
                saving = true
                Task { await state.saveEod(bullets); saving = false }
            }
        }
        .padding(18).frame(maxWidth: .infinity, alignment: .leading)
        .glass(RoundedRectangle(cornerRadius: 22, style: .continuous))
    }
}

/// Inputs over outcomes: the reps you control, with "x of 7" and never miss twice.
struct RepsSection: View {
    @EnvironmentObject var state: AppState
    @State private var adding = false
    private var inputs: [GoalItem] { state.goals.filter(\.isInput) }

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                sectionLabel("reps")
                Spacer()
                Button { adding = true } label: {
                    Label("add", systemImage: "plus").font(.system(size: 14)).foregroundStyle(Theme.title)
                        .padding(.horizontal, 14).frame(minHeight: 36).glass(Capsule()).frame(minHeight: 44)
                }.buttonStyle(PressStyle())
            }
            if inputs.isEmpty {
                Text("the inputs you control, counted every day. results come later, the reps come first.")
                    .font(.system(size: 14)).foregroundStyle(Theme.secondary)
            }
            ForEach(inputs) { g in RepRow(goal: g) }
        }
        .sheet(isPresented: $adding) { GoalSheet().environmentObject(state) }
    }
}

struct RepRow: View {
    @EnvironmentObject var state: AppState
    let goal: GoalItem
    @State private var confirmDelete = false

    var body: some View {
        HStack(alignment: .center, spacing: 14) {
            VStack(alignment: .leading, spacing: 6) {
                Text(goal.name).font(.system(size: 16)).foregroundStyle(Theme.title)
                HStack(spacing: 10) {
                    Text(repsLine(goal)).font(.system(size: 12.5)).monospacedDigit().foregroundStyle(Theme.secondary)
                    WeekDots(counts: goal.last7 ?? [], target: goal.target)
                    Text("\(goal.hit7 ?? 0) of 7").font(.system(size: 12.5)).monospacedDigit().foregroundStyle(Theme.tertiary)
                }
                if goal.missedTwice == true {
                    Text("missed twice. today counts.").font(.system(size: 12.5)).foregroundStyle(Theme.title)
                }
            }
            Spacer(minLength: 0)
            Button { Task { await state.logInput(goal, count: (goal.today ?? 0) + 1) } } label: {
                Image(systemName: (goal.today ?? 0) >= goal.target ? "checkmark" : "plus")
                    .font(.system(size: 16, weight: .medium))
                    .foregroundStyle((goal.today ?? 0) >= goal.target ? Color.black : Theme.title)
                    .contentTransition(.symbolEffect(.replace))
                    .frame(width: 44, height: 44)
                    .background {
                        if (goal.today ?? 0) >= goal.target {
                            Circle().fill(LinearGradient(colors: [.white, Color(white: 0.82)], startPoint: .top, endPoint: .bottom))
                        } else {
                            Circle().fill(Color.clear).glass(Circle())
                        }
                    }
            }
            .buttonStyle(PressStyle())
            .sensoryFeedback(.impact(weight: .light), trigger: goal.today)
            .accessibilityLabel("add one to \(goal.name)")
        }
        .contentShape(Rectangle())
        .contextMenu {
            Button("take one off", systemImage: "minus") { Task { await state.logInput(goal, count: (goal.today ?? 0) - 1) } }
            Button("remove", systemImage: "trash", role: .destructive) { confirmDelete = true }
        }
        .confirmationDialog("remove \(goal.name)? its history is kept.", isPresented: $confirmDelete, titleVisibility: .visible) {
            Button("remove", role: .destructive) { Task { await state.deleteGoal(goal.id) } }
        }
    }
}

/// Seven small marks, oldest first: filled when the target was hit, a ring when not.
struct WeekDots: View {
    let counts: [Int]
    let target: Int
    var body: some View {
        HStack(spacing: 4) {
            ForEach(Array(counts.enumerated()), id: \.offset) { i, n in
                Circle().fill(n >= target ? Color.white : Color.clear)
                    .overlay(Circle().stroke(n >= target ? Color.white : Theme.tertiary, lineWidth: 1))
                    .frame(width: i == counts.count - 1 ? 7 : 5, height: i == counts.count - 1 ? 7 : 5)
            }
        }
        .accessibilityElement().accessibilityLabel("\(counts.filter { $0 >= target }.count) of \(counts.count) days hit")
    }
}

/// Outcome goals: set them, then stop checking. Quiet bars at the bottom of the page.
struct MailboxSection: View {
    @EnvironmentObject var state: AppState
    @State private var editing: GoalItem?
    @State private var adding = false
    private var outcomes: [GoalItem] { state.goals.filter { !$0.isInput } }

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                sectionLabel("in the mailbox")
                Spacer()
                Button("add") { adding = true }.font(.system(size: 13)).foregroundStyle(Theme.secondary).frame(minHeight: 44)
            }
            if outcomes.isEmpty {
                Text("outcome goals go here. set them, then put your attention on the reps.")
                    .font(.system(size: 13)).foregroundStyle(Theme.tertiary)
            }
            ForEach(outcomes) { g in
                Button { editing = g } label: {
                    VStack(alignment: .leading, spacing: 6) {
                        HStack {
                            Text(g.name).font(.system(size: 14.5)).foregroundStyle(Theme.body)
                            Spacer()
                            Text("\(g.current ?? 0) of \(g.target)" + (g.unit.isEmpty ? "" : " " + g.unit))
                                .font(.system(size: 12.5)).monospacedDigit().foregroundStyle(Theme.tertiary)
                        }
                        Bar(fraction: outcomeFraction(g), strong: false)
                    }.frame(maxWidth: .infinity, alignment: .leading)
                }.buttonStyle(PressStyle())
            }
        }
        .sheet(isPresented: $adding) { GoalSheet(kind: "outcome").environmentObject(state) }
        .sheet(item: $editing) { g in OutcomeSheet(goal: g).environmentObject(state) }
    }
}

struct GoalSheet: View {
    @EnvironmentObject var state: AppState
    @Environment(\.dismiss) private var dismiss
    @State var kind = "input"
    @State private var name = ""
    @State private var unit = ""
    @State private var target = "1"
    @State private var current = ""
    @State private var saving = false
    @FocusState private var nameFocused: Bool

    private let suggestions = [("leetcode problems", "problems"), ("recorded speaking take", "take"),
                               ("one hard thing", "thing"), ("applications", "apps")]
    private var targetValue: Int? { Int(target.filter(\.isNumber)).flatMap { $0 > 0 ? $0 : nil } }
    private var canSave: Bool { !saving && !name.trimmingCharacters(in: .whitespaces).isEmpty && targetValue != nil }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                sheetTitle(kind == "input" ? "New rep" : "New outcome").contentTransition(.opacity)
                Picker("", selection: $kind.animation(Theme.spring)) {
                    Text("reps a day").tag("input"); Text("total to reach").tag("outcome")
                }.pickerStyle(.segmented)
                Text(kind == "input"
                     ? "something you control, counted daily. ask: how many reps would make missing the result unreasonable?"
                     : "the result you want. it sits in the mailbox, you update it now and then.")
                    .font(.system(size: 13)).foregroundStyle(Theme.secondary)
                if kind == "input" {
                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack(spacing: 8) {
                            ForEach(suggestions, id: \.0) { s in
                                Button { name = s.0; unit = s.1 } label: {
                                    Text(s.0).font(.system(size: 13)).foregroundStyle(Theme.body)
                                        .padding(.horizontal, 14).frame(minHeight: 36).glass(Capsule())
                                }.buttonStyle(PressStyle())
                            }
                        }
                    }
                }
                input("name", $name).focused($nameFocused)
                HStack(spacing: 10) {
                    input(kind == "input" ? "a day" : "target", $target, numbers: true)
                    input("unit", $unit)
                }
                if kind == "outcome" { input("where you are now", $current, numbers: true) }
                PillButton(label: saving ? "saving" : "save", primary: true, enabled: canSave, feedback: .success) { save() }
            }
            .padding(24).padding(.top, 8).frame(maxWidth: .infinity, alignment: .leading)
        }
        .sheetChrome([.large])
        .onAppear { nameFocused = true }
    }

    private func input(_ prompt: String, _ text: Binding<String>, numbers: Bool = false) -> some View {
        TextField(prompt, text: text).font(.system(size: 16)).foregroundStyle(Theme.title)
            #if os(iOS)
            .keyboardType(numbers ? .numberPad : .default)
            #endif
            .padding(.horizontal, 18).frame(minHeight: 48).glass(Capsule())
    }

    private func save() {
        guard let t = targetValue, canSave else { return }
        saving = true
        var body: [String: Any] = ["name": String(name.trimmingCharacters(in: .whitespaces).prefix(60)), "kind": kind,
                                   "unit": String(unit.prefix(20)), "target": t]
        if kind == "outcome", let c = Int(current.filter(\.isNumber)) { body["current"] = c }
        Task {
            if await state.addGoal(body) { dismiss() }
            saving = false
        }
    }
}

struct OutcomeSheet: View {
    @EnvironmentObject var state: AppState
    @Environment(\.dismiss) private var dismiss
    let goal: GoalItem
    @State private var current = ""

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            sheetTitle(goal.name)
            Text("target \(goal.target)" + (goal.unit.isEmpty ? "" : " " + goal.unit)).font(.system(size: 14)).foregroundStyle(Theme.secondary)
            TextField("where you are now", text: $current).font(.system(size: 22)).foregroundStyle(Theme.title)
                #if os(iOS)
                .keyboardType(.numberPad)
                #endif
                .padding(.horizontal, 18).frame(minHeight: 48).glass(Capsule())
            HStack(spacing: 10) {
                PillButton(label: "save", primary: true, enabled: Int(current.filter(\.isNumber)) != nil, feedback: .success) {
                    guard let c = Int(current.filter(\.isNumber)) else { return }
                    dismiss(); Task { await state.updateGoal(goal.id, ["current": c]) }
                }
                PillButton(label: "remove", feedback: .warning) { dismiss(); Task { await state.deleteGoal(goal.id) } }
            }
            Spacer()
        }
        .padding(24).padding(.top, 8).frame(maxWidth: .infinity, alignment: .leading)
        .sheetChrome([.medium])
        .onAppear { current = String(goal.current ?? 0) }
    }
}

/// Right after the vision: name what is most likely to get in the way, then decide now what you'll do.
/// Picturing only the win lowers effort. Pairing it with the obstacle raises it.
struct ObstaclePlan: View {
    @EnvironmentObject var state: AppState
    @State private var obstacle = ""
    @State private var ifThen = ""
    @State private var loaded = false
    @FocusState private var focus: Int?

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            sectionLabel("what's most likely to stop you today?")
            box("scrolling, a late night, ...", $obstacle, tag: 0)
            sectionLabel("if that happens, I'll")
            box("put the phone in the other room", $ifThen, tag: 1)
        }
        .onAppear(perform: fill)
        .onDisappear(perform: save)
        .onChange(of: state.checkin) { _, _ in fill() }
        .onChange(of: focus) { old, _ in if old != nil { save() } }  // saves when you leave a field
    }

    private func fill() {
        guard !loaded, let t = state.checkin?.today else { return }
        obstacle = t.obstacle ?? ""; ifThen = t.ifThen ?? ""; loaded = true
    }

    private func save() {
        let t = state.checkin?.today
        var body: [String: Any] = [:]
        if obstacle != (t?.obstacle ?? "") { body["obstacle"] = String(obstacle.prefix(200)) }
        if ifThen != (t?.ifThen ?? "") { body["if_then"] = String(ifThen.prefix(200)) }
        guard !body.isEmpty else { return }
        Task { await state.saveCheckin(body) }
    }

    private func box(_ prompt: String, _ text: Binding<String>, tag: Int) -> some View {
        TextField(prompt, text: text, axis: .vertical).font(.system(size: 15)).foregroundStyle(Theme.title)
            .lineLimit(1...3).focused($focus, equals: tag).submitLabel(.done).onSubmit { focus = nil }
            .padding(.horizontal, 16).padding(.vertical, 12)
            .glass(RoundedRectangle(cornerRadius: 18, style: .continuous))
    }
}
