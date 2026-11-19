import SwiftUI

/// The daily brief: the standing lines, then a ranked list of hard deadlines, capped at seven.
struct DigestView: View {
    @EnvironmentObject var state: AppState

    /// When the agent built the brief, not when the screen was opened.
    private func stamp() -> String {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.dateFormat = "EEEE, MMMM d 'at' h:mm a"
        return f.string(from: parseISO(state.digest?.generatedAt) ?? Date()).lowercased()
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 30) {
                VStack(alignment: .leading, spacing: 4) {
                    BigTitle(text: "Digest")
                    Text(stamp()).font(.system(size: 14.5)).foregroundStyle(Theme.secondary)
                }.reveal(0)

                if let d = state.digest {
                    if let m = d.mantra { line("mantra", m).reveal(1) }
                    if let v = d.vision { line("vision", v).reveal(2) }
                    if let w = d.why { line("why, \(w.date)", w.text).reveal(3) }
                    if let id = d.identity, !id.isEmpty { identity(id).reveal(4) }
                    plan(d.plan).reveal(5)
                    deadlines(d).reveal(6)
                    ForEach(Array(d.notes.enumerated()), id: \.offset) { _, n in
                        Text(n).font(.system(size: 12.5)).foregroundStyle(Theme.secondary)
                    }
                } else {
                    Text(state.waitingText).font(.system(size: 14.5)).foregroundStyle(Theme.secondary)
                }
            }
            .page()
        }
        .refreshable { await state.loadDigest() }
        .task { await state.loadDigest() }
    }

    private func line(_ label: String, _ text: String) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            sectionLabel(label)
            Text(text).font(.system(size: 15)).foregroundStyle(Theme.body).lineSpacing(3)
        }
    }

    private func identity(_ lines: [String]) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            sectionLabel("identity, say it out loud, repeat each twice")
            ForEach(Array(lines.enumerated()), id: \.offset) { _, l in
                Text(l).font(.system(size: 15)).foregroundStyle(Theme.title)
            }
        }
    }

    @ViewBuilder
    private func plan(_ p: DigestPlan?) -> some View {
        if let p {
            VStack(alignment: .leading, spacing: 8) {
                sectionLabel("today's plan")
                if p.logged {
                    ForEach(Array(p.items.enumerated()), id: \.offset) { _, i in
                        HStack(alignment: .firstTextBaseline, spacing: 10) {
                            Image(systemName: i.done ? "checkmark.circle.fill" : "circle")
                                .font(.system(size: 13)).foregroundStyle(i.done ? Theme.tertiary : Theme.secondary)
                            Text(i.text).font(.system(size: 15))
                                .foregroundStyle(i.done ? Theme.tertiary : Theme.body)
                                .strikethrough(i.done, color: Theme.tertiary)
                        }
                        .accessibilityElement(children: .combine)
                        .accessibilityValue(i.done ? "done" : "not done")
                    }
                } else {
                    Text("no plan logged, what's the schedule today?").font(.system(size: 14.5)).foregroundStyle(Theme.secondary)
                }
            }
        }
    }

    private func deadlines(_ d: Digest) -> some View {
        VStack(alignment: .leading, spacing: 18) {
            sectionLabel("deadlines")
            if d.deadlines.isEmpty {
                Text("nothing has a hard deadline today.").font(.system(size: 14.5)).foregroundStyle(Theme.secondary)
            }
            ForEach(Array(d.deadlines.enumerated()), id: \.element.id) { i, t in
                HStack(alignment: .top, spacing: 14) {
                    Text("\(i + 1)").font(.system(size: 16)).monospacedDigit().foregroundStyle(Theme.tertiary).frame(width: 18, alignment: .leading)
                    VStack(alignment: .leading, spacing: 3) {
                        Text(t.title).font(.system(size: 16)).foregroundStyle(Theme.title)
                        Text(t.dueLocal ?? dueLine(t.dueAt)).font(.system(size: 12.5)).foregroundStyle(Theme.secondary)
                    }
                }
            }
            if d.overflow > 0 {
                Text("+\(d.overflow) more with deadlines past \(d.overflowAfter ?? "this list")").font(.system(size: 12.5)).foregroundStyle(Theme.tertiary)
            }
        }
    }
}
