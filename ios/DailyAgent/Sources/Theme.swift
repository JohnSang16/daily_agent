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
    static let toggle = Color(white: 0.62)  // switch track: the iOS knob is white, so a white track would hide it

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
            .scaleEffect(configuration.isPressed && !reduceMotion ? 0.97 : 1)
            .opacity(configuration.isPressed ? 0.8 : 1)
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
    var enabled = true
    var feedback: SensoryFeedback = .impact(weight: .light)
    let action: () -> Void
    @State private var taps = 0
    var body: some View {
        Button { taps += 1; action() } label: {
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
        .disabled(!enabled)
        .opacity(enabled ? 1 : 0.4)
        .animation(Theme.ease, value: enabled)
        .sensoryFeedback(feedback, trigger: taps)
    }
}

/// The black page with one faint light from above, so the glass has something to catch.
struct Backdrop: View {
    var body: some View {
        ZStack {
            Color.black
            RadialGradient(colors: [Color.white.opacity(0.075), .clear], center: .init(x: 0.5, y: -0.1),
                           startRadius: 0, endRadius: 520)
        }.ignoresSafeArea()
    }
}

/// A small "first" tag, outlined, beside the top priority.
struct FirstTag: View {
    var body: some View {
        Text("first").font(.system(size: 11)).foregroundStyle(Theme.secondary)
            .padding(.horizontal, 7).padding(.vertical, 2).overlay(Capsule().stroke(Theme.tertiary, lineWidth: 0.8))
    }
}

/// A sheet title: sentence case, the one place besides the big titles that is not lowercase.
func sheetTitle(_ s: String) -> some View {
    Text(s).font(.system(size: 26)).tracking(-0.4).foregroundStyle(Theme.title)
}

/// Every sheet shares one look: frosted, rounded, with a grabber.
extension View {
    func sheetChrome(_ detents: Set<PresentationDetent> = [.medium, .large]) -> some View {
        self.presentationBackground(.regularMaterial).presentationDetents(detents)
            .presentationCornerRadius(28).presentationDragIndicator(.visible)
    }

    /// Shared page layout: side gutter and room under the menu button.
    func page() -> some View {
        self.padding(.horizontal, 24).padding(.top, 72).padding(.bottom, 60)
            .frame(maxWidth: .infinity, alignment: .leading)
    }
}

func sectionLabel(_ s: String) -> some View {
    Text(s).font(.system(size: 13)).foregroundStyle(Theme.tertiary)
}
