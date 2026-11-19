import SwiftUI

struct CalendarView: View {
    @EnvironmentObject var state: AppState
    @State private var selected = weekDays(from: Date())[0]
    @State private var adding = false
    @Namespace private var pick
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    private var days: [String] { weekDays(from: Date()) }

    private func date(_ day: String) -> Date {
        let f = DateFormatter(); f.locale = Locale(identifier: "en_US_POSIX"); f.dateFormat = "yyyy-MM-dd"
        return f.date(from: day) ?? Date()
    }

    private func text(_ day: String, _ pattern: String) -> String {
        let f = DateFormatter(); f.locale = Locale(identifier: "en_US_POSIX"); f.dateFormat = pattern
        return f.string(from: date(day))
    }

    private func agenda(_ day: String) -> AgendaSections {
        buildAgenda(day: day, events: state.weekEvents[day] ?? [], tasks: state.weekTasks, firstTaskId: state.firstTaskId)
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 26) {
                VStack(alignment: .leading, spacing: 4) {
                    BigTitle(text: text(selected, "EEEE"))
                    HStack {
                        Text(text(selected, "MMMM d").lowercased()).font(.system(size: 14.5)).foregroundStyle(Theme.secondary)
                        Spacer()
                        Button("add") { adding = true }
                            .font(.system(size: 14.5)).foregroundStyle(Theme.body).frame(minHeight: 44)
                    }
                }
                weekStrip
                let a = agenda(selected)
                if a.isEmpty {
                    Text("nothing on this day.").font(.system(size: 14.5)).foregroundStyle(Theme.secondary)
                } else {
                    section("all day", a.allDay)
                    section("morning", a.morning)
                    section("afternoon", a.afternoon)
                    section("evening", a.evening)
                }
                if let p = state.problem { Text(p).font(.system(size: 12.5)).foregroundStyle(Theme.secondary) }
            }
            .padding(.horizontal, 24).padding(.top, 72).padding(.bottom, 60)
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .refreshable { await state.loadWeek() }
        .task { await state.loadWeek() }
        .sheet(isPresented: $adding) { AddItemSheet(day: selected).environmentObject(state) }
    }

    private var weekStrip: some View {
        HStack(spacing: 0) {
            ForEach(days, id: \.self) { d in
                let busy = !agenda(d).isEmpty
                Button { withAnimation(reduceMotion ? Theme.ease : Theme.spring) { selected = d } } label: {
                    VStack(spacing: 6) {
                        Text(text(d, "EEE").lowercased().prefix(2)).font(.system(size: 12)).foregroundStyle(Theme.secondary)
                        Text(text(d, "d")).font(.system(size: 16, weight: selected == d ? .medium : .regular))
                            .foregroundStyle(selected == d ? Color.black : Theme.title)
                            .frame(width: 34, height: 34)
                            .background {
                                // one white disc that glides between the days
                                if selected == d {
                                    Circle().fill(LinearGradient(colors: [.white, Color(white: 0.82)], startPoint: .top, endPoint: .bottom))
                                        .shadow(color: .white.opacity(0.15), radius: 8)
                                        .matchedGeometryEffect(id: "selected-day", in: pick)
                                }
                            }
                        Circle().fill(busy ? Theme.secondary : Color.clear).frame(width: 4, height: 4)
                    }.frame(maxWidth: .infinity, minHeight: 44)
                }.buttonStyle(PressStyle())
                .sensoryFeedback(.selection, trigger: selected)
            }
        }
    }

    @ViewBuilder
    private func section(_ label: String, _ items: [AgendaItem]) -> some View {
        if !items.isEmpty {
            VStack(alignment: .leading, spacing: 16) {
                sectionLabel(label)
                ForEach(Array(items.enumerated()), id: \.element.id) { i, it in
                    HStack(alignment: .top, spacing: 14) {
                        // a filled dot is a task, a ring is an event
                        Circle().fill(it.isTask ? Color.white : Color.clear)
                            .overlay(Circle().stroke(Theme.title, lineWidth: 1.2))
                            .frame(width: 9, height: 9).padding(.top, 6)
                        VStack(alignment: .leading, spacing: 3) {
                            HStack(spacing: 8) {
                                Text(it.title).font(.system(size: 16)).foregroundStyle(Theme.title)
                                if it.isFirst {
                                    Text("first").font(.system(size: 11)).foregroundStyle(Theme.secondary)
                                        .padding(.horizontal, 7).padding(.vertical, 2).overlay(Capsule().stroke(Theme.tertiary))
                                }
                            }
                            Text(it.timeText).font(.system(size: 12.5)).foregroundStyle(Theme.secondary)
                        }
                    }
                    .reveal(i)
                }
            }
        }
    }
}

struct AddItemSheet: View {
    @EnvironmentObject var state: AppState
    @Environment(\.dismiss) private var dismiss
    let day: String
    @State private var kind = "task"
    @State private var title = ""
    @State private var when = Date()
    @State private var end = Date().addingTimeInterval(3600)
    @State private var withTime = false
    @State private var failed = false

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            Text("add").font(.system(size: 26)).foregroundStyle(Theme.title)
            Picker("", selection: $kind) {
                Text("task").tag("task"); Text("event").tag("event")
            }.pickerStyle(.segmented)
            TextField("title", text: $title).font(.system(size: 16)).foregroundStyle(Theme.title)
                .padding(.horizontal, 18).frame(minHeight: 48).glass(Capsule())
            if kind == "task" {
                Toggle("set a time", isOn: $withTime).tint(.white).foregroundStyle(Theme.body)
                DatePicker("due", selection: $when, displayedComponents: withTime ? [.date, .hourAndMinute] : [.date])
                    .foregroundStyle(Theme.body)
            } else {
                DatePicker("starts", selection: $when).foregroundStyle(Theme.body)
                DatePicker("ends", selection: $end).foregroundStyle(Theme.body)
            }
            Text("saved in the agent only. it is never written to google calendar or reminders.")
                .font(.system(size: 12.5)).foregroundStyle(Theme.tertiary)
            if failed { Text("could not save. check the connection.").font(.system(size: 12.5)).foregroundStyle(Theme.secondary) }
            PillButton(label: "save", primary: true) { Task { await save() } }
            Spacer()
        }
        .padding(24).frame(maxWidth: .infinity, alignment: .leading)
        .presentationBackground(.regularMaterial).presentationDetents([.large]).presentationCornerRadius(28).presentationDragIndicator(.visible)
        .onAppear { if let d = parseDay(day) { when = d; end = d.addingTimeInterval(3600) } }
    }

    private func parseDay(_ s: String) -> Date? {
        let f = DateFormatter(); f.locale = Locale(identifier: "en_US_POSIX"); f.dateFormat = "yyyy-MM-dd"
        guard let d = f.date(from: s) else { return nil }
        return Calendar.current.date(bySettingHour: 9, minute: 0, second: 0, of: d)
    }

    private func save() async {
        let name = title.trimmingCharacters(in: .whitespaces)
        guard !name.isEmpty else { return }
        var body: [String: Any] = ["kind": kind, "title": name]
        if kind == "task" {
            if withTime {
                body["due"] = isoString(when)
            } else {
                let f = DateFormatter(); f.locale = Locale(identifier: "en_US_POSIX"); f.dateFormat = "yyyy-MM-dd"
                body["due"] = f.string(from: when)
            }
        } else {
            body["start"] = isoString(when)
            body["end"] = isoString(max(end, when.addingTimeInterval(60)))
        }
        if await state.addItem(body) { dismiss() } else { failed = true }
    }
}
