import Foundation
import SwiftUI
import UserNotifications

/// A short win message: "that's the type of person you are." over one identity line.
struct Toast: Equatable, Identifiable {
    let id = UUID()
    let title: String
    let line: String?
}

@MainActor
final class AppState: ObservableObject {
    @Published var today: Today?
    @Published var lastUpdated: Date?
    @Published var offline = false
    @Published var problem: String?
    @Published var goal: String?
    @Published var page: TxnPage?
    @Published var recurring: Recurring?
    @Published var banks: Banks?
    @Published var configured = false
    @Published var reminderStatus = ""
    @Published var weekEvents: [String: [EventItem]] = [:]
    @Published var weekTasks: [RankedTask] = []
    @Published var weekLoaded = false
    @Published var firstTaskId: Int?
    @Published var digest: Digest?
    @Published var summary: MoneySummary?
    @Published var budgets: [BudgetGoal] = []
    @Published var checkin: CheckinDay?
    @Published var eod: Eod?
    @Published var goals: [GoalItem] = []
    @Published var toast: Toast?
    @Published var courses: [Course] = []
    private var wins = 0

    init() {
        if let (t, at) = Cache.load() { today = t; lastUpdated = at }
        configured = client != nil
    }

    var client: APIClient? {
        guard let u = Keychain.get("baseURL"), let url = URL(string: u), url.host != nil,
              let t = Keychain.get("token"), !t.isEmpty else { return nil }
        return APIClient(baseURL: url, token: t)
    }

    /// What a screen says while it has nothing to show yet.
    var waitingText: String { offline ? "offline. can't reach the agent." : (problem ?? "loading.") }

    /// Older than five minutes, or never fetched.
    var isStale: Bool { lastUpdated.map { Date().timeIntervalSince($0) > 300 } ?? true }

    func saveConnection(url: String, token: String) {
        Keychain.set(normalizedAddress(url), for: "baseURL")
        Keychain.set(token.trimmingCharacters(in: .whitespacesAndNewlines), for: "token")
        configured = client != nil
    }

    private func fail(_ e: Error) {
        if let a = e as? APIError, a == .offline { offline = true; problem = nil; return }
        offline = false
        switch e {
        case APIError.http(401, _): problem = "the token was refused. check settings."
        case APIError.notConfigured: problem = "add the address and token in settings."
        case APIError.http(_, let detail?): problem = detail
        default: problem = "something went wrong reading the agent."
        }
    }

    /// Runs one call against the agent. Success clears any old problem, failure records it.
    @discardableResult
    private func call(_ body: (APIClient) async throws -> Void) async -> Bool {
        guard let c = client else { problem = "add the address and token in settings."; return false }
        do {
            try await body(c)
            offline = false
            problem = nil
            return true
        } catch {
            fail(error)
            return false
        }
    }

    func refresh() async {
        await call { c in
            let data = try await c.getData("/today")
            let t = try makeDecoder().decode(Today.self, from: data)
            Cache.save(data)
            today = t
            lastUpdated = Date()
            if let g: Goal = try? await c.get("/goal/today") { goal = g.text }
            async let ck: CheckinDay? = try? c.get("/checkin/today")
            async let gs: [GoalItem]? = try? c.get("/goals")
            async let dg: Digest? = try? c.get("/digest")  // also feeds the win toast's identity lines
            async let eo: Eod? = try? c.get("/eod/today")
            if let v = await ck { checkin = v }
            if let v = await gs { goals = v }
            if let v = await dg { digest = v }
            if let v = await eo { eod = v }
        }
    }

    // MARK: agent screen (spec 19)

    /// One question to POST /ask. Returns nil on failure, with the problem line set.
    func ask(_ question: String, context: AskContext, course: String?) async -> AskReply? {
        var out: AskReply?
        var body: [String: Any] = ["question": String(question.prefix(500)), "context": context.sources]
        if let course { body["course"] = course; body["context"] = ["vault"] }
        await call { c in out = try await c.post("/ask", json: body) }
        return out
    }

    // MARK: homework agent (spec 13)

    func startHomework(taskId: Int, site: String) async -> HomeworkSession? {
        var out: HomeworkSession?
        await call { c in out = try await c.post("/agent/sessions", json: ["task_id": taskId, "site": site]) }
        return out
    }

    func homeworkSession(_ id: Int) async -> HomeworkSession? {
        var out: HomeworkSession?
        await call { c in out = try await c.get("/agent/sessions/\(id)") }
        return out
    }

    /// pause, takeover, handback or stop.
    func homeworkControl(_ id: Int, _ action: String) async -> HomeworkSession? {
        var out: HomeworkSession?
        await call { c in out = try await c.post("/agent/sessions/\(id)/\(action)", json: [:]) }
        return out
    }

    func homeworkMessage(_ id: Int, _ text: String) async -> HomeworkSession? {
        var out: HomeworkSession?
        await call { c in out = try await c.post("/agent/sessions/\(id)/message", json: ["text": String(text.prefix(1000))]) }
        return out
    }

    func homeworkDecide(_ id: Int, approval: Int, approve: Bool) async -> HomeworkSession? {
        var out: HomeworkSession?
        await call { c in
            out = try await c.post("/agent/sessions/\(id)/approvals/\(approval)", json: ["decision": approve ? "approve" : "deny"])
        }
        return out
    }

    func loadCourses() async {
        await call { c in courses = try await c.get("/courses") }
    }

    /// Whatever homework session is running right now, if any. A 404 here just means none is
    /// active, not a real problem, so this stays quiet instead of going through `call`.
    func activeHomeworkSession() async -> HomeworkSession? {
        guard let c = client else { return nil }
        return try? await c.get("/agent/sessions/active")
    }

    // MARK: follow through (spec 18)

    /// Self talk right after a win: said once, then it fades.
    func celebrate(_ title: String = "that's the type of person you are.") {
        wins += 1
        let t = Toast(title: title, line: identityLine(digest?.identity, turn: wins))
        withAnimation(Theme.spring) { toast = t }
        Task {
            try? await Task.sleep(nanoseconds: 2_800_000_000)
            if toast == t { withAnimation(Theme.ease) { toast = nil } }
        }
    }

    func loadCheckin() async {
        await call { c in checkin = try await c.get("/checkin/today") }
    }

    /// Partial save: only the keys given change. Shows on screen first.
    func saveCheckin(_ fields: [String: Any]) async {
        if var ck = checkin {
            if let v = fields["obstacle"] as? String { ck.today.obstacle = v }
            if let v = fields["if_then"] as? String { ck.today.ifThen = v }
            if let v = fields["did_top"] as? Bool { ck.today.didTop = v }
            if let v = fields["why_not"] as? String { ck.today.whyNot = v }
            if let v = fields["let_go"] as? String { ck.today.letGo = v }
            withAnimation(Theme.spring) { checkin = ck }
        }
        await call { c in try await c.send("PUT", "/checkin/today", json: fields) }
        await loadCheckin()
    }

    func loadEod() async {
        await call { c in eod = try await c.get("/eod/today") }
    }

    /// Closes the day: one write, both the DB and the vault's daily-agent-logs/ file.
    func saveEod(_ bullets: String) async {
        let ok = await call { c in try await c.send("PUT", "/eod/today", json: ["bullets": bullets]) }
        if ok { celebrate("day logged.") }
        await loadEod()
    }

    func loadGoals() async {
        await call { c in goals = try await c.get("/goals") }
    }

    /// Sets today's count for an input goal. Hitting the target is a win.
    func logInput(_ g: GoalItem, count: Int) async {
        let n = max(0, count)
        let hitNow = n >= g.target && (g.today ?? 0) < g.target
        if let i = goals.firstIndex(where: { $0.id == g.id }) {
            goals[i].today = n
            if var l = goals[i].last7, !l.isEmpty { l[l.count - 1] = n; goals[i].last7 = l }
        }
        if hitNow { celebrate() }
        await call { c in try await c.send("PUT", "/goals/\(g.id)/today", json: ["count": n]) }
        await loadGoals()
    }

    func addGoal(_ body: [String: Any]) async -> Bool {
        let ok = await call { c in try await c.send("POST", "/goals", json: body) }
        if ok { await loadGoals() }
        return ok
    }

    func updateGoal(_ id: Int, _ body: [String: Any]) async {
        await call { c in try await c.send("PATCH", "/goals/\(id)", json: body) }
        await loadGoals()
    }

    func deleteGoal(_ id: Int) async {
        withAnimation(Theme.spring) { goals.removeAll { $0.id == id } }
        await call { c in try await c.send("DELETE", "/goals/\(id)") }
        await loadGoals()
    }

    /// A local 9 pm reminder, every day. Nothing leaves the phone.
    func setNightlyReminder(_ on: Bool) async -> Bool {
        let center = UNUserNotificationCenter.current()
        center.removePendingNotificationRequests(withIdentifiers: ["nightly-checkin"])
        UserDefaults.standard.set(on, forKey: "nightlyCheckin")
        guard on else { return true }
        guard (try? await center.requestAuthorization(options: [.alert, .sound])) == true else {
            UserDefaults.standard.set(false, forKey: "nightlyCheckin")
            return false
        }
        let content = UNMutableNotificationContent()
        content.title = "did #1 happen?"
        content.body = "one minute. answer honestly, then let the rest go."
        let trigger = UNCalendarNotificationTrigger(dateMatching: DateComponents(hour: 21, minute: 0), repeats: true)
        try? await center.add(UNNotificationRequest(identifier: "nightly-checkin", content: content, trigger: trigger))
        return true
    }

    /// Shows the new goal right away, puts the old one back if the agent refuses it.
    func saveGoal(_ text: String) async {
        let clean = String(text.trimmingCharacters(in: .whitespacesAndNewlines).prefix(90))
        guard !clean.isEmpty else { return }
        let old = goal
        goal = clean
        let ok = await call { c in try await c.send("PUT", "/goal/today", json: ["text": clean]) }
        if !ok { goal = old }
    }

    /// The task leaves the list at once. A refresh afterwards puts it back if the call failed.
    private func dropTask(_ id: Int) {
        withAnimation(Theme.spring) {
            today?.ranked.removeAll { $0.id == id }
            weekTasks.removeAll { $0.id == id }
        }
    }

    func snooze(_ id: Int, _ option: SnoozeOption) async {
        dropTask(id)
        await call { c in try await c.send("POST", "/tasks/\(id)/snooze", json: ["until": isoString(option.date(from: Date()))]) }
        await refresh()
    }

    func done(_ id: Int) async {
        dropTask(id)
        today?.doneToday = (today?.doneToday ?? 0) + 1
        celebrate()
        await call { c in try await c.send("POST", "/tasks/\(id)/done") }
        await refresh()
    }

    /// months=24 so 3M/1Y/ALL can slice client side with no refetch; daily_days anchors the
    /// rolling window the 7D/1M chart needs (not pinned to the 1st of the calendar month).
    private func moneyQuery(days: Int) -> [URLQueryItem] {
        [URLQueryItem(name: "months", value: "24"), URLQueryItem(name: "daily_days", value: String(days))]
    }

    /// Re-anchors the daily series to a different rolling window (7D vs 1M) when the money
    /// screen's range picker changes. The month-resolution ranges reuse what's already loaded.
    func loadMoneyDaily(days: Int) async {
        await call { c in summary = try await c.get("/money/summary", query: moneyQuery(days: days)) }
    }

    /// Everything the money screen shows, fetched side by side.
    func loadAllMoney() async {
        await call { c in
            async let s: MoneySummary = c.get("/money/summary", query: moneyQuery(days: 31))
            async let b: [BudgetGoal] = c.get("/budgets")
            async let bk: Banks = c.get("/banks")
            async let p: TxnPage = c.get("/transactions", query: [URLQueryItem(name: "limit", value: "100")])
            async let r: Recurring = c.get("/money/recurring")
            let (s1, b1, bk1, p1, r1) = try await (s, b, bk, p, r)
            summary = s1; budgets = b1; banks = bk1; page = p1; recurring = r1
        }
    }

    private func loadOverview() async {
        await call { c in
            async let s: MoneySummary = c.get("/money/summary", query: moneyQuery(days: 31))
            async let b: [BudgetGoal] = c.get("/budgets")
            let (s1, b1) = try await (s, b)
            summary = s1; budgets = b1
        }
    }

    func saveBudget(_ category: String, cents: Int) async {
        if let i = budgets.firstIndex(where: { $0.category == category }) { budgets[i].limitCents = cents }
        await call { c in try await c.send("PUT", "/budgets/\(category)", json: ["limit_cents": cents]) }
        await loadOverview()
    }

    func deleteBudget(_ category: String) async {
        withAnimation(Theme.spring) { budgets.removeAll { $0.category == category } }
        await call { c in try await c.send("DELETE", "/budgets/\(category)") }
        await loadOverview()
    }

    /// Flips the switch at once so it never snaps back, then reloads the totals it changes.
    func setAccount(_ id: Int, enabled: Bool) async {
        if let i = banks?.accounts.firstIndex(where: { $0.id == id }) { banks?.accounts[i].enabled = enabled }
        let ok = await call { c in try await c.send("PATCH", "/banks/accounts/\(id)", json: ["enabled": enabled]) }
        if !ok {
            if let i = banks?.accounts.firstIndex(where: { $0.id == id }) { banks?.accounts[i].enabled = !enabled }
            return
        }
        await loadAllMoney()
    }

    /// Today first (it warms the agent's explanation cache), then the other six days side by side.
    func loadWeek() async {
        await call { c in
            let days = weekDays(from: Date())
            let limit = URLQueryItem(name: "limit", value: "500")
            let first: Today = try await c.get("/today", query: [URLQueryItem(name: "date", value: days[0]), limit])
            var events: [String: [EventItem]] = [days[0]: first.events]
            try await withThrowingTaskGroup(of: (String, [EventItem]).self) { group in
                for d in days.dropFirst() {
                    group.addTask {
                        let t: Today = try await c.get("/today", query: [URLQueryItem(name: "date", value: d), limit])
                        return (d, t.events)
                    }
                }
                for try await (d, e) in group { events[d] = e }
            }
            weekEvents = events; weekTasks = first.ranked; firstTaskId = first.topTask?.id
            weekLoaded = true
        }
    }

    /// Saved only in the agent's own database, never to Google Calendar or Reminders.
    /// Returns as soon as the agent has it, the screens reload behind the closed sheet.
    func addItem(_ body: [String: Any]) async -> Bool {
        let ok = await call { c in try await c.send("POST", "/items", json: body) }
        if ok { Task { await loadWeek(); await refresh() } }
        return ok
    }

    /// Only items the app itself created ("manual") can be edited here.
    func patchItem(_ itemId: String, _ body: [String: Any]) async -> Bool {
        let ok = await call { c in try await c.send("PATCH", "/items/\(itemId)", json: body) }
        if ok { Task { await loadWeek(); await refresh() } }
        return ok
    }

    func deleteItem(_ itemId: String) async -> Bool {
        let ok = await call { c in try await c.send("DELETE", "/items/\(itemId)") }
        if ok { Task { await loadWeek(); await refresh() } }
        return ok
    }

    func uploadReminders() async {
        guard let c = client else { reminderStatus = "add the address and token first."; return }
        reminderStatus = "uploading."
        do {
            let items = try await RemindersUploader.collect()
            try await c.send("POST", "/ingest/reminders", json: ["reminders": items])
            reminderStatus = "uploaded \(items.count) reminders."
            await refresh()
        } catch RemindersUploader.Denied.denied {
            reminderStatus = "reminders access was not allowed. turn it on in iOS settings."
        } catch { reminderStatus = "upload failed."; fail(error) }
    }
}
