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
}

struct TopTask: Codable, Equatable {
    var id: Int
    var title: String
    var dueAt: String?
    var reasons: [String]
    var atRisk: Bool
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
    var title: String
    var start: String
    var end: String
    var allDay: Bool
    var id: String { start + title }
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
