"""Index vault notes into heading chunks so questions can be answered from them. Read only."""

import hashlib
import re
from datetime import datetime
from fnmatch import fnmatch
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import NoteChunk
from app.sources.obsidian import iter_notes

HEAD = re.compile(r"^#{1,6}\s+(.*)$")
PRIVATE_TAG = re.compile(r"(?m)(^|\s)#private\b|^tags:.*\bprivate\b")
CHUNK_CHARS = 1500


def split_chunks(text: str) -> list[tuple[str, str]]:
    out, head, buf = [], "", []

    def flush():
        body = "\n".join(buf).strip()
        for i in range(0, len(body), CHUNK_CHARS):
            out.append((head, body[i : i + CHUNK_CHARS]))

    for line in text.splitlines():
        if m := HEAD.match(line):
            flush()
            head, buf = m.group(1).strip(), []
        else:
            buf.append(line)
    flush()
    return out


def index_vault(
    s: Session,
    vault_path,
    now: datetime,
    ignore_globs=("templates/*", "archive/*"),
    private_globs=(),
    max_bytes: int = 1_000_000,
) -> int:
    """Re-index only chunks whose content changed. Returns the number of chunks written."""
    existing: dict[str, dict[int, NoteChunk]] = {}
    for c in s.scalars(select(NoteChunk)):
        existing.setdefault(c.path, {})[c.chunk_index] = c
    seen, changed = set(), 0
    for rel, p in iter_notes(Path(vault_path), ignore_globs, max_bytes):
        if any(fnmatch(rel, g) for g in private_globs):
            continue
        text = p.read_text(errors="replace")
        if PRIVATE_TAG.search(text):
            continue
        seen.add(rel)
        have = existing.get(rel, {})
        chunks = split_chunks(text)
        for i, (head, body) in enumerate(chunks):
            h = hashlib.sha256(f"{head}\x1f{body}".encode()).hexdigest()
            row = have.get(i)
            if row and row.content_hash == h:
                continue
            if row:
                row.heading, row.content_hash, row.text, row.updated_at = head, h, body, now
            else:
                s.add(
                    NoteChunk(
                        path=rel,
                        chunk_index=i,
                        heading=head,
                        content_hash=h,
                        text=body,
                        updated_at=now,
                    )
                )
            changed += 1
        for i, row in have.items():
            if i >= len(chunks):
                s.delete(row)
                changed += 1
    gone = set(existing) - seen
    if gone:  # deleted, ignored or newly private notes leave the index
        s.execute(delete(NoteChunk).where(NoteChunk.path.in_(gone)))
        changed += sum(len(existing[g]) for g in gone)
    s.commit()
    return changed
