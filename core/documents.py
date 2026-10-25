"""Reading documents and computing quick analytics (no AI needed)."""
from __future__ import annotations

import io
import re
from collections import Counter
from dataclasses import dataclass, field
from html import unescape

IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp")
SUPPORTED = ["pdf", "docx", "pptx", "txt", "md", "rst", "csv", "log", "json", "html", "htm",
             "png", "jpg", "jpeg", "webp"]


DEFAULT_MAX_PAGES = 300      # used when the visitor gives no page range
HARD_MAX_PAGES = 600         # ceiling even for explicit ranges


@dataclass
class Parsed:
    name: str
    ftype: str
    text: str = ""
    pages: int = 0               # total pages / slides in the file
    selected: list = field(default_factory=list)   # 1-based pages actually analysed
    needs_ocr: bool = False
    raw: bytes = b""
    warning: str = ""
    note: str = ""               # friendly coverage message, e.g. "Analysing pages 1–300 of 5,000"


def parse_page_spec(spec: str, total: int) -> list[int]:
    """'1-50, 80, 120-180' -> sorted page list. Raises ValueError with a friendly message."""
    pages: set[int] = set()
    for part in re.split(r"[,;]", spec):
        part = part.strip()
        if not part:
            continue
        m = re.fullmatch(r"(\d+)\s*[-–:]\s*(\d+)", part)
        if m:
            a, b = sorted((int(m[1]), int(m[2])))
            pages.update(range(max(a, 1), min(b, total) + 1))
        elif part.isdigit():
            if 1 <= int(part) <= total:
                pages.add(int(part))
        else:
            raise ValueError(f"Can't understand page range '{part}'. Use something like 1-50, 80, 120-180.")
    if not pages:
        raise ValueError(f"No pages match that range — this file has {total:,} pages.")
    return sorted(pages)


def select_pages(total: int, spec: str = "", max_pages: int = DEFAULT_MAX_PAGES) -> list[int]:
    if spec.strip():
        return parse_page_spec(spec, total)[:HARD_MAX_PAGES]
    return list(range(1, min(total, max_pages) + 1))


def describe_pages(sel: list[int], total: int, unit: str = "pages") -> str:
    """[1..300] -> 'pages 1–300'; [5,6,7,20] -> 'pages 5–7, 20'."""
    runs, start, prev = [], sel[0], sel[0]
    for n in sel[1:] + [None]:
        if n is None or n != prev + 1:
            runs.append(f"{start}–{prev}" if prev > start else f"{start}")
            start = n
        prev = n if n is not None else prev
    shown = ", ".join(runs[:6]) + (" …" if len(runs) > 6 else "")
    return f"{unit} {shown} of {total:,}"


# ── Format readers ─────────────────────────────────────────────────────────────

def _pdf(raw: bytes, spec: str, max_pages: int) -> tuple[str, int, list[int]]:
    """Returns (text, total_pages, pages_analysed). PyMuPDF is ~10-50x faster than pypdf on big files."""
    try:
        import pymupdf
    except ImportError:
        pymupdf = None
    if pymupdf is not None:
        doc = pymupdf.open(stream=raw, filetype="pdf")
        if doc.needs_pass and not doc.authenticate(""):
            raise ValueError("This PDF is password-protected.")
        total = len(doc)
        sel = select_pages(total, spec, max_pages)
        out = []
        for n in sel:
            t = doc[n - 1].get_text("text").strip()
            if t:
                out.append(f"[Page {n}]\n{t}")
        return "\n\n".join(out), total, sel

    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(raw))
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception:  # noqa: BLE001
            raise ValueError("This PDF is password-protected.")
    total = len(reader.pages)
    sel = select_pages(total, spec, max_pages)
    out = []
    for n in sel:
        t = (reader.pages[n - 1].extract_text() or "").strip()
        if t:
            out.append(f"[Page {n}]\n{t}")
    return "\n\n".join(out), total, sel


def _docx(raw: bytes) -> str:
    import docx
    d = docx.Document(io.BytesIO(raw))
    parts = []
    for p in d.paragraphs:
        if not p.text.strip():
            continue
        style = (p.style.name or "").lower() if p.style is not None else ""
        parts.append(("## " + p.text) if style.startswith("heading") else p.text)
    for ti, table in enumerate(d.tables, 1):
        rows = [" | ".join(c.text.strip().replace("\n", " ") for c in r.cells) for r in table.rows]
        parts.append(f"[Table {ti}]\n" + "\n".join(rows))
    return "\n\n".join(parts)


def _pptx(raw: bytes, spec: str, max_pages: int) -> tuple[str, int, list[int]]:
    from pptx import Presentation
    prs = Presentation(io.BytesIO(raw))
    slides = list(prs.slides)
    sel = select_pages(len(slides), spec, max_pages)
    out = []
    for i in sel:
        slide, lines = slides[i - 1], []
        for shape in slide.shapes:
            if shape.has_text_frame:
                lines += [p.text for p in shape.text_frame.paragraphs if p.text.strip()]
            if getattr(shape, "has_table", False) and shape.has_table:
                lines.append("[Table on this slide]")
                for r in shape.table.rows:
                    lines.append(" | ".join(c.text.strip() for c in r.cells))
        if slide.has_notes_slide and slide.notes_slide.notes_text_frame.text.strip():
            lines.append("Notes: " + slide.notes_slide.notes_text_frame.text.strip())
        if lines:
            out.append(f"[Slide {i}]\n" + "\n".join(lines))
    return "\n\n".join(out), len(slides), sel


def _html(raw: bytes) -> str:
    s = _text(raw)
    s = re.sub(r"(?is)<(script|style).*?</\1>", " ", s)
    s = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</h\d>|</li>", "\n", s)
    return re.sub(r"[ \t]+", " ", unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def _text(raw: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def parse_file(name: str, raw: bytes, page_spec: str = "", max_pages: int = DEFAULT_MAX_PAGES) -> Parsed:
    low = name.lower()
    p = Parsed(name=name, ftype=low.rsplit(".", 1)[-1].upper() if "." in low else "TXT", raw=raw)
    try:
        if low.endswith(".pdf"):
            p.text, p.pages, p.selected = _pdf(raw, page_spec, max_pages)
            p.needs_ocr = len(p.text.strip()) < 40 * max(len(p.selected), 1)
        elif low.endswith(".pptx"):
            p.text, p.pages, p.selected = _pptx(raw, page_spec, max_pages)
        elif low.endswith(".docx"):
            p.text = _docx(raw)
        elif low.endswith((".html", ".htm")):
            p.text = _html(raw)
        elif low.endswith(IMAGE_EXT):
            p.needs_ocr, p.pages, p.selected = True, 1, [1]
        else:
            p.text = _text(raw)
        if p.pages and len(p.selected) < p.pages:
            unit = "slides" if low.endswith(".pptx") else "pages"
            p.note = f"Analysing {describe_pages(p.selected, p.pages, unit)}" + (
                "" if page_spec.strip() else f" (default limit {max_pages}). Use Page range in ⚙️ Advanced options to pick other parts.")
    except ValueError as e:
        p.warning = str(e)
    except Exception as e:  # noqa: BLE001
        p.warning = f"Couldn't read this file ({type(e).__name__}). It may be corrupted."
    return p


OCR_MAX_PAGES = 16


def render_pdf_pages(raw: bytes, pages: list[int] | None = None, max_pages: int = OCR_MAX_PAGES):
    """Render PDF pages to JPEG for vision OCR. Returns [(bytes, mime, page_number)]."""
    import pymupdf
    doc = pymupdf.open(stream=raw, filetype="pdf")
    pages = (pages or list(range(1, len(doc) + 1)))[:max_pages]
    out = []
    for n in pages:
        pix = doc[n - 1].get_pixmap(matrix=pymupdf.Matrix(1.6, 1.6))
        out.append((pix.tobytes("jpeg"), "image/jpeg", n))
    return out


def image_mime(name: str) -> str:
    low = name.lower()
    return "image/png" if low.endswith(".png") else "image/webp" if low.endswith(".webp") else "image/jpeg"


# ── Analytics ──────────────────────────────────────────────────────────────────

STOP = set("""a about above after again all also am an and any are as at be because been before being below between both but by
can could did do does doing down during each few for from further had has have having he her here hers him his how i if in into is it
its just me more most my no nor not now of off on once only or other our out over own page same she should so some such than that the
their them then there these they this those through to too under until up us very was we were what when where which while who whom why
will with would you your yours also may shall per via etc one two use used using new""".split())

_WORD = re.compile(r"[A-Za-z][A-Za-z'\-]{2,}")


@dataclass
class Stats:
    words: int = 0
    chars: int = 0
    sentences: int = 0
    unique: int = 0
    read_min: int = 0
    flesch: float = 0.0
    grade: str = ""
    keywords: list[tuple[str, int]] = field(default_factory=list)
    found: dict[str, int] = field(default_factory=dict)


def _syllables(w: str) -> int:
    w = w.lower()
    groups = re.findall(r"[aeiouy]+", w)
    n = len(groups) - (1 if w.endswith("e") and len(groups) > 1 else 0)
    return max(1, n)


def analyse(text: str) -> Stats:
    s = Stats(chars=len(text))
    words = re.findall(r"\b[\w'’\-]+\b", text)
    s.words = len(words)
    if not s.words:
        return s
    s.read_min = max(1, round(s.words / 200))
    s.sentences = max(1, len(re.findall(r"[.!?]+(?:\s|$)", text)))
    alpha = [w.lower() for w in _WORD.findall(text)]
    s.unique = len(set(alpha))
    if alpha:
        syl = sum(_syllables(w) for w in alpha)
        s.flesch = round(max(0, min(100, 206.835 - 1.015 * (len(alpha) / s.sentences) - 84.6 * (syl / len(alpha)))), 1)
        s.grade = ("Very easy" if s.flesch >= 80 else "Easy" if s.flesch >= 65 else "Standard" if s.flesch >= 50
                   else "Fairly hard" if s.flesch >= 30 else "Very hard")
    s.keywords = Counter(w for w in alpha if w not in STOP and len(w) > 3).most_common(12)
    s.found = {
        "Numbers": len(re.findall(r"\b\d[\d,.]*\b", text)),
        "Dates": len(re.findall(r"\b(?:\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}|\d{4}-\d{2}-\d{2}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.? \d{1,2},? \d{4})\b", text)),
        "Emails": len(re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", text)),
        "Links": len(re.findall(r"https?://\S+", text)),
        "Currency": len(re.findall(r"(?:[$€£₹]\s?\d[\d,.]*|\b(?:USD|EUR|INR|GBP|Rs\.?)\s?\d[\d,.]*)", text)),
    }
    return s
