"""The 'lens': highlight reader, section navigation and document-type hints (no AI, no quota)."""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from html import escape

from .search import MARK

_MON = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?"
PATTERNS = {
    "date": rf"\b(?:\d{{1,2}}[/\-.]\d{{1,2}}[/\-.]\d{{2,4}}|\d{{4}}-\d{{2}}-\d{{2}}|{_MON} \d{{1,2}},? \d{{4}}|\d{{1,2}} {_MON},? \d{{4}})\b",
    "money": r"(?:[$€£₹]\s?\d[\d,]*(?:\.\d+)?|\b(?:USD|EUR|INR|GBP|Rs\.?)\s?\d[\d,]*(?:\.\d+)?)",
    "email": r"[\w.+-]+@[\w-]+\.[\w.-]+",
    "link": r"https?://[^\s<>\"')]+",
}
OPTIONS = {"Dates": "date", "Amounts": "money", "Emails": "email", "Links": "link", "Key terms": "key"}
LABELS = {"term": "Search", "date": "Dates", "money": "Amounts", "email": "Emails", "link": "Links", "key": "Key terms"}


def build_pattern(kinds, term: str = "", keywords: tuple = ()):
    parts = []
    if term and len(term) >= 2:
        parts.append(("term", re.escape(term)))                 # search term wins any overlap
    for k in ("date", "money", "email", "link"):
        if k in kinds:
            parts.append((k, PATTERNS[k]))
    if "key" in kinds and keywords:
        parts.append(("key", r"\b(?:" + "|".join(re.escape(w) for w in keywords) + r")\b"))
    if not parts:
        return None
    return re.compile("|".join(f"(?P<{n}>{p})" for n, p in parts), re.I)


def highlight(text: str, pat) -> tuple[str, Counter]:
    """HTML-safe text with <span class="hl hl-KIND"> around matches."""
    counts: Counter = Counter()
    if pat is None:
        return escape(text), counts
    out, last = [], 0
    for m in pat.finditer(text):
        out.append(escape(text[last:m.start()]))
        counts[m.lastgroup] += 1
        out.append(f'<span class="hl hl-{m.lastgroup}">{escape(m.group(0))}</span>')
        last = m.end()
    out.append(escape(text[last:]))
    return "".join(out), counts


def count_all(text: str, pat) -> Counter:
    c: Counter = Counter()
    if pat is not None:
        for m in pat.finditer(text):
            c[m.lastgroup] += 1
    return c


# ── Sections for the reader ────────────────────────────────────────────────────

def _split_long(label: str, body: str, size: int = 4000) -> list[tuple[str, str]]:
    body = body.strip("\n")
    if len(body) <= size * 1.5:
        return [(label, body)]
    parts, cur = [], ""
    for line in body.split("\n"):
        if len(cur) + len(line) > size and cur:
            parts.append(cur)
            cur = ""
        while len(line) > size:
            parts.append(line[:size])
            line = line[size:]
        cur += line + "\n"
    if cur.strip():
        parts.append(cur)
    return [(f"{label} · Part {i}", p.strip("\n")) for i, p in enumerate(parts, 1)]


def split_sections(text: str) -> list[tuple[str, str]]:
    """[(label, body)] — by [Page N]/[Slide N] when present, else by file, else by length."""
    marks = list(MARK.finditer(text))
    if not marks:
        return _split_long("Full text", text)
    sections, cur_file = [], ""
    if text[:marks[0].start()].strip():
        sections += _split_long("Start", text[:marks[0].start()])
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        body = text[m.end():end]
        if m.group(3):
            cur_file, label = m.group(3), m.group(3)
        else:
            label = f"{m.group(1)} {m.group(2)}"
            if cur_file:
                label = f"{cur_file} · {label}"
        if body.strip():
            sections += _split_long(label, body)
    return sections or _split_long("Full text", text)


# ── What kind of document is this? ─────────────────────────────────────────────

@dataclass
class Guess:
    emoji: str
    label: str
    modes: tuple      # suggested mode keys


_TYPES = {
    "invoice": ("🧾", "invoice", ("data", "full"), ["invoice", "bill to", "amount due", "subtotal", "total due", "unit price", "qty",
                                                      "quantity", "payment terms", "tax", "invoice no", "due date"]),
    "contract": ("📜", "contract / agreement", ("legal", "risks"), ["agreement", "hereby", "parties", "party", "shall", "termination",
                 "governing law", "indemnify", "confidential", "liability", "warranty", "effective date", "whereas"]),
    "resume": ("👤", "résumé / CV", ("entities", "keypoints"), ["experience", "education", "skills", "resume", "curriculum vitae",
              "objective", "certifications", "linkedin", "projects", "references available"]),
    "paper": ("🔬", "research paper", ("summary", "concepts"), ["abstract", "introduction", "methodology", "references", "et al",
              "conclusion", "figure", "results", "literature review", "hypothesis"]),
    "meeting": ("🗓️", "meeting notes", ("actions", "summary"), ["agenda", "attendees", "action items", "minutes", "discussed",
               "next steps", "follow up", "meeting"]),
    "financial": ("📈", "financial report", ("data", "summary"), ["revenue", "quarter", "fiscal", "profit", "ebitda", "balance sheet",
                 "cash flow", "net income", "earnings", "shareholders"]),
    "study": ("🎓", "study material", ("study", "concepts"), ["chapter", "definition", "example", "exercise", "theorem", "lecture",
             "syllabus", "unit", "learning objectives"]),
}


def guess_type(text: str, ftype: str = "") -> Guess | None:
    if len(text) < 200:
        return None
    if ftype.upper() == "PPTX":
        return Guess("📊", "presentation", ("summary", "keypoints"))
    sample = text[:60_000].lower()
    scores = {}
    for key, (_, _, _, words) in _TYPES.items():
        scores[key] = sum(1 for w in words if re.search(rf"\b{re.escape(w)}\b", sample))
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    (best, top), (_, second) = ranked[0], ranked[1]
    if top < 4 or top - second < 2:                           # only speak up when it's fairly clear
        return None
    e, label, modes, _ = _TYPES[best]
    return Guess(e, label, modes)
