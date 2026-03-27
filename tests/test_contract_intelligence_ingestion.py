from __future__ import annotations

import importlib
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

loader = importlib.import_module("apps.contract_intelligence.ingestion.project_loader")

extract_clause_spans = loader.extract_clause_spans
iter_project_documents = loader.iter_project_documents


def test_extract_clause_spans_recognizes_headings() -> None:
    text = "\n".join(
        [
            "Section 7.2 Payment Terms",
            "Subcontractor shall be paid on a pay-if-paid basis.",
            "",
            "Section 9.1 Claims",
            "Notice of claim must be provided within 7 calendar days.",
        ]
    )

    clauses = extract_clause_spans("Prime Contract Agreement.md", text)

    assert len(clauses) == 2
    assert clauses[0].heading == "Section 7.2 Payment Terms"
    assert "pay-if-paid" in clauses[0].text
    assert clauses[1].location.endswith(":L4")


def test_iter_project_documents_extracts_docx_and_pdf_text(tmp_path: Path) -> None:
    project_dir = tmp_path / "ingestion-fixtures"
    project_dir.mkdir()

    docx_path = project_dir / "Insurance Requirements.docx"
    with zipfile.ZipFile(docx_path, "w") as archive:
        archive.writestr(
            "word/document.xml",
            """
            <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
              <w:body>
                <w:p><w:r><w:t>Section 1 Insurance</w:t></w:r></w:p>
                <w:p><w:r><w:t>Additional insured status is required.</w:t></w:r></w:p>
              </w:body>
            </w:document>
            """.strip(),
        )

    pdf_path = project_dir / "Funding Memo.pdf"
    pdf_path.write_bytes(
        b"%PDF-1.4\n"
        b"1 0 obj << /Length 128 >> stream\n"
        b"BT /F1 12 Tf 72 720 Td (Section 2 Federal Funding) Tj T* "
        b"(Davis-Bacon prevailing wage applies.) Tj ET\n"
        b"endstream\nendobj\n"
    )

    documents = iter_project_documents(project_dir)
    by_name = {item.relative_path: item for item in documents}

    assert by_name["Insurance Requirements.docx"].text_available is True
    assert by_name["Insurance Requirements.docx"].text_source == "docx_xml"
    assert by_name["Insurance Requirements.docx"].text_quality in {"medium", "high"}
    assert len(by_name["Insurance Requirements.docx"].clauses) >= 1

    assert by_name["Funding Memo.pdf"].text_available is True
    assert by_name["Funding Memo.pdf"].text_source in {"pdf_stream", "pdf_spotlight"}
    assert by_name["Funding Memo.pdf"].text_quality in {"medium", "high"}
    assert "Davis-Bacon" in by_name["Funding Memo.pdf"].text


def test_iter_project_documents_ignores_internal_contract_intelligence_store(tmp_path: Path) -> None:
    project_dir = tmp_path / "ingestion-ignore-fixtures"
    project_dir.mkdir()
    (project_dir / "Prime Contract Agreement.md").write_text("Section 1 Scope", encoding="utf-8")

    internal_store = project_dir / ".contract_intelligence" / "sample-project" / "runs"
    internal_store.mkdir(parents=True)
    (internal_store / "run_001.json").write_text('{"ignored": true}', encoding="utf-8")

    documents = iter_project_documents(project_dir)

    assert [item.relative_path for item in documents] == ["Prime Contract Agreement.md"]


def test_iter_project_documents_uses_content_aware_classification_and_binary_guards(tmp_path: Path) -> None:
    project_dir = tmp_path / "ingestion-guards"
    project_dir.mkdir()
    (project_dir / "Attachment A.txt").write_text(
        "General Conditions AIA A201\nNotice of claim must be provided within 7 calendar days.",
        encoding="utf-8",
    )
    (project_dir / "archive.bin").write_bytes(b"\x00" * 256)

    documents = iter_project_documents(project_dir)
    by_name = {item.relative_path: item for item in documents}

    assert by_name["Attachment A.txt"].document_type.value == "general_conditions"
    assert "archive.bin" not in by_name


def test_iter_project_documents_marks_low_quality_pdf_text_unavailable(tmp_path: Path) -> None:
    project_dir = tmp_path / "ingestion-low-quality-pdf"
    project_dir.mkdir()
    pdf_path = project_dir / "Scanned Funding Memo.pdf"
    pdf_path.write_bytes(
        b"%PDF-1.4\n"
        b"1 0 obj << /Length 48 >> stream\n"
        b"BT /F1 12 Tf 72 720 Td (() ) Tj ET\n"
        b"endstream\nendobj\n"
    )

    documents = iter_project_documents(project_dir)
    document = documents[0]

    assert document.relative_path == "Scanned Funding Memo.pdf"
    assert document.text_available is False
    assert document.text_quality in {"none", "low"}
