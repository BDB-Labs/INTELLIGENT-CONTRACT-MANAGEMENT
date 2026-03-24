from __future__ import annotations

import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

corpus = importlib.import_module("apps.contract_intelligence.evaluation.corpus")

default_corpus_dir = corpus.default_corpus_dir
evaluate_corpus = corpus.evaluate_corpus
evaluate_corpus_case = corpus.evaluate_corpus_case


def test_default_corpus_cases_pass(tmp_path: Path) -> None:
    results = evaluate_corpus(default_corpus_dir(), artifacts_root=tmp_path / "eval")
    assert results
    assert all(result.passed for result in results)


def test_specific_case_evaluation_returns_named_result(tmp_path: Path) -> None:
    case_dir = default_corpus_dir() / "riverside_bridge"
    result = evaluate_corpus_case(case_dir, artifacts_root=tmp_path / "single-case")
    assert result.case_id == "riverside_bridge"
    assert result.passed is True
    assert result.failures == ()
