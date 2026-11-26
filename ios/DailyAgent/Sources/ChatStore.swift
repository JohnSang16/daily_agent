import Foundation

/// One saved ask chat. The title is its first question, like any LLM chat list.
struct Chat: Codable, Identifiable, Equatable {
    var id = UUID()
    var turns: [ChatTurn] = []
    var updated = Date()
    var title: String { turns.first.map { String($0.question.prefix(60)) } ?? "new chat" }
}

/// Ask chats saved on the phone only, never on the agent (rule 15: the backend keeps no questions).
enum ChatStore {
    private static var file: URL {
        let dir = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir.appendingPathComponent("chats.json")
    }

    static func load() -> [Chat] {
        guard let data = try? Data(contentsOf: file),
              var chats = try? JSONDecoder().decode([Chat].self, from: data) else { return [] }
        // a question still waiting when the app closed will never get its answer
        for c in chats.indices {
            for t in chats[c].turns.indices where chats[c].turns[t].reply == nil { chats[c].turns[t].failed = true }
        }
        return chats.sorted { $0.updated > $1.updated }
    }

    static func save(_ chats: [Chat]) {
        try? JSONEncoder().encode(chats.filter { !$0.turns.isEmpty }).write(to: file, options: .atomic)
    }
}
