import RealityKit
import SwiftUI

struct AreaDetailScreen: View {
    let area: AreaSummary
    @Environment(AreaStore.self) private var store
    @State private var scene: AreaScene?
    @State private var loadError: String?

    private var detail: AreaDetail? { store.details[area.id] }

    var body: some View {
        let slots = detail?.slots ?? []
        ZStack {
            LinearGradient(colors: [Brand.blue.opacity(0.22), Color(hex: 0xF2F5F7)],
                           startPoint: .top, endPoint: .bottom)
                .ignoresSafeArea()

            if let scene {
                RealityView { content in
                    content.add(scene.root)
                } update: { _ in
                    scene.apply(slots)
                }
                .realityViewCameraControls(.orbit)
                .ignoresSafeArea()
            } else if let loadError {
                ContentUnavailableView("3D model unavailable", systemImage: "cube.transparent",
                                       description: Text(loadError))
            } else {
                ProgressView("Loading 3D view")
            }
        }
        .safeAreaInset(edge: .bottom) {
            StatusCard(summary: detail?.summary ?? area, detail: detail)
                .padding(.horizontal, 12)
        }
        .navigationTitle(area.name)
        .navigationBarTitleDisplayMode(.inline)
        .task {
            do {
                scene = try await AreaScene.load(area)
            } catch {
                loadError = error.localizedDescription
            }
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

            if let slots = detail?.slots {
                LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 6), count: 7), spacing: 6) {
                    ForEach(slots) { slot in
                        Text("\(slot.label)")
                            .font(.caption.weight(.bold).monospacedDigit())
                            .frame(maxWidth: .infinity, minHeight: 28)
                            .foregroundStyle(.white)
                            .background(slot.occupied ? Brand.red : Brand.blue,
                                        in: RoundedRectangle(cornerRadius: 7, style: .continuous))
                    }
                }
                .animation(.snappy, value: slots)
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
