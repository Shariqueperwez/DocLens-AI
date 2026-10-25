# DocLens-AI
AI-powered document intelligence app: extract, chat, search and compare PDFs, Word and PowerPoint files, and export to Excel. Built with Streamlit and Gemini.

# ◈ DocLens AI
### AI-Powered Document Intelligence — free to run, no credit card

> Upload any document. Extract, chat with it, analyse it, download the result.

DocLens is a Streamlit app that reads PDFs, Word, PowerPoint, scanned pages and more, then uses a **free** LLM
(Google Gemini by default) to extract exactly the intelligence you ask for.

---

## ✨ Features

| | |
|---|---|
| 🧠 **16 extraction modes** | Auto, Summary, Key Points, Data & Stats, Action Items, Concepts, Legal, **Risks & Red Flags**, Entities, **Timeline**, Q&A, **Study Notes & Flashcards**, **ELI5**, **Tone & Sentiment**, **Compare Documents**, Full Report |
| 🧾 **Fields → Excel** | Type the fields you want (or use Invoice / Résumé / Contract / Receipt templates), run on up to 5 files, get a table + `.xlsx` / `.csv` |
| 🔀 **Compare documents** | What changed between two versions, conflicts, differing numbers, plus a similarity score |
| 🔍 **Lens reader** | Read the document page by page with **dates, amounts, emails, links and key terms colour-highlighted**, plus instant search with file + page numbers — no AI, no quota |
| 📎 **Sources for every chat answer** | See the exact passages (with page numbers) an answer is based on, so you can verify it |
| 🧭 **Smart hint** | Recognises invoices, contracts, résumés, papers, meeting notes… and suggests the best mode |
| 💬 **Chat with your document** | Ask follow-up questions; answers cite page numbers; streaming replies; save the chat |
| 📷 **Scanned PDF & image OCR** | Gemini vision reads scans, photos and screenshots (`.png .jpg .webp`) |
| 📁 **Multi-file upload** | Up to 5 files, 5 MB each, analysed together |
| 📂 **15+ formats** | PDF, DOCX (incl. tables), PPTX (incl. notes), TXT, MD, RST, CSV, LOG, JSON, HTML, images |
| 🌍 **16 output languages** | English, Hindi, Hinglish, Urdu, Bengali, Tamil, Telugu, Marathi, Gujarati, Spanish, French… |
| 🎚️ **Detail control** | Brief / Standard / Detailed |
| 📈 **Instant insights (no AI)** | Word count, reading time, readability score, top keywords, detected dates / emails / links / currency |
| 📱 **Works on phones & tablets** | Layout adapts to any screen: tabs wrap into a grid, button rows become 2-column, 16 px inputs (no iPhone zoom), 46 px tap targets, and the page scrolls to your result after Extract |
| ⬇️ **7 export formats** | TXT, Markdown, styled HTML, JSON, **Word (.docx)**, **Excel (.xlsx)**, **CSV** |
| 🕘 **Session history** | Compare different modes on the same document |
| 🛡️ **Never goes down** | Automatic failover: Gemini → OpenRouter → Groq, model-by-model |
| 📏 **Huge documents, handled honestly** | Default 300-page window, **page-range picker** (`1-50, 120-180`), clear "analysing pages X of Y" notice, full-coverage condensing with a warning if anything can't be read |
| 🔎 **Smart chat on big files** | Instead of cutting the middle out, chat finds the most relevant sections for each question |
| ⚡ **Fast & quota-friendly** | PyMuPDF opens a 5,000-page PDF in ~0.1 s; repeated identical extractions are served instantly from cache |

---

## 🚀 Quick start

```bash
pip install -r requirements.txt
```

**1. Get a free Gemini key** (no credit card): <https://aistudio.google.com/apikey>

**2. Add it as a secret**

Local — create `.streamlit/secrets.toml`:
```toml
GEMINI_API_KEY = "AIza..."
```
Streamlit Cloud — *App → Settings → Secrets*, paste the same line.

**3. Run**
```bash
streamlit run app.py
```

The key lives only on the server (secrets) — visitors never see or enter one. If no key is configured, the app shows an "AI service offline" notice.

### Optional fallbacks (add any of them for extra reliability)
```toml
OPENROUTER_API_KEY = "sk-or-..."   # https://openrouter.ai/keys   (free models)
GROQ_API_KEY       = "gsk_..."     # https://console.groq.com/keys
```
If a provider is rate-limited, rejects the key, or retires a model, DocLens quietly tries the next one.
Free-tier models change often — override names without touching code:
```toml
GEMINI_MODEL = "gemini-2.5-flash"
OPENROUTER_MODEL = "meta-llama/llama-3.3-70b-instruct:free"
GROQ_MODEL = "llama-3.3-70b-versatile"
```

---

## 🗂️ Project structure

```
app.py                 # Streamlit UI
assets/style.css       # editorial theme
core/
  llm.py               # providers, streaming, failover, vision OCR, long-doc condensing
  documents.py         # file readers (page ranges, OCR prep) + analytics
  retrieval.py         # relevance search for chat on large documents
  fields.py            # structured field extraction -> table
  search.py            # instant highlighted search + document similarity
  lens.py              # highlight reader, page sections, document-type hints
  prompts.py           # the 15 modes, detail levels, languages
  exporters.py         # TXT / MD / HTML / JSON / DOCX
```

## 📚 How big documents are handled

| Situation | What DocLens does |
|---|---|
| Normal doc (up to ~300 pages) | Sent to Gemini in one request — full document used |
| Thousands of pages | Analyses pages 1–300 by default and tells you; use **Page range** to choose any other part |
| Text longer than a provider's limit | Condenses section by section so the whole selection is represented, and warns if coverage < 100% |
| Chat on a large document | Retrieves the most relevant sections per question (≈80k characters max) |
| Scanned pages | Vision OCR on up to 16 selected pages |

Upload limits: 5 MB per file (`maxUploadSize` in `.streamlit/config.toml`) and 5 files at once (`MAX_FILES` in `app.py`).

## 🔒 Privacy
Every visitor gets their own private session: uploads, chat, results and History are visible only to that visitor, in that browser tab, and disappear on refresh (checked with a two-user test). Short-lived server caches that speed up repeat work expire after 30 minutes, are keyed by file content, and are never shown to other visitors.

DocLens stores nothing. Document text is sent to the selected AI provider only to process your request.
Note: on Google's *free* tier, prompts may be used to improve Google products (outside the EU/UK/CH) —
don't upload confidential documents on a free key.

## ⚠️ Limitations
Free tiers have rate limits (a few requests per minute). Scanned-document OCR reads up to 16 pages at a time.
Output is AI-generated — verify anything important, especially legal and financial content.

---
*Built with Streamlit · Google Gemini · Python*

