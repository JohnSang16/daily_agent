import Foundation

enum APIError: Error, Equatable {
    case notConfigured
    case offline
    case http(Int)
}

struct APIClient {
    var baseURL: URL
    var token: String
    var session: URLSession = .shared

    private func request(_ method: String, _ path: String, query: [URLQueryItem] = [], body: Data? = nil) throws -> URLRequest {
        guard var comps = URLComponents(url: baseURL, resolvingAgainstBaseURL: false) else { throw APIError.notConfigured }
        comps.path = path
        comps.queryItems = query.isEmpty ? nil : query
        guard let url = comps.url else { throw APIError.notConfigured }
        var r = URLRequest(url: url, timeoutInterval: 15)
        r.httpMethod = method
        r.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        if let body { r.httpBody = body; r.setValue("application/json", forHTTPHeaderField: "Content-Type") }
        return r
    }

    private func run(_ r: URLRequest) async throws -> Data {
        do {
            let (data, resp) = try await session.data(for: r)
            let code = (resp as? HTTPURLResponse)?.statusCode ?? 0
            guard (200..<300).contains(code) else { throw APIError.http(code) }
            return data
        } catch let e as APIError {
            throw e
        } catch {
            throw APIError.offline  // no route to the Mac: show cached data instead
        }
    }

    func get<T: Decodable>(_ path: String, query: [URLQueryItem] = []) async throws -> T {
        try makeDecoder().decode(T.self, from: try await run(try request("GET", path, query: query)))
    }

    func send(_ method: String, _ path: String, json: [String: Any]? = nil) async throws {
        let body = try json.map { try JSONSerialization.data(withJSONObject: $0) }
        _ = try await run(try request(method, path, body: body))
    }

    func getData(_ path: String) async throws -> Data {
        try await run(try request("GET", path))
    }
}
