import CoreLocation
import RealityKit
import SwiftUI

/// A diorama of the real surroundings: a square cut of the site around the opened shelter, with
/// the buildings, streets and trees from OpenStreetMap (Site/south-bend.json, written by
/// code/scene-generator/site_context.py) and every shelter at its measured position.
@MainActor
final class SiteScene {
    let root = Entity()
    private var shelters: [String: AreaScene] = [:]
    private var badges: [String: Badge] = [:]

    /// Floating "A · 7 free" sign above a shelter, redrawn when its count changes.
    private struct Badge {
        let entity: Entity
        let letter: String
        let focused: Bool
        var free: Int
    }

    /// Half the side of the diorama in metres; enough for the shelters' corner and the street.
    private static let halfSize: CGFloat = 22

    static func load(around area: AreaSummary, with areas: [AreaSummary]) async throws -> SiteScene {
        let site = try JSONDecoder().decode(SiteContext.self, from: Data(contentsOf: try siteFile()))
        var shelters: [(AreaSummary, AreaScene)] = []
        for other in areas.contains(area) ? areas : areas + [area] {
            shelters.append((other, try await AreaScene.load(other)))
        }
        return SiteScene(site: site, focus: area, shelters: shelters)
    }

    private static func siteFile() throws -> URL {
        guard let url = Bundle.main.url(forResource: "south-bend", withExtension: "json") else {
            throw URLError(.fileDoesNotExist)
        }
        return url
    }

    private init(site: SiteContext, focus: AreaSummary, shelters: [(AreaSummary, AreaScene)]) {
        let centre = site.local(focus.coordinate)
        let world = Entity()
        // Everything is built in metres around the opened shelter, then turned so its open
        // front faces the camera.
        world.orientation = simd_quatf(angle: -Self.heading(of: focus), axis: [0, 1, 0])
        root.addChild(world)

        let clip = Path(CGRect(x: -Self.halfSize, y: -Self.halfSize, width: 2 * Self.halfSize, height: 2 * Self.halfSize))
        let shift = { (point: CGPoint) in CGPoint(x: point.x - centre.x, y: point.y - centre.y) }

        // Base plate: pavement on top of a darker cut edge.
        let side = Float(2 * Self.halfSize)
        let base = ModelEntity(mesh: .generateBox(width: side, height: 0.8, depth: side),
                               materials: [Style.edge])
        base.position.y = -0.41
        world.addChild(base)
        let pavement = ModelEntity(mesh: .generatePlane(width: side, depth: side), materials: [Style.pavement])
        world.addChild(pavement)

        // Streets as one rectangle per segment plus a disc at every bend: a stroked SwiftUI path
        // overlaps itself at the joins, which the extrusion cannot fill.
        for road in site.roads {
            let points = road.line.map(shift)
            for (a, b) in zip(points, points.dropFirst()) {
                add(Self.slab(Self.strip(from: a, to: b, width: road.width).intersection(clip),
                              bottom: 0, height: 0.04, material: Style.asphalt), to: world)
                let length = hypot(b.x - a.x, b.y - a.y)
                for start in stride(from: 1.5, to: length - 3, by: 7.0) {
                    let from = CGPoint(x: a.x + (b.x - a.x) * start / length, y: a.y + (b.y - a.y) * start / length)
                    let to = CGPoint(x: a.x + (b.x - a.x) * (start + 3) / length, y: a.y + (b.y - a.y) * (start + 3) / length)
                    add(Self.slab(Self.strip(from: from, to: to, width: 0.15).intersection(clip),
                                  bottom: 0.04, height: 0.005, material: Style.marking), to: world)
                }
            }
            for bend in points.dropFirst().dropLast()
            where abs(bend.x) < Self.halfSize - road.width / 2 && abs(bend.y) < Self.halfSize - road.width / 2 {
                let disc = ModelEntity(mesh: .generateCylinder(height: 0.04, radius: Float(road.width / 2)),
                                       materials: [Style.asphalt])
                disc.position = [Float(bend.x), 0.02, -Float(bend.y)]
                world.addChild(disc)
            }
        }

        for building in site.buildings {
            let outline = Path { $0.addLines(building.outline.map(shift)); $0.closeSubpath() }.intersection(clip)
            add(Self.building(outline, floors: building.floors, floorHeight: site.floorHeight,
                              silver: building.style == "silver"), to: world)
        }

        for (index, point) in site.trees.map(shift).enumerated()
        where abs(point.x) < Self.halfSize - 1.5 && abs(point.y) < Self.halfSize - 1.5 {
            let tree = Self.tree(scale: 0.85 + Float(index % 3) * 0.12)
            tree.position = [Float(point.x), 0, -Float(point.y)]
            world.addChild(tree)
        }

        for (area, shelter) in shelters {
            let spot = shift(site.local(area.coordinate))
            let holder = Entity()
            holder.position = [Float(spot.x), 0, -Float(spot.y)]
            holder.orientation = simd_quatf(angle: Self.heading(of: area), axis: [0, 1, 0])
            // The measured position is the rack, not the middle of the model.
            shelter.root.position = -shelter.rackCentre
            holder.addChild(shelter.root)
            world.addChild(holder)
            self.shelters[area.id] = shelter

            let focused = area.id == focus.id
            if focused {
                holder.addChild(Self.highlight(under: shelter.root, in: holder))
            }
            let stem = ModelEntity(mesh: .generateCylinder(height: 0.9, radius: 0.025), materials: [Style.stem])
            stem.position.y = 2.75
            holder.addChild(stem)
            let sign = Entity()
            sign.position.y = 3.55
            sign.components.set(BillboardComponent())
            holder.addChild(sign)
            let letter = area.name.components(separatedBy: "·").first?
                .replacingOccurrences(of: "Shelter", with: "").trimmingCharacters(in: .whitespaces) ?? ""
            let badge = Badge(entity: sign, letter: letter, focused: focused, free: area.free)
            Self.draw(badge)
            badges[area.id] = badge
        }

        // Start in front of the opened shelter, above roof height, with its building behind it
        // and the street in the foreground.
        let camera = PerspectiveCamera()
        camera.camera.fieldOfViewOrientation = .horizontal
        camera.camera.fieldOfViewInDegrees = 60
        camera.look(at: [0, 1, -1], from: [11, 17, 23], relativeTo: nil)
        root.addChild(camera)

        // Low afternoon sun from the south-west, so the facades and racks cast long shadows.
        let sun = DirectionalLight()
        sun.light.intensity = 3800
        sun.shadow = DirectionalLightComponent.Shadow(maximumDistance: 70, depthBias: 3)
        sun.look(at: .zero, from: [-18, 26, 22], relativeTo: nil)
        world.addChild(sun)
    }

    func apply(_ details: [String: AreaDetail]) {
        for (id, shelter) in shelters {
            guard let detail = details[id] else { continue }
            shelter.apply(detail.slots)
            let free = detail.slots.filter { !$0.occupied }.count
            if var badge = badges[id], badge.free != free {
                badge.free = free
                Self.draw(badge)
                badges[id] = badge
            }
        }
    }

    private static func draw(_ badge: Badge) {
        badge.entity.children.removeAll()
        let mesh = MeshResource.generateText("\(badge.letter) · \(badge.free) free", extrusionDepth: 0.01,
                                             font: .systemFont(ofSize: 0.7, weight: .bold))
        let size = mesh.bounds.extents
        let height = size.y + 0.4
        let plate = ModelEntity(mesh: .generatePlane(width: size.x + 1.3, height: height, cornerRadius: height / 2),
                                materials: [UnlitMaterial(color: UIColor(badge.free == 0 ? Brand.red : Brand.blue))])
        let label = ModelEntity(mesh: mesh, materials: [UnlitMaterial(color: .white)])
        label.position = [-mesh.bounds.center.x, -mesh.bounds.center.y, 0.02]
        badge.entity.addChild(plate)
        badge.entity.addChild(label)
        badge.entity.scale = .init(repeating: badge.focused ? 1.15 : 0.85)
    }

    /// Soft blue pad on the ground under the opened shelter, so it stands out from its neighbours.
    private static func highlight(under shelter: Entity, in holder: Entity) -> Entity {
        let bounds = shelter.visualBounds(relativeTo: holder)
        var material = UnlitMaterial(color: UIColor(Brand.blue))
        material.blending = .transparent(opacity: 0.3)
        let pad = ModelEntity(mesh: .generatePlane(width: bounds.extents.x + 1.4, depth: bounds.extents.z + 1.4,
                                                   cornerRadius: 0.6), materials: [material])
        pad.position = [bounds.center.x, 0.045, bounds.center.z]
        return pad
    }

    private func add(_ entity: Entity?, to parent: Entity) {
        if let entity { parent.addChild(entity) }
    }

    /// Direction of the shelter's length axis, from its outline: the first edge runs along the
    /// rack (backend `footprint`), so the model's x axis turns onto it.
    private static func heading(of area: AreaSummary) -> Float {
        guard area.polygon.count >= 2 else { return 0 }
        let (a, b) = (area.polygon[0], area.polygon[1])
        let east = (b[1] - a[1]) * cos(a[0] * .pi / 180)
        let north = b[0] - a[0]
        return Float(atan2(north, east))
    }

    /// Facade in ribbon-window bands, one per floor, with a flat roof on top.
    private static func building(_ outline: Path, floors: Int, floorHeight: Float, silver: Bool) -> Entity? {
        guard !outline.isEmpty else { return nil }
        let entity = Entity()
        let wall = floorHeight * 0.62
        for floor in 0..<floors {
            let level = Float(floor) * floorHeight
            if let band = slab(outline, bottom: level, height: wall, material: silver ? Style.silver : Style.plaster) {
                entity.addChild(band)
            }
            if let glass = slab(outline, bottom: level + wall, height: floorHeight - wall, material: Style.glass) {
                entity.addChild(glass)
            }
        }
        if let roof = slab(outline, bottom: Float(floors) * floorHeight, height: 0.4, material: Style.roof) {
            entity.addChild(roof)
        }
        return entity
    }

    /// A flat shape (x east, y north, in metres) pulled up from `bottom` by `height`.
    private static func slab(_ shape: Path, bottom: Float, height: Float, material: any RealityKit.Material) -> ModelEntity? {
        guard !shape.isEmpty else { return nil }
        var options = MeshResource.ShapeExtrusionOptions()
        options.extrusionMethod = .linear(depth: height)
        guard let mesh = try? MeshResource(extruding: shape, extrusionOptions: options) else { return nil }
        let entity = ModelEntity(mesh: mesh, materials: [material])
        // The extrusion is centred on z; standing it up turns that z into height, so north
        // points away from the camera and the bottom face lands on `bottom`.
        entity.orientation = simd_quatf(angle: -.pi / 2, axis: [1, 0, 0])
        entity.position.y = bottom - mesh.bounds.min.z
        return entity
    }

    /// A rectangle `width` wide centred on the line from `a` to `b`.
    private static func strip(from a: CGPoint, to b: CGPoint, width: CGFloat) -> Path {
        let length = max(hypot(b.x - a.x, b.y - a.y), 0.001)
        let side = CGPoint(x: -(b.y - a.y) / length * width / 2, y: (b.x - a.x) / length * width / 2)
        return Path {
            $0.addLines([CGPoint(x: a.x + side.x, y: a.y + side.y), CGPoint(x: b.x + side.x, y: b.y + side.y),
                         CGPoint(x: b.x - side.x, y: b.y - side.y), CGPoint(x: a.x - side.x, y: a.y - side.y)])
            $0.closeSubpath()
        }
    }

    private static func tree(scale: Float) -> Entity {
        let tree = Entity()
        let trunk = ModelEntity(mesh: .generateCylinder(height: 2.4, radius: 0.13), materials: [Style.bark])
        trunk.position.y = 1.2
        tree.addChild(trunk)
        for (offset, radius) in [(SIMD3<Float>(0, 3.1, 0), Float(1.5)), ([0.5, 3.9, 0.3], 1.05), ([-0.45, 3.7, -0.35], 1.0)] {
            let crown = ModelEntity(mesh: .generateSphere(radius: radius), materials: [Style.leaves])
            crown.position = offset
            tree.addChild(crown)
        }
        tree.scale = .init(repeating: scale)
        return tree
    }

    private enum Style {
        static let pavement = SimpleMaterial(color: UIColor(white: 0.84, alpha: 1), roughness: 0.95, isMetallic: false)
        static let edge = SimpleMaterial(color: UIColor(white: 0.42, alpha: 1), roughness: 0.9, isMetallic: false)
        // Stroked street outlines can wind either way; drawing both sides keeps their tops visible.
        static let asphalt: SimpleMaterial = {
            var material = SimpleMaterial(color: UIColor(white: 0.36, alpha: 1), roughness: 0.9, isMetallic: false)
            material.faceCulling = .none
            return material
        }()
        static let marking: UnlitMaterial = {
            var material = UnlitMaterial(color: UIColor(white: 0.97, alpha: 1))
            material.faceCulling = .none
            return material
        }()
        static let stem = UnlitMaterial(color: UIColor(white: 0.97, alpha: 1))
        static let silver = SimpleMaterial(color: UIColor(red: 0.80, green: 0.82, blue: 0.86, alpha: 1),
                                           roughness: 0.45, isMetallic: false)
        static let plaster = SimpleMaterial(color: UIColor(white: 0.95, alpha: 1), roughness: 0.8, isMetallic: false)
        static let glass = SimpleMaterial(color: UIColor(red: 0.27, green: 0.36, blue: 0.46, alpha: 1),
                                          roughness: 0.15, isMetallic: false)
        static let roof = SimpleMaterial(color: UIColor(white: 0.66, alpha: 1), roughness: 0.9, isMetallic: false)
        static let bark = SimpleMaterial(color: UIColor(red: 0.42, green: 0.31, blue: 0.22, alpha: 1),
                                         roughness: 0.9, isMetallic: false)
        static let leaves = SimpleMaterial(color: UIColor(red: 0.36, green: 0.60, blue: 0.32, alpha: 1),
                                           roughness: 0.85, isMetallic: false)
    }
}

/// Site/south-bend.json: local metres, x east and y north of `origin`.
struct SiteContext: Decodable {
    struct Building: Decodable {
        let outline: [CGPoint]
        let floors: Int
        let style: String
    }

    struct Road: Decodable {
        let line: [CGPoint]
        let width: CGFloat
    }

    let origin: [Double]
    let floorHeight: Float
    let buildings: [Building]
    let roads: [Road]
    let trees: [CGPoint]

    private enum CodingKeys: String, CodingKey {
        case origin, buildings, roads, trees
        case floorHeight = "floor_height"
    }

    func local(_ coordinate: CLLocationCoordinate2D) -> CGPoint {
        CGPoint(x: (coordinate.longitude - origin[1]) * 111_320 * cos(origin[0] * .pi / 180),
                y: (coordinate.latitude - origin[0]) * 111_320)
    }
}
