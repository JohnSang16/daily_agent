import SwiftUI

struct DashboardView: View {
    @EnvironmentObject var state: AppState
    @State private var editingGoal = false
    @State private var draft = ""
    @State private var picked: RankedTask?
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
                if let d = state.digest {
                    if let m = d.mantra { line("mantra", m).reveal(1) }
                    if let v = d.vision { line("vision", v).reveal(2) }
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
                schedule.reveal(9)
                footer.reveal(10)
            }
            .page()
            .animation(Theme.spring, value: state.today)
        }
        .scrollDismissesKeyboard(.interactively)
        .refreshable { await state.refresh() }
        .task { if state.isStale { await state.refresh() } }
        .sheet(item: $picked) { t in TaskSheet(task: t).environmentObject(state) }
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

    private var deadlines: some View {
        VStack(alignment: .leading, spacing: 18) {
            sectionLabel("deadlines")
            if let t = state.today, !t.ranked.isEmpty {
                ForEach(Array(t.ranked.prefix(3).enumerated()), id: \.element.id) { i, r in
                    Button { picked = r } label: {
                        HStack(alignment: .top, spacing: 14) {
                            Text("\(i + 1)").font(.system(size: 16)).monospacedDigit().foregroundStyle(Theme.tertiary)
                                .frame(width: 18, alignment: .leading).contentTransition(.numericText())
                            VStack(alignment: .leading, spacing: 3) {
                                HStack(spacing: 8) {
                                    Text(r.title).font(.system(size: 16)).foregroundStyle(Theme.title).multilineTextAlignment(.leading)
                                    if i == 0 { FirstTag() }
                                }
                                Text(dueLine(r.dueAt)).font(.system(size: 12.5)).foregroundStyle(Theme.secondary)
                            }
                            Spacer(minLength: 0)
                            Image(systemName: "chevron.right").font(.system(size: 12)).foregroundStyle(Theme.tertiary).padding(.top, 4)
                        }
                        .frame(maxWidth: .infinity, minHeight: 44, alignment: .leading)
                        .contentShape(Rectangle())
                    }
                    .buttonStyle(PressStyle())
                    .transition(.asymmetric(insertion: .opacity, removal: .opacity.combined(with: .move(edge: .leading))))
                }
            } else {
                Text(state.today == nil ? state.waitingText : "nothing due.").font(.system(size: 14.5)).foregroundStyle(Theme.secondary)
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
