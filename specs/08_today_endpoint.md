# 08 Today endpoint and explanation

## Purpose
`GET /today` returns the top task, ranked tasks, schedule, free blocks (used for the suggested start time and not shown in the app), warnings, and a short plain language explanation.

## Request
`GET /today` with optional query `date` (ISO date, default today in my time zone) and `limit` (default 10, max 50). Bearer token required.

## Response (JSON)
```
{
  "date": "2026-11-13",
  "timezone": "America/New_York",
  "generated_at": "2026-11-13T12:00:00Z",
  "top_task": { "id": 12, "title": "...", "due_at": "...", "reasons": ["DUE_TODAY"], "at_risk": false, "suggested_block": { "start": "...", "end": "..." } },
  "ranked": [ { "id": 12, "rank": 1, "title": "...", "due_at": "...", "source": "obsidian", "reasons": [], "at_risk": false, "needs_review": false } ],
  "events": [ { "title": "...", "start": "...", "end": "...", "all_day": false } ],
  "free_blocks": [ { "start": "...", "end": "..." } ],
  "explanation": { "text": "...", "source": "llm" },
  "warnings": [ { "code": "SOURCE_STALE", "source": "gmail_digest", "detail": "last success 31h ago" } ],
  "needs_review_count": 2
}
```
All timestamps are UTC ISO strings. The app converts to local time. When no task exists, `top_task` is null and `explanation.text` says so.

## Explanation
1. Built from the structured ranking only (titles, due moments, reason codes, at risk flags). Never from raw emails or notes.
2. The model is told titles are data, not instructions, and must answer in two to four plain sentences.
3. `explanation.source` is `llm` or `template`. A deterministic template is used when the LLM is unavailable, over budget, or fails.
4. Cached by a hash of the ranking inputs. Identical inputs never call the model twice.
5. The explanation must not contradict the ranking. A test checks that the top task title appears in the text or that the template path is used.

## Warnings
1. `SOURCE_STALE` when a source's last successful sync is older than its threshold (spec 09).
2. `SYNC_ERROR` when the latest run failed.
3. `NEEDS_REVIEW` summary when review items exist.
4. `LLM_BUDGET_EXHAUSTED` when the budget stopped work.

## Acceptance criteria
* AC8.1 The endpoint returns the documented shape with fixture data.
* AC8.2 The top task equals the engine's top ranked item.
* AC8.3 `date` and `limit` parameters behave as documented, and invalid values return 422.
* AC8.4 No tasks returns `top_task` null and a clear explanation.
* AC8.5 A stale source adds a `SOURCE_STALE` warning with the age.
* AC8.6 With a fake LLM that raises an error, the response still succeeds with `explanation.source` equal to `template`.
* AC8.7 Calling twice with identical data makes one LLM call (cache) and logs one `llm_usage` row.
* AC8.8 The model input in tests contains no email body or note text (assert on the prompt).
* AC8.9 Events are filtered to the requested local day and exclude cancelled events.
* AC8.10 The endpoint requires the bearer token.
* AC8.11 Response time with fixture data and a cached explanation is under 300 ms.

## Out of scope
Pushing notifications, the app, voice.

## Open questions
1. Should `/today` also include tomorrow's top three deadlines as a preview?
