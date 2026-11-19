import SwiftUI

/// Pure black and white, from design/DESIGN_NOTES.md. No accent colors anywhere.
enum Theme {
    static let bg = Color.black
    static let surface = Color(white: 0.043)
    static let raised = Color(white: 0.086)
    static let line = Color(white: 0.141)
    static let title = Color.white
    static let body = Color(white: 0.863)
    static let secondary = Color(white: 0.643)
    static let tertiary = Color(white: 0.522)  // the lowest allowed for text
    static let ease = Animation.easeOut(duration: 0.38)
}

struct BigTitle: View {
    let text: String
    var body: some View {
        Text(text).font(.system(size: 46, weight: .light)).tracking(-1.2).foregroundStyle(Theme.title)
    }
}

struct PillButton: View {
    let label: String
    var primary = false
    let action: () -> Void
    var body: some View {
        Button(action: action) {
            Text(label).font(.system(size: 15))
                .padding(.horizontal, 18).frame(minHeight: 44)
                .foregroundStyle(primary ? Color.black : Theme.title)
                .background(primary ? Color.white : Color.clear, in: Capsule())
                .overlay(Capsule().stroke(primary ? Color.clear : Theme.tertiary, lineWidth: 1))
        }.buttonStyle(.plain)
    }
}

func sectionLabel(_ s: String) -> some View {
    Text(s).font(.system(size: 13)).foregroundStyle(Theme.tertiary)
}
