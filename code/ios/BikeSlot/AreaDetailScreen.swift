import MapKit
import SwiftUI

struct AreaDetailScreen: View {
    let area: AreaSummary
    @Environment(AreaStore.self) private var store
    @State private var lookAround: MKLookAroundScene?
    @State private var showLookAround = false

    private var detail: AreaDetail? { store.details[area.id] }

    var body: some View {
        ZStack {
            Color(hex: 0xE6EDF1).ignoresSafeArea()
            if let detail {
                SpotView(area: area, slots: detail.slots, known: detail.summary.updatedAt != nil)
                    .ignoresSafeArea()
            } else {
                ProgressView("Loading spot")
            }
        }
        .safeAreaInset(edge: .bottom) {
            VStack(alignment: .trailing, spacing: 6) {
                // The 3D world is built from OpenStreetMap data (ODbL).
                Text("Map data © OpenStreetMap contributors")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
                    .padding(.horizontal, 8)
                StatusCard(summary: detail?.summary ?? area, detail: detail)
            }
            .padding(.horizontal, 12)
        }
        .navigationTitle(area.name)
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            if lookAround != nil {
                Button { showLookAround = true } label: {
                    Label("Look Around", systemImage: "binoculars.fill")
                        .labelStyle(.titleAndIcon)
                }
            }
        }
        .lookAroundViewer(isPresented: $showLookAround, initialScene: lookAround)
        .task {
            // Apple's street-level imagery nearest the shelter. Nil where Apple has none or the
            // phone is offline, which keeps the button hidden instead of opening an empty viewer.
            lookAround = try? await MKLookAroundSceneRequest(coordinate: area.coordinate).scene
        }
        .task { await store.pollDetail(area.id) }
    }
}

private struct StatusCard: View {
    let summary: AreaSummary
    let detail: AreaDetail?

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .firstTextBaseline, spacing: 6) {
                Text(summary.updatedAt == nil ? "–" : "\(summary.free)")
                    .font(.system(size: 44, weight: .bold, design: .rounded).monospacedDigit())
                    .foregroundStyle(summary.availability.color)
                    .contentTransition(.numericText())
                Text("of \(summary.capacity) spots free")
                    .font(.headline)
                    .foregroundStyle(.secondary)
                Spacer()
            }
            .animation(.snappy, value: summary.free)

            if summary.updatedAt == nil {
                Label("No camera at this spot yet", systemImage: "video.slash")
                    .font(.footnote)
                    .foregroundStyle(.secondary)
            }

            if detail?.personPresent == true {
                Label("Someone is in view, showing the last known state", systemImage: "figure.walk")
                    .font(.footnote)
                    .foregroundStyle(.orange)
            }
        }
        .padding(16)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 24, style: .continuous))
    }
}
