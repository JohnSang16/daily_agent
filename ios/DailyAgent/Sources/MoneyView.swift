import SwiftUI

struct MoneyView: View {
    @EnvironmentObject var state: AppState
    @State private var showBanks = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 22) {
                VStack(alignment: .leading, spacing: 4) {
                    BigTitle(text: "Money")
                    Text(monthName()).font(.system(size: 14.5)).foregroundStyle(Theme.secondary)
                }
                Button { showBanks = true } label: {
                    Text(state.banks?.chip ?? "banks: all").font(.system(size: 13.5)).foregroundStyle(Theme.body)
                        .padding(.horizontal, 16).frame(minHeight: 44).glass(Capsule())
                }.buttonStyle(PressStyle())
                if let note = state.page?.note { Text(note).font(.system(size: 12.5)).foregroundStyle(Theme.secondary) }
                if let page = state.page {
                    ForEach(groupByDay(page.transactions, now: Date()), id: \.heading) { g in
                        VStack(alignment: .leading, spacing: 14) {
                            sectionLabel(g.heading).reveal(0)
                            ForEach(g.items) { t in
                                HStack(alignment: .top) {
                                    VStack(alignment: .leading, spacing: 3) {
                                        Text(t.merchant).font(.system(size: 16)).foregroundStyle(Theme.title)
                                        Text(subline(t)).font(.system(size: 12.5)).foregroundStyle(Theme.secondary)
                                    }
                                    Spacer()
                                    Text(t.amount).font(.system(size: 16)).foregroundStyle(Theme.title)
                                }
                            }
                        }
                    }
                } else {
                    Text("loading.").font(.system(size: 14.5)).foregroundStyle(Theme.secondary)
                }
            }
            .padding(.horizontal, 24).padding(.top, 72).padding(.bottom, 60)
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .refreshable { await state.loadMoney() }
        .task { await state.loadMoney() }
        .sheet(isPresented: $showBanks) { BanksSheet().environmentObject(state) }
    }

    private func monthName() -> String {
        let f = DateFormatter(); f.locale = Locale(identifier: "en_US_POSIX"); f.dateFormat = "MMMM"
        return f.string(from: Date()).lowercased()
    }

    private func subline(_ t: Txn) -> String {
        var parts = [t.bank.lowercased()]
        if let c = t.category { parts.append(c.replacingOccurrences(of: "_", with: " ").lowercased()) }
        if t.pending { parts.append("pending") }
        return parts.joined(separator: " · ")
    }
}

struct BanksSheet: View {
    @EnvironmentObject var state: AppState
    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            Text("banks").font(.system(size: 26)).foregroundStyle(Theme.title)
            if let accts = state.banks?.accounts, !accts.isEmpty {
                ForEach(accts) { a in
                    Toggle(isOn: Binding(get: { a.enabled }, set: { v in Task { await state.setAccount(a.id, enabled: v) } })) {
                        VStack(alignment: .leading, spacing: 2) {
                            Text(a.nickname.lowercased()).font(.system(size: 16)).foregroundStyle(Theme.title)
                            Text("\(a.bank.lowercased()) · \(a.mask)").font(.system(size: 12.5)).foregroundStyle(Theme.secondary)
                        }
                    }.tint(.white).frame(minHeight: 44)
                }
            } else {
                Text("no bank connected yet.").font(.system(size: 14.5)).foregroundStyle(Theme.secondary)
            }
            Spacer()
        }
        .padding(24).frame(maxWidth: .infinity, alignment: .leading)
        .presentationBackground(.regularMaterial).presentationDetents([.medium, .large]).presentationCornerRadius(28).presentationDragIndicator(.visible)
    }
}
