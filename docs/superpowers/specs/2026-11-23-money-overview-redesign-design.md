# Money overview redesign: Rocket Money patterns, same monochrome theme

## Why

John wants the Money overview tab to be easier to visually digest, borrowing layout patterns from
Rocket Money (a trend hero card, goal rings, a category donut), but staying inside the app's
existing pure black-and-white glass design system. No new accent colors, no new fonts, no new
libraries. Confirmed via browser mockups during brainstorming (two rounds: individual directions,
then a combined screen) before any code was written.

## Scope

Replaces, inside `MoneyOverviewView` (`ios/DailyAgent/Sources/MoneyView.swift`):

1. `thisMonth(_:)` + `chart(_:)` (the three-figure row and the grouped income/spend bar chart) →
   one `TrendHeroCard`.
2. `categories(_:)` (stacked category bars) → `CategoryDonutView`.
3. The linear bars inside `goals` → `GoalRingsView`, using a new small `RingGauge` primitive.

Stays unchanged: colors, fonts, glass/pill styling, animations, the holdings rows, the
Banks/Income/Activity tabs, the `BudgetSheet` edit flow, `AppState` method signatures.

One deliberate behavior change, confirmed with John: income no longer gets its own line/bars on
the chart. It moves to a text-only footer line under the hero card ("income $4,100 · net
+$1,158"). The chart itself tracks spend only.

## Backend: `app/money.py` + `app/api/money.py`

Today `GET /money/summary` returns `months` (6 monthly totals), `this_month`, `categories` (top 8),
and `holdings`. It has no day-level breakdown, so the hero card's "day" mode has nothing to read
from yet.

Add:

- `daily_cumulative_spend(db: Session, today: date) -> list[tuple[date, int]]` in `app/money.py`.
  Same spend rules as `month_totals` (reuses `is_internal`: excludes transfers between own
  accounts and card payments; a refund reduces spend instead of counting as income), but grouped
  by day instead of month, for day 1 of the current month through `today`. A day with no
  qualifying transactions carries forward the previous day's cumulative total (no gaps in the
  line). The running total is floored at 0, same as the monthly calc.
- `GET /money/summary` gains one field: `"daily": [{"date": "2026-11-01",
  "cumulative_spend_cents": N}, ...]`. `months`, `this_month`, `categories`, `holdings` are
  unchanged.

Test (in `tests/test_money_overview.py`, alongside the existing money tests):

- The last entry in `daily` equals `this_month.spend_cents` exactly (same rules, so they cannot
  drift apart).
- A day with no transactions carries forward the prior day's cumulative value instead of
  resetting to 0 or being omitted.
- Internal transfers and card payments are excluded from the daily series the same way they are
  excluded from the monthly total (reuse of `is_internal`, not a re-implementation).

## iOS: `ios/DailyAgent/Sources/MoneyView.swift` + `Models.swift`

No new files. Everything below lives in the existing `MoneyView.swift`, matching how the whole
Money screen is already organized as one file.

**`Models.swift`:** add

```swift
struct DailyPoint: Codable, Equatable, Identifiable {
    var date: String
    var cumulativeSpendCents: Int
    var id: String { date }
}
```

and `var daily: [DailyPoint]` on `MoneySummary`. No `AppState` changes: `daily` rides along on the
existing `loadAllMoney()` fetch of `/money/summary`.

**`TrendHeroCard`:** a 22pt-corner glass card (`.glass(RoundedRectangle(cornerRadius: 22, style:
.continuous))`, the same card style already used on `DashboardView`), containing:

- A small two-way pill toggle, `day` / `month`, visually matching the existing `MoneyTab` pill
  (white-on-black capsule for the selected side), local `@State` only, no persistence needed.
- The big spend number (reuses the existing `figure`-style type treatment: 26pt light,
  monospaced digits).
- A line + area chart (Swift Charts `LineMark` + `AreaMark`, the same framework already imported
  and already used for the current bar chart — no new dependency):
  - `day` mode plots `summary.daily` (x: day of month, y: cumulative spend).
  - `month` mode plots `summary.months` (x: month, y: spend only — not income), i.e. the same
    data the current chart already receives, just drawn as a line instead of bars.
  - White line, white-to-transparent gradient fill under it, consistent with the Rocket Money
    reference but monochrome.
- A footer line: `"income $X · net $Y"`, computed from `summary.thisMonth`, plus an
  average-comparison line (`"$N below/above average"`), where average is the mean `spendCents`
  of the other months in `summary.months` (excluding the current month). If there are no other
  months yet (a brand-new account), the average-comparison line is omitted, not shown as a
  divide-by-zero or a comparison against nothing.

**`CategoryDonutView`:** Swift Charts `SectorMark` (donut, `.innerRadius(.ratio(0.65))`,
available in the same framework since iOS 17), fed by `summary.categories` bucketed client-side to
the top 5 by spend plus one "other" slice for the remainder (the backend already caps to top 8,
so this is a pure view-layer grouping, no backend change). Gray-scale ramp: white, then
progressively darker grays, ending in the darkest allowed text gray for "other" — no new colors.
Legend list beside the donut, reusing the existing row/label text styles.

**`RingGauge`:** a new small primitive, same spirit as the existing `Bar` component (animates in
on appear via the same shown/grown pattern, white fill on a `Theme.raised` track). A `Circle`
trimmed from 0 to `fraction`, rotated -90°, with the percentage centered inside.

**`GoalRingsView`:** replaces the bars inside `goals`. A horizontal `ScrollView` of `RingGauge`s
(so it scales to any number of budget goals, not just 2-3), one per `state.budgets` entry, each
tappable to open the existing `BudgetSheet` for editing (`editing = g`, unchanged), plus a
trailing "+ add goal" ring tapping the existing `adding = true` path. Empty state keeps the
current "no goals yet..." text.

## Error handling

No new error states. If `daily` is empty (not yet possible in practice — `this_month` always has
at least day 1 — but trivially true on a fresh account with zero transactions), Swift Charts
renders a single-point line without crashing; no special-casing needed. All existing
`state.problem` / `state.waitingText` handling is untouched since `daily` is just an additional
field on the already-fetched summary.

## Testing

- Backend: three new pytest cases described above, in the existing `tests/test_money_overview.py`.
- iOS: a few `check(...)` lines added to the existing `ios/DailyAgent/Checks/main.swift`
  (matching its existing lightweight assert-based pattern, no new test framework): decode a
  `MoneySummary` JSON fixture that includes `daily`, and verify the top-5-plus-other category
  bucketing function on a fixture with more than 5 categories.
