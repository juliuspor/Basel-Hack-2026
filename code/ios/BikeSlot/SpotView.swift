import SwiftUI
import WebKit

/// The 3D view of one bike spot: Spot/spot.html (three.js) draws the rack as seen from the
/// front, a blue pad on every free slot and a bike on every taken one, over the real photo of
/// the spot. The camera is fixed, so the view takes no touches.
struct SpotView: UIViewRepresentable {
    let area: AreaSummary
    let slots: [Slot]
    /// False until a camera has reported; the pads then stay grey instead of showing "free".
    let known: Bool

    func makeCoordinator() -> Coordinator { Coordinator() }

    func makeUIView(context: Context) -> WKWebView {
        let web = WKWebView(frame: .zero, configuration: WKWebViewConfiguration())
        web.isOpaque = false
        web.backgroundColor = .clear
        web.isUserInteractionEnabled = false
        // The page draws edge to edge behind the bars; SwiftUI already handles the safe area.
        web.scrollView.contentInsetAdjustmentBehavior = .never
        web.navigationDelegate = context.coordinator
        if let folder = Bundle.main.url(forResource: "Spot", withExtension: nil) {
            web.loadFileURL(folder.appendingPathComponent("spot.html"), allowingReadAccessTo: folder)
        }
        return web
    }

    func updateUIView(_ web: WKWebView, context: Context) {
        context.coordinator.state = (area, slots, known)
        context.coordinator.flush(web)
    }

    @MainActor
    final class Coordinator: NSObject, WKNavigationDelegate {
        var state: (area: AreaSummary, slots: [Slot], known: Bool)?
        private var loaded = false
        private var shownSlots: Int?
        private var sent: (slots: [Slot], known: Bool)?

        func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
            loaded = true
            flush(webView)
        }

        /// The model is built once the slot count is known; later changes only update the slots.
        func flush(_ web: WKWebView) {
            guard loaded, let state, !state.slots.isEmpty else { return }
            if let sent, sent.slots == state.slots, sent.known == state.known { return }
            let slots = Self.json(state.slots)
            let script: String
            if shownSlots == nil {
                script = "BikeSpot.show({id: \(Self.json(state.area.id)), kind: \(Self.json(state.area.kind)), "
                    + "known: \(state.known), slots: \(slots)})"
                shownSlots = state.slots.count
            } else {
                script = "BikeSpot.update(\(slots), \(state.known))"
            }
            sent = (state.slots, state.known)
            web.evaluateJavaScript(script)
        }

        /// JSON text of a value, safe to paste into a script.
        private static func json(_ value: some Encodable) -> String {
            (try? JSONEncoder().encode(value)).flatMap { String(data: $0, encoding: .utf8) } ?? "null"
        }
    }
}
