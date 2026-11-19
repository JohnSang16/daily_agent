import EventKit
import Foundation

/// Reads open Apple Reminders on the device and returns only id, title, due and completed.
/// Nothing is ever saved back to Reminders.
enum RemindersUploader {
    enum Denied: Error { case denied }

    static func collect() async throws -> [[String: Any]] {
        let store = EKEventStore()
        guard try await store.requestFullAccessToReminders() else { throw Denied.denied }
        let predicate = store.predicateForIncompleteReminders(withDueDateStarting: nil, ending: nil, calendars: nil)
        let reminders: [EKReminder] = await withCheckedContinuation { cont in
            store.fetchReminders(matching: predicate) { cont.resume(returning: $0 ?? []) }
        }
        return reminders.compactMap { r in
            guard let title = r.title, !title.trimmingCharacters(in: .whitespaces).isEmpty else { return nil }
            var item: [String: Any] = ["id": r.calendarItemIdentifier, "title": title, "completed": false]
            if let due = reminderDue(r.dueDateComponents) { item["due"] = due }
            return item
        }
    }
}
