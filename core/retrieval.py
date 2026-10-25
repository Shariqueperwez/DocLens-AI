"""Lightweight relevance search so chat stays fast and accurate on very large documents.

Instead of cutting the middle out of a big document, we split it into sections, score them against the
question (TF-IDF style) and send only the most relevant ones.
"""
from __future__ import annotations

import math
import re
from collections import Counter

from html import escape

from .documents import STOP
from .llm import chunk_text
from .search import MARK

_TOK = re.compile(r"[A-Za-z0-9][A-Za-z0-9'\-]+")
CHUNK = 2500


def tokens(s: str) -> list[str]:
    return [w for w in (t.lower() for t in _TOK.findall(s)) if w not in STOP]


def build_index(text: str):
    chunks = chunk_text(text, CHUNK)
    tfs = [Counter(tokens(c)) for c in chunks]
    df: Counter = Counter()
    for tf in tfs:
        df.update(tf.keys())
    return chunks, tfs, dict(df)


def select_context(index, query: str, budget: int) -> tuple[str, int, int]:
    """Return (context_text, sections_used, sections_total) within `budget` characters."""
    chunks, tfs, df = index
    n = len(chunks)
    q = set(tokens(query))
    scores = []
    for i, tf in enumerate(tfs):
        sc = sum((1 + math.log(tf[t])) * math.log(1 + n / df[t]) for t in q if t in tf and t in df)
        scores.append(sc)
    order = sorted(range(n), key=lambda i: scores[i], reverse=True)
    if not order or scores[order[0]] == 0:                      # nothing matched: spread evenly across the document
        step = max(1, n // max(1, budget // CHUNK))
        order = list(range(0, n, step))
    picked, used = {0}, len(chunks[0])                           # always keep the opening (title, intro)
    for i in order:
        if i in picked:
            continue
        if used + len(chunks[i]) > budget:
            continue
        picked.add(i)
        used += len(chunks[i])
    parts, prev = [], -1
    for i in sorted(picked):
        if prev != -1 and i != prev + 1:
            parts.append("[… other sections omitted …]")
        parts.append(chunks[i].strip())
        prev = i
    return "\n\n".join(parts), len(picked), n


def _label_for(chunks: list[str], i: int) -> str:
    """Nearest preceding [Page N] / file marker for chunk i."""
    page = file_ = ""
    for j in range(i, -1, -1):
        for m in reversed(list(MARK.finditer(chunks[j]))):
            if m.group(3) and not file_:
                file_ = m.group(3)
            elif m.group(1) and not page:
                page = f"{m.group(1)} {m.group(2)}"
            if page and file_:
                break
        if page and file_:
            break
    return " · ".join(x for x in (file_, page) if x) or "Document"


def top_passages(index, query: str, k: int = 3, width: int = 460) -> list[tuple[str, str]]:
    """[(label, html_snippet)] — the passages most relevant to `query`, with matching words highlighted."""
    chunks, tfs, df = index
    n, q = len(chunks), set(tokens(query))
    if not q:
        return []
    scored = []
    for i, tf in enumerate(tfs):
        sc = sum((1 + math.log(tf[t])) * math.log(1 + n / df[t]) for t in q if t in tf and t in df)
        if sc > 0:
            scored.append((sc, i))
    scored.sort(reverse=True)
    pat = re.compile("|".join(re.escape(t) for t in sorted(q, key=len, reverse=True)), re.I)
    out = []
    for _, i in scored[:k]:
        clean = re.sub(r"\s+", " ", MARK.sub(" ", chunks[i])).strip()
        m = pat.search(clean)
        start = max(0, (m.start() if m else 0) - width // 3)
        seg = clean[start:start + width]
        html, last = [], 0
        for mm in pat.finditer(seg):
            html += [escape(seg[last:mm.start()]), "<mark>", escape(mm.group(0)), "</mark>"]
            last = mm.end()
        html.append(escape(seg[last:]))
        out.append((_label_for(chunks, i), ("…" if start else "") + "".join(html) + ("…" if start + width < len(clean) else "")))
    return out
