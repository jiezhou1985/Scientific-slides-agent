# CLAUDE.md -- Agent Guide for Scientific Slides Agent

## Project Overview

This is a Python CLI tool that converts scientific PDF papers into presentation slide decks. The pipeline: **parse PDF -> Claude generates JSON slide spec -> render to PDF**.

## Architecture

- `main.py` -- Entry point. Orchestrates parse -> generate -> render.
- `parser.py` -- Extracts text and figures from PDF using PyMuPDF. Filters junk images (small, extreme aspect ratios). Saves figures as `fig1.png`, `fig2.png`, etc. to a temp dir.
- `agent.py` -- Sends paper text + figure list to Claude via `claude` CLI (not the SDK). Returns validated JSON slide spec. Uses system prompt from `prompts/system.txt`.
- `renderer.py` -- Renders JSON spec + figures to PDF using ReportLab. Handles equation typesetting (stacked fractions, radicals, sub/superscripts), figure layout (right-panel vs full-width), and five slide types.
- `prompts/system.txt` -- System prompt defining slide design rules, equation notation, figure rules, and JSON output schema.

## Key Design Decisions

- **Claude CLI, not SDK**: Uses `subprocess.run(["claude", "--system-prompt", ..., "-p", ...])` to leverage Pro/Max plan auth. No API key needed.
- **ReportLab, not WeasyPrint**: Pure Python PDF generation. No system library dependencies (libpango, etc.).
- **DejaVu fonts**: Registered for Unicode math symbol support (Greek letters like rho, pi, theta). Falls back to Helvetica if not installed.
- **Equation notation**: Claude outputs equations using `_` for subscripts, `^` for superscripts, `(N/D)` for fractions, Unicode symbols for Greek letters. The renderer parses and typesets these.
- **Figure layout**: Images with aspect ratio > 2.5 are placed full-width below text. Others go in a right-side panel (108mm wide).

## Coding Patterns

- All rendering uses ReportLab canvas API with absolute positioning (points, not mm -- convert with `* mm` or `* PTS`).
- Color palette defined as module-level constants (`C_DARK`, `C_ACCENT`, etc.).
- Each slide type has its own `_draw_*` function.
- Equation rendering uses `_draw_equation_formatted()` which tokenizes the equation string and dispatches to `_draw_frac()`, `_draw_sqrt()`, `_draw_math_text()` etc.

## Common Tasks

### Adding a new slide type
1. Add the type name to `_validate_spec()` in `agent.py`
2. Add a new `_draw_<type>()` function in `renderer.py`
3. Add the dispatch case in `render_slides()`
4. Update `prompts/system.txt` to describe when Claude should use it

### Changing slide visual style
Edit constants at the top of `renderer.py`: colors (`C_*`), margins (`MARGIN_*`), font sizes, and layout widths.

### Changing content generation rules
Edit `prompts/system.txt`. Key sections: bullet count, equation notation guide, figure rules, slide type definitions, JSON schema.

### Debugging Claude output
Run `python agent.py "paper.pdf"` to see the raw JSON spec without rendering.

## Testing

```bash
python main.py "The physics of cranberry bogs.pdf"
# Check: The physics of cranberry bogs_slides.pdf
```

Verify:
- 8-14 slides generated
- Figures appear on relevant slides (not in corners)
- Equations render with proper fractions, radicals, subscripts
- No raw LaTeX or `_` underscores visible in the PDF
- Wide figures span full width, normal figures in right panel
