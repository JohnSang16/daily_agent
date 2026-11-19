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
    @Published var firstTaskId: Int?

    init() {
        if let (t, at) = Cache.load() { today = t; lastUpdated = at }
        configured = client != nil
    }

    var client: APIClient? {
        guard let u = Keychain.get("baseURL"), let url = URL(string: u), let t = Keychain.get("token"), !t.isEmpty else { return nil }
        return APIClient(baseURL: url, token: t)
    }

    func saveConnection(url: String, token: String) {
        Keychain.set(url.trimmingCharacters(in: .whitespacesAndNewlines), for: "baseURL")
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

    func refresh() async {
        guard let c = client else { problem = "add the address and token in settings."; return }
        do {
            let data = try await c.getData("/today")
            let t = try makeDecoder().decode(Today.self, from: data)
            Cache.save(data)
            today = t
            lastUpdated = Date()
            offline = false
            problem = nil
            if let g: Goal = try? await c.get("/goal/today") { goal = g.text }
        } catch { fail(error) }
    }

    func saveGoal(_ text: String) async {
        guard let c = client else { return }
        do {
            try await c.send("PUT", "/goal/today", json: ["text": String(text.prefix(90))])
            goal = String(text.prefix(90))
        } catch { fail(error) }
    }

    func snooze(_ id: Int, _ option: SnoozeOption) async {
        guard let c = client else { return }
        do {
            try await c.send("POST", "/tasks/\(id)/snooze", json: ["until": isoString(option.date(from: Date()))])
            await refresh()
        } catch { fail(error) }
    }

    func done(_ id: Int) async {
        guard let c = client else { return }
        do {
            try await c.send("POST", "/tasks/\(id)/done")
            await refresh()
        } catch { fail(error) }
    }

    func loadMoney() async {
        guard let c = client else { return }
        do {
            page = try await c.get("/transactions", query: [URLQueryItem(name: "limit", value: "100")])
            banks = try await c.get("/banks")
            offline = false
        } catch { fail(error) }
    }

    func setAccount(_ id: Int, enabled: Bool) async {
        guard let c = client else { return }
        do {
            try await c.send("PATCH", "/banks/accounts/\(id)", json: ["enabled": enabled])
            await loadMoney()
        } catch { fail(error) }
    }

    func loadWeek() async {
        guard let c = client else { return }
        do {
            var events: [String: [EventItem]] = [:]
            var tasks: [RankedTask] = []
            var first: Int?
            for (i, d) in weekDays(from: Date()).enumerated() {
                let t: Today = try await c.get("/today", query: [URLQueryItem(name: "date", value: d),
                                                                  URLQueryItem(name: "limit", value: "50")])
                events[d] = t.events
                if i == 0 { tasks = t.ranked; first = t.topTask?.id }
            }
            weekEvents = events; weekTasks = tasks; firstTaskId = first
            offline = false
        } catch { fail(error) }
    }

    /// Saved only in the agent's own database, never to Google Calendar or Reminders.
    func addItem(_ body: [String: Any]) async -> Bool {
        guard let c = client else { return false }
        do {
            try await c.send("POST", "/items", json: body)
            await loadWeek()
            await refresh()
            return true
        } catch { fail(error); return false }
    }

    func uploadReminders() async {
        guard let c = client else { reminderStatus = "add the address and token first."; return }
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
