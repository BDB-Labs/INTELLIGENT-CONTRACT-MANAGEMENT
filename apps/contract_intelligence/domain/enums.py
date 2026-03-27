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


class TextQuality(str, Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ObligationType(str, Enum):
    NOTICE_DEADLINE = "notice_deadline"
    RECURRING_REPORTING = "recurring_reporting"
    PRE_START_REQUIREMENT = "pre_start_requirement"


class OwnerRole(str, Enum):
    PROJECT_MANAGER = "project_manager"
    PAYROLL_COMPLIANCE_MANAGER = "payroll_compliance_manager"
    RISK_MANAGER = "risk_manager"
    PROJECT_CONTROLS_MANAGER = "project_controls_manager"


class ObligationStatus(str, Enum):
    PENDING = "pending"
    DUE = "due"
    LATE = "late"
    SATISFIED = "satisfied"


class AlertType(str, Enum):
    DUE = "due"
    LATE = "late"


class AlertStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"


class OutcomeStatus(str, Enum):
    TERMINATION_TAKEOVER = "termination_takeover"
    BANKRUPTCY_RESTRUCTURING = "bankruptcy_restructuring"
    SCOPE_RESCOPE = "scope_rescope"
    DISPUTE_OR_CHANGE_DOCUMENTED = "dispute_or_change_documented"
    COMPLETION_DOCUMENTED = "completion_documented"
    ACTIVE_DELIVERY_DOCUMENTED = "active_delivery_documented"
    AWARD_DOCUMENTED = "award_documented"
    UNKNOWN_PUBLICLY_DOCUMENTED = "unknown_publicly_documented"


class ReportMode(str, Enum):
    INTERNAL = "internal"
    EXTERNAL = "external"


class ReviewTargetKind(str, Enum):
    FINDING = "finding"
    OBLIGATION = "obligation"


class ReviewActionEventType(str, Enum):
    UPSERT = "upsert"
    CLEAR = "clear"


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
