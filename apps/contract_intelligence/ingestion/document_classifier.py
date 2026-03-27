from __future__ import annotations

import re

from apps.contract_intelligence.domain.enums import DocumentType


REQUIRED_BID_REVIEW_DOCUMENTS: tuple[DocumentType, ...] = (
    DocumentType.PRIME_CONTRACT,
    DocumentType.GENERAL_CONDITIONS,
    DocumentType.INSURANCE_REQUIREMENTS,
)


KEYWORD_HINTS: tuple[tuple[DocumentType, tuple[str, ...]], ...] = (
    (DocumentType.CHANGE_ORDER, ("change order", "cco")),
    (DocumentType.AMENDMENT, ("amendment", "amended", "restated")),
    (DocumentType.BOARD_RECORD, ("resolution", "agenda", "council", "board", "legistar", "minutes")),
    (DocumentType.BUDGET_DOCUMENT, ("budget", "capital improvement plan", "cip", "financial plan")),
    (DocumentType.AUDIT_REPORT, ("audit", "auditor", "inspector general")),
    (DocumentType.PROJECT_STATUS, ("status", "dashboard", "progress report", "construction map", "closeout")),
    (
        DocumentType.ENVIRONMENTAL_DOCUMENT,
        ("ceqa", "environmental", "eir", "negative declaration", "swppp"),
    ),
    (DocumentType.LITIGATION_RECORD, ("complaint", "lawsuit", "litigation", "settlement", "release")),
    (DocumentType.INSURANCE_REQUIREMENTS, ("insurance", "coverage", "endorsement")),
    (DocumentType.GENERAL_CONDITIONS, ("general conditions", "aia a201", "gc")),
    (DocumentType.SPECIAL_PROVISIONS, ("special provisions", "supplementary conditions")),
    (DocumentType.ADDENDUM, ("addendum", "addenda")),
    (DocumentType.FUNDING_DOCUMENT, ("funding", "grant", "federal aid", "state aid")),
    (DocumentType.PROCUREMENT_DOCUMENT, ("rfp", "rfq", "ifb", "bid package", "procurement", "procedures")),
    (DocumentType.PRIME_CONTRACT, ("prime contract", "agreement", "owner contract", "contract")),
)


def _normalized_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").lower().replace("_", " ").replace("-", " ")).strip()


def classify_document(filename: str, *, text: str | None = None) -> DocumentType:
    normalized_name = _normalized_text(filename)
    normalized_text = _normalized_text(text)[:12000]
    scores: dict[DocumentType, int] = {document_type: 0 for document_type, _ in KEYWORD_HINTS}

    for document_type, keywords in KEYWORD_HINTS:
        for keyword in keywords:
            if keyword in normalized_name:
                scores[document_type] += 5
            if keyword in normalized_text:
                scores[document_type] += 2

    contract_language = (
        "pay if paid",
        "no damages for delay",
        "termination for convenience",
        "notice of claim",
        "subcontractor shall",
    )
    insurance_language = (
        "additional insured",
        "primary and noncontributory",
        "waiver of subrogation",
        "certificate of insurance",
    )
    procurement_language = ("rfq", "rfp", "ifb", "qualifications-based selection", "procurement process")
    funding_language = ("davis-bacon", "federal aid", "state aid", "grant reimbursement", "appropriation")

    if "agreement" in normalized_name and any(term in normalized_text for term in contract_language):
        scores[DocumentType.PRIME_CONTRACT] += 4
    if "general conditions" in normalized_text or "aia a201" in normalized_text:
        scores[DocumentType.GENERAL_CONDITIONS] += 4
    if "insurance" in normalized_name and any(term in normalized_text for term in insurance_language):
        scores[DocumentType.INSURANCE_REQUIREMENTS] += 4
    if any(term in normalized_text for term in procurement_language):
        scores[DocumentType.PROCUREMENT_DOCUMENT] += 3
    if any(term in normalized_text for term in funding_language):
        scores[DocumentType.FUNDING_DOCUMENT] += 3
    if "board" in normalized_name and "resolution" in normalized_text:
        scores[DocumentType.BOARD_RECORD] += 4
    if "budget" in normalized_name and ("capital" in normalized_text or "financial plan" in normalized_text):
        scores[DocumentType.BUDGET_DOCUMENT] += 4
    if "status" in normalized_name and ("percent complete" in normalized_text or "estimated completion" in normalized_text):
        scores[DocumentType.PROJECT_STATUS] += 4

    best_type = DocumentType.OTHER
    best_score = 0
    for document_type, score in scores.items():
        if score > best_score:
            best_type = document_type
            best_score = score
    return best_type if best_score > 0 else DocumentType.OTHER


def missing_required_documents(document_types: list[DocumentType | str]) -> list[DocumentType]:
    seen = {DocumentType(item) if isinstance(item, str) else item for item in document_types}
    return [item for item in REQUIRED_BID_REVIEW_DOCUMENTS if item not in seen]
