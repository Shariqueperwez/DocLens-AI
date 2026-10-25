"""Structured field extraction: 'give me Invoice No, Date, Total from these files' -> table."""
from __future__ import annotations

import json
import re

PRESETS: dict[str, list[str]] = {
    "🧾 Invoice": ["Invoice number", "Invoice date", "Due date", "Vendor", "Bill to", "Subtotal", "Tax", "Total amount", "Currency"],
    "👤 Resume": ["Full name", "Email", "Phone", "Current role", "Years of experience", "Top skills", "Education", "Location"],
    "📜 Contract": ["Parties", "Effective date", "Term / duration", "Payment terms", "Termination clause", "Governing law", "Total value"],
    "🧾 Receipt": ["Merchant", "Date", "Items purchased", "Payment method", "Total paid"],
}
MAX_FIELDS = 12
NOT_FOUND = "Not found"


def parse_fields(raw: str) -> list[str]:
    seen, out = set(), []
    for part in re.split(r"[,\n;]", raw):
        f = part.strip(" \t-•*")
        if f and f.lower() not in seen:
            seen.add(f.lower())
            out.append(f[:60])
    return out[:MAX_FIELDS]


def build_messages(fields: list[str], name: str, text: str, limit: int = 60_000) -> list[dict]:
    if len(text) > limit:                                   # keep head + tail: key data is usually at the start or end
        text = text[: int(limit * 0.7)] + "\n[… middle trimmed …]\n" + text[-int(limit * 0.3):]
    system = (
        "You extract structured data from documents. Return ONLY one JSON object with exactly these keys: "
        + json.dumps(fields, ensure_ascii=False)
        + f". Every value must be a short string copied or normalised from the document. If a field is absent, use \"{NOT_FOUND}\". "
        "Never guess or invent. Keep numbers and currency exactly as written. No markdown, no commentary."
    )
    return [{"role": "system", "content": system},
            {"role": "user", "content": f"File: {name}\n<document>\n{text}\n</document>"}]


def parse_json(reply: str) -> dict:
    """Tolerant JSON parsing: strips code fences/chatter around the object."""
    t = re.sub(r"```(?:json)?", "", reply).strip()
    i, j = t.find("{"), t.rfind("}")
    if i == -1 or j <= i:
        return {}
    try:
        data = json.loads(t[i:j + 1])
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def to_row(fields: list[str], name: str, reply: str) -> dict:
    data = parse_json(reply)
    lower = {str(k).strip().lower(): v for k, v in data.items()}
    row = {"File": name}
    for f in fields:
        v = lower.get(f.lower(), NOT_FOUND)
        if isinstance(v, (list, tuple)):
            v = "; ".join(str(x) for x in v)
        elif isinstance(v, dict):
            v = "; ".join(f"{k}: {x}" for k, x in v.items())
        row[f] = NOT_FOUND if v is None or str(v).strip() == "" else str(v).strip()
    return row
