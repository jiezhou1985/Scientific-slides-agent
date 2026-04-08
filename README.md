# Scientific Slides Agent

An AI-powered tool that converts scientific PDF papers into clean, accessible presentation slides. It extracts text and figures from a paper, uses Claude to plan the slide content, and renders a polished PDF slide deck -- all in one command.

Built for a **general educated audience**: jargon is explained or replaced, equations are shown in proper mathematical notation, and each slide focuses on a single idea.

## Quick Start

```bash
pip install -r requirements.txt
python main.py "path/to/paper.pdf"
```

Output: `path/to/paper_slides.pdf`

## How It Works

```
PDF Paper
   |
   v
parser.py      Extract full text + crop figures as PNG (PyMuPDF)
   |
   v
agent.py       Send text + figure list to Claude --> JSON slide spec
   |
   v
renderer.py    Render slide spec + figures into PDF (ReportLab)
   |
   v
Slide Deck PDF
```

**Three stages, one pipeline:**

1. **Parse** -- `parser.py` opens the PDF with PyMuPDF, extracts all text, and saves embedded images as numbered PNGs to a temp directory. Small images (<100px) and extreme aspect ratios (>5:1, e.g. journal sidebars) are filtered out. Captions are heuristically matched to figures.

2. **Generate** -- `agent.py` sends the extracted text and figure list to Claude via the `claude` CLI. Claude returns a structured JSON slide specification following rules defined in `prompts/system.txt`: 8-14 slides, 3-4 bullets per slide, key equations in Unicode notation, and at most one figure per slide.

3. **Render** -- `renderer.py` takes the JSON spec and figures, and produces a PDF using ReportLab. Slides are A4 landscape with a professional color scheme. The renderer supports:
   - Stacked fractions (numerator/denominator with fraction bar)
   - Square root radicals with overbars
   - Proper subscript/superscript positioning
   - Automatic figure layout (right panel or full-width for wide images)
   - Five slide types: title, overview, content, figure_only, conclusion

## Requirements

- **Python 3.10+**
- **Claude Code CLI** installed and authenticated (Pro, Max, or Team plan -- no API key needed)
- **DejaVu Sans fonts** (optional, for full Unicode math symbol support)

### Install dependencies

```bash
pip install -r requirements.txt
```

Dependencies: `pymupdf`, `reportlab`, `pillow`

### Font setup (recommended)

The renderer uses DejaVu Sans for Greek letters and math symbols. On most Linux systems these are pre-installed. On other systems:

```bash
# Ubuntu/Debian
sudo apt install fonts-dejavu

# macOS (Homebrew)
brew install font-dejavu

# The renderer falls back to Helvetica if DejaVu is not found
```

## Usage

### Basic usage

```bash
python main.py "paper.pdf"
# Output: paper_slides.pdf (in the same directory as the input)
```

### Debug: inspect the JSON slide spec

```bash
python agent.py "paper.pdf"
# Prints the raw JSON that Claude produces, without rendering
```

### Example

```bash
python main.py "The physics of cranberry bogs.pdf"
# --> The physics of cranberry bogs_slides.pdf (11 slides)
```

## Slide Design

| Slide Type    | Layout |
|---------------|--------|
| `title`       | Dark background, centered title and subtitle |
| `overview`    | "What This Paper Is About" -- 3 key bullets + overview figure |
| `content`     | Heading + 3-4 bullets + optional figure + optional equations |
| `figure_only` | Full-page figure with heading and annotation |
| `conclusion`  | "Key Takeaways" -- 3-5 main lessons |

### Equation rendering

Equations are rendered with proper mathematical typesetting:
- **Stacked fractions**: `(4/3)` renders as a vertical fraction with bar
- **Square roots**: `sqrt(expr)` renders with radical symbol and overbar
- **Subscripts/superscripts**: `F_g`, `R^2` render at proper size and position
- **Unicode math**: Greek letters, operators, and symbols render natively

### Figure handling

- Figures are extracted directly from the source PDF
- Wide figures (aspect ratio > 2.5) span the full slide width below text
- Normal figures appear in a right-side panel
- Figures are centered and scaled to fit their panel
- Tiny images and journal sidebars are automatically filtered

## Project Structure

```
Scientific-slides-agent/
  main.py              Entry point
  parser.py            PDF text + figure extraction
  agent.py             Claude CLI integration
  renderer.py          PDF slide rendering
  requirements.txt     Python dependencies
  prompts/
    system.txt         System prompt for Claude (slide design rules)
```

## Customization

### Modify slide design rules

Edit `prompts/system.txt` to change:
- Number of slides (default: 8-14)
- Bullets per slide (default: 3-4)
- Equation style and notation
- Figure selection criteria
- Slide type definitions

### Modify visual style

Edit constants at the top of `renderer.py`:
- **Colors**: `C_DARK`, `C_ACCENT`, `C_BODY`, etc.
- **Margins**: `MARGIN_L`, `MARGIN_R`, `MARGIN_T`, `MARGIN_B`
- **Layout**: `FIG_W_MM` (figure panel width), `EQ_FONT_SZ` (equation font size)

## Limitations

- Input must be a PDF with extractable text (not scanned images)
- Figure extraction depends on how images are embedded in the PDF
- Equation rendering handles common patterns (fractions, radicals, sub/superscripts) but is not a full LaTeX engine
- Requires an active Claude Code CLI session
