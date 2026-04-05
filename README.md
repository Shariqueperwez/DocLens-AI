# ◈ DocLens AI
### AI-Powered Document Intelligence

> Upload any document. Choose what to extract. Download the intelligence.

---

## 🤔 What is DocLens AI?

DocLens AI is a Streamlit web application that uses AI to extract structured, meaningful information from any document — instantly.

Instead of reading a 50-page report manually, you upload it, choose what you need (a summary, the legal clauses, the key stats, action items), and the AI does the work in seconds. The result can be downloaded in 4 formats ready for any workflow.

No account needed. Just upload and go.

---

## ⚙️ How It Works

```
1. Upload your document (PDF, DOCX, TXT, and more)
        ↓
2. Choose an extraction mode (Summary, Legal, Data, Q&A, etc.)
        ↓
3. Optionally add custom instructions ("focus on 2024 data only")
        ↓
4. AI reads and extracts exactly what you asked for
        ↓
5. Download the result as TXT, Markdown, HTML, or JSON
```

The app extracts raw text from your file, sends it to **Groq's API** running **Llama 3.3 70B**, and returns a structured Markdown response — all in a few seconds.

---

## ✨ Features

- 🧠 **10 specialized extraction modes** — not just a generic summarizer
- 📁 **7 supported file formats** — PDF, DOCX, TXT, MD, CSV, LOG, RST
- ⬇️ **4 download formats** — TXT, Markdown, HTML, JSON
- ✍️ **Custom instructions** — tell the AI exactly what to focus on
- ⚡ **Ultra-fast** — powered by Groq's LPU hardware

---

## 📄 Supported File Types

| Format | Extension |
|--------|-----------|
| PDF | `.pdf` |
| Word | `.docx` |
| Text | `.txt` |
| Markdown | `.md` |
| CSV | `.csv` |
| Logs | `.log` |
| RST | `.rst` |

---

## 🧠 Extraction Modes

| Mode | What it does |
|------|-------------|
| 🔍 Smart Auto-Extract | AI decides what's most important based on document type |
| 📋 Executive Summary | Concise overview + key takeaways |
| 🔑 Key Points & Insights | Numbered list of key points + insights |
| 📊 Data & Statistics | All numbers, dates, metrics |
| ⚠️ Action Items & Deadlines | Tasks, next steps, deadlines |
| 🧠 Concepts & Definitions | Technical terms, explained |
| 📜 Legal & Compliance | Obligations, rights, risk flags |
| 👤 People, Orgs & Places | Named entity extraction |
| ❓ Q&A Pairs | Auto-generated Q&A from the document |
| 🗂️ Full Structured Report | Everything, fully organized |

---

## ⬇️ Download Formats

- 📝 **TXT** — Plain text, works everywhere
- 🖊️ **Markdown** — Great for Notion, Obsidian, GitHub
- 🌐 **HTML** — Formatted document, open in any browser
- 🔧 **JSON** — Structured data, great for developers and automation

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| 🖥️ Framework | Streamlit |
| 🤖 AI Model | Llama 3.3 70B |
| ⚡ AI Provider | Groq |
| 📄 PDF Reading | PyPDF2 |
| 📝 DOCX Reading | python-docx |
| 🔌 API Client | openai (pointed at Groq) |
| 🔒 Secrets | Streamlit Secrets |

---

## 📦 Requirements

```
streamlit>=1.35.0
PyPDF2>=3.0.0
python-docx>=1.1.0
openai
```

---

## 💡 Tips

- For best results on large documents, use **🗂️ Full Structured Report** mode
- Use the **Extra Instructions** box to narrow focus — e.g. *"only extract 2024 financial figures"*
- **🔧 JSON format** is ideal if you want to use the output in another tool or script
- **Scanned PDFs** (image-based) won't work — the file must have selectable text

---

## 🔒 Privacy

- 🚫 Nothing is stored or logged by this app

---

*Built with ❤️ using Streamlit · Groq · Llama 3.3 70B*
