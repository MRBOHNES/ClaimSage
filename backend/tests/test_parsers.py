"""Unit tests for the multi-format parsers.

These run offline (no OpenRouter / Qdrant needed) — they check that each format
is turned into LlamaIndex Documents carrying the right text and metadata, which
is what makes downstream citations possible.

Run: ../backend_venv/bin/pytest tests/test_parsers.py -v
"""
from __future__ import annotations

import fitz  # pymupdf
import pytest
from docx import Document as DocxDocument
from openpyxl import Workbook

from app.services import parsers
from app.services.parsers import (
    UnsupportedFileTypeError,
    parse_file,
)

CLAIM = "test-claim"
DOCID = "test-doc"


def _parse(path, name, ocr_mode="auto"):
    return parse_file(str(path), name, CLAIM, DOCID, ocr_mode=ocr_mode)


def test_txt(tmp_path):
    p = tmp_path / "note.txt"
    p.write_text("Knee surgery is covered after 3 months.")
    docs = _parse(p, "note.txt")
    assert len(docs) == 1
    assert "Knee surgery" in docs[0].text
    assert docs[0].metadata["source_filename"] == "note.txt"
    assert docs[0].metadata["claim_id"] == CLAIM
    assert docs[0].metadata["file_type"] == "txt"


# Long page text (> ocr_min_chars) so "auto" mode deterministically skips OCR
# regardless of whether a tesseract binary is installed on the test machine.
_PAGE_1 = "Page one: general terms and conditions. " * 4
_PAGE_2 = "Page two: cardiac coverage details and waiting periods. " * 4


def test_pdf_pages_carry_page_labels(tmp_path, monkeypatch):
    # OCR must not run for digital pages with a healthy text layer.
    monkeypatch.setattr(
        parsers.ocr, "ocr_page", _fail_if_called("ocr_page should not run")
    )
    p = tmp_path / "policy.pdf"
    doc = fitz.open()
    doc.new_page().insert_text((72, 72), _PAGE_1)
    doc.new_page().insert_text((72, 72), _PAGE_2)
    doc.save(str(p))
    doc.close()

    docs = _parse(p, "policy.pdf")
    assert len(docs) == 2
    assert docs[0].metadata["page_label"] == 1
    assert docs[1].metadata["page_label"] == 2
    assert docs[0].metadata["extraction_method"] == "text"
    assert "cardiac" in docs[1].text.lower()


def test_docx(tmp_path):
    p = tmp_path / "policy.docx"
    d = DocxDocument()
    d.add_paragraph("Maternity benefits apply after 24 months.")
    d.add_paragraph("Dental is excluded unless accidental.")
    d.save(str(p))

    docs = _parse(p, "policy.docx")
    assert len(docs) == 1
    assert "Maternity" in docs[0].text
    assert "Dental" in docs[0].text


def test_xlsx_one_document_per_row(tmp_path):
    p = tmp_path / "schedule.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "Benefits"
    ws.append(["Procedure", "Limit", "WaitingPeriod"])
    ws.append(["Knee Surgery", "300000", "3 months"])
    ws.append(["Cardiac", "500000", "12 months"])
    wb.save(str(p))

    docs = _parse(p, "schedule.xlsx")
    # 2 data rows -> 2 documents (header is used as column names, not a row)
    assert len(docs) == 2
    assert docs[0].metadata["sheet_name"] == "Benefits"
    assert docs[0].metadata["row_number"] == 2  # 1-based + header
    # column context preserved (not a raw CSV dump)
    assert "Procedure: Knee Surgery" in docs[0].text
    assert "WaitingPeriod: 3 months" in docs[0].text


def test_eml_headers_and_body(tmp_path):
    p = tmp_path / "claim.eml"
    p.write_bytes(
        b"From: alice@example.com\r\n"
        b"To: claims@insurer.com\r\n"
        b"Subject: Knee surgery claim\r\n"
        b"\r\n"
        b"Please process my knee surgery claim from last week.\r\n"
    )
    docs = _parse(p, "claim.eml")
    assert len(docs) >= 1
    body = docs[0]
    assert "knee surgery" in body.text.lower()
    assert "alice@example.com" in body.text  # header included
    assert body.metadata["email_field"] == "body"


def test_rejected_legacy_format(tmp_path):
    p = tmp_path / "old.doc"
    p.write_bytes(b"not really a doc")
    with pytest.raises(UnsupportedFileTypeError):
        _parse(p, "old.doc")


def test_unknown_extension(tmp_path):
    p = tmp_path / "data.xyz"
    p.write_bytes(b"whatever")
    with pytest.raises(UnsupportedFileTypeError):
        _parse(p, "data.xyz")


# --- OCR fallback + image uploads --------------------------------------------


def _fail_if_called(msg):
    def _boom(*args, **kwargs):
        raise AssertionError(msg)

    return _boom


def _make_pdf(tmp_path, pages: list[str], name="scan.pdf"):
    """Build a PDF with the given per-page text (empty string = blank page)."""
    p = tmp_path / name
    doc = fitz.open()
    for text in pages:
        page = doc.new_page()
        if text:
            page.insert_text((72, 72), text)
    doc.save(str(p))
    doc.close()
    return p


def test_pdf_sparse_page_triggers_ocr_in_auto(tmp_path, monkeypatch):
    # A blank/sparse page (below the char threshold) should be OCR'd in auto mode.
    monkeypatch.setattr(
        parsers.ocr, "ocr_page", lambda page, dpi, lang: "OCR RECOVERED CONTENT"
    )
    p = _make_pdf(tmp_path, [""])  # no text layer
    docs = _parse(p, "scan.pdf")
    assert len(docs) == 1
    assert docs[0].text == "OCR RECOVERED CONTENT"
    assert docs[0].metadata["extraction_method"] == "ocr"
    assert docs[0].metadata["page_label"] == 1


def test_ocr_mode_always_ocrs_even_with_text(tmp_path, monkeypatch):
    monkeypatch.setattr(
        parsers.ocr,
        "ocr_page",
        lambda page, dpi, lang: "FORCED OCR " * 10,  # longer than native text
    )
    p = _make_pdf(tmp_path, [_PAGE_1])
    docs = _parse(p, "scan.pdf", ocr_mode="always")
    assert docs[0].metadata["extraction_method"] == "ocr"
    assert "FORCED OCR" in docs[0].text


def test_ocr_mode_off_never_ocrs(tmp_path, monkeypatch):
    monkeypatch.setattr(parsers.ocr, "ocr_page", _fail_if_called("OCR ran with mode=off"))
    p = _make_pdf(tmp_path, ["Hi"])  # sparse text, but OCR disabled
    docs = _parse(p, "scan.pdf", ocr_mode="off")
    assert len(docs) == 1
    assert docs[0].text == "Hi"
    assert docs[0].metadata["extraction_method"] == "text"


def test_page_order_preserved_across_mixed_text_and_ocr(tmp_path, monkeypatch):
    # Middle page is blank (OCR'd); the surrounding digital pages keep their text.
    monkeypatch.setattr(
        parsers.ocr, "ocr_page", lambda page, dpi, lang: "OCR PAGE TWO"
    )
    p = _make_pdf(tmp_path, [_PAGE_1, "", _PAGE_2])
    docs = _parse(p, "scan.pdf")
    assert [d.metadata["page_label"] for d in docs] == [1, 2, 3]
    assert [d.metadata["extraction_method"] for d in docs] == ["text", "ocr", "text"]
    assert docs[1].text == "OCR PAGE TWO"


def test_image_upload_is_ocrd(tmp_path, monkeypatch):
    monkeypatch.setattr(
        parsers.ocr, "ocr_image_file", lambda path, lang: "TEXT FROM PHOTO"
    )
    p = tmp_path / "photo.jpg"
    p.write_bytes(b"\xff\xd8\xff")  # bytes irrelevant — OCR is stubbed
    docs = _parse(p, "photo.jpg")
    assert len(docs) == 1
    assert docs[0].text == "TEXT FROM PHOTO"
    assert docs[0].metadata["extraction_method"] == "ocr"
    assert docs[0].metadata["page_label"] == 1
    assert docs[0].metadata["file_type"] == "jpg"


def test_image_upload_with_ocr_off_yields_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(
        parsers.ocr, "ocr_image_file", _fail_if_called("OCR ran with mode=off")
    )
    p = tmp_path / "photo.png"
    p.write_bytes(b"\x89PNG")
    docs = _parse(p, "photo.png", ocr_mode="off")
    assert docs == []
