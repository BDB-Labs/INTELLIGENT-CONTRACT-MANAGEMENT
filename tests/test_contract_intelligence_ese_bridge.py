from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

bridge = importlib.import_module("apps.contract_intelligence.orchestration.ese_bridge")
corpus = importlib.import_module("apps.contract_intelligence.evaluation.corpus")

build_bid_review_ese_config = bridge.build_bid_review_ese_config
run_bid_review_with_ese = bridge.run_bid_review_with_ese
default_corpus_dir = corpus.default_corpus_dir


def test_build_bid_review_ese_config_uses_domain_roles_and_dry_run_defaults() -> None:
    project_dir = default_corpus_dir() / "riverside_bridge" / "inputs"
    cfg = build_bid_review_ese_config(project_dir=project_dir)

    assert list(cfg["roles"].keys()) == [
        "document_intake_analyst",
        "contract_risk_analyst",
        "insurance_requirements_analyst",
        "funding_compliance_analyst",
        "relationship_strategy_analyst",
        "context_intelligence_analyst",
        "procurement_structure_analyst",
        "outcome_evidence_analyst",
        "adversarial_reviewer",
        "bid_decision_analyst",
        "obligation_register_builder",
    ]
    assert cfg["runtime"]["adapter"] == "dry-run"
    assert "Document Inventory:" in cfg["input"]["prompt"]
    assert "Use findings for contract issues, not software defects." in cfg["roles"]["document_intake_analyst"]["prompt"]
    assert cfg["input"]["analysis_perspective"] == "vendor"


def test_run_bid_review_with_ese_executes_through_pipeline(tmp_path: Path) -> None:
    project_dir = default_corpus_dir() / "riverside_bridge" / "inputs"
    _, summary_path = run_bid_review_with_ese(
        project_dir=project_dir,
        artifacts_dir=str(tmp_path / "ese-run"),
    )

    artifacts_dir = Path(summary_path).parent
    state = json.loads((artifacts_dir / "pipeline_state.json").read_text(encoding="utf-8"))
    executed_roles = [item["role"] for item in state["execution"]]
    assert executed_roles[0] == "document_intake_analyst"
    assert executed_roles[-1] == "obligation_register_builder"

    first_role_output = json.loads((artifacts_dir / "01_document_intake_analyst.json").read_text(encoding="utf-8"))
    prompt_excerpt = first_role_output["metadata"]["prompt_excerpt"]
    assert "contractor-side construction bid review" in prompt_excerpt


def test_build_bid_review_ese_config_supports_agency_perspective() -> None:
    project_dir = default_corpus_dir() / "riverside_bridge" / "inputs"
    cfg = build_bid_review_ese_config(project_dir=project_dir, analysis_perspective="agency")

    assert cfg["input"]["analysis_perspective"] == "agency"
    assert "from the agency perspective" in cfg["input"]["scope"]
    assert "agency-side construction bid review" in cfg["roles"]["contract_risk_analyst"]["prompt"]


def test_build_bid_review_ese_config_prioritizes_salient_clauses_in_prompt(tmp_path: Path) -> None:
    project_dir = tmp_path / "ese-salience"
    project_dir.mkdir()
    prime_lines = [f"Section {index}.0 Administrative Filler\nRoutine coordination language only." for index in range(1, 15)]
    prime_lines.extend(
        [
            "Section 99.1 Commercial Risk",
            "Subcontractor shall be paid on a pay-if-paid basis and no damages for delay shall be allowed.",
        ]
    )
    (project_dir / "Prime Contract Agreement.md").write_text("\n".join(prime_lines), encoding="utf-8")
    (project_dir / "General Conditions.md").write_text(
        "Section 2 Claims\nNotice of claim must be provided within 7 calendar days.",
        encoding="utf-8",
    )
    (project_dir / "Insurance Requirements.md").write_text(
        "Section 3 Insurance\nAdditional insured status is required.",
        encoding="utf-8",
    )

    cfg = build_bid_review_ese_config(project_dir=project_dir)
    prompt = cfg["input"]["prompt"]

    assert "pay-if-paid basis" in prompt
    assert "no damages for delay" in prompt
