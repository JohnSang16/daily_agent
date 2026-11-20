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
 "identity":["I'm a Googler.","Fear is not real."],"plan":{"logged":true,"items":[{"text":"Do the lab (2 pm)","done":false}]},
 "overflow":3,"overflow_after":"Thu Nov 26","notes":["google calendar is out of date"]}
"""
let dg = try! makeDecoder().decode(Digest.self, from: Data(digestJSON.utf8))
check(dg.deadlines[0].dueLocal == "Wed Dec 2 at 5:17 PM" && dg.overflow == 3 && dg.why?.date == "2026-11-18", "decodes the digest")
check(dg.identity == ["I'm a Googler.", "Fear is not real."] && dg.plan?.items[0].text == "Do the lab (2 pm)" && dg.overflowAfter == "Thu Nov 26", "decodes identity, plan and overflow date")
let bare = """
{"date":"2026-11-19","generated_at":null,"mantra":null,"vision":null,"why":null,"deadlines":[],"overflow":0,"notes":[]}
"""
let dg2 = try! makeDecoder().decode(Digest.self, from: Data(bare.utf8))
check(dg2.mantra == nil && dg2.why == nil && dg2.deadlines.isEmpty, "decodes an empty digest with null lines")
check(dg2.identity == nil && dg2.plan == nil, "an older agent without the new fields still decodes")

// money
check(dollars(286100) == "$2,861" && dollars(0) == "$0" && dollars(-5000) == "-$50" && dollars(99) == "$1", "whole dollar formatting (got \(dollars(286100)), \(dollars(-5000)), \(dollars(99)))")
check(monthShort("2026-11") == "nov" && monthLong("2026-02") == "february" && monthShort("") == "", "month names")
check(categoryLabel("FOOD_AND_DRINK") == "food and drink" && categoryLabel("TOTAL") == "all spending", "category labels")
check(centsFromDisplay("+2100.00") == 210000 && centsFromDisplay("12.50") == 1250 && centsFromDisplay("4.5") == 450 && centsFromDisplay("7") == 700, "display amount back to cents")
let acc: [BankAccountInfo] = [
    BankAccountInfo(id: 1, itemId: 1, bank: "Chase", nickname: "Checking", mask: "0001", enabled: true, kind: "depository", subtype: "checking", balanceCents: 100000),
    BankAccountInfo(id: 2, itemId: 1, bank: "Chase", nickname: "Card", mask: "0002", enabled: true, kind: "credit", subtype: "credit card", balanceCents: 30000),
    BankAccountInfo(id: 3, itemId: 2, bank: "Fidelity", nickname: "Brokerage", mask: "0003", enabled: true, kind: "investment", subtype: "brokerage", balanceCents: 500000),
    BankAccountInfo(id: 4, itemId: 2, bank: "Fidelity", nickname: "Off", mask: "0004", enabled: false, kind: "depository", subtype: "savings", balanceCents: 999900)]
let gb = groupBanks(acc)
check(gb.count == 2 && gb[0].bank == "Chase" && gb[0].totalCents == 70000, "bank total is assets minus what is owed (got \(gb[0].totalCents))")
check(gb[1].totalCents == 500000, "a turned off account does not count toward the bank total")
check(accountKindLabel(acc[1]) == "credit card" && accountKindLabel(acc[2]) == "brokerage" && isOwed(acc[1]) && !isOwed(acc[0]), "account kind labels and owed")
let inc = [Txn(id: "1", date: "2026-11-05", merchant: "Pay", amount: "+2100.00", direction: "in", bank: "B", category: "INCOME", pending: false),
           Txn(id: "2", date: "2026-11-01", merchant: "Pay", amount: "+50.50", direction: "in", bank: "B", category: "INCOME", pending: false),
           Txn(id: "3", date: "2026-10-15", merchant: "Pay", amount: "+2000.00", direction: "in", bank: "B", category: "INCOME", pending: false)]
let ib = incomeByMonth(inc)
check(ib.count == 2 && ib[0].month == "2026-11" && ib[0].totalCents == 215050 && ib[1].totalCents == 200000, "income log groups by month with subtotals (got \(ib.map { $0.totalCents }))")
check(goalProgress(spent: 250, limit: 500).fraction == 0.5 && !goalProgress(spent: 250, limit: 500).over, "goal halfway")
check(goalProgress(spent: 900, limit: 500).fraction == 1 && goalProgress(spent: 900, limit: 500).over, "goal over reads full and over")
check(goalProgress(spent: 10, limit: 0).fraction == 0, "goal with no limit")
let sumJSON = """
{"months":[{"month":"2026-10","income_cents":184500,"spend_cents":264900},{"month":"2026-11","income_cents":12400,"spend_cents":286100}],
 "this_month":{"month":"2026-11","income_cents":12400,"spend_cents":286100,"net_cents":-273700},
 "categories":[{"category":"FOOD_AND_DRINK","spend_cents":36000}],
 "holdings":{"cash_cents":24200,"savings_cents":280200,"invested_cents":137000,"credit_owed_cents":21400,"loans_owed_cents":0,"net_cents":420000}}
"""
let ms = try! makeDecoder().decode(MoneySummary.self, from: Data(sumJSON.utf8))
check(ms.months.count == 2 && ms.thisMonth.netCents == -273700 && ms.holdings.investedCents == 137000, "decodes the money summary")
let bg = try! makeDecoder().decode([BudgetGoal].self, from: Data(#"[{"category":"TOTAL","limit_cents":300000,"spent_cents":286100}]"#.utf8))
check(bg[0].limitCents == 300000 && bg[0].id == "TOTAL", "decodes budget goals")
let oldBank = try! makeDecoder().decode(Banks.self, from: Data(#"{"chip":"banks: all","accounts":[{"id":1,"item_id":1,"bank":"B","nickname":"N","mask":"1","enabled":true}]}"#.utf8))
check(oldBank.accounts[0].balanceCents == nil && oldBank.accounts[0].kind == nil, "an older agent without balances still decodes")
let newBank = try! makeDecoder().decode(Banks.self, from: Data(#"{"chip":"banks: all","accounts":[{"id":1,"item_id":1,"bank":"B","nickname":"N","mask":"1","enabled":true,"kind":"credit","subtype":"credit card","balance_cents":30000}]}"#.utf8))
check(newBank.accounts[0].balanceCents == 30000 && newBank.accounts[0].kind == "credit", "decodes balances and kinds")

// settings and warnings
check(normalizedAddress(" 100.1.2.3:8000/ ") == "http://100.1.2.3:8000", "address gets a scheme and loses the trailing slash")
check(normalizedAddress("https://mac.ts.net") == "https://mac.ts.net" && normalizedAddress("") == "", "a full address is left alone")
check(warningLine(Warning(code: "SOURCE_STALE", source: "google_calendar", detail: nil)) == "google calendar is out of date", "stale warning in words")
check(warningLine(Warning(code: "LLM_BUDGET_EXHAUSTED", source: nil, detail: "Daily token budget reached")) == "daily token budget reached", "other warnings are lowercase detail")
check(warningLine(Warning(code: "SOME_NEW_CODE", source: nil, detail: nil)) == "some new code", "an unknown code with no detail reads as words")

// follow through (spec 18)
check(blockLine(TimeBlock(start: "2026-11-19T19:00:00Z", end: "2026-11-19T21:00:00Z"), tz: ny) == "deep work, 2:00 to 4:00 pm", "block line drops the repeated pm (got \(blockLine(TimeBlock(start: "2026-11-19T19:00:00Z", end: "2026-11-19T21:00:00Z"), tz: ny)))")
check(blockLine(TimeBlock(start: "2026-11-19T16:00:00Z", end: "2026-11-19T18:00:00Z"), tz: ny) == "deep work, 11:00 am to 1:00 pm", "block line keeps am when it crosses noon")
check(blockLine(nil, tz: ny) == "", "no block, no line")
check(!checkinDue(parseISO("2026-11-20T01:59:00Z")!, answered: false, tz: ny) && checkinDue(parseISO("2026-11-20T02:00:00Z")!, answered: false, tz: ny), "check-in shows from 9 pm")
check(!checkinDue(parseISO("2026-11-20T03:00:00Z")!, answered: true, tz: ny), "an answered check-in stays hidden")
check(sayDoLine(SayDo(kept: 9, of: 11)) == "kept your word 9 of 11 days" && sayDoLine(SayDo(kept: 0, of: 0)) == "" && sayDoLine(SayDo(kept: 1, of: 1)) == "kept your word 1 of 1 day", "say do line")
let reps = GoalItem(id: 1, name: "leetcode", kind: "input", unit: "problems", target: 2, current: nil, today: 1, last7: [0,1,1,0,0,2,1], hit7: 1, missedTwice: false, total30: 9)
check(repsLine(reps) == "1 of 2 problems", "reps line")
check(identityLine(["a", "b"], turn: 3) == "b" && identityLine(nil, turn: 0) == nil && identityLine([], turn: 1) == nil, "identity line rotates")
let roth = GoalItem(id: 2, name: "Roth IRA", kind: "outcome", unit: "dollars", target: 7500, current: 1450, today: nil, last7: nil, hit7: nil, missedTwice: nil, total30: nil)
check(abs(outcomeFraction(roth) - 0.1933) < 0.001, "outcome fraction")
let ck = try! makeDecoder().decode(CheckinDay.self, from: Data(#"{"date":"2026-11-19","today":{"obstacle":"scrolling","if_then":null,"top_task_title":null,"did_top":null,"why_not":null,"let_go":null},"yesterday":{"top_task_title":"OA","did_top":false,"why_not":"slept in"},"say_do":{"kept":3,"of":4}}"#.utf8))
check(ck.today.obstacle == "scrolling" && ck.yesterday.didTop == false && ck.sayDo.of == 4, "decodes the check-in")
let gl = try! makeDecoder().decode([GoalItem].self, from: Data(#"[{"id":1,"name":"lc","kind":"input","unit":"","target":1,"today":0,"last7":[0,0,0,0,0,0,0],"hit7":0,"missed_twice":true,"total30":0},{"id":2,"name":"Roth","kind":"outcome","unit":"dollars","target":7500,"current":1450}]"#.utf8))
check(gl[0].missedTwice == true && gl[1].current == 1450 && !gl[1].isInput, "decodes both goal kinds")
let td = try! makeDecoder().decode(Today.self, from: Data(todayJSON.utf8))
check(td.doneToday == nil && td.topTask?.suggestedBlock == nil, "an older /today without done_today still decodes")

// agent screen (spec 19)
check(AskContext.all.sources == ["vault", "calendar"] && AskContext.notes.sources == ["vault"] && AskContext.tasks.sources == ["calendar"], "context chip maps to what ask may read")
check(noteName("career/school/os-lecture-notes.md") == "os lecture notes" && noteName("a_b") == "a b", "note names for sources")
check(courseLabel("OPERATING SYSTEMS") == "operating systems" && courseLabel(String(repeating: "A", count: 40)).count == 28, "course chip label")
let ar = try! makeDecoder().decode(AskReply.self, from: Data(#"{"answer":"x","sources":[{"path":"a.md","heading":"H","excerpt":"e"}],"used_llm":true,"route":"vault"}"#.utf8))
check(ar.usedLlm && ar.sources[0].id == "a.md#H", "decodes an ask reply")
let cs = try! makeDecoder().decode([Course].self, from: Data(#"[{"course":"OS","assignments":[{"id":1,"title":"HW 3","due_at":"2026-11-22T04:59:00+00:00"}]}]"#.utf8))
check(cs[0].assignments[0].title == "HW 3" && parseISO(cs[0].assignments[0].dueAt) != nil, "decodes courses and their due dates parse")

// homework sessions (spec 13)
let hs = try! makeDecoder().decode(HomeworkSession.self, from: Data(#"{"id":1,"title":"HW 3","site":"icollege","status":"needs_approval","reason":"clicking submit could hand in work.","steps":[{"at":"2026-11-20T15:00:00+00:00","kind":"click","summary":"clicked next on gastate.view.usg.edu"}],"approval":{"id":4,"label":"Submit","expires_at":"2026-11-20T15:10:00+00:00"},"live_view_url":"https://x","usage":{"steps":3,"input_tokens":3000,"output_tokens":150}}"#.utf8))
check(hs.approval?.label == "Submit" && hs.isActive && hs.usage.steps == 3 && hs.liveViewUrl != nil, "decodes a homework session")
let ended = try! makeDecoder().decode(HomeworkSession.self, from: Data(#"{"id":1,"title":"HW 3","site":"icollege","status":"ended","reason":null,"steps":[],"approval":null,"live_view_url":null,"usage":{"steps":0,"input_tokens":0,"output_tokens":0}}"#.utf8))
check(!ended.isActive && ended.liveViewUrl == nil && sessionStatusLine("takeover") == "you have control", "an ended session has no live view")

print(failures == 0 ? "all checks passed" : "\(failures) check(s) failed")
exit(failures == 0 ? 0 : 1)
