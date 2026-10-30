import MapKit
import SwiftUI

struct MapScreen: View {
    @Environment(AreaStore.self) private var store
    @State private var path: [AreaSummary] = []
    @State private var showSettings = false
    @State private var search = LocationSearch()
    @State private var destination: Destination?
    @FocusState private var searchFocused: Bool
    @State private var position = Self.camera(at: Site.center, distance: 380)

    private static func camera(at center: CLLocationCoordinate2D, distance: Double) -> MapCameraPosition {
        .camera(MapCamera(centerCoordinate: center, distance: distance, heading: 0, pitch: 45))
    }

    var body: some View {
        NavigationStack(path: $path) {
            Map(position: $position) {
                ForEach(store.areas) { area in
                    MapPolygon(coordinates: area.outline)
                        .foregroundStyle(area.availability.color.opacity(0.5))
                        .stroke(area.availability.color, lineWidth: 2)
                    Annotation(area.name, coordinate: area.coordinate, anchor: .bottom) {
                        Button { path.append(area) } label: { AreaPin(area: area) }
                            .buttonStyle(.plain)
                    }
                }
                if let destination {
                    Marker(destination.name, systemImage: "building.2.fill", coordinate: destination.coordinate)
                        .tint(.blue)
                }
            }
            .mapStyle(.hybrid(elevation: .realistic, pointsOfInterest: .excludingAll))
            .safeAreaInset(edge: .top) {
                SearchOverlay(search: search, focused: $searchFocused, areas: store.areas,
                              openArea: { area in
                                  searchFocused = false
                                  path.append(area)
                              },
                              choose: { completion in Task { await go(to: completion) } })
                    .padding(.horizontal, 12)
            }
            .safeAreaInset(edge: .bottom) {
                // Faded rather than removed while searching, so the map's safe area stays put.
                SummaryPanel(destination: destination,
                             open: { path.append($0) },
                             clearDestination: clearDestination,
                             settings: { showSettings = true })
                    .padding(.horizontal, 12)
                    .opacity(searchFocused ? 0 : 1)
                    .allowsHitTesting(!searchFocused)
                    .animation(.easeOut(duration: 0.15), value: searchFocused)
            }
            // The keyboard covers the faded panel instead of pushing it, and the map, upwards.
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

    private func go(to completion: MKLocalSearchCompletion) async {
        searchFocused = false
        guard let place = await search.resolve(completion) else { return }
        search.query = ""
        destination = place
        withAnimation { position = framing(place) }
    }

    /// Shows the destination together with the shelters within 3 km of it.
    private func framing(_ place: Destination) -> MapCameraPosition {
        let points = [place.coordinate] + store.areas.filter { place.distance(to: $0) < 3000 }.map(\.coordinate)
        guard points.count > 1 else { return Self.camera(at: place.coordinate, distance: 500) }
        let lats = points.map(\.latitude), lons = points.map(\.longitude)
        let center = CLLocationCoordinate2D(latitude: (lats.min()! + lats.max()!) / 2,
                                            longitude: (lons.min()! + lons.max()!) / 2)
        let span = MKCoordinateSpan(latitudeDelta: (lats.max()! - lats.min()!) * 1.6 + 0.002,
                                    longitudeDelta: (lons.max()! - lons.min()!) * 1.6 + 0.002)
        return .region(MKCoordinateRegion(center: center, span: span))
    }

    private func clearDestination() {
        destination = nil
        withAnimation { position = Self.camera(at: Site.center, distance: 380) }
    }

    private func openLinkedArea() {
        guard let id = linkedArea, let area = store.areas.first(where: { $0.id == id }) else { return }
        linkedArea = nil
        path = [area]
    }
}

private struct AreaPin: View {
    let area: AreaSummary

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
        .overlay(Capsule().stroke(.white, lineWidth: 2))
        .shadow(radius: 4, y: 2)
        .animation(.snappy, value: area.free)
    }
}

private struct SummaryPanel: View {
    @Environment(AreaStore.self) private var store
    let destination: Destination?
    let open: (AreaSummary) -> Void
    let clearDestination: () -> Void
    let settings: () -> Void

    /// Closest shelters first once a destination is set, otherwise most free spots first.
    private var areas: [AreaSummary] {
        guard let destination else { return store.areas.sorted { $0.free > $1.free } }
        return store.areas.sorted { destination.distance(to: $0) < destination.distance(to: $1) }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .firstTextBaseline) {
                VStack(alignment: .leading, spacing: 2) {
                    if let destination {
                        HStack(spacing: 4) {
                            Label("Near \(destination.name)", systemImage: "building.2.fill")
                                .lineLimit(1)
                            Button(action: clearDestination) { Image(systemName: "xmark.circle.fill") }
                                .accessibilityLabel("Clear destination")
                        }
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(.blue)
                    } else {
                        Text("Endress+Hauser · Reinach")
                            .font(.caption.weight(.semibold))
                            .foregroundStyle(.secondary)
                    }
                    Text("\(store.totalFree) free bike spots")
                        .font(.title2.weight(.bold))
                        .contentTransition(.numericText())
                        .animation(.snappy, value: store.totalFree)
                }
                Spacer()
                if let time = store.cameraTime {
                    Label(time, systemImage: "video.fill")
                        .font(.caption.weight(.semibold).monospacedDigit())
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(.red.opacity(0.15), in: Capsule())
                        .foregroundStyle(.red)
                }
                Button(action: settings) { Image(systemName: "gearshape") }
                    .foregroundStyle(.secondary)
            }

            if let error = store.errorMessage {
                Label(error, systemImage: "wifi.exclamationmark")
                    .font(.footnote)
                    .foregroundStyle(.orange)
            }

            ForEach(areas) { area in
                Button { open(area) } label: {
                    AreaRow(area: area, distance: destination?.distance(to: area))
                }
                .buttonStyle(.plain)
            }
        }
        .padding(16)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 24, style: .continuous))
    }
}

private struct AreaRow: View {
    let area: AreaSummary
    var distance: CLLocationDistance?

    var body: some View {
        HStack(spacing: 12) {
            Circle()
                .fill(area.availability.color)
                .frame(width: 10, height: 10)
            VStack(alignment: .leading, spacing: 4) {
                HStack(spacing: 6) {
                    Text(area.name)
                        .font(.subheadline.weight(.semibold))
                    if let distance {
                        Text(Measurement(value: distance, unit: UnitLength.meters)
                            .formatted(.measurement(width: .abbreviated, usage: .road)))
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }
                ProgressView(value: Double(area.occupied), total: Double(max(area.capacity, 1)))
                    .tint(area.availability.color)
            }
            Text("\(area.free)/\(area.capacity)")
                .font(.subheadline.monospacedDigit())
                .foregroundStyle(.secondary)
                .contentTransition(.numericText())
            Image(systemName: "chevron.right")
                .font(.caption.weight(.semibold))
                .foregroundStyle(.tertiary)
        }
        .contentShape(Rectangle())
        .animation(.snappy, value: area.free)
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
