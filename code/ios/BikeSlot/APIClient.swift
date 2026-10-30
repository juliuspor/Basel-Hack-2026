import Foundation

/// Talks to the Find my Bike Slot backend. The base URL can be changed in the app.
struct APIClient {
    static let defaultURL = "http://localhost:8000"

    static var baseURL: URL {
        let stored = UserDefaults.standard.string(forKey: "backendURL") ?? defaultURL
        return URL(string: stored) ?? URL(string: defaultURL)!
    }

    private static let decoder: JSONDecoder = {
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        return decoder
    }()

    func areas() async throws -> [AreaSummary] {
        try await get("/areas")
    }

    func area(_ id: String) async throws -> AreaDetail {
        try await get("/areas/\(id)")
    }

    /// Downloads a USDZ model once per launch and returns its local file URL.
    func modelFile(_ path: String) async throws -> URL {
        let local = FileManager.default.temporaryDirectory.appendingPathComponent((path as NSString).lastPathComponent)
        if Self.downloaded.contains(path), FileManager.default.fileExists(atPath: local.path) {
            return local
        }
        let (data, response) = try await URLSession.shared.data(from: Self.baseURL.appendingPathComponent(path))
        try Self.check(response)
        try data.write(to: local, options: .atomic)
        Self.downloaded.insert(path)
        return local
    }

    nonisolated(unsafe) private static var downloaded: Set<String> = []

    private func get<T: Decodable>(_ path: String) async throws -> T {
        let (data, response) = try await URLSession.shared.data(from: Self.baseURL.appendingPathComponent(path))
        try Self.check(response)
        return try Self.decoder.decode(T.self, from: data)
    }

    private static func check(_ response: URLResponse) throws {
        if let http = response as? HTTPURLResponse, !(200..<300).contains(http.statusCode) {
            throw URLError(.badServerResponse)
        }
    }
}
