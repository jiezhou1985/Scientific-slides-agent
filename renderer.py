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


def render_slides(spec: dict, figures_dir: str, source_pdf_path: str,
                   presenter: str = "") -> str:
    base = os.path.splitext(source_pdf_path)[0]
    output_path = base + "_slides.pdf"

    c = canvas.Canvas(output_path, pagesize=landscape(A4))
    slides = spec["slides"]

    # Inject presenter into title slide
    if presenter:
        for slide in slides:
            if slide.get("type") == "title":
                slide["presenter"] = presenter
                break

    total = len(slides) + 1  # +1 for Thank You slide

    for idx, slide in enumerate(slides):
        stype = slide.get("type", "content")
        if stype == "title":
            _draw_title(c, slide)
        elif stype == "figure_only":
            _draw_figure_only(c, slide, figures_dir)
        elif stype == "conclusion":
            _draw_conclusion(c, slide)
        else:
            _draw_content(c, slide, figures_dir, stype)
        _draw_slide_number(c, idx + 1, total)
        c.showPage()

    # Thank You closing slide
    _draw_thankyou(c, total)
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


# ── Equation rendering with fractions, radicals, sub/superscripts ─────────────

def _find_matching_paren(s: str, pos: int) -> int:
    """Find index of the closing ')' that matches '(' at pos."""
    depth = 0
    for i in range(pos, len(s)):
        if s[i] == "(":
            depth += 1
        elif s[i] == ")":
            depth -= 1
            if depth == 0:
                return i
    return len(s) - 1


def _find_top_level_slash(s: str):
    """Find index of '/' not inside parentheses, or None."""
    depth = 0
    for i, ch in enumerate(s):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == "/" and depth == 0:
            return i
    return None


def _measure_math_text(c, text: str, font: str, size: float) -> float:
    """Measure width of text that may contain _sub and ^sup markers."""
    w, i, sub_sz = 0.0, 0, size * 0.65
    while i < len(text):
        if text[i] in ("_", "^") and i + 1 < len(text):
            i += 1
            if text[i] == "{":
                end = text.find("}", i)
                if end == -1:
                    end = len(text)
                w += c.stringWidth(text[i + 1:end], font, sub_sz)
                i = end + 1
            else:
                w += c.stringWidth(text[i], font, sub_sz)
                i += 1
        else:
            start = i
            while i < len(text) and text[i] not in ("_", "^"):
                i += 1
            w += c.stringWidth(text[start:i], font, size)
    return w


def _draw_math_text(c, text: str, x: float, y: float,
                    font: str, size: float, color) -> float:
    """Draw text with sub/superscript support. Returns x after last char."""
    cx, i, sub_sz = x, 0, size * 0.65
    while i < len(text):
        if text[i] == "_" and i + 1 < len(text):
            i += 1
            if text[i] == "{":
                end = text.find("}", i)
                if end == -1:
                    end = len(text)
                chunk = text[i + 1:end]
                i = end + 1
            else:
                chunk = text[i]
                i += 1
            c.setFont(font, sub_sz)
            c.setFillColor(color)
            c.drawString(cx, y - size * 0.22, chunk)
            cx += c.stringWidth(chunk, font, sub_sz)
        elif text[i] == "^" and i + 1 < len(text):
            i += 1
            if text[i] == "{":
                end = text.find("}", i)
                if end == -1:
                    end = len(text)
                chunk = text[i + 1:end]
                i = end + 1
            elif text[i] == "(":
                end = _find_matching_paren(text, i)
                chunk = text[i + 1:end]
                i = end + 1
            else:
                chunk = text[i]
                i += 1
            c.setFont(font, sub_sz)
            c.setFillColor(color)
            c.drawString(cx, y + size * 0.35, chunk)
            cx += c.stringWidth(chunk, font, sub_sz)
        else:
            start = i
            while i < len(text) and text[i] not in ("_", "^"):
                i += 1
            chunk = text[start:i]
            c.setFont(font, size)
            c.setFillColor(color)
            c.drawString(cx, y, chunk)
            cx += c.stringWidth(chunk, font, size)
    return cx


def _draw_frac(c, num: str, den: str, x: float, y: float,
               font: str, base_size: float, color) -> float:
    """Draw a stacked fraction (num over den). Returns width consumed."""
    frac_sz = base_size * 0.75
    num_w = _measure_math_text(c, num, font, frac_sz)
    den_w = _measure_math_text(c, den, font, frac_sz)
    frac_w = max(num_w, den_w) + 6          # 3pt padding each side
    bar_y = y + base_size * 0.30             # fraction bar at mid-cap height

    # Fraction bar
    c.setStrokeColor(color)
    c.setLineWidth(0.7)
    c.line(x, bar_y, x + frac_w, bar_y)

    # Numerator centered above bar
    _draw_math_text(c, num, x + (frac_w - num_w) / 2,
                    bar_y + 2, font, frac_sz, color)
    # Denominator centered below bar
    _draw_math_text(c, den, x + (frac_w - den_w) / 2,
                    bar_y - frac_sz - 1, font, frac_sz, color)
    return frac_w


def _draw_sqrt(c, content: str, x: float, y: float,
               font: str, base_size: float, color) -> float:
    """Draw √ with overbar over content. Returns width consumed."""
    # Check if content is a fraction (has top-level /)
    slash = _find_top_level_slash(content)
    if slash is not None:
        return _draw_sqrt_frac(c, content[:slash].strip(),
                               content[slash + 1:].strip(),
                               x, y, font, base_size, color)

    content_w = _measure_math_text(c, content, font, base_size)
    rad_w = base_size * 0.55
    top_y = y + base_size * 1.05

    # Radical checkmark + overbar
    c.setStrokeColor(color)
    c.setLineWidth(0.8)
    p = c.beginPath()
    p.moveTo(x + 2, y + base_size * 0.45)
    p.lineTo(x + rad_w * 0.35, y + base_size * 0.30)
    p.lineTo(x + rad_w * 0.65, y - base_size * 0.12)
    p.lineTo(x + rad_w, top_y)
    p.lineTo(x + rad_w + content_w + 3, top_y)
    c.drawPath(p, fill=0, stroke=1)

    # Content
    _draw_math_text(c, content, x + rad_w + 1, y, font, base_size, color)
    return rad_w + content_w + 4


def _draw_sqrt_frac(c, num: str, den: str, x: float, y: float,
                    font: str, base_size: float, color) -> float:
    """Draw √ over a stacked fraction. Returns width consumed."""
    frac_sz = base_size * 0.75
    num_w = _measure_math_text(c, num, font, frac_sz)
    den_w = _measure_math_text(c, den, font, frac_sz)
    frac_w = max(num_w, den_w) + 6
    rad_w = base_size * 0.55

    bar_y = y + base_size * 0.30
    top_y = bar_y + frac_sz + 5              # above numerator

    # Fraction bar
    c.setStrokeColor(color)
    c.setLineWidth(0.7)
    c.line(x + rad_w, bar_y, x + rad_w + frac_w, bar_y)

    # Numerator / denominator
    _draw_math_text(c, num, x + rad_w + (frac_w - num_w) / 2,
                    bar_y + 2, font, frac_sz, color)
    _draw_math_text(c, den, x + rad_w + (frac_w - den_w) / 2,
                    bar_y - frac_sz - 1, font, frac_sz, color)

    # Radical checkmark + overbar
    c.setStrokeColor(color)
    c.setLineWidth(0.8)
    p = c.beginPath()
    p.moveTo(x + 2, y + base_size * 0.45)
    p.lineTo(x + rad_w * 0.35, y + base_size * 0.30)
    p.lineTo(x + rad_w * 0.65, y - base_size * 0.12)
    p.lineTo(x + rad_w, top_y)
    p.lineTo(x + rad_w + frac_w + 3, top_y)
    c.drawPath(p, fill=0, stroke=1)

    return rad_w + frac_w + 4


def _is_simple_frac(s: str, pos: int) -> bool:
    """Check if '(' at pos starts a simple (A/B) fraction."""
    end = _find_matching_paren(s, pos)
    inside = s[pos + 1:end]
    slash = _find_top_level_slash(inside)
    if slash is None:
        return False
    num, den = inside[:slash], inside[slash + 1:]
    return len(num) <= 12 and len(den) <= 12 and "(" not in num


_UNICODE_SUPS = set("\u2070\u00b9\u00b2\u00b3\u2074\u2075\u2076\u2077\u2078\u2079")  # ⁰¹²³⁴⁵⁶⁷⁸⁹


def _measure_equation_width(c, eq: str, base_font: str, base_size: float) -> float:
    """Measure total drawn width of a formatted equation (no drawing)."""
    w = 0.0
    i = 0
    sub_sz = base_size * 0.65
    frac_sz = base_size * 0.75

    # Label prefix
    colon = eq.find(": ")
    if 0 < colon < 25:
        w += c.stringWidth(eq[:colon + 2], base_font, base_size)
        i = colon + 2

    while i < len(eq):
        ch = eq[i]

        if ch == "\u221a" and i + 1 < len(eq) and eq[i + 1] == "(":
            end = _find_matching_paren(eq, i + 1)
            content = eq[i + 2:end]
            slash = _find_top_level_slash(content)
            rad_w = base_size * 0.55
            if slash is not None:
                num_w = _measure_math_text(c, content[:slash].strip(), base_font, frac_sz)
                den_w = _measure_math_text(c, content[slash + 1:].strip(), base_font, frac_sz)
                w += rad_w + max(num_w, den_w) + 10
            else:
                w += rad_w + _measure_math_text(c, content, base_font, base_size) + 4
            i = end + 1
            continue

        if ch == "(" and _is_simple_frac(eq, i):
            end = _find_matching_paren(eq, i)
            inside = eq[i + 1:end]
            slash = _find_top_level_slash(inside)
            num_w = _measure_math_text(c, inside[:slash].strip(), base_font, frac_sz)
            den_w = _measure_math_text(c, inside[slash + 1:].strip(), base_font, frac_sz)
            w += max(num_w, den_w) + 6
            i = end + 1
            continue

        if ch == "_" and i + 1 < len(eq):
            i += 1
            if eq[i] == "{":
                end = eq.find("}", i);
                if end == -1: end = len(eq)
                w += c.stringWidth(eq[i + 1:end], base_font, sub_sz)
                i = end + 1
            else:
                w += c.stringWidth(eq[i], base_font, sub_sz)
                i += 1
            continue

        if ch == "^" and i + 1 < len(eq):
            i += 1
            if eq[i] == "{":
                end = eq.find("}", i)
                if end == -1: end = len(eq)
                w += c.stringWidth(eq[i + 1:end], base_font, sub_sz)
                i = end + 1
            elif eq[i] == "(":
                end = _find_matching_paren(eq, i)
                w += c.stringWidth(eq[i + 1:end], base_font, sub_sz)
                i = end + 1
            else:
                w += c.stringWidth(eq[i], base_font, sub_sz)
                i += 1
            continue

        if ch in _UNICODE_SUPS:
            w += c.stringWidth(ch, base_font, sub_sz)
            i += 1
            continue

        start = i
        while i < len(eq):
            if eq[i] in ("_", "^") or eq[i] in _UNICODE_SUPS:
                break
            if eq[i] == "\u221a" and i + 1 < len(eq) and eq[i + 1] == "(":
                break
            if eq[i] == "(" and _is_simple_frac(eq, i):
                break
            i += 1
        w += c.stringWidth(eq[start:i], base_font, base_size)

    return w


def _draw_equation_formatted(c, eq: str, x: float, y: float,
                             base_font: str, base_size: float,
                             color, label_color):
    """
    Draw a single equation with stacked fractions, radicals,
    and proper sub/superscripts.
    """
    cx = x
    i = 0

    # ── Label prefix (e.g. "Gravity: ") ──────────────────────────────────
    colon = eq.find(": ")
    if 0 < colon < 25:
        label = eq[:colon + 2]
        c.setFont(base_font, base_size)
        c.setFillColor(label_color)
        c.drawString(cx, y, label)
        cx += c.stringWidth(label, base_font, base_size)
        i = colon + 2

    # ── Main equation body ───────────────────────────────────────────────
    while i < len(eq):
        ch = eq[i]

        # √( → square root
        if ch == "\u221a" and i + 1 < len(eq) and eq[i + 1] == "(":
            end = _find_matching_paren(eq, i + 1)
            content = eq[i + 2:end]
            cx += _draw_sqrt(c, content, cx, y, base_font, base_size, color)
            i = end + 1
            continue

        # ( → possible stacked fraction
        if ch == "(" and _is_simple_frac(eq, i):
            end = _find_matching_paren(eq, i)
            inside = eq[i + 1:end]
            slash = _find_top_level_slash(inside)
            num = inside[:slash].strip()
            den = inside[slash + 1:].strip()
            cx += _draw_frac(c, num, den, cx, y, base_font, base_size, color)
            i = end + 1
            continue

        # _ → subscript
        if ch == "_" and i + 1 < len(eq):
            i += 1
            sub_sz = base_size * 0.65
            if eq[i] == "{":
                end = eq.find("}", i)
                if end == -1:
                    end = len(eq)
                chunk = eq[i + 1:end]
                i = end + 1
            else:
                chunk = eq[i]
                i += 1
            c.setFont(base_font, sub_sz)
            c.setFillColor(color)
            c.drawString(cx, y - base_size * 0.22, chunk)
            cx += c.stringWidth(chunk, base_font, sub_sz)
            continue

        # ^ → superscript
        if ch == "^" and i + 1 < len(eq):
            i += 1
            sub_sz = base_size * 0.65
            if eq[i] == "{":
                end = eq.find("}", i)
                if end == -1:
                    end = len(eq)
                chunk = eq[i + 1:end]
                i = end + 1
            elif eq[i] == "(":
                end = _find_matching_paren(eq, i)
                chunk = eq[i + 1:end]
                i = end + 1
            else:
                chunk = eq[i]
                i += 1
            c.setFont(base_font, sub_sz)
            c.setFillColor(color)
            c.drawString(cx, y + base_size * 0.55, chunk)
            cx += c.stringWidth(chunk, base_font, sub_sz)
            continue

        # Unicode superscript characters (², ³, etc.) — draw raised
        if ch in _UNICODE_SUPS:
            sup_sz = base_size * 0.65
            c.setFont(base_font, sup_sz)
            c.setFillColor(color)
            c.drawString(cx, y + base_size * 0.55, ch)
            cx += c.stringWidth(ch, base_font, sup_sz)
            i += 1
            continue

        # Regular text — collect until next special char
        start = i
        while i < len(eq):
            if eq[i] in ("_", "^"):
                break
            if eq[i] in _UNICODE_SUPS:
                break
            if eq[i] == "\u221a" and i + 1 < len(eq) and eq[i + 1] == "(":
                break
            if eq[i] == "(" and _is_simple_frac(eq, i):
                break
            i += 1
        chunk = eq[start:i]
        c.setFont(base_font, base_size)
        c.setFillColor(color)
        c.drawString(cx, y, chunk)
        cx += c.stringWidth(chunk, base_font, base_size)

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
        ty -= 12 * 1.3 + 6

    presenter = slide.get("presenter") or ""
    if presenter:
        c.setFont("Helvetica", 11)
        c.setFillColor(HexColor("#aaaacc"))
        pw = c.stringWidth(presenter, "Helvetica", 11)
        c.drawString(PAGE_W / 2 - pw / 2, ty - 12, presenter)


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
    EQ_FONT_SZ  = 18
    EQ_LEADING  = EQ_FONT_SZ * 2.6  # taller for stacked fractions / radicals
    EQ_ACCENT_W = 3              # pts, accent bar width
    EQ_PAD_L    = 5 * mm         # left padding inside box (after accent bar)
    EQ_PAD_V    = 4 * mm         # vertical padding top/bottom

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
        lh_pre = []
        for eq in equations:
            has_tall = ("/" in eq) or ("\u221a" in eq)
            lh_pre.append(EQ_LEADING if has_tall else EQ_FONT_SZ * 1.8)
        baseline_span_pre = sum(lh_pre[:-1]) if len(lh_pre) > 1 else 0
        frac_extra = EQ_FONT_SZ * 0.8 if any(
            ("/" in eq) or ("\u221a" in eq) for eq in equations
        ) else 0
        visual_top_pre = EQ_FONT_SZ * 0.7
        eq_h = EQ_PAD_V * 2 + visual_top_pre + baseline_span_pre + frac_extra

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

        # Measure actual content height: taller leading for lines with
        # fractions/radicals, normal leading for simple lines
        line_heights = []
        for eq in equations:
            # Any equation containing / likely has a stacked fraction
            has_tall = ("/" in eq) or ("\u221a" in eq)
            lh = EQ_LEADING if has_tall else EQ_FONT_SZ * 1.8
            line_heights.append(lh)
        # Baseline-to-baseline span (N-1 gaps for N equations)
        baseline_span = sum(line_heights[:-1]) if len(line_heights) > 1 else 0
        # Extra below last baseline for fraction denominators
        frac_descend = EQ_FONT_SZ * 0.8 if any(
            ("/" in eq) or ("\u221a" in eq) for eq in equations
        ) else 0
        visual_top = EQ_FONT_SZ * 0.7   # cap-height above first baseline
        total_visual = visual_top + baseline_span + frac_descend
        bh = EQ_PAD_V * 2 + total_visual

        # ── Draw equations centered in the text area ──────────────────────
        # First pass: draw invisibly off-page to measure actual rendered widths
        eq_actual_widths = []
        for eq in equations:
            x_before = -10000.0
            x_after = _draw_equation_formatted(
                c, eq, x_before, -10000,
                MATH_FONT, EQ_FONT_SZ,
                color=C_DARK, label_color=C_ACCENT,
            )
            eq_actual_widths.append(x_after - x_before)
        max_eq_w = max(eq_actual_widths)

        # Size box to fit widest equation + padding
        h_pad = 8 * mm                          # horizontal padding each side
        bw = max_eq_w + h_pad * 2 + EQ_ACCENT_W

        # Center box in available text area
        area_w = text_w_mm * PTS
        bx = MARGIN_L + (area_w - bw) / 2
        by = bullet_end_y - eq_gap - bh

        # Light background with rounded corners
        c.setFillColor(HexColor("#f4f5fa"))
        c.roundRect(bx, by, bw, bh, 5, fill=1, stroke=0)

        # Purple accent bar on left edge
        c.setFillColor(C_ACCENT)
        c.roundRect(bx, by, EQ_ACCENT_W, bh, 2, fill=1, stroke=0)

        # Second pass: draw each equation truly centered in the box
        usable_w = bw - EQ_ACCENT_W
        # Vertically center: place content midpoint at box midpoint
        center_y = by + bh / 2
        ey = center_y + total_visual / 2 - visual_top
        for idx_eq, eq in enumerate(equations):
            ew = eq_actual_widths[idx_eq]
            eq_x = bx + EQ_ACCENT_W + (usable_w - ew) / 2
            _draw_equation_formatted(
                c, eq, eq_x, ey,
                MATH_FONT, EQ_FONT_SZ,
                color=C_DARK, label_color=C_ACCENT,
            )
            ey -= line_heights[idx_eq]

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


def _draw_tetris(c, cx: float, cy: float, block: float):
    """
    Draw a small Tetris-style block tower.  cx, cy = bottom-left of the grid.
    block = size of one cell in pts.
    """
    # Tetris color palette
    colors = [
        HexColor("#00b4d8"),  # I - cyan
        HexColor("#e63946"),  # Z - red
        HexColor("#2a9d8f"),  # S - teal
        HexColor("#f4a261"),  # L - orange
        HexColor("#533483"),  # T - purple
        HexColor("#457b9d"),  # J - blue
        HexColor("#e9c46a"),  # O - yellow
    ]
    # Grid layout: each row is a list of (col, color_index)
    # Builds a recognisable "stacked Tetris" look
    rows = [
        [(0, 0), (1, 0), (2, 0), (3, 0), (4, 1), (5, 1), (6, 2), (7, 2)],  # bottom
        [(0, 3), (1, 3), (2, 4), (3, 4), (4, 4), (5, 1), (6, 2), (7, 6)],
        [(1, 3), (2, 5), (3, 4), (5, 6), (6, 6), (7, 6)],
        [(2, 5), (3, 5), (4, 5), (6, 0), (7, 0)],
        [(3, 1), (4, 1), (6, 0), (7, 0)],
        [(3, 1), (4, 2), (5, 2)],
        [(4, 2), (5, 4)],
    ]
    gap = 1.5
    for r, row in enumerate(rows):
        for col, ci in row:
            x = cx + col * (block + gap)
            y = cy + r * (block + gap)
            c.setFillColor(colors[ci])
            c.roundRect(x, y, block, block, block * 0.15, fill=1, stroke=0)
            # Highlight
            c.setFillColor(HexColor("#ffffff40"))
            c.roundRect(x + 1, y + block * 0.55, block - 2, block * 0.35,
                        block * 0.1, fill=1, stroke=0)


def _draw_conclusion(c, slide):
    """Draw conclusion slide with Tetris graphic and takeaway bullets."""
    _draw_accent_bar(c)

    heading = slide.get("heading", "Key Takeaways")
    bullets = slide.get("bullets") or []

    area_top = PAGE_H - MARGIN_T - 4 * mm

    # Heading in accent color
    H_SIZE = 22
    c.setFont("Helvetica-Bold", H_SIZE)
    c.setFillColor(C_ACCENT)
    c.drawString(MARGIN_L, area_top, heading)
    heading_bottom = area_top - H_SIZE * 1.3 - 4 * mm

    # Tetris block in the right area
    tetris_x = PAGE_W - MARGIN_R - 100 * mm
    tetris_y = MARGIN_B + SLIDE_NUM_H + 10 * mm
    _draw_tetris(c, tetris_x, tetris_y, 12)

    # Bullets on the left side
    text_w_mm = (tetris_x - MARGIN_L - 8 * mm) / PTS
    B_SIZE = 16
    max_bc = _max_chars(text_w_mm, B_SIZE)
    bullet_y = heading_bottom
    indent = MARGIN_L + 6 * mm
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
        bullet_y -= B_SIZE * 0.8

    # Inspirational quote at bottom-left
    quote = "\u201cSmall ideas can generate greatness.\u201d"
    c.setFont("Helvetica-BoldOblique", 13)
    c.setFillColor(C_ACCENT)
    c.drawString(MARGIN_L + 6 * mm, MARGIN_B + SLIDE_NUM_H + 6 * mm, quote)


def _draw_thankyou(c, total_slides: int):
    """Draw a stylish 'Thank You' closing slide."""
    # Dark background
    c.setFillColor(C_MID)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

    # Accent bar left
    c.setFillColor(C_ACCENT)
    c.rect(0, 0, 5 * mm, PAGE_H, fill=1, stroke=0)

    # Decorative blocks (Tetris-inspired scattered pieces)
    deco_colors = [
        HexColor("#533483"), HexColor("#0f3460"),
        HexColor("#2a9d8f"), HexColor("#e9c46a"),
        HexColor("#00b4d8"), HexColor("#f4a261"),
    ]
    import random
    rng = random.Random(42)   # deterministic for reproducibility
    for _ in range(25):
        bx = rng.uniform(20, PAGE_W - 20)
        by = rng.uniform(20, PAGE_H - 20)
        bs = rng.uniform(6, 18)
        col = deco_colors[rng.randint(0, len(deco_colors) - 1)]
        c.setFillColor(col)
        c.setFillAlpha(0.12)
        c.roundRect(bx, by, bs, bs, 2, fill=1, stroke=0)
    c.setFillAlpha(1.0)

    # "THANK YOU" in large art text
    cy = PAGE_H / 2 + 20
    # Shadow
    c.setFont("Helvetica-Bold", 54)
    c.setFillColor(HexColor("#000000"))
    c.setFillAlpha(0.15)
    tw = c.stringWidth("THANK YOU", "Helvetica-Bold", 54)
    c.drawString(PAGE_W / 2 - tw / 2 + 2, cy - 2, "THANK YOU")
    c.setFillAlpha(1.0)

    # Main text with gradient-like effect (two overlapping renders)
    c.setFillColor(HexColor("#e9c46a"))
    c.drawString(PAGE_W / 2 - tw / 2, cy, "THANK YOU")

    # Subtitle
    sub = "for your attention"
    c.setFont("Helvetica", 16)
    c.setFillColor(HexColor("#ccccdd"))
    sw = c.stringWidth(sub, "Helvetica", 16)
    c.drawString(PAGE_W / 2 - sw / 2, cy - 40, sub)

    # Bottom decorative line
    c.setStrokeColor(C_ACCENT)
    c.setLineWidth(2)
    line_w = 60 * mm
    c.line(PAGE_W / 2 - line_w / 2, cy - 60, PAGE_W / 2 + line_w / 2, cy - 60)

    # Slide number
    _draw_slide_number(c, total_slides, total_slides)
