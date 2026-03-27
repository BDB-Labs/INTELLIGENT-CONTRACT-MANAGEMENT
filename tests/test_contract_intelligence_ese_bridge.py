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
