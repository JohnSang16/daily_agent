"""Seed my monthly budgets and money goals into a running agent. Safe to rerun.
Plan source: vault personal/finances/pay-yourself-first.md.
Run: AGENT_URL=http://<host>:8000 API_TOKEN=... uv run python scripts/seed_money.py"""

import json
import os
import urllib.request

URL = os.environ.get("AGENT_URL", "http://127.0.0.1:8000").rstrip("/")
TOKEN = os.environ["API_TOKEN"]

BUDGETS = {  # dollars per month, Plaid primary categories
    "FOOD_AND_DRINK": 250,
    "ENTERTAINMENT": 75,
    "GENERAL_MERCHANDISE": 100,
    "TRANSPORTATION": 100,
}
GOALS = [  # outcome goals in dollars, current is the 2026-11-24 balance, only set on create
    {"name": "Emergency fund", "target": 2000, "current": 518},
    {"name": "Japan fund", "target": 2500, "current": 514},
    {"name": "Cards paid off", "target": 757, "current": 0},
]


def call(method, path, body=None):
    req = urllib.request.Request(
        URL + path,
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as r:
        return json.load(r)


for cat, dollars in BUDGETS.items():
    call("PUT", f"/budgets/{cat}", {"limit_cents": dollars * 100})
    print(f"budget {cat} ${dollars}")

existing = {g["name"]: g for g in call("GET", "/goals")}
for g in GOALS:
    if g["name"] in existing:
        call("PATCH", f"/goals/{existing[g['name']]['id']}", {"target": g["target"]})
        print(f"goal {g['name']} target ${g['target']} (kept current)")
    else:
        call("POST", "/goals", {**g, "kind": "outcome", "unit": "$"})
        print(f"goal {g['name']} created ${g['current']} of ${g['target']}")
