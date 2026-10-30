import MapKit
import SwiftUI

struct MapScreen: View {
    @Environment(AreaStore.self) private var store
    @State private var path: [AreaSummary] = []
    @State private var showSettings = false
    @State private var position: MapCameraPosition = .camera(MapCamera(
        centerCoordinate: CLLocationCoordinate2D(latitude: 47.48872, longitude: 7.59805),
        distance: 380, heading: 0, pitch: 45))

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
            }
            .mapStyle(.hybrid(elevation: .realistic, pointsOfInterest: .excludingAll))
            .safeAreaInset(edge: .bottom) {
                SummaryPanel(open: { path.append($0) }, settings: { showSettings = true })
                    .padding(.horizontal, 12)
            }
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
    let open: (AreaSummary) -> Void
    let settings: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .firstTextBaseline) {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Endress+Hauser · Reinach")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(.secondary)
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

            ForEach(store.areas.sorted { $0.free > $1.free }) { area in
                Button { open(area) } label: { AreaRow(area: area) }
                    .buttonStyle(.plain)
            }
        }
        .padding(16)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 24, style: .continuous))
    }
}

private struct AreaRow: View {
    let area: AreaSummary

    var body: some View {
        HStack(spacing: 12) {
            Circle()
                .fill(area.availability.color)
                .frame(width: 10, height: 10)
            VStack(alignment: .leading, spacing: 4) {
                Text(area.name)
                    .font(.subheadline.weight(.semibold))
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
