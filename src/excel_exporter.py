"""Utility for exporting anonymized document text to an Excel file."""

from __future__ import annotations

import fitz  # PyMuPDF
import openpyxl
import io


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract all text from a PDF file.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        Concatenated text content of all pages.
    """
    doc = fitz.open(pdf_path)
    pages_text = [page.get_text() for page in doc]
    doc.close()
    return "\n".join(pages_text)


def export_to_excel(
    results: list[dict],
    output_path: str | io.BytesIO,
) -> None:
    """Write anonymized document results to an Excel (.xlsx) file.

    Each row represents one document with columns:
    - **Dokument** (column A): the document/file name
    - **Text** (column B): the full anonymized text content as a single cell

    Args:
        results: List of dicts with keys ``"document"`` (str) and
            ``"text"`` (str).  The ``"text"`` value is written verbatim;
            callers are responsible for extracting text from the anonymized
            PDF beforehand (e.g. via :func:`extract_text_from_pdf`).
        output_path: Destination ``.xlsx`` file path or a writable
            :class:`io.BytesIO` buffer.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Anonymisierte Texte"

    # Header row
    ws.append(["Dokument", "Text"])

    for entry in results:
        document = entry.get("document", "")
        text = entry.get("text", "")
        ws.append([document, text])

    wb.save(output_path)
