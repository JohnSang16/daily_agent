import Foundation

/// The last good /today response, so the app still shows something with no connection.
enum Cache {
    private static var file: URL {
        let dir = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir.appendingPathComponent("today-cache.json")
    }

    static func save(_ data: Data) {
        try? data.write(to: file, options: .atomic)
        UserDefaults.standard.set(Date(), forKey: "todayFetchedAt")
    }

    static func load() -> (Today, Date)? {
        guard let data = try? Data(contentsOf: file),
              let t = try? makeDecoder().decode(Today.self, from: data),
              let at = UserDefaults.standard.object(forKey: "todayFetchedAt") as? Date else { return nil }
        return (t, at)
    }
}
