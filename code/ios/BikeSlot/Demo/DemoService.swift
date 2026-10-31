import Foundation

/// Built-in sample shelters so the app runs without a backend. Every few seconds
/// a random slot is taken or freed, so the UI has live changes to show.
/// Refresh the data with code/ios/refresh-demo.sh.
actor DemoService: AreaService {
    static let shared = DemoService()

    private var details: [AreaDetail]
    private var lastStep = Date()
    private static let stepSeconds = 4.0

    init() {
        let url = Bundle.main.url(forResource: "demo-areas", withExtension: "json")
        let data = url.flatMap { try? Data(contentsOf: $0) } ?? Data("[]".utf8)
        let loaded = (try? APIClient.decoder.decode([AreaDetail].self, from: data)) ?? []
        details = loaded.map { $0.with(slots: $0.slots, at: Date()) }
    }

    func areas() async throws -> [AreaSummary] {
        advance()
        return details.map(\.summary)
    }

    func area(_ id: String) async throws -> AreaDetail {
        advance()
        guard let detail = details.first(where: { $0.summary.id == id }) else { throw URLError(.fileDoesNotExist) }
        return detail
    }

    private func advance() {
        let steps = Int(Date().timeIntervalSince(lastStep) / Self.stepSeconds)
        guard steps > 0, !details.isEmpty else { return }
        lastStep.addTimeInterval(Double(steps) * Self.stepSeconds)
        for _ in 0..<min(steps, 10) {
            let area = Int.random(in: details.indices)
            var slots = details[area].slots
            guard let index = slots.indices.randomElement() else { continue }
            let slot = slots[index]
            slots[index] = Slot(id: slot.id, label: slot.label, occupied: !slot.occupied)
            details[area] = details[area].with(slots: slots, at: Date())
        }
    }
}

private extension AreaDetail {
    func with(slots: [Slot], at date: Date) -> AreaDetail {
        let old = summary
        let occupied = slots.filter(\.occupied).count
        let now = date.timeIntervalSince1970
        let summary = AreaSummary(id: old.id, name: old.name, kind: old.kind, center: old.center,
                                  polygon: old.polygon, capacity: slots.count, occupied: occupied,
                                  free: slots.count - occupied, updatedAt: now, checkedAt: now,
                                  cameraTime: date.formatted(.dateTime.hour(.twoDigits(amPM: .omitted)).minute(.twoDigits)),
                                  analyzer: old.analyzer, modelUrl: old.modelUrl)
        return AreaDetail(summary: summary, slots: slots, personPresent: false,
                          framesAnalyzed: framesAnalyzed + 1, framesSkipped: framesSkipped)
    }
}
