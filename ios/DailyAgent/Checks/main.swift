// Runs without Xcode: swiftc Sources/Models.swift Sources/Format.swift Checks/main.swift -o /tmp/checks && /tmp/checks
import Foundation

var failures = 0
func check(_ ok: Bool, _ name: String) {
    print(ok ? "ok   \(name)" : "FAIL \(name)")
    if !ok { failures += 1 }
}

let ny = TimeZone(identifier: "America/New_York")!
let todayJSON = """
{"date":"2026-11-19","timezone":"America/New_York","generated_at":"2026-11-19T15:00:00Z",
 "top_task":{"id":4,"title":"OA","due_at":"2026-12-02T22:17:00Z","reasons":["due_soon"],"at_risk":false,"suggested_block":null},
 "ranked":[{"id":4,"rank":1,"title":"OA","due_at":"2026-12-02T22:17:00Z","source":"obsidian","reasons":["due_soon"],"at_risk":false,"needs_review":false},
           {"id":9,"rank":2,"title":"Project","due_at":"2026-12-05T04:59:59Z","source":"icollege","reasons":[],"at_risk":true,"needs_review":false}],
 "events":[{"title":"Class","start":"2026-11-19T16:00:00Z","end":"2026-11-19T17:00:00Z","all_day":false}],
 "free_blocks":[],"explanation":{"text":"Start with OA.","source":"llm"},
 "warnings":[{"code":"SOURCE_STALE","source":"obsidian","detail":"last success 3h ago"},{"code":"NEEDS_REVIEW","source":null,"detail":"1 to review"}],
 "needs_review_count":1}
"""
let t = try! makeDecoder().decode(Today.self, from: Data(todayJSON.utf8))
check(t.ranked.count == 2 && t.ranked[1].atRisk, "decodes /today ranked list")
check(t.topTask?.id == 4 && t.explanation.source == "llm", "decodes top task and explanation")
check(t.warnings.count == 2 && t.warnings[1].source == nil, "decodes warnings with null source")
check(t.events[0].allDay == false, "decodes events")

let txnJSON = """
{"demo":false,"note":null,"next_cursor":"2026-11-18:7","transactions":[
 {"id":12,"date":"2026-11-19","merchant":"Shell Gas","amount":"60.10","direction":"out","bank":"Bank","category":"TRANSPORTATION","pending":false},
 {"id":"demo-0","date":"2026-11-18","merchant":"Payroll","amount":"+1200.00","direction":"in","bank":"Demo Bank","category":null,"pending":true}]}
"""
let page = try! makeDecoder().decode(TxnPage.self, from: Data(txnJSON.utf8))
check(page.transactions[0].id == "12" && page.transactions[1].id == "demo-0", "txn id decodes as int or string")
check(page.nextCursor == "2026-11-18:7" && page.transactions[1].pending, "decodes cursor and pending")

let now = parseISO("2026-11-19T15:00:00Z")!
check(dueLine("2026-12-02T22:17:00Z", tz: ny) == "wed dec 2, 5:17 pm", "due line with a time (got \(dueLine("2026-12-02T22:17:00Z", tz: ny)))")
check(dueLine("2026-12-05T04:59:59Z", tz: ny) == "fri dec 4", "date only due shows just the day (got \(dueLine("2026-12-05T04:59:59Z", tz: ny)))")
check(dueLine(nil, tz: ny) == "no due date", "no due date")
check(clock("2026-11-19T16:00:00Z", tz: ny) == "11:00 am", "clock time")

check(dayHeading("2026-11-19", now: now, tz: ny) == "today", "heading today")
check(dayHeading("2026-11-18", now: now, tz: ny) == "yesterday", "heading yesterday")
check(dayHeading("2026-11-10", now: now, tz: ny) == "tuesday nov 10", "heading older day (got \(dayHeading("2026-11-10", now: now, tz: ny)))")
let groups = groupByDay(page.transactions + [page.transactions[1]], now: now, tz: ny)
check(groups.count == 2 && groups[1].items.count == 2, "groups transactions by day, newest first")

let tonight = SnoozeOption.tonight.date(from: now, tz: ny)  // 10 am New York
check(isoString(tonight, tz: ny) == "2026-11-19T19:00:00-05:00", "snooze tonight is 7 pm local (got \(isoString(tonight, tz: ny)))")
let late = parseISO("2026-11-20T02:30:00Z")!  // 9:30 pm New York, tonight 7 pm already passed
check(SnoozeOption.tonight.date(from: late, tz: ny) == late.addingTimeInterval(3600), "snooze tonight after 7 pm falls back to an hour")
check(isoString(SnoozeOption.tomorrow.date(from: now, tz: ny), tz: ny) == "2026-11-20T09:00:00-05:00", "snooze tomorrow is 9 am local")
check(SnoozeOption.oneHour.date(from: now, tz: ny) == now.addingTimeInterval(3600), "snooze one hour")

var dateOnly = DateComponents(); dateOnly.year = 2026; dateOnly.month = 11; dateOnly.day = 25
check(reminderDue(dateOnly, tz: ny) == "2026-11-25", "reminder date only")
var timed = dateOnly; timed.hour = 9; timed.minute = 30
check(reminderDue(timed, tz: ny) == "2026-11-25T09:30:00-05:00", "reminder with time has an offset (got \(reminderDue(timed, tz: ny) ?? "nil"))")
check(reminderDue(nil, tz: ny) == nil, "reminder with no due date")

// calendar agenda
let wk = weekDays(from: now, tz: ny)
check(wk.count == 7 && wk[0] == "2026-11-19" && wk[6] == "2026-11-25", "week strip starts today and runs seven days (got \(wk.first ?? "") to \(wk.last ?? ""))")
check(localDay("2026-12-05T04:59:59Z", tz: ny) == "2026-12-04", "date only due belongs to the local day before its UTC date")
let evs = [EventItem(title: "Class", start: "2026-11-19T16:00:00Z", end: "2026-11-19T17:15:00Z", allDay: false),
           EventItem(title: "Holiday", start: "2026-11-19T05:00:00Z", end: "2026-11-20T05:00:00Z", allDay: true),
           EventItem(title: "Dinner", start: "2026-11-19T23:30:00Z", end: "2026-11-20T00:30:00Z", allDay: false)]
let tks = [RankedTask(id: 4, rank: 1, title: "OA", dueAt: "2026-11-19T20:00:00Z", source: "obsidian", reasons: [], atRisk: false, needsReview: false),
           RankedTask(id: 9, rank: 2, title: "Project", dueAt: "2026-11-20T04:59:59Z", source: "icollege", reasons: [], atRisk: false, needsReview: false),
           RankedTask(id: 7, rank: 3, title: "Other day", dueAt: "2026-11-22T20:00:00Z", source: "obsidian", reasons: [], atRisk: false, needsReview: false)]
let ag = buildAgenda(day: "2026-11-19", events: evs, tasks: tks, firstTaskId: 4, tz: ny)
check(ag.allDay.map { $0.title } == ["Holiday", "Project"], "all day holds all day events and date only tasks (got \(ag.allDay.map { $0.title }))")
check(ag.morning.map { $0.title } == ["Class"] && ag.morning[0].timeText == "11:00 am to 12:15 pm", "morning event with a time range (got \(ag.morning.map { $0.timeText }))")
check(ag.afternoon.map { $0.title } == ["OA"] && ag.afternoon[0].isTask && ag.afternoon[0].isFirst, "afternoon task is marked first")
check(ag.evening.map { $0.title } == ["Dinner"], "evening event")
check(!ag.allDay.contains { $0.title == "Other day" } && !ag.afternoon.contains { $0.title == "Other day" }, "tasks from another day are left out")
check(buildAgenda(day: "2026-11-21", events: [], tasks: tks, firstTaskId: nil, tz: ny).isEmpty, "empty day is empty")

// digest
let digestJSON = """
{"date":"2026-11-19","generated_at":"2026-11-19T21:00:00Z","mantra":"Keep pushing.","vision":"FAANG next summer.",
 "why":{"date":"2026-11-18","text":"Because I am tired of almost."},
 "deadlines":[{"id":4,"title":"OA","due_at":"2026-12-02T22:17:00Z","due_local":"Wed Dec 2 at 5:17 PM"}],
 "overflow":3,"notes":["google calendar is out of date"]}
"""
let dg = try! makeDecoder().decode(Digest.self, from: Data(digestJSON.utf8))
check(dg.deadlines[0].dueLocal == "Wed Dec 2 at 5:17 PM" && dg.overflow == 3 && dg.why?.date == "2026-11-18", "decodes the digest")
let bare = """
{"date":"2026-11-19","generated_at":null,"mantra":null,"vision":null,"why":null,"deadlines":[],"overflow":0,"notes":[]}
"""
let dg2 = try! makeDecoder().decode(Digest.self, from: Data(bare.utf8))
check(dg2.mantra == nil && dg2.why == nil && dg2.deadlines.isEmpty, "decodes an empty digest with null lines")

print(failures == 0 ? "all checks passed" : "\(failures) check(s) failed")
exit(failures == 0 ? 0 : 1)
