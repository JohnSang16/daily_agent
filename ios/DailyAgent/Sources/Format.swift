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
    let backendId: Int
    let source: String  // "manual" is editable in the app
    let title: String
    let timeText: String
    let isTask: Bool
    let isFirst: Bool
    let sort: Date
    let rawEnd: Date?  // events only, nil for tasks
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
            out.allDay.append(AgendaItem(id: "e-\(e.id)", backendId: e.id, source: e.source, title: e.title,
                                         timeText: "all day", isTask: false, isFirst: false,
                                         sort: parseISO(e.start) ?? .distantPast, rawEnd: parseISO(e.end)))
        } else if let s = parseISO(e.start) {
            let end = parseISO(e.end) != nil ? " to " + clock(e.end, tz: tz) : ""
            place(AgendaItem(id: "e-\(e.id)", backendId: e.id, source: e.source, title: e.title,
                             timeText: clock(e.start, tz: tz) + end, isTask: false, isFirst: false,
                             sort: s, rawEnd: parseISO(e.end)))
        }
    }
    for t in tasks where localDay(t.dueAt, tz: tz) == day {
        guard let due = parseISO(t.dueAt) else { continue }
        let c = cal.dateComponents([.hour, .minute], from: due)
        let item = AgendaItem(id: "t-\(t.id)", backendId: t.id, source: t.source, title: t.title,
                              timeText: "due " + (c.hour == 23 && c.minute == 59 ? "end of day" : clock(t.dueAt!, tz: tz)),
                              isTask: true, isFirst: t.id == firstTaskId, sort: due, rawEnd: nil)
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

/// Top N categories by spend (default 5), any remainder bundled into one "OTHER" bucket.
func topCategoriesWithOther(_ categories: [CategorySpend], limit: Int = 5) -> [CategorySpend] {
    guard categories.count > limit else { return categories }
    let sorted = categories.sorted { $0.spendCents > $1.spendCents }
    let other = sorted.dropFirst(limit).reduce(0) { $0 + $1.spendCents }
    return Array(sorted.prefix(limit)) + [CategorySpend(category: "OTHER", spendCents: other)]
}

/// "$150 below average" or "$150 above average"; nil with no other months to compare to.
func averageComparisonLine(current: Int, others: [Int]) -> String? {
    guard !others.isEmpty else { return nil }
    let avg = others.reduce(0, +) / others.count
    let diff = avg - current
    return diff >= 0 ? "\(dollars(diff)) below average" : "\(dollars(-diff)) above average"
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

// MARK: follow through (spec 18)

/// "deep work, 2:00 to 4:00 pm" for the #1 task's suggested block. Empty when there is none.
func blockLine(_ b: TimeBlock?, tz: TimeZone = .current) -> String {
    guard let b, parseISO(b.start) != nil else { return "" }
    let start = clock(b.start, tz: tz), end = clock(b.end, tz: tz)
    // "2:00 pm to 4:00 pm" reads heavy, drop the first am/pm when both match
    let s = start.hasSuffix(String(end.suffix(2))) ? String(start.dropLast(3)) : start
    return "deep work, \(s) to \(end)"
}

/// The nightly check-in shows from 9 pm until it is answered.
func checkinDue(_ now: Date, answered: Bool, tz: TimeZone = .current) -> Bool {
    var cal = Calendar(identifier: .gregorian)
    cal.timeZone = tz
    return !answered && cal.component(.hour, from: now) >= 21
}

/// "kept your word 9 of 11 days", or nothing until there is an answer.
func sayDoLine(_ s: SayDo) -> String {
    s.of == 0 ? "" : "kept your word \(s.kept) of \(s.of) day" + (s.of == 1 ? "" : "s")
}

/// "1 of 2 problems", with the unit only when set.
func repsLine(_ g: GoalItem) -> String {
    "\(g.today ?? 0) of \(g.target)" + (g.unit.isEmpty ? "" : " " + g.unit)
}

/// The identity line under the win toast, rotated by a counter so it is not always the first one.
func identityLine(_ lines: [String]?, turn: Int) -> String? {
    guard let lines, !lines.isEmpty else { return nil }
    return lines[abs(turn) % lines.count]
}

/// 0 to 1 for an outcome goal's bar.
func outcomeFraction(_ g: GoalItem) -> Double {
    guard g.target > 0 else { return 0 }
    return min(1, Double(g.current ?? 0) / Double(g.target))
}

// MARK: agent screen (spec 19)

enum AskContext: String, CaseIterable, Identifiable {
    case all, notes, tasks
    var id: String { rawValue }
    /// What POST /ask may read. Email stays off until spec 06 exists.
    var sources: [String] {
        switch self {
        case .all: return ["vault", "calendar"]
        case .notes: return ["vault"]
        case .tasks: return ["calendar"]
        }
    }
}

/// "career/school/os-lecture-notes.md" -> "os lecture notes"
func noteName(_ path: String) -> String {
    let file = path.split(separator: "/").last.map(String.init) ?? path
    let base = file.hasSuffix(".md") ? String(file.dropLast(3)) : file
    return base.replacingOccurrences(of: "-", with: " ").replacingOccurrences(of: "_", with: " ")
}

/// "OPERATING SYSTEMS XLS Group ACS37 Fall S" -> "operating systems xls group acs37 fall s", trimmed to fit a chip.
func courseLabel(_ c: String, max: Int = 28) -> String {
    let l = c.lowercased().trimmingCharacters(in: .whitespaces)
    return l.count > max ? String(l.prefix(max - 1)).trimmingCharacters(in: .whitespaces) + "…" : l
}

// MARK: homework sessions (spec 13)

/// The status chip in plain words.
func sessionStatusLine(_ status: String) -> String {
    switch status {
    case "starting": return "starting the browser"
    case "running": return "working"
    case "paused": return "paused"
    case "takeover": return "you have control"
    case "needs_approval": return "needs your approval"
    case "ended": return "ended"
    default: return status.replacingOccurrences(of: "_", with: " ")
    }
}

// MARK: money tabs redesign

/// What each part of holdings is as a share of everything owned (cash + savings + invested).
func holdingShares(_ h: Holdings) -> (cash: Double, savings: Double, invested: Double) {
    let total = Double(max(h.cashCents, 0) + max(h.savingsCents, 0) + max(h.investedCents, 0))
    guard total > 0 else { return (0, 0, 0) }
    return (Double(max(h.cashCents, 0)) / total, Double(max(h.savingsCents, 0)) / total, Double(max(h.investedCents, 0)) / total)
}

/// 2340 -> "$23.40", with "+" or "-" in front when signed.
func dollarsAndCents(_ cents: Int, signed: Bool = false) -> String {
    let f = NumberFormatter()
    f.numberStyle = .decimal
    f.minimumFractionDigits = 2
    f.maximumFractionDigits = 2
    f.locale = Locale(identifier: "en_US")
    let body = "$" + (f.string(from: NSNumber(value: Double(abs(cents)) / 100)) ?? "\(abs(cents))")
    return cents < 0 ? "-" + body : (signed ? "+" + body : body)
}

/// Money in minus money out for a set of rows.
func netCents(_ txns: [Txn]) -> Int {
    txns.reduce(0) { $0 + ($1.direction == "in" ? 1 : -1) * centsFromDisplay($1.amount) }
}

enum ActivityFilter: String, CaseIterable, Identifiable {
    case all, spending, income, pending
    var id: String { rawValue }
}

/// Filters the loaded activity page. The query matches merchant, bank or category, ignoring case.
func filterTxns(_ txns: [Txn], query: String, filter: ActivityFilter) -> [Txn] {
    let q = query.trimmingCharacters(in: .whitespaces).lowercased()
    return txns.filter { t in
        let kept: Bool
        switch filter {
        case .all: kept = true
        case .spending: kept = t.direction == "out"
        case .income: kept = t.direction == "in"
        case .pending: kept = t.pending
        }
        guard kept else { return false }
        guard !q.isEmpty else { return true }
        return t.merchant.lowercased().contains(q) || t.bank.lowercased().contains(q)
            || categoryLabel(t.category ?? "").contains(q)
    }
}

/// SF Symbol for a Plaid primary category.
func categoryIcon(_ c: String?) -> String {
    switch c ?? "" {
    case "FOOD_AND_DRINK": return "fork.knife"
    case "GENERAL_MERCHANDISE": return "bag"
    case "TRANSPORTATION": return "car"
    case "TRAVEL": return "airplane"
    case "ENTERTAINMENT": return "music.note"
    case "RENT_AND_UTILITIES": return "house"
    case "INCOME": return "arrow.down.left"
    case "TRANSFER_IN", "TRANSFER_OUT": return "arrow.left.arrow.right"
    case "LOAN_PAYMENTS": return "creditcard"
    case "MEDICAL": return "cross.case"
    case "PERSONAL_CARE": return "sparkles"
    case "GENERAL_SERVICES": return "wrench.and.screwdriver"
    case "HOME_IMPROVEMENT": return "hammer"
    case "BANK_FEES": return "building.columns"
    case "GOVERNMENT_AND_NON_PROFIT": return "building.2"
    default: return "circle.dashed"
    }
}
