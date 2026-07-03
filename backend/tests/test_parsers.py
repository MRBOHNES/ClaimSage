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

from app.services.parsers import (
    UnsupportedFileTypeError,
    parse_file,
)

CLAIM = "test-claim"
DOCID = "test-doc"


def _parse(path, name):
    return parse_file(str(path), name, CLAIM, DOCID)


def test_txt(tmp_path):
    p = tmp_path / "note.txt"
    p.write_text("Knee surgery is covered after 3 months.")
    docs = _parse(p, "note.txt")
    assert len(docs) == 1
    assert "Knee surgery" in docs[0].text
    assert docs[0].metadata["source_filename"] == "note.txt"
    assert docs[0].metadata["claim_id"] == CLAIM
    assert docs[0].metadata["file_type"] == "txt"


def test_pdf_pages_carry_page_labels(tmp_path):
    p = tmp_path / "policy.pdf"
    doc = fitz.open()
    doc.new_page().insert_text((72, 72), "Page one: general terms.")
    doc.new_page().insert_text((72, 72), "Page two: cardiac coverage.")
    doc.save(str(p))
    doc.close()

    docs = _parse(p, "policy.pdf")
    assert len(docs) == 2
    assert docs[0].metadata["page_label"] == 1
    assert docs[1].metadata["page_label"] == 2
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
    p = tmp_path / "image.png"
    p.write_bytes(b"\x89PNG")
    with pytest.raises(UnsupportedFileTypeError):
        _parse(p, "image.png")
