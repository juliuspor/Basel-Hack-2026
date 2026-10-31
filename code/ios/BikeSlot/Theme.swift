import SwiftUI

/// Endress+Hauser colors, taken from endress.com.
enum Brand {
    /// Logo blue: the app's accent, main actions and free spots. Free (blue) and
    /// full (red) also stay distinguishable with red-green color blindness.
    static let blue = Color(hex: 0x00AEEF)
    /// Dark slate used for text and icons on endress.com.
    static let slate = Color(hex: 0x36444C)
    /// Light slate for inactive states.
    static let mist = Color(hex: 0xA4B3BC)
    static let red = Color(hex: 0xD50C2F)
}

extension Color {
    init(hex: UInt32) {
        self.init(red: Double((hex >> 16) & 0xFF) / 255,
                  green: Double((hex >> 8) & 0xFF) / 255,
                  blue: Double(hex & 0xFF) / 255)
    }
}
