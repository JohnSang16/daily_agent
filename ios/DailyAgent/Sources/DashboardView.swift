import SwiftUI

struct DashboardView: View {
    @EnvironmentObject var state: AppState
    @State private var editingGoal = false
    @State private var draft = ""
    @State private var picked: RankedTask?

    private var now: Date { Date() }
    private func f(_ p: String) -> String {
        let d = DateFormatter(); d.locale = Locale(identifier: "en_US_POSIX"); d.dateFormat = p
        return d.string(from: now)
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 30) {
                VStack(alignment: .leading, spacing: 4) {
                    BigTitle(text: f("EEEE"))
                    Text(f("MMMM d").lowercased()).font(.system(size: 14.5)).foregroundStyle(Theme.secondary)
                }
                if let t = state.today { Text(t.explanation.text).font(.system(size: 14.5)).foregroundStyle(Theme.body).lineSpacing(3).reveal(1) }
                goalSection.reveal(2)
                deadlines.reveal(3)
                schedule.reveal(4)
                footer.reveal(5)
            }
            .padding(.horizontal, 24).padding(.top, 72).padding(.bottom, 60)
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .refreshable { await state.refresh() }
        .sheet(item: $picked) { t in TaskSheet(task: t).environmentObject(state) }
    }

    private var goalSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            sectionLabel("today's goal")
            if let g = state.goal, !g.isEmpty, !editingGoal {
                Text(g).font(.system(size: 26)).foregroundStyle(Theme.title)
                Button("edit") { draft = g; editingGoal = true }
                    .font(.system(size: 13)).foregroundStyle(Theme.secondary).frame(minHeight: 44, alignment: .leading)
            } else {
                HStack {
                    TextField("one line", text: $draft).font(.system(size: 18)).foregroundStyle(Theme.title)
                        .onChange(of: draft) { _, v in if v.count > 90 { draft = String(v.prefix(90)) } }
                    PillButton(label: "save", primary: true) {
                        let text = draft; editingGoal = false
                        Task { await state.saveGoal(text) }
                    }
                }
            }
        }
    }

    private var deadlines: some View {
        VStack(alignment: .leading, spacing: 18) {
            sectionLabel("deadlines")
            if let t = state.today, !t.ranked.isEmpty {
                ForEach(Array(t.ranked.prefix(3).enumerated()), id: \.element.id) { i, r in
                    Button { picked = r } label: {
                        HStack(alignment: .top, spacing: 14) {
                            Text("\(i + 1)").font(.system(size: 16)).foregroundStyle(Theme.tertiary).frame(width: 18, alignment: .leading)
                            VStack(alignment: .leading, spacing: 3) {
                                HStack(spacing: 8) {
                                    Text(r.title).font(.system(size: 16)).foregroundStyle(Theme.title).multilineTextAlignment(.leading)
                                    if i == 0 {
                                        Text("first").font(.system(size: 11)).foregroundStyle(Theme.secondary)
                                            .padding(.horizontal, 7).padding(.vertical, 2).overlay(Capsule().stroke(Theme.tertiary))
                                    }
                                }
                                Text(dueLine(r.dueAt)).font(.system(size: 12.5)).foregroundStyle(Theme.secondary)
                            }
                        }.frame(maxWidth: .infinity, alignment: .leading).frame(minHeight: 44)
                    }.buttonStyle(PressStyle())
                }
            } else {
                Text("nothing due.").font(.system(size: 14.5)).foregroundStyle(Theme.secondary)
            }
        }
    }

    private var schedule: some View {
        VStack(alignment: .leading, spacing: 14) {
            if let t = state.today, !t.events.isEmpty {
                sectionLabel("today's schedule")
                ForEach(t.events) { e in
                    HStack(alignment: .firstTextBaseline, spacing: 12) {
                        Text(e.allDay ? "all day" : clock(e.start)).font(.system(size: 12.5)).foregroundStyle(Theme.secondary)
                            .frame(width: 64, alignment: .leading)
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
            if let p = state.problem { Text(p).font(.system(size: 12.5)).foregroundStyle(Theme.secondary) }
            if let at = state.lastUpdated {
                Text((state.offline ? "offline. last updated " : "updated ") + timeText(at))
                    .font(.system(size: 12.5)).foregroundStyle(Theme.tertiary)
            }
        }
    }

    private func timeText(_ d: Date) -> String {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.dateFormat = "h:mm a"
        return f.string(from: d).lowercased()
    }

    private func warningLine(_ w: Warning) -> String {
        let s = (w.source ?? "a source").replacingOccurrences(of: "_", with: " ")
        switch w.code {
        case "SOURCE_STALE": return "\(s) is out of date"
        case "SYNC_ERROR": return "\(s) failed its last sync"
        case "NEEDS_REVIEW": return w.detail ?? "some items need review"
        default: return w.detail ?? w.code.lowercased()
        }
    }
}

struct TaskSheet: View {
    @EnvironmentObject var state: AppState
    @Environment(\.dismiss) private var dismiss
    let task: RankedTask

    var body: some View {
        VStack(alignment: .leading, spacing: 22) {
            Text(task.title).font(.system(size: 26)).foregroundStyle(Theme.title)
            Text("due " + dueLine(task.dueAt)).font(.system(size: 14.5)).foregroundStyle(Theme.secondary)
            if !task.reasons.isEmpty {
                Text(task.reasons.joined(separator: ", ").lowercased().replacingOccurrences(of: "_", with: " "))
                    .font(.system(size: 13.5)).foregroundStyle(Theme.secondary)
            }
            if task.atRisk { Text("at risk. give it your first free block.").font(.system(size: 13.5)).foregroundStyle(Theme.body) }
            sectionLabel("snooze")
            ForEach(SnoozeOption.allCases) { o in
                PillButton(label: o.rawValue) { Task { await state.snooze(task.id, o); dismiss() } }
            }
            PillButton(label: "mark done", primary: true) { Task { await state.done(task.id); dismiss() } }
                .sensoryFeedback(.success, trigger: task.id)
            Spacer()
        }
        .padding(24).frame(maxWidth: .infinity, alignment: .leading)
        .presentationBackground(.regularMaterial).presentationDetents([.medium, .large])
        .presentationCornerRadius(28).presentationDragIndicator(.visible)
    }
}
