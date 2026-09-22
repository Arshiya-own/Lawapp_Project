"""Text extraction from uploaded case PDFs (03_backend_spec.md § 7).

Two-stage: the embedded text layer via pypdf first, rasterise-and-OCR via pytesseract
only if that yields too little. Both sample PDFs are ReportLab documents with a real
text layer (~6.5K chars over 4 pages), so the fast path handles them and the fallback
exists for scanned substitutes.

Ordering the stages this way also matters operationally: rasterising four pages at
200 DPI is the memory-hungry step, and the deployment target is a 512 MB instance.
"""

import io
import time
from dataclasses import dataclass

from pypdf import PdfReader

from config import OCR_MIN_CHARS, PAGE_MARKER
from middleware import log_event


@dataclass
class OcrResult:
    text: str
    pages_processed: int
    method: str  # "text_layer" or "tesseract"


def _join_pages(pages: list[str]) -> str:
    """Prefix each page with its marker, per § 7 step 3."""
    return "".join(PAGE_MARKER.format(n=i) + page for i, page in enumerate(pages, 1))


def _extract_text_layer(data: bytes) -> tuple[str, int]:
    """Parse failures return no text rather than raising.

    A structurally broken PDF is an OCR failure (422 `ocr_failed`), not a server
    fault. Letting `PdfStreamError` escape would surface it as a 500 and contradict
    § 4, which lists "corrupted" under the 422 case.
    """
    try:
        reader = PdfReader(io.BytesIO(data))
        pages = [(page.extract_text() or "") for page in reader.pages]
    except Exception as exc:
        log_event(event="pdf_parse_failed", error=repr(exc))
        return "", 0
    return _join_pages(pages), len(pages)


def _extract_with_tesseract(data: bytes) -> tuple[str, int]:
    """Rasterise and OCR. Requires the poppler and tesseract binaries."""
    import pytesseract
    from pdf2image import convert_from_bytes

    images = convert_from_bytes(data, dpi=200)
    pages = [pytesseract.image_to_string(image) for image in images]
    return _join_pages(pages), len(pages)


def extract_text(data: bytes) -> OcrResult:
    """Return extracted text, or an ``OcrResult`` whose text is below threshold.

    Deciding what counts as a failure is left to the caller so the HTTP concern (422
    `ocr_failed`) stays in the router.
    """
    started = time.perf_counter()

    text, pages = _extract_text_layer(data)
    method = "text_layer"

    if len(text.strip()) < OCR_MIN_CHARS:
        try:
            ocr_text, ocr_pages = _extract_with_tesseract(data)
            if len(ocr_text.strip()) > len(text.strip()):
                text, pages, method = ocr_text, ocr_pages, "tesseract"
        except Exception as exc:
            # Missing poppler/tesseract binaries, or an unrasterisable file. Neither
            # is a server fault: the caller still sees "too little text" and returns
            # 422, which is the same outcome the spec wants for an illegible scan.
            log_event(event="ocr_fallback_unavailable", error=repr(exc))

    duration_ms = round((time.perf_counter() - started) * 1000, 2)
    log_event(event="ocr", duration_ms=duration_ms, pages_processed=pages, method=method)
    return OcrResult(text=text, pages_processed=pages, method=method)


def is_failure(result: OcrResult) -> bool:
    """§ 7 step 4: under 200 characters is an OCR failure."""
    return len(result.text.strip()) < OCR_MIN_CHARS
