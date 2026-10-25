"""DocLens AI — document intelligence. Free-tier AI (Gemini + fallbacks), chat, insights, 5 export formats."""
import hashlib
from datetime import datetime
from html import escape
from pathlib import Path

import pandas as pd
import streamlit as st

import time

import streamlit.components.v1 as components

from core import documents as D
from core import fields as FLD
from core import lens as L
from core import search as SRCH
from core import exporters as X
from core import llm
from core import prompts as P
from core import retrieval as R

MAX_FILES = 5

# On phones the result sits far below the Extract button — scroll it into view once it's ready.
SCROLL_TO_TABS = """<script>setTimeout(function(){try{var w=window.parent;if(w.innerWidth>800)return;
var t=w.document.querySelector('.stTabs [role="tablist"]');if(t)t.scrollIntoView({behavior:'smooth',block:'start'});}catch(e){}},400);</script>"""

st.set_page_config(page_title="DocLens AI", page_icon="◈", layout="wide", initial_sidebar_state="collapsed")
st.markdown(f"<style>{(Path(__file__).parent / 'assets' / 'style.css').read_text()}</style>", unsafe_allow_html=True)

for k, v in {"result": None, "fname": "", "mode_key": "", "model_used": "", "history": [], "chat": [],
             "ocr_cache": {}, "doc_sig": ""}.items():
    st.session_state.setdefault(k, v)


# ── Cached parsing ─────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False, max_entries=25, ttl=1800)
def cached_parse(name: str, raw: bytes, spec: str, max_pages: int) -> D.Parsed:
    return D.parse_file(name, raw, spec, max_pages)


@st.cache_data(show_spinner=False, max_entries=10, ttl=1800)
def cached_sections(text: str):
    return L.split_sections(text)


@st.cache_data(show_spinner=False, max_entries=20, ttl=1800)
def cached_counts(text: str, kinds: tuple, term: str, keywords: tuple):
    return dict(L.count_all(text, L.build_pattern(set(kinds), term, keywords)))


@st.cache_data(show_spinner=False, max_entries=6, ttl=1800)
def cached_index(text: str):
    return R.build_index(text)


@st.cache_data(show_spinner=False, max_entries=25, ttl=1800)
def cached_stats(text: str) -> D.Stats:
    return D.analyse(text)


def load_documents(files, use_ocr: bool, spec: str) -> list[D.Parsed]:
    """Parse every upload; run vision-OCR on scanned ones (cached per session)."""
    out = []
    for f in files:
        raw = f.getvalue()
        p = cached_parse(f.name, raw, spec, D.DEFAULT_MAX_PAGES)
        if p.needs_ocr and not p.warning:
            h = hashlib.md5(raw + spec.encode()).hexdigest()
            if h in st.session_state.ocr_cache:
                p.text = st.session_state.ocr_cache[h]
            elif not use_ocr:
                p.warning = "Looks like a scanned/image file. Turn on 'Read scanned pages with AI vision' in Advanced options."
            elif not llm.vision_available():
                p.warning = "Scanned/image file — reading it needs a free Gemini key (it's the vision-capable provider)."
            else:
                try:
                    is_img = f.name.lower().endswith(D.IMAGE_EXT)
                    todo = p.selected[:D.OCR_MAX_PAGES]
                    with st.spinner(f"Reading {len(todo)} scanned page(s) of {f.name} with AI vision…"):
                        imgs = ([(raw, D.image_mime(f.name), 1)] if is_img else D.render_pdf_pages(raw, todo))
                        p.text = llm.ocr_images(imgs)
                    st.session_state.ocr_cache[h] = p.text
                    if not is_img and len(p.selected) > len(todo):
                        p.note = (f"Scanned file: read {len(todo)} of {len(p.selected)} selected pages "
                                  f"(vision limit {D.OCR_MAX_PAGES}). Use Page range to read others.")
                except Exception as e:  # noqa: BLE001
                    p.warning = f"OCR failed: {e}"
        out.append(p)
    return out


def combine(docs: list[D.Parsed]) -> str:
    good = [d for d in docs if d.text.strip()]
    if len(good) == 1:
        return good[0].text
    return "\n\n".join(f"=== FILE: {d.name} ===\n{d.text}" for d in good)


# ── Hero ───────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero">
  <div class="hero-eyebrow">◈ AI-Powered Document Intelligence</div>
  <div class="hero-title">Doc<em>Lens</em></div>
  <div class="hero-sub">Drop any document. Extract, chat, analyse and download the intelligence.</div>
  <div class="hero-pills">
    <span class="pill"><b>16</b> extraction modes</span><span class="pill"><b>Chat</b> with your doc</span>
    <span class="pill"><b>Fields</b> → Excel</span><span class="pill"><b>Compare</b> documents</span>
    <span class="pill"><b>Scanned</b> PDF OCR</span><span class="pill"><b>16</b> languages</span>
  </div>
  <div class="hero-rule"></div>
</div>""", unsafe_allow_html=True)

# The API key is configured by the app owner via secrets — visitors never see or enter one.
ready = llm.has_provider()
if not ready:
    _, mid, _ = st.columns([1, 2, 1])
    mid.markdown("""<div class="setup-card"><h4>The AI service isn't connected yet</h4>
        <div style="font-size:.88rem">App owner: add a free <b>GEMINI_API_KEY</b> in <i>Streamlit → Settings → Secrets</i>
        (or <code>.streamlit/secrets.toml</code> locally), then reload. Get one at aistudio.google.com/apikey.</div></div>""",
                 unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)
col_left, col_right = st.columns([1, 1.65], gap="large")

# ─── LEFT PANEL ────────────────────────────────────────────────────────────────
with col_left:
    st.markdown('<div class="section-label">01 — Upload Document(s)</div>', unsafe_allow_html=True)
    uploads = st.file_uploader("upload", type=D.SUPPORTED, accept_multiple_files=True, label_visibility="collapsed",
                               help=f"Up to {MAX_FILES} files, 5 MB each.")
    if len(uploads) > MAX_FILES:
        st.warning(f"Maximum {MAX_FILES} files at once — using the first {MAX_FILES}.")
        uploads = uploads[:MAX_FILES]
    chips_slot = st.container()

    st.markdown('<div class="section-label" style="margin-top:1.2rem">02 — Choose Extraction Mode</div>',
                unsafe_allow_html=True)
    mode_key = st.selectbox("mode", list(P.MODES), format_func=lambda k: P.MODES[k][0], label_visibility="collapsed")
    st.markdown(f'<div class="mode-desc">{P.MODES[mode_key][1]}</div>', unsafe_allow_html=True)

    st.markdown('<div class="section-label" style="margin-top:1.2rem">03 — Extra Instructions (optional)</div>',
                unsafe_allow_html=True)
    extra = st.text_area("extra", placeholder="e.g. Focus on financial figures only. Ignore the appendix. 2024 data only…",
                         height=88, label_visibility="collapsed")

    with st.expander("⚙️ Advanced options"):
        detail = st.radio("Detail level", list(P.DETAIL), index=1, horizontal=True)
        language = st.selectbox("Output language", P.LANGUAGES)
        page_spec = st.text_input("Page range (PDF / PowerPoint)", placeholder=f"e.g. 1-50, 120-180   (blank = first {D.DEFAULT_MAX_PAGES} pages)",
                                  help="Analyse only the parts you care about. Much faster for huge documents.")
        use_ocr = st.checkbox("Read scanned pages with AI vision", value=True,
                              help="Uses Gemini vision for scanned PDFs and images (first 16 pages).")
    st.markdown("<br>", unsafe_allow_html=True)
    run = st.button("◈  Extract Now", width="stretch", type="primary")

# Load documents (cheap on reruns thanks to caching)
docs = load_documents(uploads, use_ocr, page_spec) if uploads else []

doc_text = combine(docs)
sig = hashlib.md5("|".join(f"{d.name}{len(d.raw)}" for d in docs).encode()).hexdigest() if docs else ""
if sig != st.session_state.doc_sig:                       # new document set → fresh chat
    st.session_state.doc_sig, st.session_state.chat = sig, []
stats = cached_stats(doc_text) if doc_text.strip() else None
names = [d.name for d in docs]

if docs:
    with chips_slot:
        chips = "".join(f'<div class="stat-chip">{escape(d.name[:22] + ("…" if len(d.name) > 22 else ""))}'
                        f'<span>{len(d.raw) / 1024:.0f} KB</span></div>' for d in docs[:4])
        if len(docs) > 4:
            chips += f'<div class="stat-chip">+{len(docs) - 4} more</div>'
        if stats:
            chips += (f'<div class="stat-chip">Words<span>{stats.words:,}</span></div>'
                      f'<div class="stat-chip">Read<span>~{stats.read_min} min</span></div>')
        st.markdown(f'<div class="stat-row" style="margin-top:.9rem">{chips}</div>', unsafe_allow_html=True)
        guess = L.guess_type(doc_text, docs[0].ftype) if len(docs) == 1 else None
        if guess:
            tips = " or ".join(P.MODES[m][0] for m in guess.modes)
            if guess.label in ("invoice", "résumé / CV", "contract / agreement"):
                tips += " — or pull the details into Excel in the 🧾 Fields tab"
            art = "an" if guess.label[0] in "aeiou" else "a"
            st.markdown(f'<div class="mode-desc" style="margin:.6rem 0 0">{guess.emoji} Looks like {art} <b>{guess.label}</b> — try {tips}</div>',
                        unsafe_allow_html=True)
        for d in docs:
            if d.warning:
                st.warning(f"**{d.name}** — {d.warning}")
            elif d.note:
                st.info(f"📄 **{d.name}** — {d.note}")


# ─── RIGHT PANEL ───────────────────────────────────────────────────────────────
def show_error(e: Exception):
    st.error(f"{e}")
    st.caption("This usually clears up in a minute — the free AI tier has per-minute limits. Please try again shortly.")


with col_right:
    tab_ext, tab_chat, tab_fields, tab_lens, tab_ins, tab_hist = st.tabs(
        ["✦ Extract", "💬 Chat", "🧾 Fields", "🔍 Lens", "📈 Stats", "🕘 History"])

    # ── Extraction ──
    with tab_ext:
        st.markdown('<div class="section-label">04 — Extracted Intelligence</div>', unsafe_allow_html=True)
        if run:
            if not ready:
                st.warning("The AI service isn't connected yet — please try again later.")
            elif not docs:
                st.warning("Please upload a document first (step 01).")
            elif mode_key == "compare" and len([d for d in docs if d.text.strip()]) < 2:
                st.warning("Compare mode needs at least **two** documents — upload another file in step 01.")
            elif not doc_text.strip():
                st.error("No readable text found. The file may be image-based or protected.")
            else:
                live = st.empty()
                try:
                    fname_label = ", ".join(names) if len(names) < 3 else f"{names[0]} +{len(names) - 1}"
                    ckey = hashlib.md5(f"{hashlib.md5(doc_text.encode()).hexdigest()}|{mode_key}|{detail}|{language}|{extra.strip()}|{P.VERSION}".encode()).hexdigest()
                    cached = st.session_state.setdefault("result_cache", {}).get(ckey)
                    if cached:                                           # same doc + same settings: instant, no quota used
                        result, model_used = cached, "instant cache ⚡"
                    else:
                        t0 = time.time()
                        with live.container():
                            note = st.empty()
                            text, condensed, coverage = llm.condense(doc_text, llm.context_limit(), progress=lambda m: note.info(m))
                            note.empty()
                            if condensed:
                                msg = "ℹ️ Very long document — condensed section by section before the final extraction."
                                if coverage < 1:
                                    msg = (f"⚠️ This document is too large to read in full on the free tier — about {coverage:.0%} was covered. "
                                           "Use **Page range** (⚙️ Advanced options) to analyse specific parts in full.")
                                (st.warning if coverage < 1 else st.caption)(msg)
                            meta: dict = {}
                            unit = P.unit_of(doc_text)
                            messages = [{"role": "system", "content": P.build_system(mode_key, detail, language, unit)},
                                        {"role": "user", "content": P.build_user(text, extra, names)}]
                            result = P.tidy_citations(st.write_stream(llm.stream_chat(messages, max_tokens=6000, meta=meta)), unit)
                        model_used = f'{meta.get("model", "")} · {time.time() - t0:.1f}s'
                        st.session_state.result_cache[ckey] = result
                    live.empty()
                    st.session_state.update(result=result, fname=fname_label, mode_key=mode_key, model_used=model_used)
                    st.session_state.history.insert(0, {"t": datetime.now().strftime("%H:%M"), "file": fname_label,
                                                        "mode": mode_key, "result": result, "model": model_used})
                    del st.session_state.history[15:]
                    components.html(SCROLL_TO_TABS, height=0)
                except llm.LLMError as e:
                    live.empty()
                    show_error(e)

        res = st.session_state.result
        if res:
            fn, mk = st.session_state.fname, st.session_state.mode_key
            mode_label = P.MODES[mk][0] if mk in P.MODES else mk
            st.markdown(f'<div class="model-tag">{escape(mode_label)} · generated by {escape(st.session_state.model_used or "AI")}</div>',
                        unsafe_allow_html=True)
            t1, t2 = st.tabs(["Formatted View", "Raw Markdown"])
            with t1:
                st.markdown(res)
            with t2:
                st.code(res, language="markdown", wrap_lines=True)

            st.markdown('<br><div class="section-label">05 — Download Your Extraction</div>', unsafe_allow_html=True)
            base = (fn.split(",")[0].rsplit(".", 1)[0] or "document")[:40]
            exports_box = st.container(key="exports")
            cols = exports_box.columns(5)
            files = [("↓ TXT", X.to_txt(res), "txt", "text/plain"),
                     ("↓ Markdown", X.to_md(res, fn, mode_label), "md", "text/markdown"),
                     ("↓ HTML", X.to_html(res, fn, mode_label), "html", "text/html"),
                     ("↓ JSON", X.to_json(res, fn, mk, st.session_state.model_used), "json", "application/json"),
                     ("↓ Word", X.to_docx(res, fn, mode_label), "docx",
                      "application/vnd.openxmlformats-officedocument.wordprocessingml.document")]
            for c, (label, data, ext, mime) in zip(cols, files):
                c.download_button(label, data=data, file_name=f"{base}_doclens.{ext}", mime=mime, width="stretch")
            if st.button("✕  Clear result"):
                st.session_state.result = None
                st.rerun()
        elif not run:
            st.markdown("""<div class="empty-state"><div class="empty-icon">◈</div>
              <div class="empty-title">Your extraction will appear here</div>
              <div class="empty-sub">Upload a document, choose a mode, and hit Extract Now.</div></div>""",
                        unsafe_allow_html=True)

    # ── Chat ──
    with tab_chat:
        st.markdown('<div class="section-label">Ask questions about your document</div>', unsafe_allow_html=True)
        if not doc_text.strip():
            st.info("Upload a document to start chatting with it.")
        else:
            def show_sources(srcs):
                if srcs:
                    with st.expander(f"📎 Sources ({len(srcs)})"):
                        st.markdown("".join(f'<div class="hit"><span class="hit-where">{escape(lbl)}</span>{html}</div>' for lbl, html in srcs),
                                    unsafe_allow_html=True)

            sug_slot = st.empty()            # suggestions: shown only before the first question
            msgs_box = st.container()        # messages always sit ABOVE the input, like a normal chat app
            with msgs_box:
                for m in st.session_state.chat:
                    with st.chat_message(m["role"]):
                        st.markdown(m["content"])
                        show_sources(m.get("sources"))
            if not st.session_state.chat:
                with sug_slot.container():
                    st.caption("Try one of these:")
                    sc = st.columns(2)
                    for i, q in enumerate(P.SUGGESTIONS):
                        if sc[i % 2].button(q, key=f"sug{i}", width="stretch"):
                            st.session_state.pending_q = q
                            st.rerun()
            question = st.chat_input("Ask anything about your document…") or st.session_state.pop("pending_q", None)
            if question:
                sug_slot.empty()
                if not ready:
                    st.warning("The AI service isn't connected yet — please try again later.")
                else:
                    with msgs_box:
                        st.session_state.chat.append({"role": "user", "content": question})
                        with st.chat_message("user"):
                            st.markdown(question)
                        history = [{"role": m["role"], "content": m["content"]} for m in st.session_state.chat[-9:]]
                        budget = min(int(llm.context_limit() * 0.75), 80_000)          # keeps answers fast and quota-friendly
                        ctx, big = doc_text, len(doc_text) > budget
                        if big:
                            prior = [m["content"] for m in st.session_state.chat if m["role"] == "user"][-2:]
                            ctx, used, total_sec = R.select_context(cached_index(doc_text), " ".join(prior), budget)
                            st.caption(f"🔎 Large document — answering from the {used} most relevant of {total_sec} sections.")
                        msgs = [{"role": "system", "content": f"{P.CHAT_SYSTEM}\n\n<document>\n{ctx}\n</document>"}] + history
                        with st.chat_message("assistant"):
                            try:
                                live_ans = st.empty()
                                with live_ans.container():
                                    raw_answer = st.write_stream(llm.stream_chat(msgs, max_tokens=2000))
                                answer = P.tidy_citations(raw_answer, P.unit_of(doc_text))
                                live_ans.markdown(answer)
                                srcs = R.top_passages(cached_index(doc_text), question)
                                show_sources(srcs)
                                st.session_state.chat.append({"role": "assistant", "content": answer, "sources": srcs})
                            except llm.LLMError as e:
                                st.session_state.chat.pop()
                                show_error(e)
            if st.session_state.chat:
                chat_box = st.container(key="chatbtns")
                cc1, cc2 = chat_box.columns(2)
                cc1.download_button("↓ Save chat (.md)", X.chat_to_md(st.session_state.chat, ", ".join(names)),
                                    file_name="doclens_chat.md", mime="text/markdown", width="stretch")
                if cc2.button("✕  Clear chat", width="stretch"):
                    st.session_state.chat = []
                    st.rerun()

    # ── Fields → table ──
    with tab_fields:
        st.markdown('<div class="section-label">Pull specific fields into a table</div>', unsafe_allow_html=True)
        st.caption("Pick a template or type your own fields. It runs on every uploaded file — ideal for invoices, résumés and contracts — "
                   "and exports to Excel.")
        st.session_state.setdefault("fields_input", "")
        with st.container(key="presets"):
            pcols = st.columns(len(FLD.PRESETS))
            for c, pname in zip(pcols, FLD.PRESETS):
                c.button(pname, key=f"pre_{pname}", width="stretch",
                         on_click=lambda n=pname: st.session_state.update(fields_input=", ".join(FLD.PRESETS[n])))
        st.text_area("Fields to extract (comma-separated, max 12)", key="fields_input", height=92,
                     placeholder="e.g. Invoice number, Date, Vendor, Total amount")
        field_list = FLD.parse_fields(st.session_state.fields_input)
        if not docs:
            st.info("Upload one or more documents (step 01) to use this.")
        go_f = st.button(f"▦  Extract {len(field_list)} field(s) from {len(docs)} file(s)" if docs and field_list else "▦  Extract fields",
                         disabled=not (docs and field_list and ready), type="primary", width="stretch", key="go_fields")
        if go_f:
            cache = st.session_state.setdefault("field_cache", {})
            rows, failed = [], 0
            prog = st.progress(0.0, text="Starting…")
            for i, d in enumerate(docs):
                prog.progress(i / len(docs), text=f"Reading {d.name} ({i + 1}/{len(docs)})…")
                if not d.text.strip():
                    rows.append({"File": d.name, **{f: "⚠️ No readable text" for f in field_list}})
                    continue
                key = hashlib.md5((d.text + "|".join(field_list)).encode()).hexdigest()
                if key in cache:
                    rows.append({**cache[key], "File": d.name})
                    continue
                try:
                    row = FLD.to_row(field_list, d.name, llm.complete_retry(FLD.build_messages(field_list, d.name, d.text), 1500))
                    cache[key] = row
                    rows.append(row)
                except llm.LLMError:
                    failed += 1
                    rows.append({"File": d.name, **{f: "⚠️ AI busy — try again" for f in field_list}})
            prog.empty()
            st.session_state.fields_df = pd.DataFrame(rows)
            if failed:
                st.warning(f"{failed} file(s) couldn't be processed right now (free-tier limit). Click again in a minute — finished files are remembered.")
        fdf = st.session_state.get("fields_df")
        if fdf is not None and not fdf.empty:
            st.dataframe(fdf, hide_index=True, width="stretch")
            with st.container(key="dl2"):
                d1, d2 = st.columns(2)
                d1.download_button("↓ Excel (.xlsx)", X.to_xlsx(fdf), file_name="doclens_fields.xlsx", width="stretch",
                                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                d2.download_button("↓ CSV", X.to_csv(fdf), file_name="doclens_fields.csv", mime="text/csv", width="stretch")

    # ── Lens: highlight reader + search ──
    with tab_lens:
        st.markdown('<div class="section-label">Read your document through the lens</div>', unsafe_allow_html=True)
        if not doc_text.strip():
            st.info("Upload a document to read it with highlights and search inside it.")
        else:
            q = st.text_input("search", key="search_q", label_visibility="collapsed",
                              placeholder="Search a word, e.g. termination")
            sel = st.multiselect("Highlight", list(L.OPTIONS), default=["Dates", "Amounts", "Emails", "Links"], key="lens_kinds")
            kinds, term = {L.OPTIONS[k] for k in sel}, (q.strip() if len(q.strip()) >= 2 else "")
            kw = tuple(w for w, _ in stats.keywords) if stats else ()
            counts = cached_counts(doc_text, tuple(sorted(kinds)), term, kw)
            if q.strip() and not term:
                st.caption("Type at least 2 characters.")
            legend = "".join(f'<span class="legend hl-{k}">{L.LABELS[k]} <b>{counts.get(k, 0):,}</b></span>'
                             for k in (["term"] if term else []) + [k for k in ("date", "money", "email", "link", "key") if k in kinds])
            if legend:
                st.markdown(f'<div class="legend-row">{legend}</div>', unsafe_allow_html=True)
            if term:
                hits, total = SRCH.search(doc_text, term)
                if not total:
                    st.info("No matches found. Try a shorter or different word.")
                else:
                    with st.expander(f"🔎 {total:,} match{'es' if total != 1 else ''} for “{term}”" +
                                     (f" (showing first {len(hits)})" if total > len(hits) else ""), expanded=True):
                        st.markdown("".join(f'<div class="hit"><span class="hit-where">{escape(h.where)}</span>{h.html}</div>' for h in hits),
                                    unsafe_allow_html=True)
            sections = cached_sections(doc_text)
            pick = st.selectbox("Jump to", range(len(sections)), format_func=lambda i: sections[i][0], key=f"lens_pick_{sig}")
            body_html, _ = L.highlight(sections[pick][1], L.build_pattern(kinds, term, kw))
            st.markdown(f'<div class="reader-label">{escape(sections[pick][0])} · {pick + 1} of {len(sections)}</div>'
                        f'<div class="reader">{body_html}</div>', unsafe_allow_html=True)

    # ── Insights ──
    with tab_ins:
        st.markdown('<div class="section-label">Document insights · computed instantly, no AI</div>', unsafe_allow_html=True)
        if not stats or not stats.words:
            st.info("Upload a document to see word counts, readability, keywords and detected data.")
        else:
            pages = sum(d.pages for d in docs)
            used_pages = sum(len(d.selected) for d in docs)
            cards = [(f"{stats.words:,}", "Words"), (f"~{stats.read_min} min", "Reading time"), (f"{stats.sentences:,}", "Sentences"),
                     (f"{stats.unique:,}", "Unique words"), (f"{stats.flesch:.0f}", f"Readability · {stats.grade}")]
            if pages:
                cards.insert(1, (f"{used_pages:,}" + (f" / {pages:,}" if used_pages != pages else ""), "Pages analysed"))
            st.markdown('<div class="metric-grid">' + "".join(f'<div class="metric"><div class="v">{v}</div><div class="l">{l}</div></div>'
                                                              for v, l in cards) + "</div>", unsafe_allow_html=True)
            if stats.keywords:
                st.markdown('<div class="section-label">Top keywords</div>', unsafe_allow_html=True)
                kdf = pd.DataFrame(stats.keywords, columns=["keyword", "mentions"])
                st.bar_chart(kdf, x="keyword", y="mentions", sort="-mentions", color="#c8410a", height=260)
            st.markdown('<div class="section-label">Detected in text</div>', unsafe_allow_html=True)
            found_box = st.container(key="found")
            fcols = found_box.columns(len(stats.found))
            for c, (k, v) in zip(fcols, stats.found.items()):
                c.metric(k, f"{v:,}")
            good = [d for d in docs if d.text.strip()]
            if len(good) >= 2:
                sim, only_a, only_b = SRCH.similarity(good[0].text, good[1].text)
                st.markdown(f'<div class="section-label" style="margin-top:1rem">Similarity · {escape(good[0].name[:18])} vs {escape(good[1].name[:18])}</div>',
                            unsafe_allow_html=True)
                s1, s2, s3 = st.container(key="sims").columns(3)
                s1.metric("Similar", f"{sim:.0f}%")
                s2.metric("Only in first", f"{only_a:,} lines")
                s3.metric("Only in second", f"{only_b:,} lines")
            if len(docs) > 1:
                st.markdown('<div class="section-label" style="margin-top:1rem">Files</div>', unsafe_allow_html=True)
                st.dataframe(pd.DataFrame([{"File": d.name, "Type": d.ftype, "Pages": (f"{len(d.selected):,} of {d.pages:,}" if d.pages else "—"),
                                            "Words": len(d.text.split())} for d in docs]), hide_index=True, width="stretch")
            with st.expander("👁 Preview extracted text"):
                st.text(doc_text[:4000] + ("\n\n… (truncated preview)" if len(doc_text) > 4000 else ""))

    # ── History ──
    with tab_hist:
        st.markdown('<div class="section-label">This session\'s extractions</div>', unsafe_allow_html=True)
        if not st.session_state.history:
            st.info("Your extractions this session will be listed here, so you can compare modes.")
        for i, h in enumerate(st.session_state.history):
            with st.expander(f"{h['t']} · {P.MODES.get(h['mode'], ('', ''))[0]} · {h['file']}"):
                st.markdown(h["result"])
                if st.button("↩ Restore to main view", key=f"rest{i}"):
                    st.session_state.update(result=h["result"], fname=h["file"], mode_key=h["mode"], model_used=h["model"])
                    st.rerun()

# ── How it works ───────────────────────────────────────────────────────────────
steps = [("📄", "Upload", "PDF, Word, PowerPoint, text, HTML — even scanned PDFs and photos. Up to 5 files, 5 MB each.", "15+ Formats"),
         ("🎯", "Extract or Chat", "Pick a mode, ask questions, compare files, or pull fields into a table.", "16 Modes"),
         ("⬇️", "Download", "Word, Excel, CSV, Markdown, HTML, JSON or TXT — ready to use.", "7 Formats")]
cards = "".join(f"<div class='hiw-step'><div class='hiw-step-num'>0{i}</div><div class='hiw-step-icon'>{ic}</div>"
                f"<div class='hiw-step-title'>{t}</div><div class='hiw-step-body'>{b}</div><span class='hiw-step-tag'>{tag}</span></div>"
                for i, (ic, t, b, tag) in enumerate(steps, 1))
st.markdown(f"<div class='hiw-wrapper'><div class='hiw-header'><div class='hiw-eyebrow'>— How It Works —</div>"
            f"<div class='hiw-title'>Three Simple <em>Steps</em></div></div>"
            f"<div class='hiw-grid' style='grid-template-columns: repeat(3, 1fr);'>{cards}</div></div>", unsafe_allow_html=True)

st.markdown("""<div class="footer">◈ DocLens AI · Your files are not stored — text is sent to the AI service only to answer your request</div>""",
            unsafe_allow_html=True)
