import os
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, white, black
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from PIL import Image as PILImage

# A4 landscape: 297mm x 210mm
PAGE_W, PAGE_H = landscape(A4)

# Color palette
C_DARK    = HexColor("#0f3460")
C_MID     = HexColor("#16213e")
C_ACCENT  = HexColor("#533483")
C_TEXT    = HexColor("#1a1a2e")
C_BODY    = HexColor("#2d2d44")
C_SUBTLE  = HexColor("#aaaacc")
C_RULE    = HexColor("#e8e8f0")

MARGIN_L  = 14 * mm
MARGIN_R  = 14 * mm
MARGIN_T  = 10 * mm
MARGIN_B  = 10 * mm


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

        # Slide number
        _draw_slide_number(c, idx + 1, len(slides))
        c.showPage()

    c.save()
    return os.path.abspath(output_path)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _draw_accent_bar(c):
    bar_h = 3 * mm
    c.setFillColor(C_DARK)
    c.rect(0, PAGE_H - bar_h, PAGE_W, bar_h, fill=1, stroke=0)


def _draw_slide_number(c, current, total):
    c.setFont("Helvetica", 7)
    c.setFillColor(C_SUBTLE)
    label = f"{current} / {total}"
    c.drawRightString(PAGE_W - MARGIN_R, MARGIN_B * 0.6, label)


def _wrap_text(text: str, max_chars: int) -> list[str]:
    """Naive word-wrap."""
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
    return lines


def _draw_wrapped_text(c, text, x, y, font, size, color, max_width_mm, leading=None):
    """Draw text with word-wrap, returns final y position."""
    if leading is None:
        leading = size * 1.4
    c.setFont(font, size)
    c.setFillColor(color)
    # Approximate chars per line (each char ~0.55 * size pts, 1pt = 0.353mm)
    pts_per_mm = 2.835
    max_pts = max_width_mm * pts_per_mm
    avg_char_w = size * 0.52
    max_chars = max(10, int(max_pts / avg_char_w))
    lines = _wrap_text(text, max_chars)
    for line in lines:
        c.drawString(x, y, line)
        y -= leading
    return y


def _embed_figure(c, figures_dir, filename, x, y, max_w_mm, max_h_mm):
    """Draw a figure centered in the given bounding box. Returns actual height drawn (mm)."""
    if not filename:
        return 0
    path = os.path.join(figures_dir, filename)
    if not os.path.isfile(path):
        return 0

    pts_per_mm = 2.835
    max_w = max_w_mm * pts_per_mm
    max_h = max_h_mm * pts_per_mm

    try:
        img = PILImage.open(path)
        iw, ih = img.size
    except Exception:
        return 0

    scale = min(max_w / iw, max_h / ih, 1.0)
    draw_w = iw * scale
    draw_h = ih * scale

    # Center horizontally in the box
    cx = x + (max_w - draw_w) / 2
    # Draw from top of box downward (reportlab y is bottom-left origin)
    # y here is the top of the bounding box in pts
    draw_y = y - draw_h

    c.setStrokeColor(C_RULE)
    c.setLineWidth(0.5)
    c.rect(cx - 1, draw_y - 1, draw_w + 2, draw_h + 2, stroke=1, fill=0)
    c.drawImage(ImageReader(path), cx, draw_y, width=draw_w, height=draw_h,
                preserveAspectRatio=True, mask="auto")
    return draw_h / pts_per_mm


# ── Slide renderers ──────────────────────────────────────────────────────────

def _draw_title(c, slide):
    # Gradient background approximation: solid dark
    c.setFillColor(C_MID)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    # Left accent strip
    c.setFillColor(C_ACCENT)
    c.rect(0, 0, 4 * mm, PAGE_H, fill=1, stroke=0)

    cx = PAGE_W / 2
    cy = PAGE_H / 2

    heading = slide.get("heading", "")
    subtitle = slide.get("subtitle") or ""

    # Title
    c.setFillColor(white)
    font_size = 28
    c.setFont("Helvetica-Bold", font_size)
    # Simple centered multi-line
    words = heading.split()
    lines, cur = [], []
    for w in words:
        test = " ".join(cur + [w])
        if c.stringWidth(test, "Helvetica-Bold", font_size) > PAGE_W - 60 * mm:
            if cur:
                lines.append(" ".join(cur))
            cur = [w]
        else:
            cur.append(w)
    if cur:
        lines.append(" ".join(cur))

    total_h = len(lines) * font_size * 1.3 + (20 if subtitle else 0)
    ty = cy + total_h / 2

    for line in lines:
        tw = c.stringWidth(line, "Helvetica-Bold", font_size)
        c.drawString(cx - tw / 2, ty, line)
        ty -= font_size * 1.3

    if subtitle:
        c.setFont("Helvetica", 12)
        c.setFillColor(HexColor("#ccccdd"))
        sw = c.stringWidth(subtitle, "Helvetica", 12)
        c.drawString(cx - sw / 2, ty - 6, subtitle)


def _draw_content(c, slide, figures_dir, stype):
    _draw_accent_bar(c)

    pts_per_mm = 2.835
    heading = slide.get("heading", "")
    bullets = slide.get("bullets") or []
    figure = slide.get("figure")
    caption = slide.get("figure_caption") or ""

    has_figure = bool(figure and os.path.isfile(os.path.join(figures_dir, figure or "")))
    text_area_w = (PAGE_W / pts_per_mm - MARGIN_L / mm - MARGIN_R / mm)
    fig_w_mm = 95.0
    if has_figure:
        text_area_w -= fig_w_mm + 8  # gap

    # Heading
    heading_y = PAGE_H - MARGIN_T - 4 * mm
    c.setFont("Helvetica-Bold", 20)
    accent_color = C_ACCENT if stype == "conclusion" else C_DARK
    c.setFillColor(accent_color)

    # Wrap heading if needed
    max_heading_chars = max(10, int(text_area_w * pts_per_mm / (20 * 0.55)))
    h_lines = _wrap_text(heading, max_heading_chars)
    hy = heading_y
    for hl in h_lines:
        c.drawString(MARGIN_L, hy, hl)
        hy -= 20 * 1.3
    heading_bottom = hy - 2 * mm

    # Rule under heading
    c.setStrokeColor(C_RULE)
    c.setLineWidth(1)
    rule_x2 = (text_area_w + MARGIN_L / mm) * pts_per_mm
    c.line(MARGIN_L, heading_bottom, rule_x2, heading_bottom)

    # Bullets
    bullet_y = heading_bottom - 5 * mm
    bullet_size = 14
    bullet_leading = bullet_size * 1.6
    indent = MARGIN_L + 5 * mm
    marker_x = MARGIN_L + 1 * mm
    max_bullet_chars = max(10, int((text_area_w - 6) * pts_per_mm / (bullet_size * 0.52)))

    for bullet in bullets:
        # Arrow marker
        c.setFont("Helvetica", 10)
        c.setFillColor(C_ACCENT)
        c.drawString(marker_x, bullet_y + 1, "▸")

        # Bullet text
        c.setFont("Helvetica", bullet_size)
        c.setFillColor(C_BODY)
        lines = _wrap_text(bullet, max_bullet_chars)
        for i, line in enumerate(lines):
            c.drawString(indent, bullet_y, line)
            bullet_y -= bullet_leading
        bullet_y -= 1 * mm  # extra gap between bullets

    # Figure (right panel)
    if has_figure:
        fig_x = PAGE_W - (fig_w_mm + MARGIN_R / mm) * pts_per_mm
        fig_top = PAGE_H - MARGIN_T - 4 * mm
        fig_h_mm = PAGE_H / pts_per_mm - MARGIN_T / mm - MARGIN_B / mm - 12

        drawn_h = _embed_figure(c, figures_dir, figure, fig_x, fig_top, fig_w_mm, fig_h_mm)

        if caption and drawn_h > 0:
            cap_y = fig_top - drawn_h * pts_per_mm - 3 * mm
            c.setFont("Helvetica-Oblique", 8)
            c.setFillColor(C_SUBTLE)
            cap_lines = _wrap_text(caption, int(fig_w_mm * pts_per_mm / (8 * 0.52)))
            for cl in cap_lines:
                if cap_y > MARGIN_B + 4 * mm:
                    cw = c.stringWidth(cl, "Helvetica-Oblique", 8)
                    c.drawString(fig_x + (fig_w_mm * pts_per_mm - cw) / 2, cap_y, cl)
                    cap_y -= 8 * 1.4


def _draw_figure_only(c, slide, figures_dir):
    _draw_accent_bar(c)

    pts_per_mm = 2.835
    heading = slide.get("heading", "")
    figure = slide.get("figure")
    annotation = slide.get("annotation") or ""

    # Heading
    heading_y = PAGE_H - MARGIN_T - 4 * mm
    c.setFont("Helvetica-Bold", 20)
    c.setFillColor(C_DARK)
    hw = c.stringWidth(heading, "Helvetica-Bold", 20)
    c.drawString((PAGE_W - hw) / 2, heading_y, heading)

    # Figure centered
    fig_top = heading_y - 8 * mm
    available_h = fig_top / pts_per_mm - MARGIN_B / mm - (12 if annotation else 4)
    available_w = (PAGE_W / pts_per_mm) - 2 * (MARGIN_L / mm)
    fig_x = MARGIN_L

    drawn_h = _embed_figure(c, figures_dir, figure, fig_x, fig_top,
                            available_w, available_h)

    # Annotation
    if annotation and drawn_h > 0:
        ann_y = fig_top - drawn_h * pts_per_mm - 4 * mm
        c.setFont("Helvetica-Oblique", 10)
        c.setFillColor(C_BODY)
        max_chars = int(available_w * pts_per_mm / (10 * 0.52))
        ann_lines = _wrap_text(annotation, max_chars)
        for al in ann_lines:
            aw = c.stringWidth(al, "Helvetica-Oblique", 10)
            c.drawString((PAGE_W - aw) / 2, ann_y, al)
            ann_y -= 10 * 1.5
