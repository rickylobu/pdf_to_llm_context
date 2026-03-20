# 📖 PDF to LLM Context

> Transform a scanned PDF book into structured, accessible Markdown — readable by humans, browsers, and AI models alike.

**What this does:** Takes any image-based (scanned) PDF and converts it into clean Markdown files using Gemini's multimodal AI. The output is rendered as an accessible web app on GitHub Pages with text-to-speech, searchable pages, and interactive math visualizations.

```
Scanned PDF  →  Gemini OCR  →  Markdown pages  →  GitHub Pages viewer
                                      ↓
                              Consumable by any LLM
```

---

## ✨ Features

- **Accurate OCR** for scanned books using Google Gemini 1.5 Flash
- **Accounting-aware**: T-accounts and tables reconstructed as proper Markdown tables
- **Math support**: Formula links to GeoGebra interactive graphs; optional Wolfram Alpha validation
- **Text-to-speech**: Full Web Speech API integration with voice, speed, and pitch controls
- **Dynamic theming**: Colors automatically extracted from the book cover
- **Resume-safe**: If extraction is interrupted, it picks up exactly where it left off
- **Quota-aware**: Pre-flight check warns you before you hit the free tier limit
- **Copyright-friendly**: Source citations embedded in every page; PDF never committed to git
- **Zero hosting cost**: GitHub Pages + Gemini free tier

---

## 📋 Requirements

| Tool | Version | Install |
|---|---|---|
| Python | ≥ 3.11 | [python.org](https://python.org) |
| Node.js | ≥ 20 | [nodejs.org](https://nodejs.org) |
| Git | any | [git-scm.com](https://git-scm.com) |
| Google account | — | For Gemini API key (free) |

---

## 🚀 Quick Start

### Step 1 — Fork and clone the repository

```bash
# Fork this repo on GitHub first, then:
git clone https://github.com/YOUR_USERNAME/pdf-to-llm-context.git
cd pdf-to-llm-context
```

### Step 2 — Get your free Gemini API key

1. Go to [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Sign in with your Google account
3. Click **Create API key**
4. Copy the key — you will need it in Step 4

> The free tier includes **1,500 requests/day** and **15 requests/minute** for Gemini 1.5 Flash.
> A 300-page book takes approximately 22 minutes and costs $0.

### Step 3 — Place your PDF in the `/input/` folder

```
pdf-to-llm-context/
└── input/
    └── your_book.pdf    ← put it here
```

> The `/input/` folder is excluded from git. Your PDF will never be committed to the repository.

### Step 4 — Configure the project

Open `config.yaml` in any text editor. **This is the only file you need to edit.**

```yaml
input:
  pdf_filename: "your_book.pdf"   # ← exact filename of your PDF
  title: "Accounting Fundamentals"
  author: "John Doe"
  year: 2019
  isbn: "978-0-000-00000-0"       # optional
  original_url: "https://..."     # optional — for attribution
```

The rest of the defaults work out of the box. See [Configuration Reference](#configuration-reference) for all options.

### Step 5 — Set up Python environment

```bash
cd extractor

# Create a virtual environment (recommended)
python -m venv .venv

# Activate it
# On macOS/Linux:
source .venv/bin/activate
# On Windows:
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Step 6 — Add your API key

```bash
# In the root of the project (not inside /extractor/):
cp .env.example .env
```

Open `.env` and replace the placeholder:

```env
GEMINI_API_KEY=AIza...your_actual_key_here
```

> Never commit `.env` to git. It is already in `.gitignore`.

### Step 7 — Run the extractor

```bash
# From inside /extractor/ with your venv active:
python extractor.py
```

You will see a **pre-flight quota analysis** before processing starts:

```
============================================================
  📊  QUOTA ANALYSIS — Pre-flight Check
============================================================
  Book pages       : 342
  Pages to process : 342
  AI model         : Gemini 1.5 Flash
  Est. time        : ~31.4 minutes
  Est. tokens      : ~273,600

  Free tier usage  : [████████████████████░░░░░░░░░░░░░░░░░░░░] 342/1500 req/day

  ✅  Fits within the free tier. Good to go!
```

Then extraction begins with a live progress bar:

```
  [███████████████░░░░░░░░░░░░░░░░░░░░░░░░]  44.1%  Page 151/342 ✅ done
```

**If the process is interrupted**, just run `python extractor.py` again.
Already-processed pages are automatically skipped.

### Step 8 — Preview the viewer locally

```bash
cd ../viewer
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) in your browser.

---

## 🌐 Deploy to GitHub Pages

### One-time GitHub setup

1. Go to your forked repository on GitHub
2. **Settings → Pages → Source**: select **GitHub Actions**
3. **Settings → Secrets and variables → Actions → New repository secret**:
   - Name: `VITE_BASE_PATH`
   - Value: `/your-repository-name/` *(with leading and trailing slash)*

### Deploy

```bash
# Commit your extracted output and push
git add output/ viewer/
git commit -m "feat: add extracted book pages"
git push origin main
```

GitHub Actions will automatically build and deploy. Your book will be live at:

```
https://YOUR_USERNAME.github.io/your-repository-name/
```

The **Actions** tab on GitHub shows deployment progress in real time.

---

## ⚙️ Configuration Reference

All options are in `config.yaml`. Here is the complete reference:

```yaml
input:
  pdf_filename: "my_book.pdf"     # Filename inside /input/
  title: "Book Title"
  author: "Author Name"
  year: 2024
  isbn: ""                        # Optional
  original_url: ""                # Optional — URL for attribution

ai:
  ocr_model: "gemini-1.5-flash"   # "gemini-1.5-flash" (free) or "gemini-1.5-pro"
  enable_claude_enrichment: false # Second pass with Claude (requires ANTHROPIC_API_KEY)
  claude_model: "claude-sonnet-4-20250514"
  enable_wolfram_math: false      # Math validation (requires WOLFRAM_APP_ID)

processing:
  dpi: 300                        # 200=fast, 300=balanced, 400=quality
  page_range: null                # null=all, or [start, end] e.g. [1, 50]
  rate_limit_delay: 4.5           # Seconds between API calls (min 4.0 for free tier)
  max_retries: 3                  # Retries per page before marking failed
  skip_existing: true             # Skip already-processed pages (resume support)

output:
  pages_dir: "output/pages"
  sync_to_viewer: true            # Copy output to viewer/public/ after extraction
  viewer_public_dir: "viewer/public/pages"

theme:
  primary_color: ""               # Leave empty to auto-detect from cover
  secondary_color: ""
  accent_color: ""
  background_color: ""
  text_color: ""
```

---

## 🔑 Optional API Keys

All optional integrations require adding keys to your `.env` file:

### Claude enrichment pass (Anthropic)

Enables a second AI pass to fix OCR artifacts and improve Markdown structure.

1. Get your key at [console.anthropic.com](https://console.anthropic.com)
2. Add to `.env`: `ANTHROPIC_API_KEY=sk-ant-...`
3. Enable in `config.yaml`: `enable_claude_enrichment: true`

> Note: Claude API is paid (no free tier). A 300-page book costs approximately $0.50–$2.00.

### Wolfram Alpha math validation

Validates detected mathematical expressions and adds computed results inline.

1. Get a free App ID at [products.wolframalpha.com/api](https://products.wolframalpha.com/api)
   *(2,000 free queries/month)*
2. Add to `.env`: `WOLFRAM_APP_ID=XXXX-XXXX`
3. Enable in `config.yaml`: `enable_wolfram_math: true`

---

## 📁 Project Structure

```
pdf-to-llm-context/
├── config.yaml                   ← ⭐ Edit this file only
├── .env.example                  ← Copy to .env and add your keys
├── .gitignore
│
├── input/                        ← Place your PDF here
│   └── README.txt
│
├── output/                       ← Auto-generated by extractor
│   ├── pages/
│   │   ├── page_0001.md
│   │   └── ...
│   ├── index.json
│   ├── theme.json
│   └── cover.png
│
├── extractor/                    ← Python pipeline
│   ├── extractor.py              ← Main script
│   ├── quota_analyzer.py         ← Pre-flight API usage check
│   ├── state_manager.py          ← Resume + idempotency
│   ├── cover_analyzer.py         ← Theme extraction from cover
│   ├── math_enricher.py          ← Wolfram + GeoGebra integration
│   └── requirements.txt
│
├── viewer/                       ← React web app
│   ├── src/
│   │   ├── App.jsx
│   │   ├── components/
│   │   │   ├── Sidebar.jsx       ← Navigation + search
│   │   │   ├── Reader.jsx        ← Markdown renderer
│   │   │   └── TTSControls.jsx   ← Text-to-speech controls
│   │   └── hooks/
│   │       └── useTTS.js         ← Web Speech API hook
│   ├── package.json
│   └── vite.config.js
│
└── .github/
    └── workflows/
        └── deploy.yml            ← GitHub Pages CI/CD
```

---

## 🛡️ Security & Privacy

| What | Status | Why |
|---|---|---|
| Your PDF file | ✅ Never committed | Listed in `.gitignore` |
| API keys | ✅ Never committed | `.env` is in `.gitignore` |
| Extracted Markdown | Committed (by you) | This is the shareable output |
| Free tier keys | Client-side only | Never stored on any server |

---

## 🔧 Troubleshooting

**"PDF not found" error**
→ Make sure the filename in `config.yaml → input.pdf_filename` exactly matches the file in `/input/`, including capitalization and extension.

**Rate limit errors (429)**
→ The extractor has automatic exponential backoff. If it keeps hitting limits, increase `rate_limit_delay` to `6.0` in `config.yaml`.

**Tables not rendering correctly in viewer**
→ Make sure `remark-gfm` is installed: `cd viewer && npm install`.

**GitHub Pages showing a blank page**
→ Verify that `VITE_BASE_PATH` secret is set correctly: `/your-repo-name/` with both slashes.

**Some pages marked as failed**
→ Run `python extractor.py` again. Failed pages are retried automatically. The state manager ensures no page is double-processed.

---

## 📄 License

MIT — free to use, modify, and distribute. See [LICENSE](LICENSE).

---

## 🙏 Acknowledgments

Built with:
- [Google Gemini](https://ai.google.dev/) — multimodal OCR
- [PyMuPDF](https://pymupdf.readthedocs.io/) — PDF rendering
- [React](https://react.dev/) + [Vite](https://vitejs.dev/) — viewer framework
- [react-markdown](https://github.com/remarkjs/react-markdown) — Markdown rendering
- [GeoGebra](https://www.geogebra.org/) — interactive math visualization
- [Wolfram Alpha](https://www.wolframalpha.com/) — math validation
