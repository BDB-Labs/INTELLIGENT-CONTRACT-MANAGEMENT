from __future__ import annotations

import hashlib
import re
import zlib
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree

from apps.contract_intelligence.domain.enums import DocumentType
from apps.contract_intelligence.ingestion.document_classifier import classify_document


PLAIN_TEXT_SUFFIXES = {
    ".txt",
    ".md",
    ".markdown",
    ".json",
    ".yaml",
    ".yml",
    ".csv",
    ".rst",
}

IGNORED_PATH_PARTS = {
    ".git",
    ".contract_intelligence",
    ".venv",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "artifacts",
    "dist",
    "node_modules",
}


@dataclass(frozen=True)
class LoadedDocument:
    document_id: str
    relative_path: str
    document_type: DocumentType
    text: str
    text_available: bool
    text_source: str
    clauses: tuple["ClauseSpan", ...]


@dataclass(frozen=True)
class ClauseSpan:
    clause_id: str
    heading: str
    location: str
    text: str


def _document_id(relative_path: str) -> str:
    digest = hashlib.sha1(relative_path.encode("utf-8")).hexdigest()[:10]
    return f"doc_{digest}"


def _extract_docx_text(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        raw_xml = archive.read("word/document.xml")
    root = ElementTree.fromstring(raw_xml)
    paragraphs: list[str] = []
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    for paragraph in root.findall(".//w:p", namespace):
        text_parts = [node.text for node in paragraph.findall(".//w:t", namespace) if node.text]
        line = "".join(text_parts).strip()
        if line:
            paragraphs.append(line)
    return "\n".join(paragraphs).strip()


def _decode_pdf_literal_string(raw: str) -> str:
    raw = raw.replace(r"\(", "(").replace(r"\)", ")").replace(r"\\", "\\")
    return re.sub(r"\s+", " ", raw).strip()


def _extract_pdf_text(path: Path) -> str:
    pdf_bytes = path.read_bytes()
    fragments: list[str] = []
    for match in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", pdf_bytes, flags=re.DOTALL):
        stream = match.group(1)
        candidates = [stream]
        for wbits in (zlib.MAX_WBITS, -zlib.MAX_WBITS):
            try:
                candidates.append(zlib.decompress(stream, wbits))
            except zlib.error:
                continue
        for candidate in candidates:
            decoded = candidate.decode("latin1", errors="ignore")
            for text_match in re.finditer(r"\((?:\\.|[^\\()])*\)", decoded):
                text = _decode_pdf_literal_string(text_match.group(0)[1:-1])
                if text:
                    fragments.append(text)
    return "\n".join(fragments).strip()


def _clause_id(relative_path: str, location: str, heading: str) -> str:
    digest = hashlib.sha1(f"{relative_path}:{location}:{heading}".encode("utf-8")).hexdigest()[:10]
    return f"clause_{digest}"


def _is_clause_heading(line: str) -> bool:
    checks = (
        r"^(section|article)\s+\d+([.\-]\d+)*[:.)]?\s+.+$",
        r"^\d+([.\-]\d+){0,4}[A-Za-z]?[:.)]?\s+.+$",
        r"^[A-Z][A-Z0-9\s/&,\-]{4,80}$",
    )
    return any(re.match(pattern, line, flags=re.IGNORECASE) for pattern in checks)


def _paragraph_clauses(relative_path: str, text: str) -> tuple[ClauseSpan, ...]:
    clauses: list[ClauseSpan] = []
    for index, block in enumerate(re.split(r"\n\s*\n", text), start=1):
        clean = "\n".join(line.strip() for line in block.splitlines() if line.strip()).strip()
        if not clean:
            continue
        heading = clean.splitlines()[0][:80] if "\n" in clean else f"Paragraph {index}"
        location = f"{relative_path}:paragraph_{index}"
        clauses.append(
            ClauseSpan(
                clause_id=_clause_id(relative_path, location, heading),
                heading=heading,
                location=location,
                text=clean,
            )
        )
    return tuple(clauses)


def extract_clause_spans(relative_path: str, text: str) -> tuple[ClauseSpan, ...]:
    lines = [(line_no, line.strip()) for line_no, line in enumerate(text.splitlines(), start=1) if line.strip()]
    clauses: list[ClauseSpan] = []
    current_heading: str | None = None
    current_location: str | None = None
    current_lines: list[str] = []

    for line_no, line in lines:
        if _is_clause_heading(line):
            if current_heading and current_lines:
                clauses.append(
                    ClauseSpan(
                        clause_id=_clause_id(relative_path, current_location or f"{relative_path}:L{line_no}", current_heading),
                        heading=current_heading,
                        location=current_location or f"{relative_path}:L{line_no}",
                        text="\n".join(current_lines).strip(),
                    )
                )
            current_heading = line
            current_location = f"{relative_path}:L{line_no}"
            current_lines = [line]
        else:
            current_lines.append(line)

    if current_heading and current_lines:
        clauses.append(
            ClauseSpan(
                clause_id=_clause_id(relative_path, current_location or f"{relative_path}:L1", current_heading),
                heading=current_heading,
                location=current_location or f"{relative_path}:L1",
                text="\n".join(current_lines).strip(),
            )
        )

    if clauses:
        return tuple(clauses)
    return _paragraph_clauses(relative_path, text)


def _load_text(path: Path) -> tuple[str, str]:
    suffix = path.suffix.lower()
    if suffix in PLAIN_TEXT_SUFFIXES:
        return path.read_text(encoding="utf-8", errors="ignore").strip(), "plain_text"
    if suffix == ".docx":
        try:
            return _extract_docx_text(path), "docx_xml"
        except (KeyError, ValueError, zipfile.BadZipFile, ElementTree.ParseError):
            return "", "unavailable"
    if suffix == ".pdf":
        return _extract_pdf_text(path), "pdf_stream"
    return "", "unavailable"


def iter_project_documents(project_dir: Path) -> list[LoadedDocument]:
    documents: list[LoadedDocument] = []
    for path in sorted(project_dir.rglob("*")):
        if not path.is_file():
            continue
        relative_path = path.relative_to(project_dir).as_posix()
        if any(part in IGNORED_PATH_PARTS for part in path.relative_to(project_dir).parts):
            continue
        text, text_source = _load_text(path)
        clauses = extract_clause_spans(relative_path, text) if text else ()
        documents.append(
            LoadedDocument(
                document_id=_document_id(relative_path),
                relative_path=relative_path,
                document_type=classify_document(path.name),
                text=text,
                text_available=bool(text),
                text_source=text_source if text else "unavailable",
                clauses=clauses,
            )
        )
    return documents
