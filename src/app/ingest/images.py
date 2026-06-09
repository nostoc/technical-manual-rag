"""
ingest/images.py
Image extraction from PDFs via pdf_oxide.

Noise filtering (identical to the previous PyMuPDF implementation):
  - Images appearing on > 30 % of pages  (logos, watermarks)
  - Images smaller than 100×100 px       (icons, bullets)
  - Images with extreme aspect ratio     (banners, dividers)
"""

import logging
from pathlib import Path

from pdf_oxide import PdfDocument

from app.utils import IMAGE_DIR

logger = logging.getLogger(__name__)

# Thresholds
_MIN_DIMENSION_PX = 100
_MAX_ASPECT_RATIO = 8.0
_MIN_ASPECT_RATIO = 0.125
_REPEAT_PAGE_FRACTION = 0.3


def extract_images_from_pdf(pdf_path: str) -> dict[int, list[str]]:
    """
    Extract content images from *pdf_path* into IMAGE_DIR via pdf_oxide.

    Filters out:
      - Images appearing on > 30 % of pages  (logos, watermarks)
      - Images smaller than 100×100 px       (icons, bullets)
      - Images with extreme aspect ratio     (banners, dividers)

    Returns { page_num: [image_filename, ...] }  (1-indexed).
    """
    logger.info("Extracting images from %s", pdf_path)

    stem = Path(pdf_path).stem
    doc = PdfDocument(pdf_path)
    total_pages = doc.page_count()

    # ── First pass: count how many pages each unique image (by hash) appears on
    image_page_counts: dict[bytes, int] = {}
    all_page_image_data: list[list[dict]] = []

    for page_index in range(total_pages):
        page_images = doc.extract_images(page_index)
        all_page_image_data.append(page_images)
        seen_on_page: set[bytes] = set()
        for img in page_images:
            key = _image_key(img)
            if key not in seen_on_page:
                image_page_counts[key] = image_page_counts.get(key, 0) + 1
                seen_on_page.add(key)

    repeat_threshold = total_pages * _REPEAT_PAGE_FRACTION

    # ── Second pass: filter and save
    page_images_out: dict[int, list[str]] = {}

    for page_index in range(total_pages):
        page_num = page_index + 1
        page_images_out[page_num] = []

        for img_index, img in enumerate(all_page_image_data[page_index]):
            key = _image_key(img)
            width: int = img.get("width", 0)
            height: int = img.get("height", 0)
            aspect = width / height if height else 0

            if image_page_counts.get(key, 0) > repeat_threshold:
                logger.debug("Skip repeated image on page %s img %s", page_num, img_index)
                continue
            if width < _MIN_DIMENSION_PX or height < _MIN_DIMENSION_PX:
                logger.debug("Skip small image %sx%s on page %s", width, height, page_num)
                continue
            if aspect > _MAX_ASPECT_RATIO or (aspect > 0 and aspect < _MIN_ASPECT_RATIO):
                logger.debug("Skip banner image aspect=%.2f on page %s", aspect, page_num)
                continue

            raw_bytes = _get_image_bytes(img)
            if not raw_bytes:
                logger.debug("Skip image with no extractable bytes on page %s", page_num)
                continue

            image_name = f"{stem}_page_{page_num}_img_{img_index}.png"
            image_path = IMAGE_DIR / image_name
            image_path.write_bytes(raw_bytes)

            page_images_out[page_num].append(image_name)

    total = sum(len(v) for v in page_images_out.values())
    logger.info("Extracted %s content images from %s", total, pdf_path)
    return page_images_out


def _get_image_bytes(img: dict) -> bytes | None:
    """
    Extract raw image bytes from a pdf_oxide image dict.
    Tries known key names in order of likelihood.
    """
    for key in ("data", "bytes", "image_data", "raw"):
        value = img.get(key)
        if isinstance(value, (bytes, bytearray)) and value:
            return bytes(value)
    return None


def _image_key(img: dict) -> bytes:
    """
    Stable identity key for deduplication across pages.
    Uses raw bytes when available, falls back to (width, height).
    """
    raw = _get_image_bytes(img)
    if raw:
        return raw
    return f"{img.get('width')}x{img.get('height')}".encode()