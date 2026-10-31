import MapKit
import SwiftUI

struct MapScreen: View {
    @Environment(AreaStore.self) private var store
    @State private var path: [AreaSummary] = []
    @State private var showSettings = false
    @State private var search = LocationSearch()
    @State private var destination: Destination?
    @State private var selectedID: AreaSummary.ID?
    @FocusState private var searchFocused: Bool
    @State private var position = Self.camera(at: Site.center, distance: 900)

    private static func camera(at center: CLLocationCoordinate2D, distance: Double) -> MapCameraPosition {
        .camera(MapCamera(centerCoordinate: center, distance: distance, heading: 0, pitch: 0))
    }

    private var selected: AreaSummary? { store.areas.first { $0.id == selectedID } }

    var body: some View {
        NavigationStack(path: $path) {
            // Flat, north-up and pan/zoom only, like a mobility app map.
            Map(position: $position, interactionModes: [.pan, .zoom]) {
                ForEach(store.areas) { area in
                    MapPolygon(coordinates: area.outline)
                        .foregroundStyle(area.availability.color.opacity(0.3))
                        .stroke(area.availability.color, lineWidth: 2)
                    Annotation(area.name, coordinate: area.coordinate, anchor: .bottom) {
                        Button { select(area) } label: { AreaPin(area: area, selected: area.id == selectedID) }
                            .buttonStyle(.plain)
                    }
                    .annotationTitles(.hidden)
                }
                if let destination {
                    Marker(destination.name, systemImage: "building.2.fill", coordinate: destination.coordinate)
                        .tint(.blue)
                }
            }
            .mapStyle(.standard(elevation: .flat, emphasis: .muted, pointsOfInterest: .excludingAll))
            .mapControls {}
            .safeAreaInset(edge: .top) {
                SearchOverlay(search: search, focused: $searchFocused, areas: store.areas,
                              openArea: { area in
                                  searchFocused = false
                                  select(area)
                              },
                              choose: { completion in Task { await go(to: completion) } })
                    .padding(.horizontal, 12)
            }
            .safeAreaInset(edge: .bottom) {
                Group {
                    if let selected {
                        AreaCard(area: selected, distance: destination?.distance(to: selected),
                                 dismiss: { selectedID = nil },
                                 open: { path.append(selected) })
                            .transition(.move(edge: .bottom).combined(with: .opacity))
                    } else {
                        StatusBar(destination: destination, clearDestination: clearDestination,
                                  settings: { showSettings = true })
                            .transition(.opacity)
                    }
                }
                .padding(.horizontal, 12)
                .opacity(searchFocused ? 0 : 1)
                .allowsHitTesting(!searchFocused)
                .animation(.easeOut(duration: 0.15), value: searchFocused)
            }
            // The keyboard covers the bottom controls instead of pushing them, and the map, upwards.
            .ignoresSafeArea(.keyboard)
            .navigationDestination(for: AreaSummary.self) { AreaDetailScreen(area: $0) }
            .toolbar(.hidden, for: .navigationBar)
            .sheet(isPresented: $showSettings) { SettingsSheet() }
        }
        // bikeslot://area/<id> opens an area directly, e.g. from a notification.
        .onOpenURL { url in
            if url.host == "area" { linkedArea = url.lastPathComponent }
        }
        // Launch argument `-openArea <id>` does the same without a confirmation prompt.
        .task { linkedArea = UserDefaults.standard.string(forKey: "openArea") }
        .onChange(of: store.areas) { openLinkedArea() }
        .onChange(of: linkedArea) { openLinkedArea() }
    }

    @State private var linkedArea: String?

    private func select(_ area: AreaSummary) {
        withAnimation(.snappy) {
            selectedID = area.id
            position = Self.camera(at: area.coordinate, distance: 700)
        }
    }

    private func go(to completion: MKLocalSearchCompletion) async {
        searchFocused = false
        guard let place = await search.resolve(completion) else { return }
        search.query = ""
        destination = place
        withAnimation(.snappy) {
            // Suggest the closest shelter that still has room.
            selectedID = store.areas.filter { $0.free > 0 }.min { place.distance(to: $0) < place.distance(to: $1) }?.id
            position = framing(place)
        }
    }

    /// Shows the destination together with the shelters within 3 km of it.
    private func framing(_ place: Destination) -> MapCameraPosition {
        let points = [place.coordinate] + store.areas.filter { place.distance(to: $0) < 3000 }.map(\.coordinate)
        guard points.count > 1 else { return Self.camera(at: place.coordinate, distance: 700) }
        let lats = points.map(\.latitude), lons = points.map(\.longitude)
        let center = CLLocationCoordinate2D(latitude: (lats.min()! + lats.max()!) / 2,
                                            longitude: (lons.min()! + lons.max()!) / 2)
        let span = MKCoordinateSpan(latitudeDelta: (lats.max()! - lats.min()!) * 1.6 + 0.002,
                                    longitudeDelta: (lons.max()! - lons.min()!) * 1.6 + 0.002)
        return .region(MKCoordinateRegion(center: center, span: span))
    }

    private func clearDestination() {
        withAnimation(.snappy) {
            destination = nil
            position = Self.camera(at: Site.center, distance: 900)
        }
    }

    private func openLinkedArea() {
        guard let id = linkedArea, let area = store.areas.first(where: { $0.id == id }) else { return }
        linkedArea = nil
        path = [area]
    }
}

private struct AreaPin: View {
    let area: AreaSummary
    let selected: Bool

    var body: some View {
        HStack(spacing: 5) {
            Image(systemName: "bicycle")
                .font(.caption.weight(.bold))
            Text(area.updatedAt == nil ? "–" : "\(area.free)")
                .font(.subheadline.weight(.bold).monospacedDigit())
                .contentTransition(.numericText())
        }
        .foregroundStyle(.white)
        .padding(.horizontal, 10)
        .padding(.vertical, 6)
        .background(area.availability.color.gradient, in: Capsule())
        .overlay(Capsule().stroke(.white, lineWidth: selected ? 3 : 2))
        .shadow(color: .black.opacity(selected ? 0.35 : 0.2), radius: selected ? 8 : 4, y: 2)
        .scaleEffect(selected ? 1.25 : 1, anchor: .bottom)
        .animation(.snappy, value: area.free)
        .animation(.snappy, value: selected)
    }
}

/// Small floating bar shown while no shelter is selected.
private struct StatusBar: View {
    @Environment(AreaStore.self) private var store
    let destination: Destination?
    let clearDestination: () -> Void
    let settings: () -> Void

    var body: some View {
        HStack(spacing: 8) {
            HStack(spacing: 8) {
                if let error = store.errorMessage {
                    Label(error, systemImage: "wifi.exclamationmark")
                        .foregroundStyle(.orange)
                        .lineLimit(1)
                } else if let destination {
                    Label(destination.name, systemImage: "building.2.fill")
                        .foregroundStyle(.blue)
                        .lineLimit(1)
                    Button(action: clearDestination) { Image(systemName: "xmark.circle.fill") }
                        .buttonStyle(.plain)
                        .foregroundStyle(.secondary)
                        .accessibilityLabel("Clear destination")
                } else {
                    Label("\(store.totalFree) free spots", systemImage: "bicycle")
                        .contentTransition(.numericText())
                        .animation(.snappy, value: store.totalFree)
                    if let time = store.cameraTime {
                        Text(time)
                            .monospacedDigit()
                            .foregroundStyle(.secondary)
                    }
                }
            }
            .font(.subheadline.weight(.semibold))
            .padding(.horizontal, 14)
            .frame(height: 44)
            .glassBackground(in: Capsule())

            Spacer()

            Button(action: settings) {
                Image(systemName: "gearshape.fill")
                    .font(.body.weight(.semibold))
                    .foregroundStyle(.secondary)
                    .frame(width: 44, height: 44)
                    .glassBackground(in: Circle())
            }
            .buttonStyle(.plain)
            .accessibilityLabel("Settings")
        }
    }
}

/// Card for the tapped shelter. Pulling it down shrinks it; pulling the small card down dismisses it.
private struct AreaCard: View {
    let area: AreaSummary
    var distance: CLLocationDistance?
    let dismiss: () -> Void
    let open: () -> Void

    @Environment(\.openURL) private var openURL
    @State private var expanded = true
    @State private var drag: CGFloat = 0

    private static let spring = Animation.bouncy(duration: 0.45, extraBounce: 0.12)
    private static let shape = RoundedRectangle(cornerRadius: 34, style: .continuous)

    private var free: String { area.updatedAt == nil ? "–" : "\(area.free)" }

    var body: some View {
        VStack(spacing: 0) {
            Capsule()
                .fill(.tertiary)
                .frame(width: 36, height: 5)
                .padding(.top, 8)
                .padding(.bottom, expanded ? 12 : 8)
            if expanded {
                details.transition(.opacity)
            } else {
                compact.transition(.opacity)
            }
        }
        .padding(.horizontal, 20)
        .padding(.bottom, expanded ? 20 : 14)
        .frame(maxWidth: .infinity)
        .glassBackground(in: Self.shape)
        .contentShape(Self.shape)
        // Follows the finger downwards and resists being pulled up.
        .offset(y: drag > 0 ? drag : drag / 4)
        .gesture(DragGesture(minimumDistance: 8)
            .onChanged { drag = $0.translation.height }
            .onEnded { value in
                let pull = value.predictedEndTranslation.height
                withAnimation(Self.spring) {
                    drag = 0
                    if pull > 80 {
                        if expanded { expanded = false } else { dismiss() }
                    } else if pull < -60 {
                        expanded = true
                    }
                }
            })
        .onTapGesture {
            if !expanded { withAnimation(Self.spring) { expanded = true } }
        }
        .onChange(of: area.id) { withAnimation(Self.spring) { expanded = true } }
        .sensoryFeedback(.impact(weight: .light), trigger: expanded)
    }

    private var compact: some View {
        HStack(spacing: 12) {
            ShelterIcon(area: area, size: 40)
            VStack(alignment: .leading, spacing: 1) {
                Text(area.name)
                    .font(.headline)
                    .lineLimit(1)
                Text("\(free) of \(area.capacity) free" + (area.cameraTime.map { " · \($0)" } ?? ""))
                    .font(.subheadline.monospacedDigit())
                    .foregroundStyle(.secondary)
                    .contentTransition(.numericText())
            }
            Spacer(minLength: 8)
            Button(action: open) {
                Image(systemName: "cube.transparent")
                    .font(.body.weight(.semibold))
                    .frame(width: 28, height: 28)
            }
            .prominentGlassButton()
            .buttonBorderShape(.circle)
            .tint(.green)
            .accessibilityLabel("View in 3D")
        }
    }

    private var details: some View {
        VStack(alignment: .leading, spacing: 18) {
            HStack(spacing: 12) {
                ShelterIcon(area: area, size: 44)
                VStack(alignment: .leading, spacing: 2) {
                    Text(area.name)
                        .font(.title3.weight(.bold))
                        .lineLimit(1)
                    Text("Covered bike parking")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }
                Spacer(minLength: 0)
            }

            HStack(spacing: 0) {
                Stat(title: "Free", value: free, tint: area.availability.color)
                Divider().frame(height: 30)
                Stat(title: "Taken", value: "\(area.occupied)/\(area.capacity)")
                Divider().frame(height: 30)
                if let distance {
                    Stat(title: "Distance", value: Measurement(value: distance, unit: UnitLength.meters)
                        .formatted(.measurement(width: .abbreviated, usage: .road)))
                } else {
                    Stat(title: "Camera", value: area.cameraTime ?? "–")
                }
            }
            .animation(.snappy, value: area.free)

            HStack(spacing: 10) {
                Button(action: open) {
                    Label("View in 3D", systemImage: "cube.transparent")
                        .frame(maxWidth: .infinity)
                }
                .prominentGlassButton()
                .tint(.green)
                Button(action: directions) {
                    Label("Directions", systemImage: "bicycle")
                        .frame(maxWidth: .infinity)
                }
                .glassButton()
            }
            .font(.subheadline.weight(.semibold))
            .controlSize(.large)
        }
    }

    /// Cycling directions in Apple Maps.
    private func directions() {
        let c = area.coordinate
        if let url = URL(string: "https://maps.apple.com/directions?destination=\(c.latitude),\(c.longitude)&mode=cycling") {
            openURL(url)
        }
    }
}

private struct ShelterIcon: View {
    let area: AreaSummary
    let size: CGFloat

    var body: some View {
        Image(systemName: "bicycle")
            .font(.system(size: size * 0.42, weight: .semibold))
            .foregroundStyle(.white)
            .frame(width: size, height: size)
            .background(area.availability.color.gradient, in: Circle())
    }
}

private struct Stat: View {
    let title: String
    let value: String
    var tint: Color = .primary

    var body: some View {
        VStack(spacing: 2) {
            Text(title.uppercased())
                .font(.caption2.weight(.semibold))
                .foregroundStyle(.secondary)
            Text(value)
                .font(.title3.weight(.semibold).monospacedDigit())
                .foregroundStyle(tint)
                .contentTransition(.numericText())
        }
        .frame(maxWidth: .infinity)
    }
}

private struct SettingsSheet: View {
    @Environment(\.dismiss) private var dismiss
    @AppStorage("backendURL") private var backendURL = APIClient.defaultURL

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    TextField("Backend URL", text: $backendURL)
                        .keyboardType(.URL)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                } footer: {
                    Text("Use your laptop's address, e.g. http://192.168.1.20:8000, when running on a phone.")
                }
            }
            .navigationTitle("Settings")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { Button("Done") { dismiss() } }
        }
        .presentationDetents([.medium])
    }
}
