"""LLM layer for DocLens.

Talks to any OpenAI-compatible provider. Free providers are tried in order and
the app automatically fails over when one is rate-limited, retired or down.
"""
from __future__ import annotations

import base64
import os
import time
from dataclasses import dataclass, field
from typing import Callable, Iterator

import streamlit as st
from openai import OpenAI


class LLMError(Exception):
    """Raised when no provider could answer. Message is safe to show to users."""


# ── Provider catalogue ─────────────────────────────────────────────────────────

@dataclass
class Provider:
    key: str
    label: str
    api_key: str
    base_url: str
    models: list[str]
    max_chars: int                      # safe context size (characters) per request
    vision: bool = False
    extra_body: dict = field(default_factory=dict)


def _secret(name: str, default: str = "") -> str:
    val = os.environ.get(name)
    if val:
        return val.strip()
    try:
        return str(st.secrets.get(name, default) or default).strip()
    except Exception:  # no secrets file at all
        return default


def _build(key: str, api_key: str) -> Provider:
    if key == "gemini":
        return Provider(
            key="gemini", label="Gemini", api_key=api_key,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            models=[_secret("GEMINI_MODEL", "gemini-2.5-flash"), "gemini-2.5-flash-lite"],
            max_chars=400_000, vision=True,
            extra_body={"reasoning_effort": "low"},   # keep thinking tokens from eating the output budget
        )
    if key == "openrouter":
        return Provider(
            key="openrouter", label="OpenRouter", api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
            models=[_secret("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free"),
                    "google/gemma-3-27b-it:free"],
            max_chars=120_000,
        )
    return Provider(
        key="groq", label="Groq", api_key=api_key,
        base_url="https://api.groq.com/openai/v1",
        models=[_secret("GROQ_MODEL", "llama-3.3-70b-versatile"), "llama-3.1-8b-instant"],
        max_chars=28_000,
    )


def get_providers() -> list[Provider]:
    """Providers that have a key configured (environment or Streamlit secrets), best first."""
    providers: list[Provider] = []
    for pkey, env in (("gemini", "GEMINI_API_KEY"), ("openrouter", "OPENROUTER_API_KEY"), ("groq", "GROQ_API_KEY")):
        k = _secret(env)
        if k:
            providers.append(_build(pkey, k))
    return providers


def has_provider() -> bool:
    return bool(get_providers())


def context_limit() -> int:
    provs = get_providers()
    return provs[0].max_chars if provs else 28_000


def active_label() -> str:
    provs = get_providers()
    if not provs:
        return "No API key"
    return " → ".join(p.label for p in provs)


# ── Helpers ────────────────────────────────────────────────────────────────────

def fit_messages(messages: list[dict], max_chars: int) -> list[dict]:
    """Trim the longest text message (keeping head + tail) so the request fits."""
    msgs = [dict(m) for m in messages]
    total = sum(len(m["content"]) for m in msgs if isinstance(m["content"], str))
    if total <= max_chars:
        return msgs
    idx = max((i for i, m in enumerate(msgs) if isinstance(m["content"], str)),
              key=lambda i: len(msgs[i]["content"]))
    over = total - max_chars
    text = msgs[idx]["content"]
    keep = max(2000, len(text) - over - 200)
    head, tail = int(keep * 0.7), int(keep * 0.3)
    msgs[idx]["content"] = (text[:head] + "\n\n[… middle of document trimmed to fit the model's limit …]\n\n"
                            + text[-tail:])
    return msgs


def _status(e: Exception) -> int | None:
    return getattr(e, "status_code", None)


def _short(e: Exception) -> str:
    code = _status(e)
    if code == 429:
        return "rate limit reached"
    if code in (401, 403):
        return "API key rejected"
    if code == 404:
        return "model unavailable"
    return (str(e) or type(e).__name__)[:90]


# ── Streaming chat with failover ───────────────────────────────────────────────

def stream_chat(messages: list[dict], max_tokens: int = 6000, meta: dict | None = None) -> Iterator[str]:
    """Yield text chunks. Falls through providers/models until one produces output."""
    providers = get_providers()
    if not providers:
        raise LLMError("No API key configured.")
    errors: list[str] = []

    for p in providers:
        client = OpenAI(api_key=p.api_key, base_url=p.base_url, timeout=90, max_retries=0)
        skip_provider = False
        for model in p.models:
            if skip_provider:
                break
            for use_extra in ((True, False) if p.extra_body else (False,)):
                started = False
                try:
                    kwargs = dict(model=model, messages=fit_messages(messages, p.max_chars),
                                  max_tokens=max_tokens, stream=True)
                    if use_extra:
                        kwargs["extra_body"] = p.extra_body
                    for chunk in client.chat.completions.create(**kwargs):
                        if not chunk.choices:
                            continue
                        piece = chunk.choices[0].delta.content
                        if piece:
                            if not started and meta is not None:
                                meta["model"] = f"{p.label} · {model}"
                            started = True
                            yield piece
                    if started:
                        return
                    errors.append(f"{p.label}/{model}: empty response")
                    break                       # try next model
                except Exception as e:  # noqa: BLE001 - fail over on anything
                    if started:
                        yield "\n\n> ⚠️ The response was interrupted. Click **Extract** again to retry."
                        return
                    if _status(e) == 400 and use_extra:
                        continue                # retry same model without provider-specific extras
                    errors.append(f"{p.label}/{model}: {_short(e)}")
                    if _status(e) in (401, 403):
                        skip_provider = True    # bad key -> skip this provider's other models
                    break

    raise LLMError("All AI providers failed right now.\n\n" + "\n".join(f"• {e}" for e in errors[-6:]))


def complete(messages: list[dict], max_tokens: int = 2000) -> str:
    return "".join(stream_chat(messages, max_tokens=max_tokens))


# ── Long-document handling (map → reduce) ──────────────────────────────────────

def chunk_text(text: str, size: int) -> list[str]:
    paras, chunks, cur = text.split("\n"), [], ""
    for line in paras:
        if len(cur) + len(line) + 1 > size and cur:
            chunks.append(cur)
            cur = ""
        while len(line) > size:                      # a single enormous line
            chunks.append(line[:size])
            line = line[size:]
        cur += line + "\n"
    if cur.strip():
        chunks.append(cur)
    return chunks


MAX_CHUNKS = 40


def complete_retry(messages: list[dict], max_tokens: int, tries: int = 3) -> str:
    """Free tiers rate-limit bursts; wait a little and retry before giving up."""
    for attempt in range(tries):
        try:
            return complete(messages, max_tokens=max_tokens)
        except LLMError:
            if attempt == tries - 1:
                raise
            time.sleep(6 * (attempt + 1))
    return ""


def condense(text: str, limit: int, progress: Callable[[str], None] | None = None) -> tuple[str, bool, float]:
    """If text exceeds `limit`, summarise it chunk-by-chunk so the WHOLE document is represented.

    Returns (text, was_condensed, coverage) where coverage is the fraction (0-1) of the original that was read.
    """
    if len(text) <= limit:
        return text, False, 1.0
    coverage = 1.0
    for round_no in range(3):
        if len(text) <= limit:
            break
        size = int(min(limit * 0.8, max(limit // 2, len(text) / MAX_CHUNKS + 1)))   # bigger chunks beat dropping the tail
        chunks = chunk_text(text, size)
        if round_no == 0:
            coverage = min(1.0, MAX_CHUNKS / len(chunks))
        chunks = chunks[:MAX_CHUNKS]
        parts = []
        for i, ch in enumerate(chunks, 1):
            if progress:
                progress(f"Long document — condensing part {i}/{len(chunks)}…")
            parts.append(complete_retry([
                {"role": "system", "content": "Condense this document excerpt into dense notes. Keep EVERY name, number, date, "
                                              "obligation, decision and [Page N] marker. No commentary. Max ~300 words."},
                {"role": "user", "content": ch},
            ], max_tokens=900))
        text = "\n\n".join(parts)
    return text, True, coverage


# ── Vision OCR (scanned PDFs / images) ─────────────────────────────────────────

def vision_available() -> bool:
    return any(p.vision for p in get_providers())


def ocr_images(images: list[tuple], progress: Callable[[str], None] | None = None) -> str:
    """OCR page images with a vision model. images = [(bytes, mime) or (bytes, mime, page_number), ...]."""
    prov = next((p for p in get_providers() if p.vision), None)
    if prov is None:
        raise LLMError("Reading scanned pages needs a Gemini key (the only free provider here with vision).")
    client = OpenAI(api_key=prov.api_key, base_url=prov.base_url, timeout=120, max_retries=1)
    imgs = [(im[0], im[1], im[2] if len(im) > 2 else i + 1) for i, im in enumerate(images)]
    out, batch = [], 4
    for start in range(0, len(imgs), batch):
        group = imgs[start:start + batch]
        if progress:
            progress(f"Reading scanned pages {start + 1}–{start + len(group)} of {len(imgs)}…")
        labels = ", ".join(str(g[2]) for g in group)
        content = [{"type": "text", "text":
                    "Transcribe ALL text from these document page images, in reading order. Preserve headings, lists and "
                    "tables (use Markdown tables). The images are pages " + labels + " in that order; begin each page with a "
                    "line '[Page N]' using those numbers. Output only the transcription."}]
        for data, mime, _ in group:
            content.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{base64.b64encode(data).decode()}"}})
        last_err = None
        for model in prov.models:
            try:
                r = client.chat.completions.create(model=model, messages=[{"role": "user", "content": content}],
                                                   max_tokens=8000, extra_body=prov.extra_body or None)
                out.append(r.choices[0].message.content or "")
                break
            except Exception as e:  # noqa: BLE001
                last_err = e
        else:
            raise LLMError(f"OCR failed: {_short(last_err)}")
    return "\n\n".join(out)
