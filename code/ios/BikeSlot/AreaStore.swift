import Foundation
import Observation

/// Polls the backend and holds the latest state for the map and detail screens.
@MainActor
@Observable
final class AreaStore {
    var areas: [AreaSummary] = []
    var details: [String: AreaDetail] = [:]
    var errorMessage: String?

    private var api: any AreaService { Backend.current }

    var totalFree: Int { areas.reduce(0) { $0 + $1.free } }
    var totalCapacity: Int { areas.reduce(0) { $0 + $1.capacity } }

    func pollAreas() async {
        while !Task.isCancelled {
            do {
                areas = try await api.areas()
                errorMessage = nil
            } catch {
                errorMessage = "No backend at \(APIClient.baseURL.host() ?? "?")"
            }
            try? await Task.sleep(for: .seconds(2))
        }
    }

    func pollDetail(_ id: String) async {
        while !Task.isCancelled {
            if let detail = try? await api.area(id) {
                details[id] = detail
            }
            try? await Task.sleep(for: .seconds(1.5))
        }
    }
}
