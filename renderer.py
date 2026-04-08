import os
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, white
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from PIL import Image as PILImage

# Register DejaVu Sans for Unicode support (Greek letters, math symbols)
_DEJAVU = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
_DEJAVU_B = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
if os.path.isfile(_DEJAVU):
    pdfmetrics.registerFont(TTFont("DejaVu", _DEJAVU))
if os.path.isfile(_DEJAVU_B):
    pdfmetrics.registerFont(TTFont("DejaVu-Bold", _DEJAVU_B))
MATH_FONT = "DejaVu-Bold" if os.path.isfile(_DEJAVU_B) else "Helvetica-Bold"
MATH_FONT_REG = "DejaVu" if os.path.isfile(_DEJAVU) else "Helvetica"

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


def _parse_equation(eq: str) -> list[dict]:
    """
    Parse an equation string into segments with style info.
    Handles: _x or _{xy} for subscripts, ^x or ^{xy} for superscripts.
    A leading "Label:" prefix is detected for distinct styling.
    """
    segments = []
    i = 0
    # Detect label prefix (e.g. "Gravity: ")
    colon_pos = eq.find(": ")
    if colon_pos > 0 and colon_pos < 25:
        segments.append({"text": eq[:colon_pos + 2], "style": "label"})
        i = colon_pos + 2

    while i < len(eq):
        ch = eq[i]
        if ch in ("_", "^") and i + 1 < len(eq):
            style = "sub" if ch == "_" else "sup"
            i += 1
            if eq[i] == "{":
                # Braced group: _{abc} or ^{abc}
                end = eq.find("}", i)
                if end == -1:
                    end = len(eq)
                segments.append({"text": eq[i + 1:end], "style": style})
                i = end + 1
            else:
                segments.append({"text": eq[i], "style": style})
                i += 1
        else:
            # Collect normal chars until next _ or ^
            start = i
            while i < len(eq) and eq[i] not in ("_", "^"):
                i += 1
            segments.append({"text": eq[start:i], "style": "normal"})
    return segments


def _draw_equation_formatted(c, eq: str, x: float, y: float,
                             base_font: str, base_size: float,
                             color, label_color):
    """
    Draw a single equation with proper subscripts and superscripts.
    Returns the x position after the last character drawn.
    """
    segments = _parse_equation(eq)
    sub_size = base_size * 0.65
    cx = x
    for seg in segments:
        text = seg["text"]
        style = seg["style"]
        if style == "label":
            c.setFont(base_font, base_size)
            c.setFillColor(label_color)
            c.drawString(cx, y, text)
            cx += c.stringWidth(text, base_font, base_size)
        elif style == "sub":
            c.setFont(base_font, sub_size)
            c.setFillColor(color)
            c.drawString(cx, y - base_size * 0.22, text)
            cx += c.stringWidth(text, base_font, sub_size)
        elif style == "sup":
            c.setFont(base_font, sub_size)
            c.setFillColor(color)
            c.drawString(cx, y + base_size * 0.35, text)
            cx += c.stringWidth(text, base_font, sub_size)
        else:
            c.setFont(base_font, base_size)
            c.setFillColor(color)
            c.drawString(cx, y, text)
            cx += c.stringWidth(text, base_font, base_size)
    return cx


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

    heading   = slide.get("heading", "")
    bullets   = slide.get("bullets") or []
    equations = slide.get("equations") or []
    if not equations and slide.get("formula"):
        equations = [slide["formula"]]
    figure    = slide.get("figure") or ""
    caption   = slide.get("figure_caption") or ""

    has_figure = bool(figure and os.path.isfile(os.path.join(figures_dir, figure)))

    # Detect wide figures (aspect > 2.5) — place below text instead of right panel
    fig_is_wide = False
    if has_figure:
        try:
            img = PILImage.open(os.path.join(figures_dir, figure))
            fig_is_wide = img.size[0] / max(1, img.size[1]) > 2.5
        except Exception:
            pass

    # ── Layout constants ──────────────────────────────────────────────────────
    FIG_W_MM    = 108.0
    GAP_MM      = 7.0
    EQ_FONT_SZ  = 14
    EQ_LEADING  = EQ_FONT_SZ * 1.6
    EQ_ACCENT_W = 3              # pts, accent bar width
    EQ_PAD_L    = 5 * mm         # left padding inside box (after accent bar)
    EQ_PAD_V    = 3 * mm         # vertical padding top/bottom

    area_top    = PAGE_H - MARGIN_T - 4 * mm
    area_bottom = MARGIN_B + SLIDE_NUM_H

    full_w_mm = (PAGE_W / PTS) - (MARGIN_L / mm) - (MARGIN_R / mm)
    text_w_mm = full_w_mm
    if has_figure and not fig_is_wide:
        text_w_mm = full_w_mm - FIG_W_MM - GAP_MM

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

    # ── Pre-calculate equation box height (needed for bullet spacing) ────────
    eq_h = 0
    if equations:
        eq_h = EQ_PAD_V * 2 + len(equations) * EQ_LEADING

    # ── Bullets — laid out from top, leaving room for equations after ─────────
    bullets_top = heading_bottom - 4 * mm
    # Reserve space at bottom for wide figure + equations
    wide_fig_reserve = 0
    if has_figure and fig_is_wide:
        avail_for_fig = (bullets_top - area_bottom - eq_h - 8 * mm) * 0.45
        wide_fig_reserve = avail_for_fig + 4 * mm

    bullets_bottom = area_bottom + eq_h + (4 * mm if equations else 0) + wide_fig_reserve
    avail_h = bullets_top - bullets_bottom

    bullet_end_y = bullets_top  # tracks where bullets actually end
    if bullets:
        B_SIZE = 16
        max_bc = _max_chars(text_w_mm - 6, B_SIZE)
        total_rows = sum(len(_wrap_text(b, max_bc)) for b in bullets)
        natural_h = total_rows * B_SIZE * 1.4
        extra_per_bullet = max(0, (avail_h - natural_h) / len(bullets))
        extra_per_bullet = min(extra_per_bullet, B_SIZE * 1.2)

        bullet_y = bullets_top
        indent   = MARGIN_L + 6 * mm
        marker_x = MARGIN_L + 1 * mm

        for bullet in bullets:
            c.setFont(MATH_FONT_REG, 9)
            c.setFillColor(C_ACCENT)
            c.drawString(marker_x, bullet_y + 2, "\u25b8")

            c.setFont(MATH_FONT_REG, B_SIZE)
            c.setFillColor(C_BODY)
            lines = _wrap_text(bullet, max_bc)
            for line in lines:
                c.drawString(indent, bullet_y, line)
                bullet_y -= B_SIZE * 1.4
            bullet_y -= extra_per_bullet

        bullet_end_y = bullet_y

    # ── Equation box — placed right after bullets with accent bar ────────────
    if equations:
        eq_gap = 4 * mm
        bx = MARGIN_L
        bw = text_w_mm * PTS
        bh = eq_h
        # Place directly below the last bullet
        by = bullet_end_y - eq_gap - bh

        # Light background with rounded corners
        c.setFillColor(HexColor("#f4f5fa"))
        c.roundRect(bx, by, bw, bh, 5, fill=1, stroke=0)

        # Purple accent bar on left edge
        c.setFillColor(C_ACCENT)
        c.roundRect(bx, by, EQ_ACCENT_W, bh, 2, fill=1, stroke=0)

        # Draw each equation with formatted sub/superscripts
        ey = by + bh - EQ_PAD_V - EQ_FONT_SZ * 0.3
        for eq in equations:
            _draw_equation_formatted(
                c, eq, bx + EQ_PAD_L, ey,
                MATH_FONT, EQ_FONT_SZ,
                color=C_DARK, label_color=C_ACCENT,
            )
            ey -= EQ_LEADING

    # ── Wide figure: placed below bullets + equations ────────────────────────
    if has_figure and fig_is_wide:
        content_end = by if equations else bullet_end_y
        fig_top_y = content_end - 4 * mm
        fig_h_mm = max(20, (fig_top_y - area_bottom) / PTS)
        _draw_figure(c, figures_dir, figure,
                     MARGIN_L, fig_top_y, full_w_mm, fig_h_mm, caption)

    # ── Right-panel figure (non-wide) ────────────────────────────────────────
    if has_figure and not fig_is_wide:
        fig_x     = MARGIN_L + (text_w_mm + GAP_MM) * PTS
        fig_top_y = area_top
        fig_h_mm  = (fig_top_y - area_bottom) / PTS

        _draw_figure(c, figures_dir, figure,
                     fig_x, fig_top_y, FIG_W_MM, fig_h_mm, caption)


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
