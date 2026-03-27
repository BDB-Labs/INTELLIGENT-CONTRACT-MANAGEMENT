from __future__ import annotations

from enum import Enum


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Recommendation(str, Enum):
    GO = "go"
    GO_WITH_CONDITIONS = "go_with_conditions"
    NO_GO = "no_go"


class DocumentType(str, Enum):
    PRIME_CONTRACT = "prime_contract"
    GENERAL_CONDITIONS = "general_conditions"
    SPECIAL_PROVISIONS = "special_provisions"
    INSURANCE_REQUIREMENTS = "insurance_requirements"
    ADDENDUM = "addendum"
    AMENDMENT = "amendment"
    CHANGE_ORDER = "change_order"
    BOARD_RECORD = "board_record"
    BUDGET_DOCUMENT = "budget_document"
    PROJECT_STATUS = "project_status"
    AUDIT_REPORT = "audit_report"
    ENVIRONMENTAL_DOCUMENT = "environmental_document"
    LITIGATION_RECORD = "litigation_record"
    FUNDING_DOCUMENT = "funding_document"
    PROCUREMENT_DOCUMENT = "procurement_document"
    OTHER = "other"
