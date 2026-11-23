# Money Overview Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Money overview tab's plain figures/bar-chart/bars with a trend hero card (day/month toggle, spend line), a category donut, and ring-style budget goals, borrowing Rocket Money's layout patterns while staying inside the app's existing pure black-and-white glass design system.

**Architecture:** One small backend addition (a day-by-day cumulative spend series on `GET /money/summary`, reusing the existing `is_internal` spend-filtering rules) plus an iOS-only redesign of `MoneyOverviewView` in `ios/DailyAgent/Sources/MoneyView.swift`. No new files, no new dependencies, no `AppState` changes.

**Tech Stack:** FastAPI + SQLAlchemy (backend), SwiftUI + Swift Charts (iOS, already a dependency).

**Spec:** `docs/superpowers/specs/2026-11-23-money-overview-redesign-design.md`

---

## Task 1: Backend — daily cumulative spend function

**Status: DONE** — implemented, committed `764451b` on branch `money-overview-redesign`. Spec/quality review not yet run.

**Files:**
- Modify: `app/money.py` (add a new function after `month_totals`, before `holdings`)
- Test: `tests/test_money_overview.py`

- [x] **Step 1: Write the failing tests**

Add to `tests/test_money_overview.py` (both tests use the existing `ready()` fixture and `t()`/`Plaid2`/`build`/`connect`/`sync` helpers already in this file; `ready()` uses `NOW = datetime(2026, 11, 19, 15, 0, tzinfo=UTC)` from `test_banks.py`, so "today" is 2026-11-19):

```python
def test_daily_is_a_running_total_through_today_with_gaps_carried_forward(tmp_path):
    app, c = ready(tmp_path)
    daily = c.get("/money/summary", headers=H).json()["daily"]
    assert len(daily) == 19  # november 1 through 19
    assert daily[0] == {"date": "2026-11-01", "cumulative_spend_cents": 0}
    by = {d["date"]: d["cumulative_spend_cents"] for d in daily}
    assert by["2026-11-06"] == 4000  # 40 food
    assert by["2026-11-07"] == 10000  # +60 merchandise
    assert by["2026-11-08"] == 8000  # -20 refund
    assert by["2026-11-09"] == 11000  # +30 transport
    assert by["2026-11-15"] == 11000  # no activity that day: carries the prior total forward
    assert daily[-1] == {"date": "2026-11-19", "cumulative_spend_cents": 11000}
    this_month = c.get("/money/summary", headers=H).json()["this_month"]
    assert daily[-1]["cumulative_spend_cents"] == this_month["spend_cents"]


def test_daily_excludes_transfers_and_card_payments(tmp_path):
    page = {
        "added": [
            t("y1", "a1", 2000.00, "2026-11-01", "TRANSFER_OUT"),
            t("y2", "a2", -2000.00, "2026-11-01", "TRANSFER_IN"),
            t("y3", "a1", 300.00, "2026-11-01", "LOAN_PAYMENTS", CC, name="Card payment"),
            t("y4", "a2", -300.00, "2026-11-01", "LOAN_PAYMENTS", CC, name="Card payment"),
            t("y5", "a1", 1000.00, "2026-11-01", "FOOD_AND_DRINK"),
        ],
        "modified": [],
        "removed": [],
        "next_cursor": "c",
        "has_more": False,
    }
    app, c = build(tmp_path, Plaid2([page]))
    connect(c)
    sync(app)
    daily = c.get("/money/summary", headers=H).json()["daily"]
    assert daily[0] == {"date": "2026-11-01", "cumulative_spend_cents": 100000}
```

- [x] **Step 2: Run the tests to verify they fail**

Run: `cd /Users/johns/projects/daily_agent && uv run pytest tests/test_money_overview.py -k daily -v`
Expected: FAIL with `KeyError: 'daily'` (the field doesn't exist on the response yet).

- [x] **Step 3: Write the minimal implementation**

In `app/money.py`, add this function after `month_totals` and before `holdings`:

```python
def daily_cumulative_spend(db: Session, today: date) -> list[tuple[date, int]]:
    """One point per day of the current month, day 1 through today: a running total of spend
    cents, same filtering rules as month_totals (is_internal, refunds reduce spend). A day with
    nothing to add carries the prior day's total forward, so the series has no gaps. The running
    sum is floored at 0 the same way month_totals floors the month total: by clamping the
    cumulative sum at each point, not by clamping (and losing) any single day's delta."""
    first = date(today.year, today.month, 1)
    rows = db.execute(
        select(
            Transaction.posted_date,
            Transaction.direction,
            Transaction.amount_cents,
            Transaction.category,
            Transaction.category_detail,
        )
        .join(BankAccount, BankAccount.id == Transaction.account_id)
        .where(
            BankAccount.enabled.is_(True),
            Transaction.posted_date >= first,
            Transaction.posted_date <= today,
        )
    ).all()
    by_day: dict[date, int] = {}
    for d, direction, cents, cat, detail in rows:
        if is_internal(cat, detail) or (direction == "in" and cat == "INCOME"):
            continue
        signed = cents if direction == "out" else -cents
        by_day[d] = by_day.get(d, 0) + signed
    out: list[tuple[date, int]] = []
    raw = 0
    for i in range((today - first).days + 1):
        d = date.fromordinal(first.toordinal() + i)
        raw += by_day.get(d, 0)
        out.append((d, max(raw, 0)))
    return out
```

- [x] **Step 4: Run the tests to verify they still fail the same way**

Run: `cd /Users/johns/projects/daily_agent && uv run pytest tests/test_money_overview.py -k daily -v`
Expected: still FAIL with `KeyError: 'daily'` — the function exists now but nothing calls it yet (Task 2 wires it into the endpoint). This confirms the test is actually exercising the endpoint, not the function directly.

- [x] **Step 5: Commit**

```bash
cd /Users/johns/projects/daily_agent
git add app/money.py tests/test_money_overview.py
git commit -m "feat: add daily_cumulative_spend for the money overview redesign"
```

---

## Task 2: Backend — wire `daily` into `GET /money/summary`

**Files:**
- Modify: `app/api/money.py:22-46` (the `summary` endpoint)

- [x] **Step 1: Update the import and endpoint**

In `app/api/money.py`, change:

```python
from app.money import holdings, last_months, month_totals
```

to:

```python
from app.money import daily_cumulative_spend, holdings, last_months, month_totals
```

Then replace the `summary` function:

```python
@router.get("/money/summary")
def summary(
    request: Request, months: int = Query(6, ge=1, le=24), clock: Clock = Depends(get_clock)
):
    keys = last_months(_today(request, clock), months)
    with request.app.state.session_factory() as db:
        totals, cats = month_totals(db, keys)
        now = totals[keys[-1]]
        return {
            "months": [
                {"month": m, "income_cents": totals[m]["income"], "spend_cents": totals[m]["spend"]}
                for m in keys
            ],
            "this_month": {
                "month": keys[-1],
                "income_cents": now["income"],
                "spend_cents": now["spend"],
                "net_cents": now["income"] - now["spend"],
            },
            "categories": [
                {"category": c, "spend_cents": v}
                for c, v in sorted(cats.items(), key=lambda kv: (-kv[1], kv[0]))[:8]
            ],
            "holdings": holdings(db),
        }
```

with:

```python
@router.get("/money/summary")
def summary(
    request: Request, months: int = Query(6, ge=1, le=24), clock: Clock = Depends(get_clock)
):
    today = _today(request, clock)
    keys = last_months(today, months)
    with request.app.state.session_factory() as db:
        totals, cats = month_totals(db, keys)
        now = totals[keys[-1]]
        return {
            "months": [
                {"month": m, "income_cents": totals[m]["income"], "spend_cents": totals[m]["spend"]}
                for m in keys
            ],
            "this_month": {
                "month": keys[-1],
                "income_cents": now["income"],
                "spend_cents": now["spend"],
                "net_cents": now["income"] - now["spend"],
            },
            "categories": [
                {"category": c, "spend_cents": v}
                for c, v in sorted(cats.items(), key=lambda kv: (-kv[1], kv[0]))[:8]
            ],
            "holdings": holdings(db),
            "daily": [
                {"date": d.isoformat(), "cumulative_spend_cents": cents}
                for d, cents in daily_cumulative_spend(db, today)
            ],
        }
```

- [x] **Step 2: Run the tests to verify they pass**

Run: `cd /Users/johns/projects/daily_agent && uv run pytest tests/test_money_overview.py -v`
Expected: all tests in the file PASS, including the two new ones from Task 1.

- [x] **Step 3: Run the full backend suite and lint**

Run: `cd /Users/johns/projects/daily_agent && uv run pytest -q && uv run ruff check app/money.py app/api/money.py tests/test_money_overview.py`
Expected: all tests pass (364+2 = 366), ruff reports no errors on these files.

- [x] **Step 4: Commit**

```bash
cd /Users/johns/projects/daily_agent
git add app/api/money.py
git commit -m "feat: expose the daily cumulative spend series on GET /money/summary"
```

---

## Task 3: iOS — `DailyPoint` model

**Files:**
- Modify: `ios/DailyAgent/Sources/Models.swift:200-205` (`MoneySummary`)

- [x] **Step 1: Add the model**

In `ios/DailyAgent/Sources/Models.swift`, replace:

```swift
struct MoneySummary: Codable, Equatable {
    var months: [MonthTotal]
    var thisMonth: ThisMonth
    var categories: [CategorySpend]
    var holdings: Holdings
}
```

with:

```swift
struct DailyPoint: Codable, Equatable, Identifiable {
    var date: String
    var cumulativeSpendCents: Int
    var id: String { date }
}

struct MoneySummary: Codable, Equatable {
    var months: [MonthTotal]
    var thisMonth: ThisMonth
    var categories: [CategorySpend]
    var holdings: Holdings
    var daily: [DailyPoint]
}
```

- [x] **Step 2: Add a decode check**

In `ios/DailyAgent/Checks/main.swift`, right before the final `print(failures == 0 ...)` / `exit(...)` lines, add:

```swift
// money overview redesign
let ms = try! makeDecoder().decode(MoneySummary.self, from: Data(#"{"months":[{"month":"2026-11","income_cents":100,"spend_cents":50}],"this_month":{"month":"2026-11","income_cents":100,"spend_cents":50,"net_cents":50},"categories":[],"holdings":{"cash_cents":0,"savings_cents":0,"invested_cents":0,"credit_owed_cents":0,"loans_owed_cents":0,"net_cents":0},"daily":[{"date":"2026-11-01","cumulative_spend_cents":0},{"date":"2026-11-02","cumulative_spend_cents":50}]}"#.utf8))
check(ms.daily.count == 2 && ms.daily[1].cumulativeSpendCents == 50, "decodes money summary with the daily series")
```

- [x] **Step 3: Run the checks to verify they fail**

Run: `cd /Users/johns/projects/daily_agent/ios/DailyAgent && swiftc Sources/Models.swift Sources/Format.swift Checks/main.swift -o /tmp/checks && /tmp/checks`
Expected: a compile error, `value of type 'MoneySummary' has no member 'daily'` is not yet possible since Step 1 already added it — if Step 1 and Step 2 are done together this will actually PASS. Run this step before Step 1's edit if you want to see it fail first; otherwise skip straight to Step 4.

- [x] **Step 4: Run the checks to verify they pass**

Run: `cd /Users/johns/projects/daily_agent/ios/DailyAgent && swiftc Sources/Models.swift Sources/Format.swift Checks/main.swift -o /tmp/checks && /tmp/checks`
Expected: `all checks passed`, exit code 0.

- [x] **Step 5: Commit**

```bash
cd /Users/johns/projects/daily_agent
git add ios/DailyAgent/Sources/Models.swift ios/DailyAgent/Checks/main.swift
git commit -m "feat(ios): decode the daily cumulative spend series"
```

---

## Task 4: iOS — pure helpers (`topCategoriesWithOther`, `averageComparisonLine`)

**Files:**
- Modify: `ios/DailyAgent/Sources/Format.swift` (add two functions near `categoryLabel`/`dollars`)

- [x] **Step 1: Add checks for functions that don't exist yet**

In `ios/DailyAgent/Checks/main.swift`, right after the check added in Task 3, add:

```swift
let fiveCats = [
    CategorySpend(category: "FOOD_AND_DRINK", spendCents: 500),
    CategorySpend(category: "TRANSPORTATION", spendCents: 400),
    CategorySpend(category: "GENERAL_MERCHANDISE", spendCents: 300),
    CategorySpend(category: "TRAVEL", spendCents: 200),
    CategorySpend(category: "MEDICAL", spendCents: 100),
    CategorySpend(category: "BANK_FEES", spendCents: 50),
]
let bucketed = topCategoriesWithOther(fiveCats)
check(bucketed.count == 6 && bucketed.last?.category == "OTHER" && bucketed.last?.spendCents == 50, "buckets categories past the limit into OTHER")
check(topCategoriesWithOther(Array(fiveCats.prefix(3))).count == 3, "fewer categories than the limit are left alone")
check(averageComparisonLine(current: 300, others: [500, 400]) == "$150 below average", "below average line")
check(averageComparisonLine(current: 500, others: [300, 400]) == "$150 above average", "above average line")
check(averageComparisonLine(current: 300, others: []) == nil, "no other months means no comparison line")
```

- [x] **Step 2: Run the checks to verify they fail**

Run: `cd /Users/johns/projects/daily_agent/ios/DailyAgent && swiftc Sources/Models.swift Sources/Format.swift Checks/main.swift -o /tmp/checks && /tmp/checks`
Expected: a compile error, `cannot find 'topCategoriesWithOther' in scope`.

- [x] **Step 3: Write the minimal implementation**

In `ios/DailyAgent/Sources/Format.swift`, right after the existing `categoryLabel(_:)` function (around line 202), add:

```swift
/// Top N categories by spend (default 5), any remainder bundled into one "OTHER" bucket.
func topCategoriesWithOther(_ categories: [CategorySpend], limit: Int = 5) -> [CategorySpend] {
    guard categories.count > limit else { return categories }
    let sorted = categories.sorted { $0.spendCents > $1.spendCents }
    let other = sorted.dropFirst(limit).reduce(0) { $0 + $1.spendCents }
    return Array(sorted.prefix(limit)) + [CategorySpend(category: "OTHER", spendCents: other)]
}

/// "$150 below average" or "$150 above average"; nil with no other months to compare to.
func averageComparisonLine(current: Int, others: [Int]) -> String? {
    guard !others.isEmpty else { return nil }
    let avg = others.reduce(0, +) / others.count
    let diff = avg - current
    return diff >= 0 ? "\(dollars(diff)) below average" : "\(dollars(-diff)) above average"
}
```

- [x] **Step 4: Run the checks to verify they pass**

Run: `cd /Users/johns/projects/daily_agent/ios/DailyAgent && swiftc Sources/Models.swift Sources/Format.swift Checks/main.swift -o /tmp/checks && /tmp/checks`
Expected: `all checks passed`, exit code 0.

- [x] **Step 5: Commit**

```bash
cd /Users/johns/projects/daily_agent
git add ios/DailyAgent/Sources/Format.swift ios/DailyAgent/Checks/main.swift
git commit -m "feat(ios): add category bucketing and average-comparison helpers"
```

---

## Task 5: iOS — the trend hero card

**Files:**
- Modify: `ios/DailyAgent/Sources/MoneyView.swift`
  - Remove: `thisMonth(_:)` (lines 88-94), `chart(_:)` (lines 104-114), `legend(_:_:)` (lines 116-121), `SpendIncomeChart` (lines 194-223)
  - Add: `HeroMode` enum, `@State private var heroMode`, `@Namespace private var heroPick` on `MoneyOverviewView`, `heroCard(_:)`, `heroToggle`, `heroPoints(_:)`, `TrendPoint`, `TrendLineChart`

This is a pure visual change (no new backend calls, no new `AppState` state), so there isn't a
meaningful "failing test" to write first the way the backend tasks have one — the project's own
check for UI code is the typecheck script, run at the end of this task and Task 6 and Task 7.

- [x] **Step 1: Replace `thisMonth`, `chart`, and `legend`**

In `ios/DailyAgent/Sources/MoneyView.swift`, delete these three methods from `MoneyOverviewView`:

```swift
    private func thisMonth(_ s: MoneySummary) -> some View {
        HStack(alignment: .top, spacing: 0) {
            figure("spent", dollars(s.thisMonth.spendCents))
            figure("income", dollars(s.thisMonth.incomeCents))
            figure("net", (s.thisMonth.netCents >= 0 ? "+" : "") + dollars(s.thisMonth.netCents))
        }
    }
```

```swift
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
```

Replace them with:

```swift
    private func heroCard(_ s: MoneySummary) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                sectionLabel("spent this month")
                Spacer()
                heroToggle
            }
            Text(dollars(s.thisMonth.spendCents)).font(.system(size: 34, weight: .light))
                .monospacedDigit().foregroundStyle(Theme.title).contentTransition(.numericText())
            TrendLineChart(points: heroPoints(s), showAxes: heroMode == .month)
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

    private var heroToggle: some View {
        HStack(spacing: 2) {
            ForEach(HeroMode.allCases) { m in
                Button { withAnimation(Theme.spring) { heroMode = m } } label: {
                    Text(m.rawValue).font(.system(size: 11.5, weight: heroMode == m ? .medium : .regular))
                        .foregroundStyle(heroMode == m ? Color.black : Theme.secondary)
                        .padding(.horizontal, 10).frame(minHeight: 26)
                        .background {
                            if heroMode == m {
                                Capsule().fill(Color.white).matchedGeometryEffect(id: "hero-mode", in: heroPick)
                            }
                        }
                }.buttonStyle(PressStyle())
            }
        }
        .padding(2).glass(Capsule())
    }

    private func heroPoints(_ s: MoneySummary) -> [TrendPoint] {
        switch heroMode {
        case .day: return s.daily.map { TrendPoint(id: $0.date, label: $0.date, cents: $0.cumulativeSpendCents) }
        case .month: return s.months.map { TrendPoint(id: $0.month, label: monthShort($0.month), cents: $0.spendCents) }
        }
    }
```

Then add, at the top of `MoneyOverviewView` (alongside the existing `@State private var editing` and `@State private var adding`):

```swift
    @State private var heroMode: HeroMode = .day
    @Namespace private var heroPick
```

And update the `body` of `MoneyOverviewView` — replace:

```swift
            VStack(alignment: .leading, spacing: 34) {
                thisMonth(s).reveal(0)
                chart(s).reveal(1)
                categories(s).reveal(2)
                goals.reveal(3)
            }
```

with:

```swift
            VStack(alignment: .leading, spacing: 34) {
                heroCard(s).reveal(0)
                categories(s).reveal(1)
                goals.reveal(2)
            }
```

- [x] **Step 2: Add `HeroMode` and `TrendPoint`, replace `SpendIncomeChart`**

In `ios/DailyAgent/Sources/MoneyView.swift`, add this near the top of the file, after the existing `MoneyTab` enum:

```swift
enum HeroMode: String, CaseIterable, Identifiable {
    case day, month
    var id: String { rawValue }
}

struct TrendPoint: Identifiable {
    let id: String
    let label: String
    let cents: Int
}
```

Then delete the `SpendIncomeChart` struct entirely:

```swift
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
```

and replace it with:

```swift
struct TrendLineChart: View {
    let points: [TrendPoint]
    let showAxes: Bool
    @State private var grown = false

    @ChartContentBuilder
    private var marks: some ChartContent {
        ForEach(points) { p in
            AreaMark(x: .value("x", p.label), y: .value("spend", grown ? Double(p.cents) / 100 : 0))
                .foregroundStyle(LinearGradient(colors: [Color.white.opacity(0.3), Color.white.opacity(0)], startPoint: .top, endPoint: .bottom))
            LineMark(x: .value("x", p.label), y: .value("spend", grown ? Double(p.cents) / 100 : 0))
                .foregroundStyle(Color.white)
                .lineStyle(StrokeStyle(lineWidth: 2))
        }
    }

    var body: some View {
        Group {
            if showAxes {
                Chart { marks }
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
            } else {
                Chart { marks }
                    .chartLegend(.hidden)
                    .chartXAxis(.hidden)
                    .chartYAxis(.hidden)
            }
        }
        .frame(height: 120)
        .onAppear { withAnimation(Theme.spring.delay(0.15)) { grown = true } }
    }
}
```

- [x] **Step 3: Typecheck**

Run: `cd /Users/johns/projects/daily_agent/ios/DailyAgent && sh Checks/typecheck.sh`
Expected: `typecheck passed`. If it fails, the error will name the exact file/line — common culprits at this step are a stray reference to `thisMonth(`, `chart(`, `legend(`, or `SpendIncomeChart(` left somewhere (the body update in Step 1 should have removed the only call sites).

- [x] **Step 4: Run the existing iOS checks**

Run: `cd /Users/johns/projects/daily_agent/ios/DailyAgent && swiftc Sources/Models.swift Sources/Format.swift Checks/main.swift -o /tmp/checks && /tmp/checks`
Expected: `all checks passed` (this file doesn't touch anything `main.swift`'s checks exercise directly, this just confirms nothing broke).

- [x] **Step 5: Commit**

```bash
cd /Users/johns/projects/daily_agent
git add ios/DailyAgent/Sources/MoneyView.swift
git commit -m "feat(ios): replace the money figures and bar chart with a trend hero card"
```

---

## Task 6: iOS — category donut

**Files:**
- Modify: `ios/DailyAgent/Sources/MoneyView.swift:123-139` (the `categories(_:)` method)

- [x] **Step 1: Replace the method**

In `ios/DailyAgent/Sources/MoneyView.swift`, replace:

```swift
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
```

with:

```swift
    private let donutGrays: [Color] = [.white, Color(white: 0.68), Color(white: 0.5), Color(white: 0.36), Color(white: 0.24), Color(white: 0.3)]

    private func categories(_ s: MoneySummary) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            sectionLabel("where it went this month")
            if s.categories.isEmpty {
                Text("nothing spent yet.").font(.system(size: 14.5)).foregroundStyle(Theme.secondary)
            } else {
                let buckets = topCategoriesWithOther(s.categories)
                HStack(alignment: .center, spacing: 18) {
                    Chart(Array(buckets.enumerated()), id: \.offset) { i, c in
                        SectorMark(angle: .value("spend", c.spendCents), innerRadius: .ratio(0.65), angularInset: 1.5)
                            .foregroundStyle(donutGrays[i % donutGrays.count])
                            .cornerRadius(3)
                    }
                    .chartLegend(.hidden)
                    .frame(width: 96, height: 96)
                    VStack(alignment: .leading, spacing: 8) {
                        ForEach(Array(buckets.enumerated()), id: \.offset) { i, c in
                            HStack {
                                Circle().fill(donutGrays[i % donutGrays.count]).frame(width: 7, height: 7)
                                Text(categoryLabel(c.category)).font(.system(size: 13.5)).foregroundStyle(Theme.title)
                                Spacer()
                                Text(dollars(c.spendCents)).font(.system(size: 13.5)).monospacedDigit().foregroundStyle(Theme.title)
                            }
                        }
                    }
                }
            }
        }
    }
```

- [x] **Step 2: Typecheck**

Run: `cd /Users/johns/projects/daily_agent/ios/DailyAgent && sh Checks/typecheck.sh`
Expected: `typecheck passed`.

- [x] **Step 3: Commit**

```bash
cd /Users/johns/projects/daily_agent
git add ios/DailyAgent/Sources/MoneyView.swift
git commit -m "feat(ios): replace the category bars with a donut and legend"
```

---

## Task 7: iOS — budget goal rings

**Files:**
- Modify: `ios/DailyAgent/Sources/MoneyView.swift:141-172` (the `goals` property)
- Modify: `ios/DailyAgent/Sources/MoneyView.swift:176-192` (keep `Bar`, it's still used nowhere else after this — check Step 1 note below)

- [x] **Step 1: Replace the `goals` property**

In `ios/DailyAgent/Sources/MoneyView.swift`, replace:

```swift
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
```

with:

```swift
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
```

- [x] **Step 2: Add the `RingGauge` primitive**

In `ios/DailyAgent/Sources/MoneyView.swift`, right after the existing `Bar` struct (the one `Bar` is still used by `categories(_:)` — wait, `categories(_:)` was replaced in Task 6 and no longer uses `Bar`. Check: grep for `Bar(` in the file before deleting anything — if Task 6 was done first, `Bar` now has zero call sites and should be deleted here instead of kept. Add `RingGauge` either way:

```swift
struct RingGauge: View {
    let fraction: Double
    let label: String
    @State private var shown = false

    var body: some View {
        VStack(spacing: 6) {
            ZStack {
                Circle().stroke(Theme.raised, lineWidth: 8)
                Circle().trim(from: 0, to: shown ? fraction : 0)
                    .stroke(Color.white, style: StrokeStyle(lineWidth: 8, lineCap: .round))
                    .rotationEffect(.degrees(-90))
                Text("\(Int((fraction * 100).rounded()))%").font(.system(size: 15)).foregroundStyle(Theme.title)
            }
            .frame(width: 78, height: 78)
            Text(label).font(.system(size: 12)).foregroundStyle(Theme.secondary)
        }
        .animation(Theme.spring, value: fraction)
        .onAppear { withAnimation(Theme.spring.delay(0.1)) { shown = true } }
    }
}
```

- [x] **Step 3: Check whether `Bar` is now dead code and remove it if so**

Run: `cd /Users/johns/projects/daily_agent && grep -rn "Bar(fraction" ios/DailyAgent/Sources/`
Expected: no output (both of `Bar`'s only two call sites — the old `categories(_:)` and the old `goals` — were replaced in Task 6 and Step 1 of this task). If the grep is empty, delete the `Bar` struct from `ios/DailyAgent/Sources/Theme.swift:176-192`:

```swift
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
```

(If the grep finds a remaining call site, leave `Bar` in place — don't delete code something else still uses.)

- [x] **Step 4: Typecheck**

Run: `cd /Users/johns/projects/daily_agent/ios/DailyAgent && sh Checks/typecheck.sh`
Expected: `typecheck passed`.

- [x] **Step 5: Commit**

```bash
cd /Users/johns/projects/daily_agent
git add ios/DailyAgent/Sources/MoneyView.swift ios/DailyAgent/Sources/Theme.swift
git commit -m "feat(ios): replace linear budget bars with ring gauges"
```

---

## Task 8: Wrap-up

**Files:**
- Modify: `design/DESIGN_NOTES.md` (append a dated update, matching the existing convention of dated updates at the end of the file)
- Modify: `docs/CHECKIN_LOG.md` (append an entry, matching the existing convention for every shipped spec)

- [x] **Step 1: Run the full backend suite one more time**

Run: `cd /Users/johns/projects/daily_agent && uv run pytest -q && uv run ruff check app/ tests/test_money_overview.py`
Expected: all tests pass, no ruff errors on the touched files.

- [x] **Step 2: Run the full iOS checks one more time**

Run:
```bash
cd /Users/johns/projects/daily_agent/ios/DailyAgent
sh Checks/typecheck.sh
swiftc Sources/Models.swift Sources/Format.swift Checks/main.swift -o /tmp/checks && /tmp/checks
```
Expected: `typecheck passed` and `all checks passed`.

- [x] **Step 3: Append to `design/DESIGN_NOTES.md`**

Add at the end of the file:

```markdown
## Update 2026-11-23: money overview redesign
At John's request, borrowing Rocket Money's layout patterns while staying monochrome. The three
figures and the grouped income/spend bar chart became one trend hero card: a big spend number, a
day/month toggle, and a line+area chart (Swift Charts, white line and gradient, no new color).
Income moved from its own bars into a text-only footer line. The category bars became a donut
(Swift Charts SectorMark) with a gray-scale ramp, capped at the top 5 categories plus one "other"
slice. The linear budget-goal bars became ring gauges in a horizontal scroll row. Still no accent
colors, still respects Reduce Motion.
```

- [x] **Step 4: Append to `docs/CHECKIN_LOG.md`**

Add at the end of the file, following the format of every other entry in it:

```markdown
### 2026-11-23, money overview redesign
What: replaced the Money overview tab's plain figures/bar chart/bars with a trend hero card (day/
month toggle, spend-only line chart, income moved to a footer line), a category donut (top 5 plus
other), and ring-gauge budget goals. Backend gained one field on GET /money/summary: `daily`, a
day-by-day running total of this month's spend, reusing month_totals' exact filtering rules.
Design brainstormed with browser mockups before any code was written; spec at
docs/superpowers/specs/2026-11-23-money-overview-redesign-design.md.
Tests and lint: backend suite + 2 new daily-series tests pass, ruff clean. iOS typecheck clean,
Checks/main.swift decode and bucketing checks pass.
Deviation: none from the approved spec.
Next step: run on the phone and confirm the hero card's day/month toggle and the donut/rings read
well at real data sizes (lots of categories, lots of budget goals).
```

- [x] **Step 5: Commit**

```bash
cd /Users/johns/projects/daily_agent
git add design/DESIGN_NOTES.md docs/CHECKIN_LOG.md
git commit -m "docs: log the money overview redesign"
```
