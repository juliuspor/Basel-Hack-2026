import CoreLocation
import SwiftUI

enum Site {
    /// Endress+Hauser campus, Kägenstrasse, Reinach BL.
    static let center = CLLocationCoordinate2D(latitude: 47.48872, longitude: 7.59805)
}

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

    init(summary: AreaSummary, slots: [Slot], personPresent: Bool, framesAnalyzed: Int, framesSkipped: Int) {
        self.summary = summary
        self.slots = slots
        self.personPresent = personPresent
        self.framesAnalyzed = framesAnalyzed
        self.framesSkipped = framesSkipped
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
    /// Any free spot counts as available; the number on the pin says how many.
    case available, full, unknown

    init(free: Int, capacity: Int, known: Bool) {
        if !known || capacity == 0 {
            self = .unknown
        } else {
            self = free == 0 ? .full : .available
        }
    }

    var color: Color {
        switch self {
        case .available: .green
        case .full: .red
        case .unknown: .gray
        }
    }
}
