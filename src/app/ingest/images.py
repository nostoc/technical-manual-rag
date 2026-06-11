"""
ingest/images.py
Image extraction from PDFs via pdf_oxide.

pdf_oxide's extract_images() returns PdfImage metadata objects (width, height,
bbox, aspect_ratio) but does not expose per-image byte extraction. Pages that
contain qualifying images are rendered at 150 DPI via render_page() and saved
as PNG. One PNG per qualifying page is produced.

Noise filtering (applied to PdfImage metadata before deciding to render):
  - Pages where all images appear on > 30 % of total pages  (logos, watermarks)
  - Images smaller than 100×100 px                          (icons, bullets)
  - Images with extreme aspect ratio                        (banners, dividers)

A page is rendered only when at least one of its images passes all filters.

Returns { page_num: [image_filename] }  (1-indexed, at most one entry per page).
"""

import logging
from pathlib import Path

from pdf_oxide import PdfDocument

from app.utils import IMAGE_DIR

logger = logging.getLogger(__name__)

_MIN_DIMENSION_PX = 100
_MAX_ASPECT_RATIO = 8.0
_MIN_ASPECT_RATIO = 0.125
_REPEAT_PAGE_FRACTION = 0.3
_RENDER_DPI = 150


def extract_images_from_pdf(pdf_path: str) -> dict[int, list[str]]:
    """
    Identify pages with content images and render each qualifying page to PNG.

    Returns { page_num: [rendered_page_filename] }  (1-indexed).
    """
    logger.info("Extracting images from %s", pdf_path)

    stem = Path(pdf_path).stem
    doc = PdfDocument(pdf_path)
    total_pages = doc.page_count()

    # ── First pass: collect PdfImage metadata per page and count appearances
    # A PdfImage's identity is approximated by its (width, height) since there
    # is no xref/hash exposed. This is sufficient for logo/watermark detection.
    all_page_images: list[list] = []
    size_page_counts: dict[tuple[int, int], int] = {}

    for page_index in range(total_pages):
        imgs = doc.extract_images(page_index)
        all_page_images.append(imgs)
        seen: set[tuple[int, int]] = set()
        for img in imgs:
            key = (img.width, img.height)
            if key not in seen:
                size_page_counts[key] = size_page_counts.get(key, 0) + 1
                seen.add(key)

    repeat_threshold = total_pages * _REPEAT_PAGE_FRACTION

    # ── Second pass: render pages that have at least one qualifying image
    page_images_out: dict[int, list[str]] = {}

    for page_index in range(total_pages):
        page_num = page_index + 1
        qualifying = False

        for img in all_page_images[page_index]:
            w, h = img.width, img.height
            key = (w, h)
            aspect = img.aspect_ratio if img.aspect_ratio else (w / h if h else 0)

            if size_page_counts.get(key, 0) > repeat_threshold:
                logger.debug("Skip repeated image %sx%s on page %s", w, h, page_num)
                continue
            if w < _MIN_DIMENSION_PX or h < _MIN_DIMENSION_PX:
                logger.debug("Skip small image %sx%s on page %s", w, h, page_num)
                continue
            if aspect > _MAX_ASPECT_RATIO or (0 < aspect < _MIN_ASPECT_RATIO):
                logger.debug("Skip banner image aspect=%.2f on page %s", aspect, page_num)
                continue

            qualifying = True
            break  # one qualifying image is enough to render the page

        if not qualifying:
            continue

        png_bytes: bytes = doc.render_page(page_index, dpi=_RENDER_DPI, format="png")
        image_name = f"{stem}_page_{page_num}.png"
        image_path = IMAGE_DIR / image_name
        image_path.write_bytes(png_bytes)
        page_images_out[page_num] = [image_name]
        logger.debug("Rendered page %s → %s", page_num, image_name)

    total = sum(len(v) for v in page_images_out.values())
    logger.info("Extracted %s page renders from %s", total, pdf_path)
    return page_images_out