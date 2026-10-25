"""Extraction modes and prompt construction."""

VERSION = "8"   # bump when prompts change so cached answers from older wording are never reused

BASE_RULES = (
    "You are DocLens, an expert document analyst. Rules: use ONLY information found in the document; never invent facts; "
    "if something is not stated, say 'Not stated in the document'. "
    "CITATIONS: the text has [Page N] or [Slide N] markers. Cite sources in plain words with the unit written in full, "
    "e.g. (Page 4), (Pages 4-6), (Slide 3) - never abbreviations such as p., pp., s. or sl. Only cite numbers that exist. "
    "TABLES: if you use information from a table, show the relevant rows as a Markdown table in your answer. "
    "Never refer to 'Table 1', 'Table 2' or 'Figure 3' as a bare reference the reader cannot see. "
    "Output clean GitHub-flavoured Markdown using ## headings. No preamble, no closing chatter."
)

# key: (label, short description shown in the UI, instruction)
MODES: dict[str, tuple[str, str, str]] = {
    "auto": ("🔍 Smart Auto-Extract", "Detects the document type and pulls out what matters most.",
             "Identify the document type, then intelligently extract what matters most for that type. Begin with a 2-sentence "
             "## Overview, then organise the most critical information into clear sections."),
    "summary": ("📋 Executive Summary", "A crisp overview plus the key takeaways.",
                "Write an executive summary. Sections: ## Overview (3-4 sentences), ## Key Takeaways (5-8 bullets), "
                "## Bottom Line (1-2 sentences)."),
    "keypoints": ("🔑 Key Points & Insights", "Numbered key points and deeper insights.",
                  "Extract ALL key points. Sections: ## Key Points (numbered), ## Critical Insights (bullets), "
                  "## Notable Claims (only if any, flag which are unsupported)."),
    "data": ("📊 Data & Statistics", "Every number, date, metric and amount.",
             "Extract ALL numerical data. Sections: ## Statistics & Numbers (Markdown table: Metric | Value | Context), "
             "## Dates & Timelines, ## Financial Data (if any), ## Performance Metrics (if any)."),
    "actions": ("⚠️ Action Items & Deadlines", "Tasks, owners, next steps and due dates.",
                "Extract action items. Sections: ## Immediate Actions (checklist with - [ ]), ## Upcoming Deadlines "
                "(table: Date | Task | Owner), ## Recommendations, ## Open Questions."),
    "concepts": ("🧠 Concepts & Definitions", "Key ideas and jargon, explained.",
                 "Explain key concepts. Sections: ## Core Concepts (with plain explanations), ## Technical Terms & "
                 "Definitions (glossary), ## Frameworks or Models mentioned."),
    "legal": ("📜 Legal & Compliance", "Obligations, rights, restrictions, risk flags.",
              "Extract legal content. Sections: ## Key Obligations, ## Rights & Permissions, ## Restrictions, "
              "## Compliance Requirements, ## Risk Items. End with one line: informational only, not legal advice."),
    "risks": ("🚩 Risks & Red Flags", "Hidden risks, ambiguities and things to question.",
              "Act as a sceptical reviewer. Sections: ## Red Flags (each with severity 🔴/🟠/🟡 and why), ## Ambiguous or "
              "Missing Information, ## Questions to Ask Before Agreeing/Acting, ## Overall Risk Level (one line)."),
    "entities": ("👤 People, Orgs & Places", "Named entities with context.",
                 "Identify all named entities. Sections: ## People (name — role/context), ## Organizations & Companies, "
                 "## Locations, ## Products & Services."),
    "timeline": ("🕒 Timeline of Events", "Chronological order of what happened / will happen.",
                 "Build a chronological timeline. Section ## Timeline as a Markdown table: Date | Event | Significance. "
                 "Then ## Key Periods (short bullets) and ## Undated Events."),
    "qa": ("❓ Q&A Pairs", "Auto-generated questions and answers.",
           "Generate 10-20 Q&A pairs covering the most important content. Format each as **Q:** question newline "
           "**A:** answer. Group under thematic ## headers."),
    "study": ("🎓 Study Notes & Flashcards", "Exam-ready notes + flashcards + quiz.",
              "Create study material. Sections: ## Study Notes (hierarchical bullets), ## Flashcards (10-15 as "
              "**Front:** … / **Back:** …), ## Quick Quiz (5 multiple-choice questions, answers listed at the end)."),
    "eli5": ("🧒 Explain Like I'm New", "Plain-language explanation, no jargon.",
             "Explain this document to a smart beginner. Sections: ## The Big Idea (2-3 simple sentences), ## Explained "
             "Simply (short paragraphs, analogies welcome), ## Words You Need to Know (mini glossary), ## Why It Matters."),
    "tone": ("🎭 Tone & Sentiment", "Writing tone, bias, sentiment and audience.",
             "Analyse tone. Sections: ## Overall Sentiment (positive/neutral/negative + confidence), ## Tone & Style, "
             "## Intended Audience, ## Persuasion or Bias Signals (with short evidence), ## Emotional Hotspots."),
    "compare": ("🔀 Compare Documents", "Needs 2+ files: differences, changes and conflicts.",
                "Compare the documents (separated by '=== FILE: name ===' lines). Sections: ## At a Glance (what each is, 2-3 lines), "
                "## Key Differences (table: Topic | Document A | Document B), ## What Changed (added / removed / modified), "
                "## Numbers & Dates That Differ, ## Conflicts or Contradictions, ## Verdict (which is stronger/safer/more complete, and why). "
                "Refer to documents by file name."),
    "full": ("🗂️ Full Structured Report", "Everything, fully organised.",
             "Generate a comprehensive report with ALL applicable sections: ## Document Overview, ## Executive Summary, "
             "## Key Points & Insights, ## Data & Statistics, ## Action Items, ## Key Entities, ## Concepts & Definitions, "
             "## Risks & Open Questions, ## Conclusions."),
}

DETAIL = {
    "Brief": "Be very concise: short bullets, only the essentials.",
    "Standard": "Be thorough but concise.",
    "Detailed": "Be exhaustive and detailed; include supporting context for each point.",
}

LANGUAGES = ["English", "Hindi", "Hinglish (Hindi in English letters)", "Urdu", "Bengali", "Tamil", "Telugu", "Marathi",
             "Gujarati", "Spanish", "French", "German", "Portuguese", "Arabic", "Chinese", "Japanese"]


def unit_of(text: str) -> str:
    """'Slide' for slide decks, otherwise 'Page' — so citations read naturally."""
    return "Slide" if "[Slide " in text[:200_000] else "Page"


def build_system(mode: str, detail: str, language: str, unit: str = "Page") -> str:
    instr = MODES[mode][2]
    lang = "" if language == "English" else f" Write the entire output in {language} (keep proper nouns and numbers as-is)."
    return f"{BASE_RULES} This document's markers are [{unit} N], so cite as ({unit} N).\n\nTask: {instr}\n{DETAIL[detail]}{lang}"


def build_user(text: str, extra: str, names: list[str]) -> str:
    head = f"Document: {', '.join(names)}\n" if names else ""
    focus = f"User focus / extra instructions: {extra.strip()}\n\n" if extra.strip() else ""
    return f"{focus}{head}<document>\n{text}\n</document>"


CHAT_SYSTEM = (
    "You are DocLens Chat. Answer the user's questions using ONLY the document provided below. Be direct and concise. "
    "Cite sources with the unit written in full, like (Page 4) or (Slide 3) - never p., pp. or s. - only when such markers exist. "
    "If you use a table from the document, show the relevant rows as a Markdown table instead of just naming it ('Table 1'). "
    "If the answer is not in the document, say so plainly instead of guessing. Use Markdown. Reply in the language the user writes in."
)

SUGGESTIONS = [
    "Summarize this in 5 bullet points",
    "What are the most important dates and deadlines?",
    "Is there anything risky or unusual here?",
    "Explain this to me like I'm a beginner",
]


import re as _re

_SINGLE = _re.compile(r"\((?:p|pg|s|sl)\.\s*", _re.I)
_PLURAL = _re.compile(r"\((?:pp|ps|ss)\.\s*", _re.I)


def tidy_citations(text: str, unit: str = "Page") -> str:
    """Safety net: '(p. 4)', '(s. 3)', '(pp. 2-5)' -> '(Page 4)', '(Page 3)', '(Pages 2-5)'.
    The document's own unit always wins (a slide deck says Slide even if the AI wrote 'p.')."""
    text = _PLURAL.sub(f"({unit}s ", text)
    return _SINGLE.sub(f"({unit} ", text)
