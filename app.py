import streamlit as st
import PyPDF2
import docx
import io
import json
import re
from datetime import datetime
from openai import OpenAI

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="DocLens AI",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Custom CSS ──────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,300;0,9..144,400;0,9..144,600;1,9..144,300&family=DM+Mono:wght@300;400;500&family=Instrument+Sans:wght@400;500;600&display=swap');

:root {
    --ink:   #0f0e0d;
    --paper: #f5f0e8;
    --cream: #ede7d9;
    --gold:  #c9a84c;
    --rust:  #b5451b;
    --sage:  #3d6b4f;
    --mist:  #8a9ba8;
    --line:  rgba(15,14,13,0.12);
}

* { box-sizing: border-box; }

html, body, [data-testid="stAppViewContainer"] {
    background: var(--paper) !important;
    color: var(--ink) !important;
    font-family: 'Instrument Sans', sans-serif;
}

[data-testid="stAppViewContainer"] {
    background-image:
        repeating-linear-gradient(0deg,
            transparent, transparent 27px,
            rgba(15,14,13,0.04) 27px,
            rgba(15,14,13,0.04) 28px) !important;
}

[data-testid="stHeader"] { background: transparent !important; }
[data-testid="stSidebar"] { display: none; }
[data-testid="stDecoration"] { display: none; }

.hero { padding: 0 0 1rem; margin-top: -3rem; text-align: center; }
.hero-eyebrow {
    font-family: 'DM Mono', monospace;
    font-size: 0.7rem; letter-spacing: 0.22em;
    color: var(--rust); text-transform: uppercase; margin-bottom: 0.9rem;
}
.hero-title {
    font-family: 'Fraunces', serif;
    font-size: clamp(3rem, 7vw, 5rem);
    font-weight: 300; line-height: 1.05; color: var(--ink); letter-spacing: -0.02em;
}
.hero-title em { font-style: italic; color: var(--rust); }
.hero-sub {
    font-size: 1rem; color: var(--mist);
    margin: 1rem auto 0; max-width: 460px; line-height: 1.65;
}
.hero-rule { width: 55px; height: 2px; background: var(--gold); margin: 1.8rem auto 0; }

.section-label {
    font-family: 'DM Mono', monospace;
    font-size: 0.67rem; letter-spacing: 0.2em; text-transform: uppercase;
    color: var(--mist); border-bottom: 1px solid var(--line);
    padding-bottom: 0.45rem; margin-bottom: 1.1rem;
}

.stat-row { display: flex; gap: 0.7rem; flex-wrap: wrap; margin-bottom: 1.2rem; }
.stat-chip {
    background: var(--ink); color: var(--paper);
    font-family: 'DM Mono', monospace; font-size: 0.7rem;
    padding: 0.28rem 0.7rem; border-radius: 2px; letter-spacing: 0.08em;
}
.stat-chip span { color: var(--gold); margin-left: 0.35rem; }

[data-testid="stFileUploader"] {
    background: var(--cream) !important;
    border: 1.5px dashed var(--gold) !important;
    border-radius: 4px !important; padding: 1.2rem !important;
}
[data-testid="stFileUploader"]:hover { border-color: var(--rust) !important; }

[data-testid="stTextInput"] input {
    font-family: 'DM Mono', monospace !important;
    font-size: 0.82rem !important;
    background: var(--cream) !important;
    border: 1px solid var(--line) !important;
    border-radius: 2px !important;
    color: var(--ink) !important;
}
[data-testid="stTextInput"] input:focus {
    border-color: var(--gold) !important;
    box-shadow: 0 0 0 2px rgba(201,168,76,0.15) !important;
}

.stButton > button {
    background: var(--ink) !important; color: var(--paper) !important;
    font-family: 'DM Mono', monospace !important; font-size: 0.74rem !important;
    letter-spacing: 0.14em !important; text-transform: uppercase !important;
    border: none !important; border-radius: 2px !important;
    padding: 0.65rem 1.5rem !important; transition: background 0.2s !important;
}
.stButton > button:hover { background: var(--rust) !important; }

.stDownloadButton > button {
    background: transparent !important; color: var(--ink) !important;
    font-family: 'DM Mono', monospace !important; font-size: 0.7rem !important;
    letter-spacing: 0.1em !important; text-transform: uppercase !important;
    border: 1.5px solid var(--ink) !important; border-radius: 2px !important;
    padding: 0.5rem 1rem !important; transition: all 0.2s !important;
}
.stDownloadButton > button:hover {
    background: var(--ink) !important; color: var(--paper) !important;
}

.stSelectbox > div > div {
    background: var(--cream) !important; border: 1px solid var(--line) !important;
    border-radius: 2px !important; color: var(--ink) !important;
}
.stMultiSelect > div > div {
    background: var(--cream) !important; border: 1px solid var(--line) !important;
}
.stTextArea textarea {
    font-family: 'DM Mono', monospace !important; font-size: 0.82rem !important;
    background: var(--cream) !important; border: 1px solid var(--line) !important;
    border-radius: 2px !important; color: var(--ink) !important;
}

.stTabs [role="tablist"] { border-bottom: 1.5px solid var(--line) !important; }
.stTabs [role="tab"] {
    font-family: 'DM Mono', monospace !important; font-size: 0.68rem !important;
    letter-spacing: 0.14em !important; text-transform: uppercase !important;
    color: var(--mist) !important;
}
.stTabs [role="tab"][aria-selected="true"] {
    color: var(--rust) !important; border-bottom-color: var(--rust) !important;
}

.empty-state {
    min-height: 300px; display: flex; flex-direction: column;
    justify-content: center; align-items: center; text-align: center;
    background: var(--cream); border: 1px solid var(--line); border-radius: 3px;
    padding: 2rem;
}
.empty-icon { font-size: 2.5rem; opacity: 0.12; margin-bottom: 0.8rem; }
.empty-title { font-family: 'Fraunces', serif; font-size: 1.15rem; opacity: 0.4; }
.empty-sub { font-size: 0.85rem; opacity: 0.35; margin-top: 0.4rem; max-width: 260px; }

.footer {
    text-align: center; padding: 2.5rem 0 2rem;
    font-family: 'DM Mono', monospace; font-size: 0.63rem;
    letter-spacing: 0.15em; color: var(--mist); text-transform: uppercase;
    border-top: 1px solid var(--line); margin-top: 3.5rem;
}

::-webkit-scrollbar { width: 5px; }
::-webkit-scrollbar-track { background: var(--cream); }
::-webkit-scrollbar-thumb { background: var(--gold); border-radius: 3px; }

/* ── How It Works ── */
.hiw-wrapper { margin: 2.5rem 0 0; padding: 0; }
.hiw-header { text-align: center; margin-bottom: 2rem; }
.hiw-eyebrow {
    font-family: 'DM Mono', monospace; font-size: 0.65rem;
    letter-spacing: 0.25em; text-transform: uppercase;
    color: var(--mist); margin-bottom: 0.5rem;
}
.hiw-title {
    font-family: 'Fraunces', serif; font-size: 2rem;
    font-weight: 300; color: var(--ink); letter-spacing: -0.01em;
}
.hiw-title em { font-style: italic; color: var(--rust); }
.hiw-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1.2rem; }
.hiw-step {
    background: var(--cream); border: 1px solid var(--line); border-radius: 4px;
    padding: 1.8rem 1.5rem; display: flex; flex-direction: column;
    position: relative; overflow: hidden; transition: border-color 0.2s, box-shadow 0.2s;
}
.hiw-step:hover { border-color: var(--gold); box-shadow: 0 4px 20px rgba(201,168,76,0.12); }
.hiw-step::before {
    content: ''; position: absolute; top: 0; left: 0; right: 0;
    height: 3px; background: var(--gold);
}
.hiw-step-num {
    font-family: 'Fraunces', serif; font-size: 3rem; font-weight: 300;
    color: rgba(201,168,76,0.2); line-height: 1;
    position: absolute; top: 1rem; right: 1.2rem; letter-spacing: -0.04em;
}
.hiw-step-icon { font-size: 1.8rem; margin-bottom: 1rem; margin-top: 0.3rem; }
.hiw-step-title {
    font-family: 'Fraunces', serif; font-size: 1.05rem;
    font-weight: 400; color: var(--ink); margin-bottom: 0.55rem; line-height: 1.25;
}
.hiw-step-body { font-size: 0.83rem; color: #6a6763; line-height: 1.7; flex: 1; }
.hiw-step-tag {
    display: inline-block; margin-top: 1.2rem;
    font-family: 'DM Mono', monospace; font-size: 0.58rem;
    letter-spacing: 0.18em; text-transform: uppercase;
    color: var(--rust); border: 1px solid rgba(181,69,27,0.2);
    padding: 0.22rem 0.55rem; border-radius: 2px;
    background: rgba(181,69,27,0.04);
}
</style>
""", unsafe_allow_html=True)


# ── Groq client (server-side key, never exposed to users) ──────────────────────
# Store your key in Streamlit Cloud → Settings → Secrets as:
#   GROQ_API_KEY = "gsk_xxxxxxxxxxxxxxxxxxxx"

@st.cache_resource
def get_groq_client():
    api_key = st.secrets.get("GROQ_API_KEY", "")
    if not api_key:
        st.error("⚠️ GROQ_API_KEY not found in Streamlit secrets. Please add it in your app settings.")
        st.stop()
    return OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")


# ── Text extraction helpers ─────────────────────────────────────────────────────

def extract_pdf(file_bytes: bytes) -> str:
    reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
    pages = []
    for i, page in enumerate(reader.pages):
        t = page.extract_text() or ""
        if t.strip():
            pages.append(f"[Page {i+1}]\n{t}")
    return "\n\n".join(pages)


def extract_docx(file_bytes: bytes) -> str:
    doc = docx.Document(io.BytesIO(file_bytes))
    return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())


def extract_txt(file_bytes: bytes) -> str:
    for enc in ("utf-8", "latin-1", "cp1252"):
        try:
            return file_bytes.decode(enc)
        except UnicodeDecodeError:
            continue
    return file_bytes.decode("utf-8", errors="replace")


def read_file(uploaded_file):
    raw = uploaded_file.read()
    name = uploaded_file.name.lower()
    if name.endswith(".pdf"):
        return extract_pdf(raw), "PDF"
    elif name.endswith(".docx"):
        return extract_docx(raw), "DOCX"
    else:
        return extract_txt(raw), "TXT"


# ── Extraction modes ────────────────────────────────────────────────────────────

MODES = {
    "🔍 Smart Auto-Extract":         "auto",
    "📋 Executive Summary":          "summary",
    "🔑 Key Points & Insights":      "keypoints",
    "📊 Data & Statistics":          "data",
    "⚠️ Action Items & Deadlines":   "actions",
    "🧠 Concepts & Definitions":     "concepts",
    "📜 Legal & Compliance Clauses": "legal",
    "👤 People, Orgs & Places":      "entities",
    "❓ Q&A Pairs":                  "qa",
    "🗂️ Full Structured Report":     "full",
}

PROMPTS = {
    "auto":     "You are DocLens, an expert document analyst. Analyze the document and intelligently extract what matters most based on its type and content. Begin with a 2-sentence overview, then organize the most critical information into clear markdown sections (## headings). Be thorough but concise.",
    "summary":  "You are DocLens. Write a crisp executive summary. Sections: ## Overview (3-4 sentences), ## Key Takeaways (5-8 bullet points), ## Bottom Line (1-2 sentences).",
    "keypoints":"You are DocLens. Extract ALL key points and insights. Sections: ## Key Points (numbered), ## Critical Insights (bullets), ## Notable Claims (if any).",
    "data":     "You are DocLens. Extract ALL numerical data, stats, metrics, dates, percentages. Sections: ## Statistics & Numbers, ## Dates & Timelines, ## Financial Data (if any), ## Performance Metrics (if any).",
    "actions":  "You are DocLens. Extract all action items, tasks, recommendations, deadlines. Sections: ## Immediate Actions, ## Upcoming Deadlines, ## Recommendations, ## Open Questions.",
    "concepts": "You are DocLens. Extract and explain key concepts and terminology. Sections: ## Core Concepts (with explanations), ## Technical Terms & Definitions, ## Frameworks or Models mentioned.",
    "legal":    "You are DocLens. Extract legal clauses, obligations, rights, restrictions. Sections: ## Key Obligations, ## Rights & Permissions, ## Restrictions, ## Compliance Requirements, ## Risk Items. Note: informational only, not legal advice.",
    "entities": "You are DocLens. Identify all named entities. Sections: ## People (name + context), ## Organizations & Companies, ## Locations, ## Products & Services.",
    "qa":       "You are DocLens. Generate 10-20 Q&A pairs covering the most important content. Format: **Q:** [question]\\n**A:** [answer]. Group under ## thematic headers.",
    "full":     "You are DocLens. Generate a comprehensive structured report with ALL applicable sections: ## Document Overview, ## Executive Summary, ## Key Points & Insights, ## Data & Statistics, ## Action Items, ## Key Entities, ## Concepts & Definitions, ## Conclusions.",
}


# ── AI call (Groq backend, no user key needed) ──────────────────────────────────

def call_groq(text: str, mode: str, extra: str = "") -> str:
    client = get_groq_client()
    system_prompt = PROMPTS.get(mode, PROMPTS["auto"])
    user_content = f"{extra}\n\nDocument:\n{text}" if extra.strip() else f"Document:\n{text}"
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_content},
        ],
        max_tokens=4096,
    )
    return response.choices[0].message.content


# ── Download builders ───────────────────────────────────────────────────────────

def dl_txt(content): return content.encode("utf-8")

def safe(text):
    return text.encode("latin-1", errors="replace").decode("latin-1")

def dl_md(content, filename):
    header = f"# DocLens Extraction — {filename}\n*{datetime.now().strftime('%Y-%m-%d %H:%M')}*\n\n---\n\n"
    return (header + content).encode("utf-8")

def dl_html(content, filename):
    lines = content.split("\n")
    html_parts = []
    for line in lines:
        if line.startswith("## "):   html_parts.append(f"<h2>{line[3:]}</h2>")
        elif line.startswith("# "): html_parts.append(f"<h1>{line[2:]}</h1>")
        elif line.startswith("### "): html_parts.append(f"<h3>{line[4:]}</h3>")
        elif line.startswith(("- ", "* ")): html_parts.append(f"<li>{line[2:]}</li>")
        elif line.strip() == "": html_parts.append("<br>")
        else:
            line = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', line)
            html_parts.append(f"<p>{line}</p>")
    body = "\n".join(html_parts)
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>DocLens — {filename}</title>
<style>body{{font-family:Georgia,serif;max-width:800px;margin:40px auto;padding:0 24px;background:#f9f6f0;color:#1a1917;line-height:1.75}}
h1{{font-size:2rem;border-bottom:2px solid #c9a84c;padding-bottom:.3em}}h2{{color:#b5451b;margin-top:1.8em}}
.meta{{font-family:monospace;font-size:.78rem;color:#8a9ba8}}</style></head>
<body><p class="meta">DocLens AI · {datetime.now().strftime('%Y-%m-%d %H:%M')} · {filename}</p><hr>{body}</body></html>""".encode("utf-8")

def dl_json(content, filename, mode):
    sections = []
    cur_title, cur_lines = None, []
    for line in content.split("\n"):
        if line.startswith("## "):
            if cur_title: sections.append({"title": cur_title, "content": "\n".join(cur_lines).strip()})
            cur_title, cur_lines = line[3:].strip(), []
        else: cur_lines.append(line)
    if cur_title: sections.append({"title": cur_title, "content": "\n".join(cur_lines).strip()})
    payload = {"source_file": filename, "mode": mode,
               "generated_at": datetime.now().isoformat(), "content": content, "sections": sections}
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


# ── UI ──────────────────────────────────────────────────────────────────────────

st.markdown("""
<div class="hero">
  <div class="hero-eyebrow">◈ AI-Powered Document Intelligence</div>
  <div class="hero-title">Doc<em>Lens</em></div>
  <div class="hero-sub">Drop any document. Choose what to extract. Download the intelligence.</div>
  <div class="hero-rule"></div>
</div>
""", unsafe_allow_html=True)

col_left, col_right = st.columns([1, 1.65], gap="large")

# ─── LEFT PANEL ────────────────────────────────────────────────────────────────
with col_left:

    # 01 — Upload Document
    st.markdown('<div class="section-label">01 — Upload Document</div>', unsafe_allow_html=True)
    uploaded = st.file_uploader(
        "upload",
        type=["pdf", "docx", "txt", "md", "rst", "csv", "log"],
        label_visibility="collapsed",
    )
    if uploaded:
        sz = len(uploaded.getvalue())
        short = uploaded.name[:24] + ("…" if len(uploaded.name) > 24 else "")
        st.markdown(f"""
        <div class="stat-row">
          <div class="stat-chip">File<span>{short}</span></div>
          <div class="stat-chip">Size<span>{sz/1024:.1f} KB</span></div>
        </div>""", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    # 02 — Extraction Mode
    st.markdown('<div class="section-label">02 — Choose Extraction Mode</div>', unsafe_allow_html=True)
    mode_label = st.selectbox("mode", list(MODES.keys()), label_visibility="collapsed")
    mode_key = MODES[mode_label]
    st.markdown("<br>", unsafe_allow_html=True)

    # 03 — Extra Instructions
    st.markdown('<div class="section-label">03 — Extra Instructions (optional)</div>', unsafe_allow_html=True)
    extra = st.text_area(
        "extra",
        placeholder="e.g. Focus on financial figures only. Ignore the appendix. Extract only 2024 data…",
        height=88, label_visibility="collapsed",
    )
    st.markdown("<br>", unsafe_allow_html=True)
    run = st.button("◈  Extract Now", use_container_width=True)

# ─── RIGHT PANEL ───────────────────────────────────────────────────────────────
with col_right:
    st.markdown('<div class="section-label">04 — Extracted Intelligence</div>', unsafe_allow_html=True)

    if "result" not in st.session_state:
        st.session_state.result = None
        st.session_state.fname = ""
        st.session_state.mode_label = ""

    if run:
        if not uploaded:
            st.warning("Please upload a document first (step 01).")
        else:
            with st.spinner("Reading document…"):
                raw_text, ftype = read_file(uploaded)
            wc = len(raw_text.split())
            st.markdown(f"""
            <div class="stat-row">
              <div class="stat-chip">Type<span>{ftype}</span></div>
              <div class="stat-chip">Words<span>{wc:,}</span></div>
              <div class="stat-chip">Chars<span>{len(raw_text):,}</span></div>
            </div>""", unsafe_allow_html=True)

            if not raw_text.strip():
                st.error("No readable text found. The file may be image-based or protected.")
            else:
                with st.spinner("DocLens is reading between the lines…"):
                    try:
                        result = call_groq(raw_text, mode_key, extra)
                        st.session_state.result = result
                        st.session_state.fname = uploaded.name
                        st.session_state.mode_label = mode_label
                        st.success("Extraction complete ✓")
                    except Exception as e:
                        st.error(f"Error: {e}")

    if st.session_state.result:
        tab1, tab2 = st.tabs(["Formatted View", "Raw Markdown"])
        with tab1:
            st.markdown(st.session_state.result)
        with tab2:
            st.text_area("raw", value=st.session_state.result, height=400, label_visibility="collapsed")

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div class="section-label">05 — Download Your Extraction</div>', unsafe_allow_html=True)

        base = st.session_state.fname.rsplit(".", 1)[0]
        r = st.session_state.result
        fn = st.session_state.fname
        ml = st.session_state.mode_label

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.download_button("↓ TXT", data=dl_txt(r),
                file_name=f"{base}_doclens.txt", mime="text/plain", use_container_width=True)
        with c2:
            st.download_button("↓ Markdown", data=dl_md(r, fn),
                file_name=f"{base}_doclens.md", mime="text/markdown", use_container_width=True)
        with c3:
            st.download_button("↓ HTML", data=dl_html(r, fn),
                file_name=f"{base}_doclens.html", mime="text/html", use_container_width=True)
        with c4:
            st.download_button("↓ JSON", data=dl_json(r, fn, ml),
                file_name=f"{base}_doclens.json", mime="application/json", use_container_width=True)

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("✕  Clear & Start Over"):
            st.session_state.result = None
            st.session_state.fname = ""
            st.session_state.mode_label = ""
            st.rerun()

    else:
        st.markdown("""
        <div class="empty-state">
          <div class="empty-icon">◈</div>
          <div class="empty-title">Your extraction will appear here</div>
          <div class="empty-sub">Upload a document, choose a mode, and hit Extract Now.</div>
        </div>""", unsafe_allow_html=True)


# ── How It Works ──────────────────────────────────────────────────────────────
hiw_html = (
"<div class='hiw-wrapper'>"
"<div class='hiw-header'>"
"<div class='hiw-eyebrow'>— How It Works —</div>"
"<div class='hiw-title'>Three Simple <em>Steps</em></div>"
"</div>"
"<div class='hiw-grid' style='grid-template-columns: repeat(3, 1fr);'>"
"<div class='hiw-step'>"
"<div class='hiw-step-num'>01</div>"
"<div class='hiw-step-icon'>📄</div>"
"<div class='hiw-step-title'>Upload Your Document</div>"
"<div class='hiw-step-body'>Drop any PDF, DOCX, TXT, MD, or CSV — any text-bearing document up to several hundred pages.</div>"
"<span class='hiw-step-tag'>Any Format</span>"
"</div>"
"<div class='hiw-step'>"
"<div class='hiw-step-num'>02</div>"
"<div class='hiw-step-icon'>🎯</div>"
"<div class='hiw-step-title'>Choose Extraction Mode</div>"
"<div class='hiw-step-body'>Smart auto-extract or go targeted — summary, key points, legal clauses, entities, Q&amp;A, and more.</div>"
"<span class='hiw-step-tag'>10 Modes</span>"
"</div>"
"<div class='hiw-step'>"
"<div class='hiw-step-num'>03</div>"
"<div class='hiw-step-icon'>⬇️</div>"
"<div class='hiw-step-title'>Download &amp; Use</div>"
"<div class='hiw-step-body'>Export as TXT, Markdown, HTML, or JSON — clean structured output ready for any workflow.</div>"
"<span class='hiw-step-tag'>4 Formats</span>"
"</div>"
"</div>"
"</div>"
)
st.markdown(hiw_html, unsafe_allow_html=True)


# ── Footer ──────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="footer">
  ◈ DocLens AI · Powered by Groq + Llama 3.3 · Your documents stay private · No storage, no tracking
</div>""", unsafe_allow_html=True)