import os
from pathlib import Path

os.environ.setdefault("OMP_THREAD_LIMIT", "2")

import pytesseract
from pdf2image import convert_from_path

OCR_MAX_PAGES = int(os.environ.get("OCR_MAX_PAGES", "15"))
OCR_LANG = os.environ.get("OCR_LANG", "por")


def ocr_pdf(file_path: Path) -> str:
    images = convert_from_path(str(file_path), first_page=1, last_page=OCR_MAX_PAGES)
    texts = []
    for img in images:
        texts.append(pytesseract.image_to_string(img, lang=OCR_LANG))
    return "\n\n".join(texts).strip()
