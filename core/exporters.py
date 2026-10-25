"""Turn Markdown results into downloadable files."""
from __future__ import annotations

import io
import json
import re
from datetime import datetime

import markdown as md_lib

NOW = lambda: datetime.now().strftime("%Y-%m-%d %H:%M")  # noqa: E731


def to_txt(content: str) -> bytes:
    t = re.sub(r"^#{1,6}\s*", "", content, flags=re.M)
    t = re.sub(r"\*\*(.+?)\*\*", r"\1", t)
    t = re.sub(r"(?<!\*)\*(?!\s)(.+?)\*(?!\*)", r"\1", t)
    return t.replace("`", "").encode("utf-8")


def to_md(content: str, filename: str, mode: str = "") -> bytes:
    head = f"# DocLens — {filename}\n*{mode} · {NOW()}*\n\n---\n\n"
    return (head + content).encode("utf-8")


_HTML = """<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>DocLens — {title}</title><style>
body{{font-family:Georgia,serif;max-width:820px;margin:48px auto;padding:0 24px;background:#f9f6f0;color:#1a1917;line-height:1.75}}
h1{{font-size:2rem;border-bottom:2px solid #c9a84c;padding-bottom:.3em}} h2{{color:#b5451b;margin-top:1.9em;border-bottom:1px solid #e4dccb;padding-bottom:.2em}}
h3{{color:#3d6b4f}} .meta{{font-family:monospace;font-size:.78rem;color:#8a9ba8}} table{{border-collapse:collapse;width:100%;margin:1em 0;font-size:.95rem}}
th,td{{border:1px solid #d9d0bc;padding:.5em .7em;text-align:left}} th{{background:#ede7d9}} code{{background:#ede7d9;padding:.1em .35em;border-radius:3px}}
blockquote{{border-left:3px solid #c9a84c;margin:1em 0;padding:.2em 1em;color:#555;background:#f3eddf}}
@media print{{body{{background:#fff;margin:0}}}}</style></head><body>
<p class="meta">◈ DocLens AI · {when} · {title} · {mode}</p><hr>{body}</body></html>"""


def to_html(content: str, filename: str, mode: str = "") -> bytes:
    body = md_lib.markdown(content, extensions=["extra", "sane_lists", "nl2br"])
    body = re.sub(r"(?is)<(script|iframe|object|embed)\b.*?</\1>", "", body)          # never ship active content
    body = re.sub(r"(?i)\son\w+\s*=\s*(\"[^\"]*\"|'[^']*')", "", body)
    return _HTML.format(title=filename, when=NOW(), mode=mode, body=body).encode("utf-8")


def to_json(content: str, filename: str, mode: str, model: str = "") -> bytes:
    sections, title, buf = [], None, []
    for line in content.split("\n"):
        if line.startswith("## "):
            if title:
                sections.append({"title": title, "content": "\n".join(buf).strip()})
            title, buf = line[3:].strip(), []
        else:
            buf.append(line)
    if title:
        sections.append({"title": title, "content": "\n".join(buf).strip()})
    payload = {"source_file": filename, "mode": mode, "model": model,
               "generated_at": datetime.now().isoformat(timespec="seconds"), "sections": sections, "content": content}
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


# ── DOCX ───────────────────────────────────────────────────────────────────────

def _runs(par, text: str):
    for i, chunk in enumerate(re.split(r"\*\*(.+?)\*\*", text)):
        if not chunk:
            continue
        run = par.add_run(chunk.replace("`", ""))
        run.bold = i % 2 == 1


def to_docx(content: str, filename: str, mode: str = "") -> bytes:
    from docx import Document
    from docx.shared import Pt, RGBColor

    doc = Document()
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(11)
    title = doc.add_heading("DocLens Extraction", 0)
    for r in title.runs:
        r.font.color.rgb = RGBColor(0xB5, 0x45, 0x1B)
    meta = doc.add_paragraph()
    mr = meta.add_run(f"{filename}  ·  {mode}  ·  {NOW()}")
    mr.italic, mr.font.size = True, Pt(9)

    lines, i = content.split("\n"), 0
    while i < len(lines):
        line = lines[i].rstrip()
        if line.startswith("|"):                                   # Markdown table
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                if not re.match(r"^\|[\s:\-|]+\|?$", lines[i].strip()):
                    rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            if rows:
                cols = max(len(r) for r in rows)
                t = doc.add_table(rows=len(rows), cols=cols)
                t.style = "Light Grid Accent 1"
                for ri, row in enumerate(rows):
                    for ci in range(cols):
                        cell = t.cell(ri, ci)
                        cell.text = ""
                        _runs(cell.paragraphs[0], row[ci] if ci < len(row) else "")
                        if ri == 0:
                            for r in cell.paragraphs[0].runs:
                                r.bold = True
            continue
        m = re.match(r"^(#{1,4})\s+(.*)", line)
        if m:
            doc.add_heading(m.group(2).strip(), min(len(m.group(1)), 3))
        elif re.match(r"^\s*[-*•]\s+", line):
            _runs(doc.add_paragraph(style="List Bullet"), re.sub(r"^\s*[-*•]\s+(\[[ xX]\]\s*)?", "", line))
        elif re.match(r"^\s*\d+[.)]\s+", line):
            _runs(doc.add_paragraph(style="List Number"), re.sub(r"^\s*\d+[.)]\s+", "", line))
        elif line.strip() in ("---", "***"):
            pass
        elif line.strip():
            _runs(doc.add_paragraph(), line.lstrip("> "))
        i += 1

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def chat_to_md(messages: list[dict], filename: str) -> bytes:
    out = [f"# DocLens Chat — {filename}", f"*{NOW()}*", ""]
    for m in messages:
        out.append(f"**{'You' if m['role'] == 'user' else 'DocLens'}:** {m['content']}\n")
    return "\n".join(out).encode("utf-8")


# ── Tables (Fields -> Excel) ───────────────────────────────────────────────────

def to_csv(df) -> bytes:
    return df.to_csv(index=False).encode("utf-8-sig")        # utf-8-sig so Excel opens it with correct characters


def to_xlsx(df) -> bytes:
    from openpyxl.styles import Alignment, Font, PatternFill
    buf = io.BytesIO()
    with __import__("pandas").ExcelWriter(buf, engine="openpyxl") as xw:
        df.to_excel(xw, index=False, sheet_name="DocLens")
        ws = xw.sheets["DocLens"]
        for c in ws[1]:
            c.font, c.fill = Font(bold=True, color="FFFFFF"), PatternFill("solid", fgColor="B5451B")
            c.alignment = Alignment(vertical="center", wrap_text=True)
        for col in ws.columns:
            width = max(len(str(c.value or "")) for c in col)
            ws.column_dimensions[col[0].column_letter].width = min(max(12, width + 2), 48)
            for c in col[1:]:
                c.alignment = Alignment(vertical="top", wrap_text=True)
        ws.freeze_panes = "A2"
    return buf.getvalue()
