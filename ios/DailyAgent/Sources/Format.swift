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

// MARK: money

/// 286100 -> "$2,861". Whole dollars, for totals.
func dollars(_ cents: Int) -> String {
    let f = NumberFormatter()
    f.numberStyle = .decimal
    f.maximumFractionDigits = 0
    f.usesGroupingSeparator = true
    f.locale = Locale(identifier: "en_US")
    let whole = Int((Double(abs(cents)) / 100).rounded())
    return (cents < 0 ? "-$" : "$") + (f.string(from: NSNumber(value: whole)) ?? "\(whole)")
}

/// "2026-11" -> "nov"
func monthShort(_ key: String) -> String {
    let names = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
    guard key.count >= 7, let m = Int(key.dropFirst(5).prefix(2)), (1...12).contains(m) else { return key }
    return names[m - 1]
}

/// "2026-11" -> "november"
func monthLong(_ key: String) -> String {
    let names = ["january", "february", "march", "april", "may", "june", "july", "august",
                 "september", "october", "november", "december"]
    guard key.count >= 7, let m = Int(key.dropFirst(5).prefix(2)), (1...12).contains(m) else { return key }
    return names[m - 1]
}

/// "FOOD_AND_DRINK" -> "food and drink"
func categoryLabel(_ c: String) -> String {
    c == "TOTAL" ? "all spending" : c.replacingOccurrences(of: "_", with: " ").lowercased()
}

func accountKindLabel(_ a: BankAccountInfo) -> String {
    switch a.kind ?? "" {
    case "credit": return "credit card"
    case "loan": return "loan"
    case "investment": return (a.subtype ?? "").isEmpty ? "investment" : a.subtype!
    default: return (a.subtype ?? "").isEmpty ? "account" : a.subtype!
    }
}

/// Does this account count against me (card, loan) instead of for me?
func isOwed(_ a: BankAccountInfo) -> Bool { a.kind == "credit" || a.kind == "loan" }

/// One group per bank, keeping the order the agent returned.
func groupBanks(_ accounts: [BankAccountInfo]) -> [(bank: String, accounts: [BankAccountInfo], totalCents: Int)] {
    var out: [(bank: String, accounts: [BankAccountInfo], totalCents: Int)] = []
    for a in accounts {
        let signed = (a.enabled ? 1 : 0) * (isOwed(a) ? -(a.balanceCents ?? 0) : (a.balanceCents ?? 0))
        if let i = out.firstIndex(where: { $0.bank == a.bank }) {
            out[i].accounts.append(a); out[i].totalCents += signed
        } else {
            out.append((a.bank, [a], signed))
        }
    }
    return out
}

/// "+2100.00" or "12.50" -> cents
func centsFromDisplay(_ s: String) -> Int {
    let digits = s.replacingOccurrences(of: "+", with: "").replacingOccurrences(of: ",", with: "")
    let parts = digits.split(separator: ".", omittingEmptySubsequences: false)
    let whole = Int(parts.first ?? "0") ?? 0
    let frac = parts.count > 1 ? Int((String(parts[1]) + "00").prefix(2)) ?? 0 : 0
    return whole * 100 + frac
}

/// Income rows grouped by month, newest month first, with a subtotal for each.
func incomeByMonth(_ txns: [Txn]) -> [(month: String, totalCents: Int, items: [Txn])] {
    var out: [(month: String, totalCents: Int, items: [Txn])] = []
    for t in txns {
        let m = String(t.date.prefix(7))
        if let i = out.firstIndex(where: { $0.month == m }) {
            out[i].items.append(t); out[i].totalCents += centsFromDisplay(t.amount)
        } else {
            out.append((m, centsFromDisplay(t.amount), [t]))
        }
    }
    return out
}

/// How far through a goal: 0 to 1 (a goal that is over reads as 1), and whether it is over.
func goalProgress(spent: Int, limit: Int) -> (fraction: Double, over: Bool) {
    guard limit > 0 else { return (0, false) }
    return (min(1, Double(spent) / Double(limit)), spent > limit)
}

// MARK: settings

/// "100.1.2.3:8000/" -> "http://100.1.2.3:8000". Adds the scheme people forget, drops the trailing slash.
func normalizedAddress(_ raw: String) -> String {
    var s = raw.trimmingCharacters(in: .whitespacesAndNewlines)
    guard !s.isEmpty else { return s }
    if !s.contains("://") { s = "http://" + s }
    while s.hasSuffix("/") { s.removeLast() }
    return s
}

/// Plain words for a /today warning.
func warningLine(_ w: Warning) -> String {
    let s = (w.source ?? "a source").replacingOccurrences(of: "_", with: " ")
    switch w.code {
    case "SOURCE_STALE": return "\(s) is out of date"
    case "SYNC_ERROR": return "\(s) failed its last sync"
    case "NEEDS_REVIEW": return w.detail ?? "some items need review"
    default: return (w.detail ?? w.code.replacingOccurrences(of: "_", with: " ")).lowercased()
    }
}
