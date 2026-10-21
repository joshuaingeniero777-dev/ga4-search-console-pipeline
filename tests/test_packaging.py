"""The pipeline package must be importable as `pipeline`, from src/. No network calls."""

import importlib.util
from pathlib import Path

SRC_PIPELINE = Path(__file__).resolve().parent.parent / "src" / "pipeline"


def test_pipeline_modules_resolve_to_src():
    # Fails with "No module named 'pipeline'" if `pip install -e .` hasn't been run.
    spec = importlib.util.find_spec("pipeline.auth_check")
    assert spec is not None
    assert Path(spec.origin).resolve().parent == SRC_PIPELINE
