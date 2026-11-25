import Foundation

// Shapes of the backend JSON (decoded with convertFromSnakeCase).

struct Today: Codable, Equatable {
    var date: String
    var timezone: String
    var topTask: TopTask?
    var ranked: [RankedTask]
    var events: [EventItem]
    var explanation: Explanation
    var warnings: [Warning]
    var needsReviewCount: Int
    var doneToday: Int?  // optional so an older agent still decodes
}

struct TopTask: Codable, Equatable {
    var id: Int
    var title: String
    var dueAt: String?
    var reasons: [String]
    var atRisk: Bool
    var suggestedBlock: TimeBlock?
}

struct TimeBlock: Codable, Equatable {
    var start: String
    var end: String
}

struct RankedTask: Codable, Equatable, Identifiable {
    var id: Int
    var rank: Int
    var title: String
    var dueAt: String?
    var source: String
    var reasons: [String]
    var atRisk: Bool
    var needsReview: Bool
}

struct EventItem: Codable, Equatable, Identifiable {
    var id: Int
    var source: String  // "manual" is editable in the app, anything else is read only here
    var title: String
    var start: String
    var end: String
    var allDay: Bool
}

struct Explanation: Codable, Equatable {
    var text: String
    var source: String
}

struct Warning: Codable, Equatable, Identifiable {
    var code: String
    var source: String?
    var detail: String?
    var id: String { code + (source ?? "") }
}

struct Goal: Codable, Equatable {
    var date: String
    var text: String?
}

struct Txn: Codable, Equatable, Identifiable {
    var id: String
    var date: String
    var merchant: String
    var amount: String
    var direction: String
    var bank: String
    var category: String?
    var pending: Bool

    enum CodingKeys: String, CodingKey { case id, date, merchant, amount, direction, bank, category, pending }

    init(id: String, date: String, merchant: String, amount: String, direction: String, bank: String,
         category: String?, pending: Bool) {
        self.id = id; self.date = date; self.merchant = merchant; self.amount = amount
        self.direction = direction; self.bank = bank; self.category = category; self.pending = pending
    }

    init(from d: Decoder) throws {
        let c = try d.container(keyedBy: CodingKeys.self)
        // real rows have an integer id, demo rows a string id
        if let s = try? c.decode(String.self, forKey: .id) { id = s } else { id = String(try c.decode(Int.self, forKey: .id)) }
        date = try c.decode(String.self, forKey: .date)
        merchant = try c.decode(String.self, forKey: .merchant)
        amount = try c.decode(String.self, forKey: .amount)
        direction = try c.decode(String.self, forKey: .direction)
        bank = try c.decode(String.self, forKey: .bank)
        category = try c.decodeIfPresent(String.self, forKey: .category)
        pending = try c.decode(Bool.self, forKey: .pending)
    }
}

struct TxnPage: Codable, Equatable {
    var demo: Bool
    var note: String?
    var nextCursor: String?
    var transactions: [Txn]
}

struct BankAccountInfo: Codable, Equatable, Identifiable {
    var id: Int
    var itemId: Int
    var bank: String
    var nickname: String
    var mask: String
    var enabled: Bool
    var kind: String?  // depository, credit, loan, investment (optional so an older agent decodes)
    var subtype: String?
    var balanceCents: Int?
}

struct Banks: Codable, Equatable {
    var chip: String
    var accounts: [BankAccountInfo]
}

func makeDecoder() -> JSONDecoder {
    let d = JSONDecoder()
    d.keyDecodingStrategy = .convertFromSnakeCase
    return d
}

// The daily brief: GET /digest

struct DigestWhy: Codable, Equatable {
    var date: String
    var text: String
}

struct PlanItem: Codable, Equatable, Identifiable {
    var text: String
    var done: Bool
    var id: String { text }
}

struct DigestPlan: Codable, Equatable {
    var logged: Bool
    var items: [PlanItem]
}

struct DigestDeadline: Codable, Equatable, Identifiable {
    var id: Int
    var title: String
    var dueAt: String?
    var dueLocal: String?
}

struct Digest: Codable, Equatable {
    var date: String
    var generatedAt: String?
    var mantra: String?
    var vision: String?
    var why: DigestWhy?
    var identity: [String]?  // optional so an older agent still decodes
    var plan: DigestPlan?
    var deadlines: [DigestDeadline]
    var overflow: Int
    var overflowAfter: String?
    var notes: [String]
}

// Money overview: GET /money/summary and /budgets

struct MonthTotal: Codable, Equatable, Identifiable {
    var month: String
    var incomeCents: Int
    var spendCents: Int
    var id: String { month }
}

struct ThisMonth: Codable, Equatable {
    var month: String
    var incomeCents: Int
    var spendCents: Int
    var netCents: Int
}

struct CategorySpend: Codable, Equatable, Identifiable {
    var category: String
    var spendCents: Int
    var id: String { category }
}

struct Holdings: Codable, Equatable {
    var cashCents: Int
    var savingsCents: Int
    var investedCents: Int
    var creditOwedCents: Int
    var loansOwedCents: Int
    var netCents: Int
}

struct DailyPoint: Codable, Equatable, Identifiable {
    var date: String
    var cumulativeSpendCents: Int
    var id: String { date }
}

struct MoneySummary: Codable, Equatable {
    var months: [MonthTotal]
    var thisMonth: ThisMonth
    var categories: [CategorySpend]
    var holdings: Holdings
    var daily: [DailyPoint]
}

struct RecurringItem: Codable, Equatable, Identifiable {
    var merchant: String
    var amountCents: Int
    var category: String?
    var lastDate: String
    var nextDate: String
    var paidThisMonth: Bool
    var id: String { merchant }
}

struct Recurring: Codable, Equatable {
    var items: [RecurringItem]
    var monthlyCents: Int
}

struct BudgetGoal: Codable, Equatable, Identifiable {
    var category: String
    var limitCents: Int
    var spentCents: Int
    var id: String { category }
}

// Spec 16 goals tab: GET /money/goals

struct MoneyGoal: Codable, Equatable, Identifiable {
    var id: String
    var name: String
    var kind: String
    var accountId: Int?
    var targetCents: Int
    var currentCents: Int
    var fraction: Double
    var met: Bool
    var start: String?
    var due: String
    var floorCents: Int?
}

struct GoalSeason: Codable, Equatable, Identifiable {
    var due: String
    var goals: [MoneyGoal]
    var id: String { due }
}

struct MoneyGoals: Codable, Equatable {
    var stretch: MoneyGoal?
    var seasons: [GoalSeason]
}

// Spec 18: check-in and goals

struct Checkin: Codable, Equatable {
    var obstacle: String?
    var ifThen: String?
    var topTaskTitle: String?
    var didTop: Bool?
    var whyNot: String?
    var letGo: String?
}

struct YesterdayAnswer: Codable, Equatable {
    var topTaskTitle: String?
    var didTop: Bool?
    var whyNot: String?
}

struct SayDo: Codable, Equatable {
    var kept: Int
    var of: Int
}

struct CheckinDay: Codable, Equatable {
    var date: String
    var today: Checkin
    var yesterday: YesterdayAnswer
    var sayDo: SayDo
}

/// The nightly wrap: what the agent already knows, plus my own bullets once logged.
struct Eod: Codable, Equatable {
    var date: String
    var answered: Bool
    var bullets: String?
    var tasksDoneToday: Int
    var goal: String?
}

struct GoalItem: Codable, Equatable, Identifiable {
    var id: Int
    var name: String
    var kind: String  // input, outcome
    var unit: String
    var target: Int
    var current: Int?  // outcome
    var today: Int?  // input
    var last7: [Int]?
    var hit7: Int?
    var missedTwice: Bool?
    var total30: Int?
    var isInput: Bool { kind == "input" }
}

// Spec 19: the Agent screen

struct AskSource: Codable, Equatable, Identifiable {
    var path: String
    var heading: String
    var excerpt: String
    var id: String { path + "#" + heading }
}

struct AskReply: Codable, Equatable {
    var answer: String
    var sources: [AskSource]
    var usedLlm: Bool
    var route: String?
}

struct CourseAssignment: Codable, Equatable, Identifiable {
    var id: Int
    var title: String
    var dueAt: String
}

struct Course: Codable, Equatable, Identifiable {
    var course: String
    var assignments: [CourseAssignment]
    var id: String { course }
}

// Spec 13: a homework session as GET /agent/sessions/{id} returns it

struct AgentStepLine: Codable, Equatable, Identifiable {
    var at: String
    var kind: String
    var summary: String
    var id: String { at + kind + summary }
}

struct PendingApproval: Codable, Equatable {
    var id: Int
    var label: String
    var expiresAt: String
}

struct SessionUsage: Codable, Equatable {
    var steps: Int
    var inputTokens: Int
    var outputTokens: Int
}

struct HomeworkSession: Codable, Equatable, Identifiable {
    var id: Int
    var title: String
    var site: String
    var status: String  // starting, running, paused, takeover, needs_approval, ended
    var reason: String?
    var steps: [AgentStepLine]
    var approval: PendingApproval?
    var liveViewUrl: String?
    var usage: SessionUsage
    var isActive: Bool { status != "ended" }
}
