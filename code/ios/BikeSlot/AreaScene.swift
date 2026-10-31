import RealityKit
import UIKit

/// The 3D model of one area plus a status marker and a hidden bike on every slot.
/// `SiteScene` places it on the site; camera and light live there.
@MainActor
final class AreaScene {
    let root = Entity()
    /// Middle of the rack relative to `root`, at ground level: the point slots.json measured.
    private(set) var rackCentre: SIMD3<Float> = .zero
    private var bikes: [String: Entity] = [:]
    private var markers: [String: ModelEntity] = [:]

    private static let freeMaterial = UnlitMaterial(color: UIColor(Brand.blue))
    private static let takenMaterial = UnlitMaterial(color: UIColor(Brand.red))

    static func load(_ area: AreaSummary) async throws -> AreaScene {
        let api = Backend.current
        let model = try await Entity(contentsOf: try await api.modelFile(area.modelUrl))
        let bikeFile = try await Entity(contentsOf: try await api.modelFile("/models/bike.usdz"))
        guard let bike = bikeFile.findEntity(named: "bike") else { throw URLError(.cannotDecodeContentData) }
        return AreaScene(model: model, bike: bike)
    }

    private init(model: Entity, bike: Entity) {
        let bounds = model.visualBounds(relativeTo: nil)
        model.position = [-bounds.center.x, 0, -bounds.center.z]
        root.addChild(model)
        // The site has its own pavement; the model's paving pad would flicker against it.
        model.findEntity(named: "ground")?.isEnabled = false

        let slots = Self.slots(in: model)
        if !slots.isEmpty {
            rackCentre = slots.map { $0.position(relativeTo: root) }.reduce(.zero, +) / Float(slots.count)
            rackCentre.y = 0
        }

        for slot in slots {
            let key = String(slot.name.dropFirst("slot_".count))
            // Slot children use the generator's axes: x along the rack, y towards the rear, z up.
            let marker = ModelEntity(mesh: .generateBox(width: 0.28, height: 0.28, depth: 0.02, cornerRadius: 0.05),
                                     materials: [Self.freeMaterial])
            marker.position = [0, -0.95, 0.01]
            slot.addChild(marker)
            marker.addChild(Self.label(String(Int(key.suffix(2)) ?? 0)))
            markers[key] = marker

            let parked = bike.clone(recursive: true)
            parked.isEnabled = false
            slot.addChild(parked)
            bikes[key] = parked
        }
    }

    func apply(_ slots: [Slot]) {
        for slot in slots {
            bikes[slot.id]?.isEnabled = slot.occupied
            markers[slot.id]?.model?.materials = [slot.occupied ? Self.takenMaterial : Self.freeMaterial]
        }
    }

    /// Slot number lying flat on the marker, readable from the open front.
    private static func label(_ text: String) -> ModelEntity {
        let mesh = MeshResource.generateText(text, extrusionDepth: 0.002,
                                             font: .systemFont(ofSize: 0.16, weight: .bold))
        let entity = ModelEntity(mesh: mesh, materials: [UnlitMaterial(color: .white)])
        entity.position = -mesh.bounds.center + [0, 0, 0.012]
        return entity
    }

    private static func slots(in entity: Entity) -> [Entity] {
        var found = entity.name.hasPrefix("slot_") ? [entity] : []
        for child in entity.children {
            found += slots(in: child)
        }
        return found
    }
}
