import Foundation

/// Everything the app needs from a backend. The contract is documented in
/// documentation/api/ (generated from code/backend/schemas.py).
protocol AreaService: Sendable {
    func areas() async throws -> [AreaSummary]
    func area(_ id: String) async throws -> AreaDetail
    /// Local file URL of a USDZ model, given the server path or absolute URL from `modelUrl`.
    func modelFile(_ path: String) async throws -> URL
}

enum Backend {
    /// The live backend, or the built-in demo data when `demoMode` is on
    /// (Settings, or the launch argument `-demoMode YES`).
    static var current: any AreaService {
        UserDefaults.standard.bool(forKey: "demoMode") ? DemoService.shared : APIClient()
    }
}

/// Talks to the Find my Bike Slot backend. The base URL can be changed in the app.
struct APIClient: AreaService {
    /// Debug builds carry the address of the Mac that built them (set in project.yml),
    /// so a phone finds the backend on that Mac without typing an IP.
    static let defaultURL = Bundle.main.url(forResource: "backend-url", withExtension: "txt")
        .flatMap { try? String(contentsOf: $0, encoding: .utf8) }?
        .trimmingCharacters(in: .whitespacesAndNewlines) ?? "http://localhost:8000"

    static var baseURL: URL {
        let stored = UserDefaults.standard.string(forKey: "backendURL") ?? defaultURL
        return URL(string: stored) ?? URL(string: defaultURL)!
    }

    static let decoder: JSONDecoder = {
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
        let (data, response) = try await URLSession.shared.data(from: Self.url(path))
        try Self.check(response)
        try data.write(to: local, options: .atomic)
        Self.downloaded.insert(path)
        return local
    }

    nonisolated(unsafe) private static var downloaded: Set<String> = []

    /// Server paths are relative to the backend; absolute URLs (e.g. a CDN) are used as they are.
    private static func url(_ path: String) -> URL {
        if let url = URL(string: path), url.scheme != nil { return url }
        return baseURL.appendingPathComponent(path)
    }

    private func get<T: Decodable>(_ path: String) async throws -> T {
        let (data, response) = try await URLSession.shared.data(from: Self.url(path))
        try Self.check(response)
        return try Self.decoder.decode(T.self, from: data)
    }

    private static func check(_ response: URLResponse) throws {
        if let http = response as? HTTPURLResponse, !(200..<300).contains(http.statusCode) {
            throw URLError(.badServerResponse)
        }
    }
}
