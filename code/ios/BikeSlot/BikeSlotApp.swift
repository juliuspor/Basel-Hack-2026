import SwiftUI

@main
struct BikeSlotApp: App {
    @State private var store = AreaStore()

    var body: some Scene {
        WindowGroup {
            MapScreen()
                .environment(store)
                .task { await store.pollAreas() }
        }
    }
}
