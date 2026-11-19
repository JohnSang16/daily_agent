import Foundation
import SwiftUI

@MainActor
final class AppState: ObservableObject {
    @Published var today: Today?
    @Published var lastUpdated: Date?
    @Published var offline = false
    @Published var problem: String?
    @Published var goal: String?
    @Published var page: TxnPage?
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
    @Published var incomeRows: [Txn] = []

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
        case APIError.http(401): problem = "the token was refused. check settings."
        case APIError.notConfigured: problem = "add the address and token in settings."
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
        }
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
        await call { c in try await c.send("POST", "/tasks/\(id)/done") }
        await refresh()
    }

    /// Everything the money screen shows, fetched side by side.
    func loadAllMoney() async {
        await call { c in
            async let s: MoneySummary = c.get("/money/summary", query: [URLQueryItem(name: "months", value: "6")])
            async let b: [BudgetGoal] = c.get("/budgets")
            async let bk: Banks = c.get("/banks")
            async let p: TxnPage = c.get("/transactions", query: [URLQueryItem(name: "limit", value: "100")])
            async let inc: TxnPage = c.get("/transactions", query: [URLQueryItem(name: "kind", value: "income"),
                                                                     URLQueryItem(name: "limit", value: "500")])
            let (s1, b1, bk1, p1, inc1) = try await (s, b, bk, p, inc)
            summary = s1; budgets = b1; banks = bk1; page = p1; incomeRows = inc1.transactions
        }
    }

    private func loadOverview() async {
        await call { c in
            async let s: MoneySummary = c.get("/money/summary", query: [URLQueryItem(name: "months", value: "6")])
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

    func loadDigest() async {
        await call { c in digest = try await c.get("/digest") }
    }

    /// Today first (it warms the agent's explanation cache), then the other six days side by side.
    func loadWeek() async {
        await call { c in
            let days = weekDays(from: Date())
            let limit = URLQueryItem(name: "limit", value: "50")
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
