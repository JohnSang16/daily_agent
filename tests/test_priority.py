import copy
import random
import time
from datetime import UTC, datetime, timedelta
from datetime import time as dtime
from zoneinfo import ZoneInfo

from app.priority.engine import Config, EventView, TaskView, rank

NY = ZoneInfo("America/New_York")
CFG = Config(user_timezone="America/New_York", work_start=dtime(9), work_end=dtime(17))
# Monday 2026-11-16, 09:00 New York (EST)
NOW = datetime(2026, 11, 16, 14, 0, tzinfo=UTC)
CREATED = datetime(2026, 11, 1, tzinfo=UTC)


def local(y, m, d, h=0, mi=0):
    return datetime(y, m, d, h, mi, tzinfo=NY).astimezone(UTC)


def task(i, due=None, effort=60, imp=3, **kw):
    kw.setdefault("created_at", CREATED + timedelta(minutes=i))
    return TaskView(id=i, due_at=due, effort_minutes=effort, importance=imp, **kw)


def ids(r):
    return [x.task_id for x in r.ranked]


def by_id(r, i):
    return next(x for x in r.ranked if x.task_id == i)


def test_AC7_1_nearer_deadline_first():
    r = rank([task(1, local(2026, 11, 23, 12)), task(2, local(2026, 11, 17, 12))], [], NOW, CFG)
    assert ids(r) == [2, 1] and r.top_task_id == 2
    assert [x.rank for x in r.ranked] == [1, 2]


def test_AC7_2_overdue_first_and_at_risk():
    r = rank([task(1, NOW + timedelta(days=1)), task(2, NOW - timedelta(days=1))], [], NOW, CFG)
    assert ids(r) == [2, 1]
    assert {"OVERDUE", "AT_RISK"} <= set(by_id(r, 2).reasons) and by_id(r, 2).at_risk


def test_AC7_3_tie_importance():
    d = local(2026, 11, 20, 12)
    r = rank([task(1, d, imp=3), task(2, d, imp=5)], [], NOW, CFG)
    assert ids(r) == [2, 1] and "TIE_BROKEN_BY_IMPORTANCE" in by_id(r, 2).reasons


def test_AC7_4_tie_effort():
    d = local(2026, 11, 20, 12)
    r = rank([task(1, d, effort=90), task(2, d, effort=30)], [], NOW, CFG)
    assert ids(r) == [2, 1] and "TIE_BROKEN_BY_EFFORT" in by_id(r, 2).reasons


def test_AC7_5_eight_hour_task_due_in_three_hours_at_risk():
    r = rank([task(1, NOW + timedelta(hours=3), effort=480)], [], NOW, CFG)
    x = by_id(r, 1)
    assert x.at_risk and x.free_minutes_before_due < 480 and x.cumulative_effort_minutes == 480


def test_AC7_6_busy_all_day_event_removes_that_days_window():
    due = local(2026, 11, 17, 17)  # Tuesday 17:00
    t = [task(1, due, effort=480)]
    # Monday has 480 free minutes from 09:00, Tuesday 480: total 960, fits
    assert not by_id(rank(t, [], NOW, CFG), 1).at_risk
    tue_off = EventView(start_at=local(2026, 11, 17), end_at=local(2026, 11, 18))
    r = rank(t, [tue_off], NOW, CFG)
    assert by_id(r, 1).free_minutes_before_due == 480
    both = [EventView(local(2026, 11, 16), local(2026, 11, 17)), tue_off]
    assert by_id(rank(t, both, NOW, CFG), 1).free_minutes_before_due == 0
    assert by_id(rank(t, both, NOW, CFG), 1).at_risk


def test_non_busy_and_cancelled_events_ignored():
    due = local(2026, 11, 17, 17)
    t = [task(1, due, effort=60)]
    base = by_id(rank(t, [], NOW, CFG), 1).free_minutes_before_due
    evs = [
        EventView(local(2026, 11, 16, 10), local(2026, 11, 16, 12), busy=False),
        EventView(local(2026, 11, 16, 10), local(2026, 11, 16, 12), status="cancelled"),
    ]
    assert by_id(rank(t, evs, NOW, CFG), 1).free_minutes_before_due == base
    tent = [EventView(local(2026, 11, 16, 10), local(2026, 11, 16, 12), status="tentative")]
    assert by_id(rank(t, tent, NOW, CFG), 1).free_minutes_before_due == base - 120


def test_overlapping_busy_events_merged_not_double_counted():
    t = [task(1, local(2026, 11, 16, 17))]
    evs = [
        EventView(local(2026, 11, 16, 10), local(2026, 11, 16, 12)),
        EventView(local(2026, 11, 16, 11), local(2026, 11, 16, 13)),
    ]
    assert by_id(rank(t, evs, NOW, CFG), 1).free_minutes_before_due == 480 - 180


def test_AC7_7_snoozed_excluded_until_time_passes():
    t = [task(1, local(2026, 11, 20), snoozed_until=NOW + timedelta(hours=2))]
    assert rank(t, [], NOW, CFG).ranked == []
    assert ids(rank(t, [], NOW + timedelta(hours=3), CFG)) == [1]


def test_only_open_tasks():
    t = [task(1, status="done"), task(2, status="gone"), task(3)]
    assert ids(rank(t, [], NOW, CFG)) == [3]


def test_AC7_8_undated_after_dated_and_ordered():
    t = [task(1, None, imp=2), task(2, local(2026, 12, 30)), task(3, None, imp=5)]
    r = rank(t, [], NOW, CFG)
    assert ids(r) == [2, 3, 1] and "NO_DUE_DATE" in by_id(r, 3).reasons


def test_AC7_9_dst_change_does_not_shift_working_hours():
    now = local(2026, 10, 30, 9)  # Friday before fall back (Nov 1)
    t = [task(1, local(2026, 11, 2, 17))]  # Monday 17:00
    assert by_id(rank(t, [], now, CFG), 1).free_minutes_before_due == 4 * 480
    now = local(2026, 3, 6, 9)  # Friday before spring forward (Mar 8)
    t = [task(1, local(2026, 3, 9, 17))]
    assert by_id(rank(t, [], now, CFG), 1).free_minutes_before_due == 4 * 480


def test_AC7_10_pure_and_clock_free():
    t = [task(1, local(2026, 11, 20)), task(2, None)]
    assert rank(t, [], NOW, CFG) == rank(t, [], NOW, CFG)
    later = rank([task(1, NOW + timedelta(hours=3))], [], NOW + timedelta(hours=4), CFG)
    assert "OVERDUE" in later.ranked[0].reasons
    assert (
        "OVERDUE" not in rank([task(1, NOW + timedelta(hours=3))], [], NOW, CFG).ranked[0].reasons
    )


def test_AC7_11_inputs_not_mutated():
    t = [task(2, local(2026, 11, 20)), task(1, local(2026, 11, 18))]
    e = [EventView(local(2026, 11, 16, 10), local(2026, 11, 16, 11))]
    t0, e0 = copy.deepcopy(t), copy.deepcopy(e)
    rank(t, e, NOW, CFG)
    assert t == t0 and e == e0


def test_AC7_12_suggested_block():
    r = rank([task(1, local(2026, 11, 20), effort=120)], [], NOW, CFG)
    assert r.suggested_block == (local(2026, 11, 16, 9), local(2026, 11, 16, 17))
    r = rank([task(1, local(2026, 11, 20), effort=600)], [], NOW, CFG)
    assert r.suggested_block is None
    assert (
        rank([], [], NOW, CFG).suggested_block is None
        and rank([], [], NOW, CFG).top_task_id is None
    )


def test_free_blocks_today_after_now_and_around_events():
    now = local(2026, 11, 16, 10, 30)
    ev = [EventView(local(2026, 11, 16, 12), local(2026, 11, 16, 13))]
    r = rank([], ev, now, CFG)
    assert r.free_blocks_today == [
        (now, local(2026, 11, 16, 12)),
        (local(2026, 11, 16, 13), local(2026, 11, 16, 17)),
    ]


def test_min_block_dropped():
    now = local(2026, 11, 16, 9)
    ev = [EventView(local(2026, 11, 16, 9, 10), local(2026, 11, 16, 17))]  # leaves a 10 min sliver
    assert rank([], ev, now, CFG).free_blocks_today == []


def test_reason_codes_dates_flags_and_defaults():
    t = [
        task(1, local(2026, 11, 16, 20)),
        task(2, local(2026, 11, 17, 12)),
        task(3, local(2026, 11, 20, 12), effort=None, needs_review=True),
    ]
    r = rank(t, [], NOW, CFG)
    assert "DUE_TODAY" in by_id(r, 1).reasons and "DUE_TOMORROW" in by_id(r, 2).reasons
    assert {"DUE_THIS_WEEK", "NEEDS_REVIEW", "DEFAULT_EFFORT_USED"} <= set(by_id(r, 3).reasons)


def test_cumulative_effort_running_total():
    t = [task(1, local(2026, 11, 17), effort=60), task(2, local(2026, 11, 18), effort=30)]
    r = rank(t, [], NOW, CFG)
    assert [x.cumulative_effort_minutes for x in r.ranked] == [60, 90]


def _expected_key(t):
    imp = -(t.importance or 3)
    if t.due_at:
        return (
            0,
            t.due_at,
            imp,
            t.effort_minutes or CFG.default_effort_minutes,
            t.created_at,
            t.id,
        )
    return (1, imp, t.created_at, t.id)


def test_AC7_13_random_inputs_sorted_consistently():
    rng = random.Random(7)
    for _ in range(200):
        ts = []
        for i in range(rng.randint(0, 15)):
            due = NOW + timedelta(hours=rng.randint(-48, 200)) if rng.random() < 0.7 else None
            ts.append(
                task(
                    i + 1,
                    due,
                    effort=rng.choice([None, 15, 30, 90]),
                    imp=rng.choice([None, 1, 3, 5]),
                )
            )
        r = rank(ts, [], NOW, CFG)
        assert ids(r) == [t.id for t in sorted(ts, key=_expected_key)]


def test_AC7_14_performance():
    rng = random.Random(1)
    ts = [
        task(i, NOW + timedelta(hours=rng.randint(-24, 300)), effort=rng.choice([30, 60, 120]))
        for i in range(500)
    ]
    evs = [
        EventView(NOW + timedelta(hours=h), NOW + timedelta(hours=h + 1))
        for h in (rng.randint(0, 300) for _ in range(500))
    ]
    t0 = time.perf_counter()
    rank(ts, evs, NOW, CFG)
    assert time.perf_counter() - t0 < 1.0
