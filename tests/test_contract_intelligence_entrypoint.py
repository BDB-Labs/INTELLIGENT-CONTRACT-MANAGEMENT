from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from main import app


def test_root_main_exposes_fastapi_app() -> None:
    assert isinstance(app, FastAPI)
