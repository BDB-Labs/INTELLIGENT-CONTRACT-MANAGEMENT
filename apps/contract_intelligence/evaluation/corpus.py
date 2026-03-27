from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from apps.contract_intelligence.orchestration.bid_review_runner import run_bid_review


@dataclass(frozen=True)
class CorpusEvaluationResult:
    case_id: str
    passed: bool
    failures: tuple[str, ...]
    artifacts_dir: Path


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _artifact_payloads(artifacts_dir: Path) -> dict[str, Any]:
    return {
        "decision_summary": _read_json(artifacts_dir / "decision_summary.json"),
        "document_inventory": _read_json(artifacts_dir / "document_inventory.json"),
        "risk_findings": _read_json(artifacts_dir / "risk_findings.json"),
        "insurance_findings": _read_json(artifacts_dir / "insurance_findings.json"),
        "compliance_findings": _read_json(artifacts_dir / "compliance_findings.json"),
        "context_profile": _read_json(artifacts_dir / "context_profile.json"),
        "procurement_profile": _read_json(artifacts_dir / "procurement_profile.json"),
        "outcome_evidence": _read_json(artifacts_dir / "outcome_evidence.json"),
        "obligations_register": _read_json(artifacts_dir / "obligations_register.json"),
        "review_challenges": _read_json(artifacts_dir / "review_challenges.json"),
    }


def _assert_contains(actual: set[str], expected: list[str], label: str, failures: list[str]) -> None:
    missing = [item for item in expected if item not in actual]
    if missing:
        failures.append(f"{label} missing expected items: {', '.join(missing)}")


def evaluate_corpus_case(case_dir: str | Path, artifacts_root: str | Path | None = None) -> CorpusEvaluationResult:
    case_path = Path(case_dir).expanduser().resolve()
    expected = _read_json(case_path / "expected.json")
    inputs_dir = case_path / "inputs"
    run_artifacts_root = Path(artifacts_root).expanduser().resolve() if artifacts_root else default_artifacts_root()
    artifacts_dir = run_artifacts_root / case_path.name
    workspace_dir = run_artifacts_root / "_workspace" / case_path.name

    if workspace_dir.exists():
        shutil.rmtree(workspace_dir)
    workspace_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(inputs_dir, workspace_dir)

    result = run_bid_review(project_dir=workspace_dir, artifacts_dir=artifacts_dir)
    payloads = _artifact_payloads(result.artifacts_dir)

    failures: list[str] = []
    decision = payloads["decision_summary"]
    inventory = payloads["document_inventory"]
    risk_categories = {item["category"] for item in payloads["risk_findings"]}
    insurance_categories = {item["category"] for item in payloads["insurance_findings"]}
    compliance_categories = {item["category"] for item in payloads["compliance_findings"]}
    obligation_titles = {item["title"] for item in payloads["obligations_register"]}
    challenge_hazards = payloads["review_challenges"]["missed_hazards"]
    context_profile = payloads["context_profile"]
    procurement_profile = payloads["procurement_profile"]
    outcome_evidence = payloads["outcome_evidence"]

    if decision["recommendation"] != expected["recommendation"]:
        failures.append(
            f"recommendation mismatch: expected {expected['recommendation']}, got {decision['recommendation']}"
        )
    if decision["human_review_required"] is not expected["human_review_required"]:
        failures.append(
            "human_review_required mismatch: "
            f"expected {expected['human_review_required']}, got {decision['human_review_required']}"
        )
    if inventory["missing_required_documents"] != expected["missing_required_documents"]:
        failures.append(
            "missing_required_documents mismatch: "
            f"expected {expected['missing_required_documents']}, got {inventory['missing_required_documents']}"
        )

    _assert_contains(risk_categories, expected.get("risk_categories", []), "risk_categories", failures)
    _assert_contains(insurance_categories, expected.get("insurance_categories", []), "insurance_categories", failures)
    _assert_contains(compliance_categories, expected.get("compliance_categories", []), "compliance_categories", failures)
    _assert_contains(obligation_titles, expected.get("obligation_titles", []), "obligation_titles", failures)

    expected_hazard_fragments = expected.get("hazard_fragments", [])
    for fragment in expected_hazard_fragments:
        if not any(fragment in item for item in challenge_hazards):
            failures.append(f"review_challenges missing hazard fragment: {fragment}")

    expected_context = expected.get("context_profile", {})
    for key, value in expected_context.items():
        if context_profile.get(key) != value:
            failures.append(f"context_profile mismatch for {key}: expected {value}, got {context_profile.get(key)}")

    expected_procurement = expected.get("procurement_profile", {})
    for key, value in expected_procurement.items():
        if procurement_profile.get(key) != value:
            failures.append(
                f"procurement_profile mismatch for {key}: expected {value}, got {procurement_profile.get(key)}"
            )

    expected_outcome = expected.get("outcome_evidence", {})
    for key, value in expected_outcome.items():
        if outcome_evidence.get(key) != value:
            failures.append(f"outcome_evidence mismatch for {key}: expected {value}, got {outcome_evidence.get(key)}")

    return CorpusEvaluationResult(
        case_id=case_path.name,
        passed=not failures,
        failures=tuple(failures),
        artifacts_dir=result.artifacts_dir,
    )


def evaluate_corpus(corpus_dir: str | Path, artifacts_root: str | Path | None = None) -> list[CorpusEvaluationResult]:
    corpus_path = Path(corpus_dir).expanduser().resolve()
    results: list[CorpusEvaluationResult] = []
    for case_dir in sorted(path for path in corpus_path.iterdir() if path.is_dir() and (path / "expected.json").exists()):
        results.append(evaluate_corpus_case(case_dir, artifacts_root=artifacts_root))
    return results


def default_corpus_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "corpus"


def default_artifacts_root() -> Path:
    return Path(__file__).resolve().parents[3] / "artifacts" / "contract_intelligence_corpus"
