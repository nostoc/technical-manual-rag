"""
ingest/images.py
Image extraction from PDFs via pdf_oxide.

Uses extract_image_bytes(page) which returns per-embedded-image dicts:
  { 'width': int, 'height': int, 'format': str, 'data': bytes }

The `data` field contains the raw encoded image bytes (PNG/JPEG) ready
to write directly to disk.

Noise filtering:
  - Images appearing on > 30 % of pages  (logos, watermarks) — keyed by (w, h)
  - Images smaller than 100×100 px       (icons, bullets)
  - Images with extreme aspect ratio     (banners, dividers)

Returns { page_num: [image_filename, ...] }  (1-indexed).
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


def extract_images_from_pdf(pdf_path: str) -> dict[int, list[str]]:
    """
    Extract and noise-filter embedded images from *pdf_path* into IMAGE_DIR.

    Returns { page_num: [image_filename, ...] }  (1-indexed).
    """
    logger.info("Extracting images from %s", pdf_path)

    stem = Path(pdf_path).stem
    doc = PdfDocument(pdf_path)
    total_pages = doc.page_count()

    # ── First pass: count (width, height) appearances across pages for repeat filter
    all_page_images: list[list[dict]] = []
    size_page_counts: dict[tuple[int, int], int] = {}

    for page_index in range(total_pages):
        imgs: list[dict] = doc.extract_image_bytes(page_index)
        all_page_images.append(imgs)
        seen: set[tuple[int, int]] = set()
        for img in imgs:
            key = (img["width"], img["height"])
            if key not in seen:
                size_page_counts[key] = size_page_counts.get(key, 0) + 1
                seen.add(key)

    repeat_threshold = total_pages * _REPEAT_PAGE_FRACTION

    # ── Second pass: filter and save
    page_images_out: dict[int, list[str]] = {}

    for page_index in range(total_pages):
        page_num = page_index + 1
        page_images_out[page_num] = []

        for img_index, img in enumerate(all_page_images[page_index]):
            w: int = img["width"]
            h: int = img["height"]
            key = (w, h)
            aspect = w / h if h else 0

            if size_page_counts.get(key, 0) > repeat_threshold:
                logger.debug("Skip repeated image %sx%s on page %s", w, h, page_num)
                continue
            if w < _MIN_DIMENSION_PX or h < _MIN_DIMENSION_PX:
                logger.debug("Skip small image %sx%s on page %s", w, h, page_num)
                continue
            if aspect > _MAX_ASPECT_RATIO or (0 < aspect < _MIN_ASPECT_RATIO):
                logger.debug("Skip banner image aspect=%.2f on page %s", aspect, page_num)
                continue

            ext = img.get("format", "png").lstrip(".")
            image_name = f"{stem}_page_{page_num}_img_{img_index}.{ext}"
            (IMAGE_DIR / image_name).write_bytes(img["data"])
            page_images_out[page_num].append(image_name)
            logger.debug("Saved %s", image_name)

    total = sum(len(v) for v in page_images_out.values())
    logger.info("Extracted %s images from %s", total, pdf_path)
    return page_images_out