from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from apps.contract_intelligence.demo import build_demo_assets


def _write_demo_case(corpus_dir: Path, *, case_id: str) -> None:
    case_dir = corpus_dir / case_id
    inputs_dir = case_dir / "inputs"
    inputs_dir.mkdir(parents=True)
    (case_dir / "expected.json").write_text("{}", encoding="utf-8")
    (inputs_dir / "Prime Contract Agreement.md").write_text(
        "\n".join(
            [
                "Owner may terminate for convenience.",
                "Subcontractor shall be paid on a pay-if-paid basis.",
                "No damages for delay shall be allowed.",
            ]
        ),
        encoding="utf-8",
    )
    (inputs_dir / "General Conditions.md").write_text(
        "Notice of claim must be provided within 5 calendar days.",
        encoding="utf-8",
    )
    (inputs_dir / "Insurance Requirements.md").write_text(
        "Certificates of insurance are required before starting work.",
        encoding="utf-8",
    )
    (inputs_dir / "Funding Memo.md").write_text(
        "Certified payroll must be submitted weekly.",
        encoding="utf-8",
    )


def test_build_demo_assets_generates_manifest_and_dashboards(tmp_path: Path) -> None:
    corpus_dir = tmp_path / "corpus"
    corpus_dir.mkdir()
    _write_demo_case(corpus_dir, case_id="demo-bridge")

    result = build_demo_assets(
        corpus_dir=corpus_dir,
        reference_root=tmp_path / "reference",
        site_dir=tmp_path / "site",
    )

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["site_title"] == "ICM Contract Intelligence Demo"
    assert manifest["cases"][0]["case_id"] == "demo-bridge"
    assert manifest["cases"][0]["dashboard_href"] == "/generated/cases/demo-bridge/dashboard.html"
    assert result.cases[0].dashboard_path.exists()
    assert "Internal-only context is intentionally omitted from the external artifact." in result.cases[0].dashboard_path.read_text(
        encoding="utf-8"
    )
