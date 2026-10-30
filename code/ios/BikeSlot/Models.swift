import CoreLocation
import SwiftUI

struct AreaSummary: Codable, Identifiable, Hashable {
    let id: String
    let name: String
    let kind: String
    let center: [Double]
    let polygon: [[Double]]
    let capacity: Int
    let occupied: Int
    let free: Int
    let updatedAt: Double?
    let checkedAt: Double?
    let cameraTime: String?
    let analyzer: String
    let modelUrl: String

    var coordinate: CLLocationCoordinate2D {
        CLLocationCoordinate2D(latitude: center[0], longitude: center[1])
    }

    var outline: [CLLocationCoordinate2D] {
        polygon.map { CLLocationCoordinate2D(latitude: $0[0], longitude: $0[1]) }
    }

    var availability: Availability { Availability(free: free, capacity: capacity, known: updatedAt != nil) }

    var checkedDate: Date? { checkedAt.map { Date(timeIntervalSince1970: $0) } }
}

struct Slot: Codable, Identifiable, Hashable {
    let id: String
    let label: Int
    let occupied: Bool
}

struct AreaDetail: Codable {
    let summary: AreaSummary
    let slots: [Slot]
    let personPresent: Bool
    let framesAnalyzed: Int
    let framesSkipped: Int

    private enum CodingKeys: String, CodingKey {
        case slots, personPresent, framesAnalyzed, framesSkipped
    }

    init(from decoder: Decoder) throws {
        summary = try AreaSummary(from: decoder)
        let container = try decoder.container(keyedBy: CodingKeys.self)
        slots = try container.decode([Slot].self, forKey: .slots)
        personPresent = try container.decode(Bool.self, forKey: .personPresent)
        framesAnalyzed = try container.decode(Int.self, forKey: .framesAnalyzed)
        framesSkipped = try container.decode(Int.self, forKey: .framesSkipped)
    }

    func encode(to encoder: Encoder) throws {
        try summary.encode(to: encoder)
    }
}

enum Availability {
    case plenty, few, full, unknown

    init(free: Int, capacity: Int, known: Bool) {
        if !known || capacity == 0 {
            self = .unknown
        } else if free == 0 {
            self = .full
        } else if Double(free) / Double(capacity) < 0.3 {
            self = .few
        } else {
            self = .plenty
        }
    }

    var color: Color {
        switch self {
        case .plenty: .green
        case .few: .orange
        case .full: .red
        case .unknown: .gray
        }
    }
}
