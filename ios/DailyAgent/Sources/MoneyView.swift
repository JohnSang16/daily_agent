import Charts
import SwiftUI

enum MoneyTab: String, CaseIterable, Identifiable {
    case overview, banks, activity
    var id: String { rawValue }
}

/// Stocks-style range picker. Plaid transactions are date only (no time of day), so there's no
/// real sub-day data: 7D/1M read the daily series, 3M/1Y/ALL read the monthly totals.
enum MoneyRange: String, CaseIterable, Identifiable {
    case d7 = "7D", m1 = "1M", m3 = "3M", y1 = "1Y", all = "ALL"
    var id: String { rawValue }

    /// Non-nil for the two daily-resolution ranges: how many days AppState should fetch.
    var dailyDays: Int? {
        switch self {
        case .d7: return 7
        case .m1: return 31
        case .m3, .y1, .all: return nil
        }
    }

    /// Non-nil for the three month-resolution ranges: how many trailing months to show.
    /// `.all` is nil meaning "everything already loaded", not a magic large number.
    var monthCount: Int? {
        switch self {
        case .m3: return 3
        case .y1: return 12
        case .d7, .m1, .all: return nil
        }
    }

    var label: String {
        switch self {
        case .d7: return "spent, last 7 days"
        case .m1: return "spent, last 30 days"
        case .m3: return "spent, last 3 months"
        case .y1: return "spent, last year"
        case .all: return "spent, all time"
        }
    }
}

struct TrendPoint: Identifiable {
    let id: String
    let date: Date
    let cents: Int
}

/// Money: three views of the same data. Overview (spend trend, categories, goals), banks and
/// net worth, and the activity list (search and filters, income included).
struct MoneyView: View {
    @EnvironmentObject var state: AppState
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var tab: MoneyTab = .overview
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
                    switch tab {
                    case .overview: MoneyOverviewView()
                    case .banks: BanksView()
                    case .activity: ActivityView()
                    }
                }
                .transition(.opacity)
                .id(tab)
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
                Button { withAnimation(reduceMotion ? Theme.ease : Theme.spring) { tab = t } } label: {
                    Text(t.rawValue).font(.system(size: 14, weight: tab == t ? .medium : .regular))
                        .foregroundStyle(tab == t ? Color.black : Theme.secondary)
                        .frame(maxWidth: .infinity, minHeight: 40)
                        .background {
                            if tab == t {
                                Capsule().fill(LinearGradient(colors: [.white, Color(white: 0.84)], startPoint: .top, endPoint: .bottom))
                                    .matchedGeometryEffect(id: "money-tab", in: pick)
                            }
                        }
                }.buttonStyle(PressStyle())
            }
        }
        .padding(4).glass(Capsule())
        .sensoryFeedback(.selection, trigger: tab)
    }
}

// MARK: overview

struct MoneyOverviewView: View {
    @EnvironmentObject var state: AppState
    @State private var editing: BudgetGoal?
    @State private var adding = false
    @State private var range: MoneyRange = .m1
    @State private var dailyDaysLoaded = 31  // matches AppState's default fetch, so .m1 needs no refetch
    @Namespace private var heroPick

    var body: some View {
        if let s = state.summary {
            VStack(alignment: .leading, spacing: 34) {
                heroCard(s).reveal(0)
                categories(s).reveal(1)
                goals.reveal(2)
            }
            .sheet(item: $editing) { g in BudgetSheet(existing: g, categories: s.categories.map(\.category)).environmentObject(state) }
            .sheet(isPresented: $adding) { BudgetSheet(existing: nil, categories: s.categories.map(\.category)).environmentObject(state) }
        } else {
            Text(state.waitingText).font(.system(size: 14.5)).foregroundStyle(Theme.secondary)
        }
    }

    private func heroCard(_ s: MoneySummary) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            sectionLabel(range.label)
            Text(dollars(rangeSpendCents(s)))
                .font(.system(size: 34, weight: .light))
                .monospacedDigit().foregroundStyle(Theme.title).contentTransition(.numericText())
            TrendLineChart(points: heroPoints(s), monthly: range == .m3 || range == .y1 || range == .all)
            heroToggle
            HStack {
                if let line = averageComparisonLine(current: s.thisMonth.spendCents, others: s.months.dropLast().map(\.spendCents)) {
                    Text(line).font(.system(size: 12)).foregroundStyle(Theme.secondary)
                }
                Spacer()
                Text("income \(dollars(s.thisMonth.incomeCents)) · net \(s.thisMonth.netCents >= 0 ? "+" : "")\(dollars(s.thisMonth.netCents))")
                    .font(.system(size: 12)).foregroundStyle(Theme.secondary)
            }
        }
        .padding(18)
        .glass(RoundedRectangle(cornerRadius: 22, style: .continuous))
    }

    /// Full width, equal segments. Squeezed next to the header label instead, 5 of them had no
    /// room left over and truncated to "..." (confirmed with an offscreen render before this fix).
    private var heroToggle: some View {
        HStack(spacing: 2) {
            ForEach(MoneyRange.allCases) { m in
                Button {
                    withAnimation(Theme.spring) { range = m }
                    if let days = m.dailyDays, days != dailyDaysLoaded {
                        dailyDaysLoaded = days
                        Task { await state.loadMoneyDaily(days: days) }
                    }
                } label: {
                    Text(m.rawValue).font(.system(size: 12, weight: range == m ? .medium : .regular))
                        .foregroundStyle(range == m ? Color.black : Theme.secondary)
                        .frame(maxWidth: .infinity, minHeight: 30)
                        .background {
                            if range == m {
                                Capsule().fill(Color.white).matchedGeometryEffect(id: "hero-mode", in: heroPick)
                            }
                        }
                }.buttonStyle(PressStyle())
            }
        }
        .padding(2).glass(Capsule())
    }

    /// AppState keeps `daily` re-anchored to whichever window was last requested (7 or 31 days),
    /// so 7D/1M read it straight; the month ranges slice the already-loaded `months` history.
    private func heroPoints(_ s: MoneySummary) -> [TrendPoint] {
        switch range {
        case .d7, .m1:
            return s.daily.map { TrendPoint(id: $0.date, date: plainDate($0.date) ?? Date(), cents: $0.cumulativeSpendCents) }
        case .m3, .y1, .all:
            let months = s.months.suffix(range.monthCount ?? s.months.count)
            return months.map { TrendPoint(id: $0.month, date: plainDate($0.month) ?? Date(), cents: $0.spendCents) }
        }
    }

    private func rangeSpendCents(_ s: MoneySummary) -> Int {
        switch range {
        case .d7, .m1:
            return s.daily.last?.cumulativeSpendCents ?? 0
        case .m3, .y1, .all:
            return s.months.suffix(range.monthCount ?? s.months.count).reduce(0) { $0 + $1.spendCents }
        }
    }

    /// White down to darker grays; "other" always takes the darkest.
    private func donutGray(_ i: Int, _ c: CategorySpend) -> Color {
        let ramp: [Color] = [.white, Color(white: 0.78), Color(white: 0.6), Color(white: 0.46), Color(white: 0.34)]
        return c.category == "OTHER" ? Color(white: 0.24) : ramp[i % ramp.count]
    }

    private func categories(_ s: MoneySummary) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            sectionLabel("where it went this month")
            if s.categories.isEmpty {
                Text("nothing spent yet.").font(.system(size: 14.5)).foregroundStyle(Theme.secondary)
            } else {
                let buckets = Array(topCategoriesWithOther(s.categories).enumerated())
                HStack(alignment: .center, spacing: 18) {
                    Chart(buckets, id: \.offset) { i, c in
                        SectorMark(angle: .value("spend", c.spendCents), innerRadius: .ratio(0.65), angularInset: 1.5)
                            .foregroundStyle(donutGray(i, c))
                            .cornerRadius(3)
                    }
                    .chartLegend(.hidden)
                    .frame(width: 96, height: 96)
                    VStack(alignment: .leading, spacing: 8) {
                        ForEach(buckets, id: \.offset) { i, c in
                            HStack {
                                Circle().fill(donutGray(i, c)).frame(width: 7, height: 7)
                                Text(categoryLabel(c.category)).font(.system(size: 13.5)).foregroundStyle(Theme.title)
                                    .lineLimit(1)
                                Spacer()
                                Text(dollars(c.spendCents)).font(.system(size: 13.5)).monospacedDigit().foregroundStyle(Theme.title)
                            }
                        }
                    }
                }
            }
        }
    }

    private var goals: some View {
        VStack(alignment: .leading, spacing: 16) {
            sectionLabel("budget goals")
            if state.budgets.isEmpty {
                Text("no goals yet. add a monthly limit for all spending or for one category.")
                    .font(.system(size: 14)).foregroundStyle(Theme.secondary)
            }
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 20) {
                    ForEach(state.budgets) { g in
                        let p = goalProgress(spent: g.spentCents, limit: g.limitCents)
                        Button { editing = g } label: { RingGauge(fraction: p.fraction, label: categoryLabel(g.category)) }
                            .buttonStyle(PressStyle())
                    }
                    Button { adding = true } label: {
                        VStack(spacing: 6) {
                            ZStack {
                                Circle().stroke(Theme.raised, lineWidth: 8).frame(width: 78, height: 78)
                                Image(systemName: "plus").font(.system(size: 18)).foregroundStyle(Theme.secondary)
                            }
                            Text("add goal").font(.system(size: 12)).foregroundStyle(Theme.secondary)
                        }
                    }.buttonStyle(PressStyle())
                }
                .padding(.horizontal, 2).padding(.vertical, 4)
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

struct RingGauge: View {
    let fraction: Double
    let label: String
    @State private var shown = false

    var body: some View {
        VStack(spacing: 6) {
            ZStack {
                Circle().stroke(Theme.raised, lineWidth: 8)
                Circle().trim(from: 0, to: shown ? min(fraction, 1) : 0)
                    .stroke(Color.white, style: StrokeStyle(lineWidth: 8, lineCap: .round))
                    .rotationEffect(.degrees(-90))
                Text("\(Int((fraction * 100).rounded()))%").font(.system(size: 15)).monospacedDigit().foregroundStyle(Theme.title)
            }
            .frame(width: 78, height: 78)
            Text(label).font(.system(size: 12)).foregroundStyle(Theme.secondary).lineLimit(1).frame(maxWidth: 90)
        }
        .animation(Theme.spring, value: fraction)
        .onAppear { withAnimation(Theme.spring.delay(0.1)) { shown = true } }
    }
}

struct TrendLineChart: View {
    let points: [TrendPoint]
    let monthly: Bool
    @State private var grown = false

    var body: some View {
        Chart {
            ForEach(points) { p in
                AreaMark(x: .value("day", p.date), y: .value("spend", grown ? Double(p.cents) / 100 : 0))
                    .foregroundStyle(LinearGradient(colors: [Color.white.opacity(0.3), Color.white.opacity(0)], startPoint: .top, endPoint: .bottom))
                LineMark(x: .value("day", p.date), y: .value("spend", grown ? Double(p.cents) / 100 : 0))
                    .foregroundStyle(Color.white)
                    .lineStyle(StrokeStyle(lineWidth: 2))
            }
        }
        .chartLegend(.hidden)
        .chartYAxis {
            AxisMarks(position: .leading, values: .automatic(desiredCount: 4)) { v in
                AxisGridLine().foregroundStyle(Theme.line)
                AxisValueLabel {
                    if let d = v.as(Double.self) { Text(d >= 1000 ? "\(Int(d / 1000))k" : "\(Int(d))").foregroundStyle(Theme.tertiary) }
                }
            }
        }
        // a Date x-axis thins itself properly; the String axis this replaced just listed every
        // single category with no spacing, since a nominal scale has nothing to sample between
        .chartXAxis {
            AxisMarks(values: .automatic(desiredCount: 4)) { _ in
                AxisValueLabel(format: monthly ? .dateTime.month(.abbreviated).year(.twoDigits) : .dateTime.month(.abbreviated).day())
                    .foregroundStyle(Theme.secondary)
            }
        }
        .frame(height: 120)
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
        VStack(alignment: .leading, spacing: 22) {
            if let h = state.summary?.holdings { netWorthCard(h).reveal(0) }
            if let accts = state.banks?.accounts, !accts.isEmpty {
                ForEach(Array(groupBanks(accts).enumerated()), id: \.element.bank) { i, g in
                    VStack(alignment: .leading, spacing: 4) {
                        HStack {
                            Text(g.bank.lowercased()).font(.system(size: 17)).foregroundStyle(Theme.title)
                            Spacer()
                            Text(dollars(g.totalCents)).font(.system(size: 17)).monospacedDigit().foregroundStyle(Theme.title)
                        }.padding(.bottom, 4)
                        ForEach(g.accounts) { a in row(a) }
                    }
                    .padding(18)
                    .glass(RoundedRectangle(cornerRadius: 22, style: .continuous))
                    .reveal(i + 1)
                }
            } else {
                Text("no bank connected yet.").font(.system(size: 14.5)).foregroundStyle(Theme.secondary)
            }
        }
    }

    private static let shades: [Color] = [.white, Color(white: 0.71), Color(white: 0.42)]

    private func netWorthCard(_ h: Holdings) -> some View {
        let sh = holdingShares(h)
        let parts: [(String, Int, Double)] = [("cash", h.cashCents, sh.cash), ("savings", h.savingsCents, sh.savings), ("invested", h.investedCents, sh.invested)]
        return VStack(alignment: .leading, spacing: 14) {
            VStack(alignment: .leading, spacing: 6) {
                sectionLabel("net worth")
                Text(dollars(h.netCents)).font(.system(size: 34, weight: .light)).monospacedDigit()
                    .foregroundStyle(Theme.title).contentTransition(.numericText())
            }
            ShareBar(fractions: parts.map(\.2), colors: Self.shades)
            HStack(spacing: 0) {
                ForEach(Array(parts.enumerated()), id: \.offset) { i, p in
                    HStack(spacing: 5) {
                        Circle().fill(Self.shades[i]).frame(width: 7, height: 7)
                        Text("\(p.0) \(dollars(p.1))").font(.system(size: 12)).monospacedDigit().foregroundStyle(Theme.secondary)
                            .lineLimit(1).minimumScaleFactor(0.8)
                    }.frame(maxWidth: .infinity, alignment: i == 0 ? .leading : (i == 2 ? .trailing : .center))
                }
            }
            if h.creditOwedCents > 0 || h.loansOwedCents > 0 {
                Divider().overlay(Theme.line)
                if h.creditOwedCents > 0 { owed("owed on cards", h.creditOwedCents) }
                if h.loansOwedCents > 0 { owed("owed on loans", h.loansOwedCents) }
            }
        }
        .padding(18)
        .glass(RoundedRectangle(cornerRadius: 22, style: .continuous))
    }

    private func owed(_ label: String, _ cents: Int) -> some View {
        HStack {
            Text(label).font(.system(size: 12.5)).foregroundStyle(Theme.secondary)
            Spacer()
            Text(dollars(-cents)).font(.system(size: 13.5)).monospacedDigit().foregroundStyle(Theme.title)
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

/// One rounded bar split into shares, grows in from the left.
struct ShareBar: View {
    let fractions: [Double]
    let colors: [Color]
    @State private var shown = false

    var body: some View {
        GeometryReader { geo in
            HStack(spacing: 2) {
                ForEach(Array(fractions.enumerated()), id: \.offset) { i, f in
                    if f > 0 {
                        Rectangle().fill(colors[i % colors.count])
                            .frame(width: max(2, (geo.size.width - 4) * f * (shown ? 1 : 0)))
                    }
                }
                Spacer(minLength: 0)
            }
            .background(Theme.raised)
            .clipShape(Capsule())
        }
        .frame(height: 10)
        .onAppear { withAnimation(Theme.spring.delay(0.1)) { shown = true } }
    }
}

/// A category's symbol in a dark round chip.
struct CategoryIcon: View {
    let category: String?
    var body: some View {
        Image(systemName: categoryIcon(category)).font(.system(size: 14)).foregroundStyle(Theme.body)
            .frame(width: 36, height: 36)
            .background(Circle().fill(Theme.raised))
            .overlay(Circle().strokeBorder(Theme.line, lineWidth: 0.8))
            .accessibilityHidden(true)
    }
}

// MARK: activity (the plain transaction list)

struct ActivityView: View {
    @EnvironmentObject var state: AppState
    @State private var showBanks = false
    @State private var filter: ActivityFilter = .all
    @State private var day: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 22) {
            if let s = state.summary, !s.daily.isEmpty {
                SpendCalendar(daily: s.daily, monthCents: s.thisMonth.spendCents, selected: $day).reveal(0)
            }
            if let r = state.recurring, !r.items.isEmpty { recurringRow(r).reveal(1) }
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 8) {
                    if let d = day {
                        Button { withAnimation(Theme.spring) { day = nil } } label: {
                            chip(shortDay(d), on: true, icon: "xmark")
                        }.buttonStyle(PressStyle()).accessibilityLabel("show every day")
                    }
                    ForEach(ActivityFilter.allCases) { f in
                        Button { withAnimation(Theme.spring) { filter = f } } label: { chip(f.rawValue, on: filter == f) }
                            .buttonStyle(PressStyle())
                    }
                    Button { showBanks = true } label: { chip(state.banks?.chip ?? "banks: all", on: false) }
                        .buttonStyle(PressStyle())
                }
            }
            .sensoryFeedback(.selection, trigger: filter)
            if let note = state.page?.note { Text(note).font(.system(size: 12.5)).foregroundStyle(Theme.secondary) }
            if let page = state.page {
                let shown = filterTxns(page.transactions, filter: filter, day: day)
                if shown.isEmpty {
                    Text(day == nil ? "nothing here yet." : "nothing on \(shortDay(day!)).")
                        .font(.system(size: 14.5)).foregroundStyle(Theme.secondary)
                }
                ForEach(groupByDay(shown, now: Date()), id: \.heading) { g in
                    VStack(alignment: .leading, spacing: 14) {
                        HStack {
                            sectionLabel(g.heading)
                            Spacer()
                            Text(dollarsAndCents(netCents(g.items), signed: true)).font(.system(size: 12.5)).monospacedDigit()
                                .foregroundStyle(Theme.secondary)
                        }
                        ForEach(g.items) { t in
                            HStack(alignment: .center, spacing: 12) {
                                CategoryIcon(category: t.category)
                                VStack(alignment: .leading, spacing: 3) {
                                    Text(t.merchant).font(.system(size: 16)).foregroundStyle(Theme.title).lineLimit(1)
                                    Text(subline(t)).font(.system(size: 12.5)).foregroundStyle(Theme.secondary).lineLimit(1)
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

    private func recurringRow(_ r: Recurring) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                sectionLabel("recurring")
                Spacer()
                Text("\(dollars(r.monthlyCents)) / mo").font(.system(size: 12)).monospacedDigit().foregroundStyle(Theme.secondary)
            }
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 8) {
                    ForEach(r.items) { item in
                        VStack(alignment: .leading, spacing: 2) {
                            HStack(spacing: 10) {
                                Text(item.merchant.lowercased()).font(.system(size: 12.5)).foregroundStyle(Theme.title).lineLimit(1)
                                Spacer(minLength: 0)
                                Image(systemName: categoryIcon(item.category)).font(.system(size: 10.5)).foregroundStyle(Theme.tertiary)
                            }
                            Text(dollars(item.amountCents)).font(.system(size: 15, weight: .light)).monospacedDigit().foregroundStyle(Theme.title)
                            Text(item.paidThisMonth ? "paid \(shortDay(item.lastDate))" : "due \(shortDay(item.nextDate))")
                                .font(.system(size: 11)).foregroundStyle(Theme.tertiary)
                        }
                        .padding(.horizontal, 12).padding(.vertical, 9)
                        .frame(minWidth: 96, alignment: .leading)
                        .glass(RoundedRectangle(cornerRadius: 14, style: .continuous))
                    }
                }
                .padding(.vertical, 1)
            }
        }
    }

    private func chip(_ text: String, on: Bool, icon: String? = nil) -> some View {
        HStack(spacing: 5) {
            Text(text)
            if let icon { Image(systemName: icon).font(.system(size: 10, weight: .semibold)) }
        }
        .font(.system(size: 13, weight: on ? .medium : .regular))
        .foregroundStyle(on ? Color.black : Theme.body)
        .padding(.horizontal, 14).frame(minHeight: 36)
        .background { if on { Capsule().fill(Color.white) } }
        .overlay { if !on { Capsule().strokeBorder(Color(white: 0.18), lineWidth: 1) } }
        .frame(minHeight: 44)
    }

    private func subline(_ t: Txn) -> String {
        var parts: [String] = []
        if let c = t.category { parts.append(categoryLabel(c)) }
        parts.append(t.bank)
        if t.pending { parts.append("pending") }
        return parts.joined(separator: " · ")
    }
}

/// This month as a monday first grid, each day shaded by what was spent. Tap a day to show only it.
struct SpendCalendar: View {
    let daily: [DailyPoint]
    let monthCents: Int
    @Binding var selected: String?

    private let cols = Array(repeating: GridItem(.flexible(), spacing: 5), count: 7)

    var body: some View {
        let days = dailySpend(daily)
        let top = max(days.map(\.cents).max() ?? 0, 1)
        let biggest = days.max { $0.cents < $1.cents }
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                sectionLabel("spending by day")
                Spacer()
                Text(dollars(monthCents)).font(.system(size: 12)).monospacedDigit().foregroundStyle(Theme.secondary)
            }
            LazyVGrid(columns: cols, spacing: 5) {
                ForEach(Array(["m", "t", "w", "t", "f", "s", "s"].enumerated()), id: \.offset) { _, d in
                    Text(d).font(.system(size: 11)).foregroundStyle(Theme.tertiary)
                }
                ForEach(0..<leadingBlanks(daily[0].date), id: \.self) { _ in Color.clear.frame(height: 1) }
                ForEach(days, id: \.date) { d in
                    let x = Double(d.cents) / Double(top)
                    let on = selected == d.date
                    Button {
                        withAnimation(Theme.spring) { selected = on ? nil : d.date }
                    } label: {
                        Text("\(Int(d.date.suffix(2)) ?? 0)").font(.system(size: 11)).monospacedDigit()
                            .foregroundStyle(x > 0.5 ? Color.black : (on ? Theme.title : Theme.secondary))
                            .frame(maxWidth: .infinity).aspectRatio(1, contentMode: .fit)
                            .background(RoundedRectangle(cornerRadius: 8, style: .continuous).fill(Color.white.opacity(x * 0.85)))
                            .overlay {
                                if on { RoundedRectangle(cornerRadius: 8, style: .continuous).strokeBorder(Color.white, lineWidth: 1.5) }
                            }
                    }
                    .buttonStyle(PressStyle())
                    .accessibilityLabel("\(shortDay(d.date)), \(dollars(d.cents))")
                }
            }
            if let b = biggest, b.cents > 0 {
                Text("biggest day: \(shortDay(b.date)), \(dollars(b.cents))").font(.system(size: 12)).foregroundStyle(Theme.secondary)
            }
        }
        .padding(18)
        .glass(RoundedRectangle(cornerRadius: 22, style: .continuous))
        .sensoryFeedback(.selection, trigger: selected)
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
