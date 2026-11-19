import SwiftUI

/// Pure black and white, from design/DESIGN_NOTES.md. No accent colors anywhere.
/// Gloss is done with frosted material, soft highlights and springs, all monochrome.
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
    static let spring = Animation.spring(response: 0.46, dampingFraction: 0.82)  // drawer, sheets, selection
    static let snap = Animation.spring(response: 0.3, dampingFraction: 0.72)  // presses
}

// MARK: glass

/// Real Liquid Glass on iOS 26 and later, frosted material with a hairline highlight before that.
extension View {
    @ViewBuilder
    func glass<S: InsettableShape>(_ shape: S) -> some View {
        if #available(iOS 26.0, macOS 26.0, *) {
            self.glassEffect(.regular, in: shape)
        } else {
            self.background(.ultraThinMaterial, in: shape)
                .overlay(shape.strokeBorder(
                    LinearGradient(colors: [Color.white.opacity(0.32), Color.white.opacity(0.04)],
                                   startPoint: .top, endPoint: .bottom), lineWidth: 0.8))
        }
    }

    /// Fades and rises in, one after another. Plain fade when Reduce Motion is on.
    func reveal(_ index: Int = 0) -> some View { modifier(Reveal(index: index)) }
}

struct Reveal: ViewModifier {
    let index: Int
    @State private var shown = false
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    func body(content: Content) -> some View {
        content
            .opacity(shown ? 1 : 0)
            .offset(y: shown || reduceMotion ? 0 : 16)
            .onAppear {
                withAnimation((reduceMotion ? Animation.easeOut(duration: 0.2) : Theme.spring).delay(reduceMotion ? 0 : Double(index) * 0.06)) {
                    shown = true
                }
            }
    }
}

/// Springy press: shrinks a little under the finger, bounces back on release.
struct PressStyle: ButtonStyle {
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .scaleEffect(configuration.isPressed && !reduceMotion ? 0.95 : 1)
            .opacity(configuration.isPressed ? 0.85 : 1)
            .animation(Theme.snap, value: configuration.isPressed)
    }
}

struct BigTitle: View {
    let text: String
    var body: some View {
        Text(text).font(.system(size: 46, weight: .light)).tracking(-1.2).foregroundStyle(Theme.title)
            .contentTransition(.opacity)
    }
}

struct PillButton: View {
    let label: String
    var primary = false
    let action: () -> Void
    var body: some View {
        Button(action: action) {
            Text(label).font(.system(size: 15, weight: primary ? .medium : .regular))
                .padding(.horizontal, 20).frame(minHeight: 44)
                .foregroundStyle(primary ? Color.black : Theme.title)
                .background {
                    if primary {
                        // a soft sheen: bright white fading to light gray, with a thin top highlight
                        Capsule().fill(LinearGradient(colors: [.white, Color(white: 0.82)], startPoint: .top, endPoint: .bottom))
                            .overlay(Capsule().strokeBorder(Color.white.opacity(0.9), lineWidth: 0.6))
                            .shadow(color: .white.opacity(0.12), radius: 10, y: 2)
                    } else {
                        Capsule().fill(Color.clear).glass(Capsule())
                    }
                }
        }
        .buttonStyle(PressStyle())
        .sensoryFeedback(.impact(weight: .light), trigger: label)
    }
}

func sectionLabel(_ s: String) -> some View {
    Text(s).font(.system(size: 13)).foregroundStyle(Theme.tertiary)
}
