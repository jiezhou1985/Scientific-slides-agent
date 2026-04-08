import fitz  # pymupdf
import os
import tempfile


def parse_pdf(pdf_path: str) -> dict:
    """
    Extract text and figures from a scientific PDF.

    Returns:
        {
            "text": full paper text,
            "figures": [{"filename": "fig1.png", "caption": "..."}],
            "figures_dir": path to temp directory containing PNG files
        }
    """
    doc = fitz.open(pdf_path)
    figures_dir = tempfile.mkdtemp(prefix="slides_figures_")

    full_text_parts = []
    figures = []
    fig_index = 1

    for page_num, page in enumerate(doc):
        full_text_parts.append(page.get_text())

        image_list = page.get_images(full=True)
        for img_info in image_list:
            xref = img_info[0]

            # Skip tiny images (likely decorative or icons)
            pix = fitz.Pixmap(doc, xref)
            if pix.width < 100 or pix.height < 100:
                pix = None
                continue

            # Convert CMYK/other colorspaces to RGB
            if pix.n > 4:
                pix = fitz.Pixmap(fitz.csRGB, pix)

            filename = f"fig{fig_index}.png"
            filepath = os.path.join(figures_dir, filename)
            pix.save(filepath)
            pix = None

            # Find caption: look for text starting with "Fig" or "Figure"
            # in the blocks on this page, closest below any image rect
            caption = _find_caption(page, fig_index)

            figures.append({"filename": filename, "caption": caption})
            fig_index += 1

    doc.close()

    return {
        "text": "\n".join(full_text_parts),
        "figures": figures,
        "figures_dir": figures_dir,
    }


def _find_caption(page: fitz.Page, fig_index: int) -> str:
    """Heuristically find a figure caption on the page."""
    blocks = page.get_text("blocks")  # (x0, y0, x1, y1, text, block_no, block_type)
    for block in blocks:
        text = block[4].strip()
        lower = text.lower()
        if lower.startswith("fig") or lower.startswith("figure"):
            # Return first 300 chars to keep it concise
            return text[:300]
    return f"Figure {fig_index}"
