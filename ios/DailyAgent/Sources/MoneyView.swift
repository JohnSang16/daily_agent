import Charts
import SwiftUI

enum MoneyTab: String, CaseIterable, Identifiable {
    case overview, banks, income, activity, goals
    var id: String { rawValue }
}

/// Money: four views of the same data. Overview (spend vs income, goals), banks and holdings,
/// the income log, and the plain activity list.
struct MoneyView: View {
    @EnvironmentObject var state: AppState
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Namespace private var pick

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 26) {
                VStack(alignment: .leading, spacing: 4) {
                    BigTitle(text: "Money")
                    Text(state.summary.map { monthLong($0.thisMonth.month) } ?? " ").font(.system(size: 14.5)).foregroundStyle(Theme.secondary)
                        .contentTransition(.opacity)
                }
                tabs
                Group {
                    switch state.moneyTab {
                    case .overview: MoneyOverviewView()
                    case .banks: BanksView()
                    case .income: IncomeView()
                    case .activity: ActivityView()
                    case .goals: GoalsView()
                    }
                }
                .transition(.opacity)
                .id(state.moneyTab)
                if let p = state.problem, state.summary != nil { Text(p).font(.system(size: 12.5)).foregroundStyle(Theme.secondary) }
            }
            .page()
        }
        .scrollDismissesKeyboard(.interactively)
        .refreshable { await state.loadAllMoney() }
        .task { await state.loadAllMoney() }
    }

    private var tabs: some View {
        HStack(spacing: 4) {
            ForEach(MoneyTab.allCases) { t in
                Button { withAnimation(reduceMotion ? Theme.ease : Theme.spring) { state.moneyTab = t } } label: {
                    Text(t.rawValue).font(.system(size: 13, weight: state.moneyTab == t ? .medium : .regular))
                        .foregroundStyle(state.moneyTab == t ? Color.black : Theme.secondary)
                        .frame(maxWidth: .infinity, minHeight: 40)
                        .background {
                            if state.moneyTab == t {
                                Capsule().fill(LinearGradient(colors: [.white, Color(white: 0.84)], startPoint: .top, endPoint: .bottom))
                                    .matchedGeometryEffect(id: "money-tab", in: pick)
                            }
                        }
                }.buttonStyle(PressStyle())
            }
        }
        .padding(4).glass(Capsule())
        .sensoryFeedback(.selection, trigger: state.moneyTab)
    }
}

// MARK: overview

struct MoneyOverviewView: View {
    @EnvironmentObject var state: AppState
    @State private var editing: BudgetGoal?
    @State private var adding = false

    var body: some View {
        if let s = state.summary {
            VStack(alignment: .leading, spacing: 34) {
                thisMonth(s).reveal(0)
                chart(s).reveal(1)
                categories(s).reveal(2)
                goals.reveal(3)
            }
            .sheet(item: $editing) { g in BudgetSheet(existing: g, categories: s.categories.map(\.category)).environmentObject(state) }
            .sheet(isPresented: $adding) { BudgetSheet(existing: nil, categories: s.categories.map(\.category)).environmentObject(state) }
        } else {
            Text(state.waitingText).font(.system(size: 14.5)).foregroundStyle(Theme.secondary)
        }
    }

    private func thisMonth(_ s: MoneySummary) -> some View {
        HStack(alignment: .top, spacing: 0) {
            figure("spent", dollars(s.thisMonth.spendCents))
            figure("income", dollars(s.thisMonth.incomeCents))
            figure("net", (s.thisMonth.netCents >= 0 ? "+" : "") + dollars(s.thisMonth.netCents))
        }
    }

    private func figure(_ label: String, _ value: String) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            sectionLabel(label)
            Text(value).font(.system(size: 26, weight: .light)).monospacedDigit().foregroundStyle(Theme.title)
                .minimumScaleFactor(0.6).lineLimit(1).contentTransition(.numericText())
        }.frame(maxWidth: .infinity, alignment: .leading)
    }

    private func chart(_ s: MoneySummary) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 16) {
                sectionLabel("spend vs income, last 6 months")
                Spacer()
                legend("income", .white)
                legend("spend", Color(white: 0.45))
            }
            SpendIncomeChart(months: s.months)
        }
    }

    private func legend(_ text: String, _ c: Color) -> some View {
        HStack(spacing: 5) {
            Circle().fill(c).frame(width: 7, height: 7)
            Text(text).font(.system(size: 12)).foregroundStyle(Theme.secondary)
        }
    }

    private func categories(_ s: MoneySummary) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            sectionLabel("where it went this month")
            let top = max(s.categories.map(\.spendCents).max() ?? 1, 1)
            if s.categories.isEmpty { Text("nothing spent yet.").font(.system(size: 14.5)).foregroundStyle(Theme.secondary) }
            ForEach(s.categories) { c in
                VStack(alignment: .leading, spacing: 6) {
                    HStack {
                        Text(categoryLabel(c.category)).font(.system(size: 15)).foregroundStyle(Theme.title)
                        Spacer()
                        Text(dollars(c.spendCents)).font(.system(size: 15)).monospacedDigit().foregroundStyle(Theme.title)
                    }
                    Bar(fraction: Double(c.spendCents) / Double(top), strong: false)
                }
            }
        }
    }

    private var goals: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                sectionLabel("budget goals")
                Spacer()
                Button { adding = true } label: {
                    Label("add goal", systemImage: "plus").font(.system(size: 14)).foregroundStyle(Theme.title)
                        .padding(.horizontal, 14).frame(minHeight: 36).glass(Capsule()).frame(minHeight: 44)
                }.buttonStyle(PressStyle())
            }
            if state.budgets.isEmpty {
                Text("no goals yet. add a monthly limit for all spending or for one category.")
                    .font(.system(size: 14)).foregroundStyle(Theme.secondary)
            }
            ForEach(state.budgets) { g in
                let p = goalProgress(spent: g.spentCents, limit: g.limitCents)
                Button { editing = g } label: {
                    VStack(alignment: .leading, spacing: 7) {
                        HStack {
                            Text(categoryLabel(g.category)).font(.system(size: 15)).foregroundStyle(Theme.title)
                            Spacer()
                            Text("\(dollars(g.spentCents)) of \(dollars(g.limitCents))").font(.system(size: 13.5))
                                .foregroundStyle(p.over ? Theme.title : Theme.secondary)
                        }
                        Bar(fraction: p.fraction, strong: true)
                        Text(p.over ? "over by \(dollars(g.spentCents - g.limitCents))" : "\(dollars(g.limitCents - g.spentCents)) left")
                            .font(.system(size: 12)).foregroundStyle(p.over ? Theme.title : Theme.tertiary)
                    }.frame(maxWidth: .infinity, alignment: .leading)
                }.buttonStyle(PressStyle())
            }
        }
    }
}

/// A thin bar, white on a dark track. No color: "over" is said in words.
struct Bar: View {
    let fraction: Double
    let strong: Bool
    @State private var shown = false
    var body: some View {
        GeometryReader { geo in
            ZStack(alignment: .leading) {
                Capsule().fill(Theme.raised)
                Capsule().fill(strong ? Color.white : Theme.secondary)
                    .frame(width: max(4, geo.size.width * (shown ? fraction : 0)))
            }
        }
        .frame(height: 6)
        .animation(Theme.spring, value: fraction)
        .onAppear { withAnimation(Theme.spring.delay(0.1)) { shown = true } }
    }
}

struct SpendIncomeChart: View {
    let months: [MonthTotal]
    @State private var grown = false

    var body: some View {
        Chart {
            ForEach(months) { m in
                BarMark(x: .value("month", monthShort(m.month)), y: .value("income", grown ? Double(m.incomeCents) / 100 : 0))
                    .position(by: .value("kind", "income")).foregroundStyle(by: .value("kind", "income"))
                    .cornerRadius(4)
                BarMark(x: .value("month", monthShort(m.month)), y: .value("spend", grown ? Double(m.spendCents) / 100 : 0))
                    .position(by: .value("kind", "spend")).foregroundStyle(by: .value("kind", "spend"))
                    .cornerRadius(4)
            }
        }
        .chartForegroundStyleScale(["income": Color.white, "spend": Color(white: 0.45)])
        .chartLegend(.hidden)
        .chartYAxis {
            AxisMarks(position: .leading) { v in
                AxisGridLine().foregroundStyle(Theme.line)
                AxisValueLabel {
                    if let d = v.as(Double.self) { Text(d >= 1000 ? "\(Int(d / 1000))k" : "\(Int(d))").foregroundStyle(Theme.tertiary) }
                }
            }
        }
        .chartXAxis { AxisMarks { _ in AxisValueLabel().foregroundStyle(Theme.secondary) } }
        .frame(height: 190)
        .onAppear { withAnimation(Theme.spring.delay(0.15)) { grown = true } }
    }
}

struct BudgetSheet: View {
    @EnvironmentObject var state: AppState
    @Environment(\.dismiss) private var dismiss
    let existing: BudgetGoal?
    let categories: [String]
    @State private var category = "TOTAL"
    @State private var amount = ""
    @FocusState private var amountFocused: Bool

    private var cents: Int? { Int(amount.filter(\.isNumber)).flatMap { $0 > 0 ? $0 * 100 : nil } }

    private var choices: [String] {
        let common = ["FOOD_AND_DRINK", "GENERAL_MERCHANDISE", "TRANSPORTATION", "ENTERTAINMENT", "PERSONAL_CARE",
                      "GENERAL_SERVICES", "RENT_AND_UTILITIES", "TRAVEL", "MEDICAL", "HOME_IMPROVEMENT", "BANK_FEES"]
        var seen = Set<String>(), out = ["TOTAL"]
        for c in categories + common where !seen.contains(c) { seen.insert(c); out.append(c) }
        return out
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            sheetTitle(existing == nil ? "New goal" : "Edit goal")
            if existing == nil {
                Picker("", selection: $category) {
                    ForEach(choices, id: \.self) { Text(categoryLabel($0)).tag($0) }
                }.pickerStyle(.menu).tint(.white).padding(.leading, -12)
            } else {
                Text(categoryLabel(existing!.category)).font(.system(size: 18)).foregroundStyle(Theme.body)
            }
            sectionLabel("limit per month, in dollars")
            TextField("500", text: $amount).font(.system(size: 22)).foregroundStyle(Theme.title)
                #if os(iOS)
                .keyboardType(.numberPad)
                #endif
                .focused($amountFocused)
                .padding(.horizontal, 18).frame(minHeight: 48).glass(Capsule())
            HStack(spacing: 10) {
                PillButton(label: "save", primary: true, enabled: cents != nil, feedback: .success) {
                    guard let c = cents else { return }
                    let cat = existing?.category ?? category
                    dismiss(); Task { await state.saveBudget(cat, cents: c) }
                }
                if let e = existing {
                    PillButton(label: "delete goal", feedback: .warning) { dismiss(); Task { await state.deleteBudget(e.category) } }
                }
            }
            Spacer()
        }
        .padding(24).padding(.top, 8).frame(maxWidth: .infinity, alignment: .leading)
        .sheetChrome([.medium, .large])
        .onAppear {
            if let e = existing { amount = String(e.limitCents / 100) }
            amountFocused = true
        }
    }
}

// MARK: banks and holdings

struct BanksView: View {
    @EnvironmentObject var state: AppState

    var body: some View {
        VStack(alignment: .leading, spacing: 34) {
            if let h = state.summary?.holdings { holdings(h).reveal(0) }
            if let accts = state.banks?.accounts, !accts.isEmpty {
                ForEach(Array(groupBanks(accts).enumerated()), id: \.element.bank) { i, g in
                    VStack(alignment: .leading, spacing: 14) {
                        HStack {
                            Text(g.bank).font(.system(size: 18)).foregroundStyle(Theme.title)
                            Spacer()
                            Text(dollars(g.totalCents)).font(.system(size: 18)).monospacedDigit().foregroundStyle(Theme.title)
                        }
                        ForEach(g.accounts) { a in row(a) }
                    }.reveal(i + 1)
                }
            } else {
                Text("no bank connected yet.").font(.system(size: 14.5)).foregroundStyle(Theme.secondary)
            }
        }
    }

    private func holdings(_ h: Holdings) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            sectionLabel("where your money sits")
            line("cash", h.cashCents)
            line("savings", h.savingsCents)
            line("invested", h.investedCents)
            if h.creditOwedCents > 0 { line("owed on cards", -h.creditOwedCents) }
            if h.loansOwedCents > 0 { line("owed on loans", -h.loansOwedCents) }
            Divider().overlay(Theme.line)
            HStack {
                Text("net").font(.system(size: 18, weight: .medium)).foregroundStyle(Theme.title)
                Spacer()
                Text(dollars(h.netCents)).font(.system(size: 26, weight: .light)).foregroundStyle(Theme.title)
            }
        }
    }

    private func line(_ label: String, _ cents: Int) -> some View {
        HStack {
            Text(label).font(.system(size: 15)).foregroundStyle(Theme.body)
            Spacer()
            Text(dollars(cents)).font(.system(size: 15)).monospacedDigit().foregroundStyle(Theme.title)
        }
    }

    private func row(_ a: BankAccountInfo) -> some View {
        HStack(alignment: .center) {
            VStack(alignment: .leading, spacing: 3) {
                Text(a.nickname.lowercased()).font(.system(size: 15)).foregroundStyle(a.enabled ? Theme.title : Theme.tertiary)
                Text("\(accountKindLabel(a)) · \(a.mask)" + (isOwed(a) ? " · owed" : ""))
                    .font(.system(size: 12.5)).foregroundStyle(Theme.secondary)
            }
            Spacer()
            Text(a.balanceCents.map(dollars) ?? "-").font(.system(size: 15)).monospacedDigit().foregroundStyle(a.enabled ? Theme.title : Theme.tertiary)
            Toggle("", isOn: Binding(get: { a.enabled }, set: { v in Task { await state.setAccount(a.id, enabled: v) } }))
                .labelsHidden().tint(Theme.toggle).frame(width: 52)
        }.frame(minHeight: 44)
    }
}

// MARK: income log

struct IncomeView: View {
    @EnvironmentObject var state: AppState

    var body: some View {
        VStack(alignment: .leading, spacing: 30) {
            if let s = state.summary {
                let total = s.months.map(\.incomeCents).reduce(0, +)
                let counted = max(s.months.filter { $0.incomeCents > 0 }.count, 1)
                HStack(alignment: .top, spacing: 0) {
                    figure("this month", dollars(s.thisMonth.incomeCents))
                    figure("average a month", dollars(total / counted))
                }.reveal(0)
            }
            let groups = incomeByMonth(state.incomeRows)
            if groups.isEmpty {
                Text("no income logged yet.").font(.system(size: 14.5)).foregroundStyle(Theme.secondary)
            }
            ForEach(Array(groups.enumerated()), id: \.element.month) { i, g in
                VStack(alignment: .leading, spacing: 14) {
                    HStack {
                        sectionLabel(monthLong(g.month))
                        Spacer()
                        Text("+" + dollars(g.totalCents)).font(.system(size: 13)).foregroundStyle(Theme.secondary)
                    }
                    ForEach(g.items) { t in
                        HStack(alignment: .top) {
                            VStack(alignment: .leading, spacing: 3) {
                                Text(t.merchant).font(.system(size: 16)).foregroundStyle(Theme.title)
                                Text("\(t.date) · \(t.bank)").font(.system(size: 12.5)).foregroundStyle(Theme.secondary)
                            }
                            Spacer()
                            Text(t.amount).font(.system(size: 16)).monospacedDigit().foregroundStyle(Theme.title)
                        }
                    }
                }.reveal(i + 1)
            }
        }
    }

    private func figure(_ label: String, _ value: String) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            sectionLabel(label)
            Text(value).font(.system(size: 26, weight: .light)).monospacedDigit().foregroundStyle(Theme.title)
                .minimumScaleFactor(0.6).lineLimit(1)
        }.frame(maxWidth: .infinity, alignment: .leading)
    }
}

// MARK: activity (the plain transaction list)

struct ActivityView: View {
    @EnvironmentObject var state: AppState
    @State private var showBanks = false

    var body: some View {
        VStack(alignment: .leading, spacing: 22) {
            Button { showBanks = true } label: {
                Text(state.banks?.chip ?? "banks: all").font(.system(size: 13.5)).foregroundStyle(Theme.body)
                    .padding(.horizontal, 16).frame(minHeight: 44).glass(Capsule())
            }.buttonStyle(PressStyle())
            if let note = state.page?.note { Text(note).font(.system(size: 12.5)).foregroundStyle(Theme.secondary) }
            if let page = state.page {
                ForEach(groupByDay(page.transactions, now: Date()), id: \.heading) { g in
                    VStack(alignment: .leading, spacing: 14) {
                        sectionLabel(g.heading)
                        ForEach(g.items) { t in
                            HStack(alignment: .top) {
                                VStack(alignment: .leading, spacing: 3) {
                                    Text(t.merchant).font(.system(size: 16)).foregroundStyle(Theme.title)
                                    Text(subline(t)).font(.system(size: 12.5)).foregroundStyle(Theme.secondary)
                                }
                                Spacer()
                                Text(t.amount).font(.system(size: 16)).monospacedDigit().foregroundStyle(Theme.title)
                            }
                        }
                    }
                }
            } else {
                Text(state.waitingText).font(.system(size: 14.5)).foregroundStyle(Theme.secondary)
            }
        }
        .sheet(isPresented: $showBanks) { BanksSheet().environmentObject(state) }
    }

    private func subline(_ t: Txn) -> String {
        var parts = [t.bank]
        if let c = t.category { parts.append(categoryLabel(c)) }
        if t.pending { parts.append("pending") }
        return parts.joined(separator: " · ")
    }
}

struct BanksSheet: View {
    @EnvironmentObject var state: AppState
    var body: some View {
        ScrollView {
        VStack(alignment: .leading, spacing: 18) {
            sheetTitle("Banks")
            if let accts = state.banks?.accounts, !accts.isEmpty {
                ForEach(accts) { a in
                    Toggle(isOn: Binding(get: { a.enabled }, set: { v in Task { await state.setAccount(a.id, enabled: v) } })) {
                        VStack(alignment: .leading, spacing: 2) {
                            Text(a.nickname.lowercased()).font(.system(size: 16)).foregroundStyle(Theme.title)
                            Text("\(a.bank) · \(a.mask)").font(.system(size: 12.5)).foregroundStyle(Theme.secondary)
                        }
                    }.tint(Theme.toggle).frame(minHeight: 44)
                }
            } else {
                Text("no bank connected yet.").font(.system(size: 14.5)).foregroundStyle(Theme.secondary)
            }
        }
        .padding(24).padding(.top, 8).frame(maxWidth: .infinity, alignment: .leading)
        }
        .sheetChrome()
    }
}

// MARK: goals

private func dueDate(_ s: String) -> Date? {
    let f = DateFormatter(); f.locale = Locale(identifier: "en_US_POSIX"); f.dateFormat = "yyyy-MM-dd"
    return f.date(from: s)
}

private func daysLeft(_ due: String) -> Int {
    guard let d = dueDate(due) else { return 0 }
    let cal = Calendar.current
    return max(cal.dateComponents([.day], from: cal.startOfDay(for: Date()), to: d).day ?? 0, 0)
}

/// "2026" for a year end, "spring" or "summer" for those seasons, else the short month.
private func seasonLabel(_ due: String) -> String {
    guard let d = dueDate(due) else { return due }
    let c = Calendar.current.dateComponents([.year, .month], from: d)
    switch c.month ?? 0 {
    case 12: return String(c.year ?? 0)
    case 3...6: return "spring"
    case 7...9: return "summer"
    default:
        let f = DateFormatter(); f.dateFormat = "MMM"; return f.string(from: d).lowercased()
    }
}

private func shortDue(_ due: String) -> String {
    guard let d = dueDate(due) else { return due }
    let f = DateFormatter(); f.locale = Locale(identifier: "en_US_POSIX"); f.dateFormat = "MMM d"
    return f.string(from: d).lowercased()
}

private func compact(_ cents: Int) -> String {
    cents >= 100_000_00 && cents % 100_000 == 0 ? "$\(cents / 100_000)k" : dollars(cents)
}

/// The stretch goal: big number, bar with a tick at the floor, days left. Used on the dashboard too.
struct StretchCard: View {
    let goal: MoneyGoal
    var link = false

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            sectionLabel("stretch · provide value worth the number")
            HStack(alignment: .firstTextBaseline) {
                (Text(dollars(goal.currentCents)).font(.system(size: link ? 24 : 34, weight: link ? .regular : .light))
                    .foregroundColor(Theme.title)
                    + Text(" / \(dollars(goal.targetCents))").font(.system(size: link ? 13 : 14)).foregroundColor(Theme.body))
                    .monospacedDigit().lineLimit(1).minimumScaleFactor(0.7)
                Spacer()
                if link { Text("goals →").font(.system(size: 13)).foregroundStyle(Theme.title) }
            }
            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    Bar(fraction: goal.fraction, strong: true)
                    if let f = goal.floorCents, goal.targetCents > 0 {
                        Rectangle().fill(Theme.secondary).frame(width: 1.4, height: 12)
                            .offset(x: geo.size.width * Double(f) / Double(goal.targetCents))
                    }
                }
            }.frame(height: 12).padding(.top, 4)
            HStack {
                if let f = goal.floorCents { Text("floor \(compact(f))") }
                Spacer()
                Text("\(daysLeft(goal.due)) days left")
            }.font(.system(size: 12)).foregroundStyle(Theme.body)
        }
        .padding(link ? 18 : 0)
        .background { if link { RoundedRectangle(cornerRadius: 22).fill(Color.white.opacity(0.05)) } }
        .overlay { if link { RoundedRectangle(cornerRadius: 22).strokeBorder(Color.white.opacity(0.09)) } }
        .accessibilityElement(children: .combine)
    }
}

struct GoalsView: View {
    @EnvironmentObject var state: AppState
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var season = 0
    @State private var editing: BudgetGoal?
    @State private var adding = false
    @Namespace private var pick

    var body: some View {
        VStack(alignment: .leading, spacing: 30) {
            if let s = state.moneyGoals?.stretch { StretchCard(goal: s).reveal(0) }
            budget.reveal(1)
            goals.reveal(2)
        }
        .sheet(item: $editing) { g in BudgetSheet(existing: g, categories: cats).environmentObject(state) }
        .sheet(isPresented: $adding) { BudgetSheet(existing: nil, categories: cats).environmentObject(state) }
    }

    private var cats: [String] { state.summary?.categories.map(\.category) ?? [] }

    private var budget: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                sectionLabel("budget")
                Spacer()
                Button { adding = true } label: { Text("+ add").font(.system(size: 13)).foregroundStyle(Theme.title).frame(minHeight: 44) }
                    .buttonStyle(PressStyle())
            }
            if state.budgets.isEmpty {
                Text("no budget yet.").font(.system(size: 14)).foregroundStyle(Theme.secondary)
            }
            LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 14, alignment: .leading), count: 3), spacing: 18) {
                ForEach(state.budgets) { g in
                    let left = g.limitCents - g.spentCents
                    Button { editing = g } label: {
                        VStack(alignment: .leading, spacing: 4) {
                            (Text(left >= 0 ? dollars(left) : "over").font(.system(size: 24)).foregroundColor(Theme.title)
                                + Text(" / \(dollars(g.limitCents))").font(.system(size: 13)).foregroundColor(Theme.body))
                                .monospacedDigit().lineLimit(1).minimumScaleFactor(0.6)
                            Text(categoryLabel(g.category)).font(.system(size: 13)).foregroundStyle(Theme.body).lineLimit(1)
                            Bar(fraction: max(Double(left), 0) / Double(max(g.limitCents, 1)), strong: true).padding(.top, 4)
                        }.frame(maxWidth: .infinity, alignment: .leading)
                    }.buttonStyle(PressStyle())
                }
            }
        }
    }

    private var goals: some View {
        let seasons = state.moneyGoals?.seasons ?? []
        let i = min(season, max(seasons.count - 1, 0))
        return VStack(alignment: .leading, spacing: 14) {
            sectionLabel("goals")
            if seasons.isEmpty {
                Text("no goals yet.").font(.system(size: 14)).foregroundStyle(Theme.secondary)
            } else {
                HStack(spacing: 2) {
                    ForEach(Array(seasons.enumerated()), id: \.element.id) { n, s in
                        Button { withAnimation(reduceMotion ? Theme.ease : Theme.spring) { season = n } } label: {
                            Text(seasonLabel(s.due)).font(.system(size: 13, weight: i == n ? .medium : .regular))
                                .foregroundStyle(i == n ? Color.black : Theme.secondary)
                                .frame(maxWidth: .infinity, minHeight: 36)
                                .background {
                                    if i == n {
                                        Capsule().fill(LinearGradient(colors: [.white, Color(white: 0.84)], startPoint: .top, endPoint: .bottom))
                                            .matchedGeometryEffect(id: "season", in: pick)
                                    }
                                }
                        }.buttonStyle(PressStyle())
                    }
                }
                .padding(4).glass(Capsule())
                .sensoryFeedback(.selection, trigger: season)
                Text("\(shortDue(seasons[i].due)) · \(daysLeft(seasons[i].due)) days left")
                    .font(.system(size: 12)).foregroundStyle(Theme.body)
                VStack(spacing: 0) {
                    ForEach(seasons[i].goals) { g in row(g) }
                }
                .id(i).transition(.opacity)
            }
        }
    }

    private func row(_ g: MoneyGoal) -> some View {
        let cards = g.kind == "cards_owed"
        return VStack(alignment: .leading, spacing: 9) {
            HStack(alignment: .firstTextBaseline) {
                Text(g.name).font(.system(size: 16)).foregroundStyle(Theme.title)
                Spacer()
                Text(cards ? "\(dollars(g.currentCents)) owed" : "\(dollars(g.currentCents)) of \(dollars(g.targetCents))")
                    .font(.system(size: 14)).monospacedDigit().foregroundStyle(Theme.title)
            }
            Bar(fraction: g.fraction, strong: true)
            Text(g.met ? (cards ? "clear" : "hit") : cards ? "pay it off" : "\(dollars(g.targetCents - g.currentCents)) to go · \(Int((g.fraction * 100).rounded()))%")
                .font(.system(size: 12)).foregroundStyle(Theme.body)
        }
        .padding(.vertical, 14)
        .accessibilityElement(children: .combine)
    }
}
