import os
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, white
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from PIL import Image as PILImage

# A4 landscape: 297mm x 210mm
PAGE_W, PAGE_H = landscape(A4)

# Color palette
C_DARK   = HexColor("#0f3460")
C_MID    = HexColor("#16213e")
C_ACCENT = HexColor("#533483")
C_TEXT   = HexColor("#1a1a2e")
C_BODY   = HexColor("#2d2d44")
C_SUBTLE = HexColor("#aaaacc")
C_RULE   = HexColor("#e8e8f0")
C_BOX_BG = HexColor("#eef0f8")

PTS = 2.835          # 1mm in points
MARGIN_L = 14 * mm
MARGIN_R = 14 * mm
MARGIN_T = 10 * mm
MARGIN_B =  8 * mm
SLIDE_NUM_H = 6 * mm  # space reserved at bottom for slide number


def render_slides(spec: dict, figures_dir: str, source_pdf_path: str) -> str:
    base = os.path.splitext(source_pdf_path)[0]
    output_path = base + "_slides.pdf"

    c = canvas.Canvas(output_path, pagesize=landscape(A4))
    slides = spec["slides"]

    for idx, slide in enumerate(slides):
        stype = slide.get("type", "content")
        if stype == "title":
            _draw_title(c, slide)
        elif stype == "figure_only":
            _draw_figure_only(c, slide, figures_dir)
        else:
            _draw_content(c, slide, figures_dir, stype)
        _draw_slide_number(c, idx + 1, len(slides))
        c.showPage()

    c.save()
    return os.path.abspath(output_path)


# ── Shared helpers ────────────────────────────────────────────────────────────

def _draw_accent_bar(c):
    c.setFillColor(C_DARK)
    c.rect(0, PAGE_H - 3 * mm, PAGE_W, 3 * mm, fill=1, stroke=0)


def _draw_slide_number(c, current, total):
    c.setFont("Helvetica", 7)
    c.setFillColor(C_SUBTLE)
    c.drawRightString(PAGE_W - MARGIN_R, MARGIN_B * 0.5, f"{current} / {total}")


def _wrap_text(text: str, max_chars: int) -> list[str]:
    words = text.split()
    lines, current = [], []
    for w in words:
        if sum(len(x) + 1 for x in current) + len(w) > max_chars:
            if current:
                lines.append(" ".join(current))
            current = [w]
        else:
            current.append(w)
    if current:
        lines.append(" ".join(current))
    return lines or [""]


def _max_chars(width_mm: float, font_size: float) -> int:
    """Approximate max chars that fit in width_mm at font_size pt."""
    return max(10, int(width_mm * PTS / (font_size * 0.52)))


def _draw_wrapped(c, text, x, y, font, size, color, width_mm, leading_factor=1.4):
    """Draw wrapped text, return y position after last line."""
    c.setFont(font, size)
    c.setFillColor(color)
    leading = size * leading_factor
    for line in _wrap_text(text, _max_chars(width_mm, size)):
        c.drawString(x, y, line)
        y -= leading
    return y


def _figure_dims(path: str, max_w_mm: float, max_h_mm: float):
    """Return (draw_w_pts, draw_h_pts) fitting within the bounding box."""
    try:
        img = PILImage.open(path)
        iw, ih = img.size
    except Exception:
        return 0, 0
    max_w = max_w_mm * PTS
    max_h = max_h_mm * PTS
    scale = min(max_w / iw, max_h / ih)  # allow upscaling to fill panel
    return iw * scale, ih * scale


def _draw_figure(c, figures_dir: str, filename: str,
                 panel_x, panel_top_y, panel_w_mm, panel_h_mm,
                 caption: str = ""):
    """
    Draw a figure centered (both axes) inside its panel.
    panel_x, panel_top_y are in pts. Returns actual drawn height in mm.
    """
    if not filename:
        return 0
    path = os.path.join(figures_dir, filename)
    if not os.path.isfile(path):
        return 0

    cap_h = (8 * 1.4 * len(_wrap_text(caption, _max_chars(panel_w_mm, 8)))) if caption else 0
    available_h_mm = panel_h_mm - (cap_h / PTS + 3 if caption else 0)

    dw, dh = _figure_dims(path, panel_w_mm - 2, available_h_mm - 2)
    if dw == 0:
        return 0

    panel_h_pts = panel_h_mm * PTS

    # Center horizontally and vertically within the panel
    cx = panel_x + (panel_w_mm * PTS - dw) / 2
    # Vertical center: panel_top_y is the top, draw downward
    remaining = panel_h_pts - cap_h - dh
    cy = panel_top_y - (remaining / 2) - dh   # bottom-left of image

    # Border
    c.setStrokeColor(C_RULE)
    c.setLineWidth(0.5)
    c.rect(cx - 1, cy - 1, dw + 2, dh + 2, stroke=1, fill=0)
    c.drawImage(ImageReader(path), cx, cy, width=dw, height=dh,
                preserveAspectRatio=True, mask="auto")

    # Caption below image
    if caption:
        cy2 = cy - 3 * mm
        c.setFont("Helvetica-Oblique", 8)
        c.setFillColor(C_SUBTLE)
        for line in _wrap_text(caption, _max_chars(panel_w_mm, 8)):
            lw = c.stringWidth(line, "Helvetica-Oblique", 8)
            c.drawString(panel_x + (panel_w_mm * PTS - lw) / 2, cy2, line)
            cy2 -= 8 * 1.4

    return dh / PTS


# ── Slide renderers ───────────────────────────────────────────────────────────

def _draw_title(c, slide):
    c.setFillColor(C_MID)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    c.setFillColor(C_ACCENT)
    c.rect(0, 0, 5 * mm, PAGE_H, fill=1, stroke=0)

    heading  = slide.get("heading", "")
    subtitle = slide.get("subtitle") or ""
    font_size = 28
    c.setFont("Helvetica-Bold", font_size)

    # Wrap and measure title
    lines = _wrap_text(heading, _max_chars((PAGE_W / PTS) - 60, font_size))
    total_h = len(lines) * font_size * 1.3 + (20 if subtitle else 0)
    ty = PAGE_H / 2 + total_h / 2

    c.setFillColor(white)
    for line in lines:
        tw = c.stringWidth(line, "Helvetica-Bold", font_size)
        c.drawString(PAGE_W / 2 - tw / 2, ty, line)
        ty -= font_size * 1.3

    if subtitle:
        c.setFont("Helvetica", 12)
        c.setFillColor(HexColor("#ccccdd"))
        sw = c.stringWidth(subtitle, "Helvetica", 12)
        c.drawString(PAGE_W / 2 - sw / 2, ty - 6, subtitle)


def _draw_content(c, slide, figures_dir, stype):
    _draw_accent_bar(c)

    heading  = slide.get("heading", "")
    bullets  = slide.get("bullets") or []
    formula  = slide.get("formula") or ""
    figure   = slide.get("figure") or ""
    caption  = slide.get("figure_caption") or ""

    has_figure = bool(figure and os.path.isfile(os.path.join(figures_dir, figure)))

    # ── Layout constants ──────────────────────────────────────────────────────
    FIG_W_MM   = 108.0          # right panel width when figure present
    GAP_MM     = 7.0            # gap between text and figure panels
    FORMULA_H  = 14 * mm       # height of formula box
    FORMULA_GAP = 3 * mm

    # Usable slide area (pts)
    area_top    = PAGE_H - MARGIN_T - 4 * mm   # just below accent bar
    area_bottom = MARGIN_B + SLIDE_NUM_H        # above slide number

    text_w_mm = (PAGE_W / PTS) - (MARGIN_L / mm) - (MARGIN_R / mm)
    if has_figure:
        text_w_mm -= FIG_W_MM + GAP_MM

    # ── Heading ───────────────────────────────────────────────────────────────
    H_SIZE = 20
    accent_col = C_ACCENT if stype == "conclusion" else C_DARK
    c.setFont("Helvetica-Bold", H_SIZE)
    c.setFillColor(accent_col)
    h_lines = _wrap_text(heading, _max_chars(text_w_mm, H_SIZE))
    hy = area_top
    for hl in h_lines:
        c.drawString(MARGIN_L, hy, hl)
        hy -= H_SIZE * 1.3
    heading_bottom = hy - 2 * mm

    # Rule
    c.setStrokeColor(C_RULE)
    c.setLineWidth(1)
    c.line(MARGIN_L, heading_bottom, MARGIN_L + text_w_mm * PTS, heading_bottom)

    # ── Formula box (reserve space at bottom of text column) ─────────────────
    formula_y = area_bottom  # bottom of formula box (pts)
    if formula:
        bx = MARGIN_L
        bw = text_w_mm * PTS
        bh = FORMULA_H
        by = formula_y

        c.setFillColor(C_BOX_BG)
        c.roundRect(bx, by, bw, bh, 4, fill=1, stroke=0)

        c.setFont("Helvetica-Bold", 8)
        c.setFillColor(C_ACCENT)
        c.drawString(bx + 4 * mm, by + bh - 4.5 * mm, "Key Relation:")

        c.setFont("Helvetica-Bold", 11)
        c.setFillColor(C_DARK)
        c.drawString(bx + 4 * mm, by + 3.5 * mm, formula)

        formula_y += FORMULA_H + FORMULA_GAP   # bullet area ends above box

    # ── Bullets spread to fill available vertical space ───────────────────────
    bullets_top    = heading_bottom - 4 * mm
    bullets_bottom = formula_y + (FORMULA_GAP if formula else 0)
    avail_h = bullets_top - bullets_bottom

    if bullets:
        B_SIZE = 16
        # How many "rows" do the bullets take with wrap?
        max_bc = _max_chars(text_w_mm - 6, B_SIZE)
        total_rows = sum(len(_wrap_text(b, max_bc)) for b in bullets)
        # Natural height = rows * leading + inter-bullet gap
        natural_h = total_rows * B_SIZE * 1.4
        # Spread extra space equally between bullets
        extra_per_bullet = max(0, (avail_h - natural_h) / len(bullets))
        extra_per_bullet = min(extra_per_bullet, B_SIZE * 1.5)  # cap gap

        bullet_y = bullets_top
        indent   = MARGIN_L + 6 * mm
        marker_x = MARGIN_L + 1 * mm

        for bullet in bullets:
            # Marker
            c.setFont("Helvetica", 9)
            c.setFillColor(C_ACCENT)
            c.drawString(marker_x, bullet_y + 2, "▸")

            # Text
            c.setFont("Helvetica", B_SIZE)
            c.setFillColor(C_BODY)
            lines = _wrap_text(bullet, max_bc)
            for i, line in enumerate(lines):
                c.drawString(indent, bullet_y, line)
                bullet_y -= B_SIZE * 1.4
            bullet_y -= extra_per_bullet

    # ── Figure: centered in right panel, spans full content height ────────────
    if has_figure:
        fig_x     = MARGIN_L + (text_w_mm + GAP_MM) * PTS
        fig_top_y = area_top
        fig_h_mm  = (fig_top_y - area_bottom) / PTS

        _draw_figure(c, figures_dir, figure,
                     fig_x, fig_top_y, FIG_W_MM, fig_h_mm,
                     caption)


def _draw_figure_only(c, slide, figures_dir):
    _draw_accent_bar(c)

    heading    = slide.get("heading", "")
    figure     = slide.get("figure") or ""
    annotation = slide.get("annotation") or ""

    # Heading
    H_SIZE = 20
    area_top = PAGE_H - MARGIN_T - 4 * mm
    c.setFont("Helvetica-Bold", H_SIZE)
    c.setFillColor(C_DARK)
    hw = c.stringWidth(heading, "Helvetica-Bold", H_SIZE)
    c.drawString((PAGE_W - hw) / 2, area_top, heading)

    # Figure occupies remaining space
    ann_h = (10 * 1.5 * 2 + 4 * mm) if annotation else 0
    fig_top  = area_top - H_SIZE * 1.4 - 4 * mm
    area_bot = MARGIN_B + SLIDE_NUM_H
    fig_h_mm = (fig_top - area_bot - ann_h) / PTS
    fig_w_mm = (PAGE_W / PTS) - (MARGIN_L / mm) - (MARGIN_R / mm)

    _draw_figure(c, figures_dir, figure,
                 MARGIN_L, fig_top, fig_w_mm, fig_h_mm)

    if annotation:
        ann_y = area_bot + ann_h - 10 * mm
        c.setFont("Helvetica-Oblique", 10)
        c.setFillColor(C_BODY)
        for line in _wrap_text(annotation, _max_chars(fig_w_mm, 10)):
            lw = c.stringWidth(line, "Helvetica-Oblique", 10)
            c.drawString((PAGE_W - lw) / 2, ann_y, line)
            ann_y -= 10 * 1.5
