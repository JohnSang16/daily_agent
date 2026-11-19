"""Keyword search over indexed chunks. ponytail: scores in Python, move to database full text
search past about 50,000 chunks."""

import re
from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import NoteChunk

STOP = set(
    "what did the and about for with was are you how who why when where which from this that tell "
    "show find notes note wrote write plan have has had any can give list there their them then "
    "your does into over under".split()
)
WORD = re.compile(r"[a-z0-9]{3,}")


def terms(q: str) -> set[str]:
    return {w for w in WORD.findall(q.lower()) if w not in STOP}


def search(s: Session, question: str, k: int = 5) -> list[NoteChunk]:
    want = terms(question)
    if not want:
        return []
    scored = []
    for c in s.scalars(select(NoteChunk)):
        tf = Counter(WORD.findall(c.text.lower()))
        tf.update({w: n * 3 for w, n in Counter(WORD.findall(c.heading.lower())).items()})
        hit = [w for w in want if tf[w]]
        if hit:
            scored.append((len(hit) * 10 + sum(min(tf[w], 5) for w in hit), c))
    scored.sort(key=lambda x: (-x[0], x[1].path, x[1].chunk_index))
    return [c for _, c in scored[:k]]
