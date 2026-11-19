import Foundation

// Pure helpers (no UI) so they can be checked from the command line.

private let isoPlain: ISO8601DateFormatter = {
    let f = ISO8601DateFormatter()
    f.formatOptions = [.withInternetDateTime]
    return f
}()

func parseISO(_ s: String?) -> Date? {
    guard let s else { return nil }
    return isoPlain.date(from: s)
}

func isoString(_ d: Date, tz: TimeZone = .current) -> String {
    let f = ISO8601DateFormatter()
    f.timeZone = tz
    f.formatOptions = [.withInternetDateTime, .withTimeZone, .withColonSeparatorInTimeZone]
    return f.string(from: d)
}

private func fmt(_ pattern: String, _ tz: TimeZone) -> DateFormatter {
    let f = DateFormatter()
    f.locale = Locale(identifier: "en_US_POSIX")
    f.timeZone = tz
    f.dateFormat = pattern
    return f
}

/// "tue dec 2, 5:17 pm", or just "tue dec 8" when the due moment is the end of a day (date only).
func dueLine(_ iso: String?, tz: TimeZone = .current) -> String {
    guard let d = parseISO(iso) else { return "no due date" }
    var cal = Calendar(identifier: .gregorian)
    cal.timeZone = tz
    let c = cal.dateComponents([.hour, .minute], from: d)
    let day = fmt("EEE MMM d", tz).string(from: d).lowercased()
    if c.hour == 23 && c.minute == 59 { return day }
    return day + ", " + fmt("h:mm a", tz).string(from: d).lowercased()
}

func clock(_ iso: String, tz: TimeZone = .current) -> String {
    guard let d = parseISO(iso) else { return "" }
    return fmt("h:mm a", tz).string(from: d).lowercased()
}

func dayHeading(_ isoDate: String, now: Date, tz: TimeZone = .current) -> String {
    var cal = Calendar(identifier: .gregorian)
    cal.timeZone = tz
    let f = fmt("yyyy-MM-dd", tz)
    guard let d = f.date(from: isoDate) else { return isoDate }
    if cal.isDate(d, inSameDayAs: now) { return "today" }
    if let y = cal.date(byAdding: .day, value: -1, to: now), cal.isDate(d, inSameDayAs: y) { return "yesterday" }
    return fmt("EEEE MMM d", tz).string(from: d).lowercased()
}

func groupByDay(_ txns: [Txn], now: Date, tz: TimeZone = .current) -> [(heading: String, items: [Txn])] {
    var out: [(heading: String, items: [Txn])] = []
    for t in txns {  // already newest first from the backend
        let h = dayHeading(t.date, now: now, tz: tz)
        if let last = out.last, last.heading == h { out[out.count - 1].items.append(t) } else { out.append((h, [t])) }
    }
    return out
}

enum SnoozeOption: String, CaseIterable, Identifiable {
    case oneHour = "in an hour", tonight = "tonight, 7 pm", tomorrow = "tomorrow, 9 am"
    var id: String { rawValue }

    func date(from now: Date, tz: TimeZone = .current) -> Date {
        var cal = Calendar(identifier: .gregorian)
        cal.timeZone = tz
        switch self {
        case .oneHour:
            return now.addingTimeInterval(3600)
        case .tonight:
            let t = cal.date(bySettingHour: 19, minute: 0, second: 0, of: now) ?? now
            return t > now ? t : now.addingTimeInterval(3600)
        case .tomorrow:
            let next = cal.date(byAdding: .day, value: 1, to: now) ?? now
            return cal.date(bySettingHour: 9, minute: 0, second: 0, of: next) ?? next.addingTimeInterval(3600)
        }
    }
}

/// Reminder due parts -> what POST /ingest/reminders accepts: a date, or a date time with an offset.
func reminderDue(_ comps: DateComponents?, tz: TimeZone = .current) -> String? {
    guard var c = comps, let y = c.year, let m = c.month, let d = c.day else { return nil }
    if c.hour == nil {
        return String(format: "%04d-%02d-%02d", y, m, d)
    }
    var cal = Calendar(identifier: .gregorian)
    cal.timeZone = tz
    c.calendar = cal
    c.timeZone = tz
    guard let date = c.date else { return nil }
    return isoString(date, tz: tz)
}

// MARK: calendar agenda

struct AgendaItem: Identifiable, Equatable {
    let id: String
    let title: String
    let timeText: String
    let isTask: Bool
    let isFirst: Bool
    let sort: Date
}

struct AgendaSections: Equatable {
    var allDay: [AgendaItem] = []
    var morning: [AgendaItem] = []
    var afternoon: [AgendaItem] = []
    var evening: [AgendaItem] = []
    var isEmpty: Bool { allDay.isEmpty && morning.isEmpty && afternoon.isEmpty && evening.isEmpty }
}

/// yyyy-MM-dd of an instant in the given time zone.
func localDay(_ iso: String?, tz: TimeZone = .current) -> String? {
    guard let d = parseISO(iso) else { return nil }
    return fmt("yyyy-MM-dd", tz).string(from: d)
}

/// The next seven days starting today, as yyyy-MM-dd.
func weekDays(from now: Date, tz: TimeZone = .current) -> [String] {
    var cal = Calendar(identifier: .gregorian)
    cal.timeZone = tz
    let f = fmt("yyyy-MM-dd", tz)
    return (0..<7).compactMap { cal.date(byAdding: .day, value: $0, to: now) }.map { f.string(from: $0) }
}

func buildAgenda(day: String, events: [EventItem], tasks: [RankedTask], firstTaskId: Int?,
                 tz: TimeZone = .current) -> AgendaSections {
    var cal = Calendar(identifier: .gregorian)
    cal.timeZone = tz
    var out = AgendaSections()
    func place(_ item: AgendaItem) {
        let h = cal.component(.hour, from: item.sort)
        if h < 12 { out.morning.append(item) } else if h < 17 { out.afternoon.append(item) } else { out.evening.append(item) }
    }
    for e in events {
        if e.allDay {
            out.allDay.append(AgendaItem(id: "e-" + e.id, title: e.title, timeText: "all day", isTask: false,
                                         isFirst: false, sort: parseISO(e.start) ?? .distantPast))
        } else if let s = parseISO(e.start) {
            let end = parseISO(e.end) != nil ? " to " + clock(e.end, tz: tz) : ""
            place(AgendaItem(id: "e-" + e.id, title: e.title, timeText: clock(e.start, tz: tz) + end,
                             isTask: false, isFirst: false, sort: s))
        }
    }
    for t in tasks where localDay(t.dueAt, tz: tz) == day {
        guard let due = parseISO(t.dueAt) else { continue }
        let c = cal.dateComponents([.hour, .minute], from: due)
        let item = AgendaItem(id: "t-\(t.id)", title: t.title, timeText: "due " + (c.hour == 23 && c.minute == 59 ? "end of day" : clock(t.dueAt!, tz: tz)),
                              isTask: true, isFirst: t.id == firstTaskId, sort: due)
        if c.hour == 23 && c.minute == 59 { out.allDay.append(item) } else { place(item) }
    }
    out.morning.sort { $0.sort < $1.sort }
    out.afternoon.sort { $0.sort < $1.sort }
    out.evening.sort { $0.sort < $1.sort }
    return out
}
