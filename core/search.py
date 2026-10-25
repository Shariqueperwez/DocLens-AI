"""Instant in-document search (no AI, no quota)."""
from __future__ import annotations

import bisect
import re
from dataclasses import dataclass
from html import escape

MARK = re.compile(r"\[(Page|Slide) (\d+)\]|=== FILE: (.+?) ===")


@dataclass
class Hit:
    where: str
    html: str


def search(text: str, query: str, max_hits: int = 40, context: int = 90) -> tuple[list[Hit], int]:
    """Returns (hits, total_matches). Each hit knows its file/page and has a highlighted snippet (HTML-safe)."""
    query = query.strip()
    if len(query) < 2 or not text:
        return [], 0
    marks = [(m.start(), m) for m in MARK.finditer(text)]
    positions = [p for p, _ in marks]
    # ignore matches that fall inside our own [Page N] / === FILE === markers
    matches = []
    for m in re.finditer(re.escape(query), text, flags=re.I):
        i = bisect.bisect_right(positions, m.start()) - 1
        if i >= 0 and m.start() < marks[i][1].end():
            continue
        matches.append(m)
    hits = []
    for m in matches[:max_hits]:
        file_, page = "", ""
        idx = bisect.bisect_right(positions, m.start()) - 1
        k = idx                       # walk back to the latest page marker and latest file marker
        while k >= 0 and (not page or not file_):
            mk = marks[k][1]
            if mk.group(3) and not file_:
                file_ = mk.group(3)
            elif mk.group(1) and not page:
                page = f"{mk.group(1)} {mk.group(2)}"
            k -= 1
        where = " · ".join(x for x in (file_, page) if x) or "Document"
        lo = marks[idx][1].end() if idx >= 0 else 0                       # keep the snippet inside this page/section
        hi = positions[idx + 1] if idx + 1 < len(positions) else len(text)
        a, b = max(lo, m.start() - context), min(hi, m.end() + context)
        snippet = (("…" if a > lo else "") + escape(text[a:m.start()]).lstrip() + "<mark>" + escape(m.group(0)) + "</mark>"
                   + escape(text[m.end():b]).rstrip() + ("…" if b < hi else ""))
        hits.append(Hit(where, re.sub(r"\s+", " ", snippet)))
    return hits, len(matches)


def similarity(a: str, b: str) -> tuple[float, int, int]:
    """Sentence-level similarity of two documents -> (percent, only_in_a, only_in_b)."""
    def sents(t: str) -> set[str]:
        t = MARK.sub(" ", t)
        return {re.sub(r"\s+", " ", s).strip().lower() for s in re.split(r"(?<=[.!?])\s+|\n+", t) if len(s.strip()) > 12}
    sa, sb = sents(a), sents(b)
    if not sa and not sb:
        return 0.0, 0, 0
    union = len(sa | sb)
    return round(100 * len(sa & sb) / union, 1), len(sa - sb), len(sb - sa)
