"""Golden-file diff test for the end-to-end envelope.

Runs `Flow` against the FastAPI mock with `LARK_CLI_DRYRUN=1`, then compares
the resulting JSON envelope to `tests/golden/envelope_dryrun.golden.json`.

The golden file uses two value forms:
- exact: the produced value must equal it
- "!regex!<pattern>": the produced value must match the regex

This lets us pin shape + non-derived fields while tolerating timestamps and
hash-seeded ids.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from scripts.flow.form import QuoteForm
from scripts.flow.machine import Flow, FlowConfig


GOLDEN_PATH = Path(__file__).parent / "golden" / "envelope_dryrun.golden.json"


def _diff(expected, actual, path: str = "$") -> list[str]:
    """Return a list of human-readable diff lines. Empty list = match."""
    if isinstance(expected, str) and expected.startswith("!regex!"):
        pattern = expected[len("!regex!"):]
        if not isinstance(actual, str) or not re.fullmatch(pattern, actual):
            return [f"{path}: regex {pattern!r} did not match {actual!r}"]
        return []
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return [f"{path}: expected dict, got {type(actual).__name__}"]
        diffs: list[str] = []
        for k, v in expected.items():
            if k.startswith("_"):  # comment / doc keys
                continue
            if k not in actual:
                diffs.append(f"{path}.{k}: missing in actual")
                continue
            diffs.extend(_diff(v, actual[k], f"{path}.{k}"))
        return diffs
    if isinstance(expected, list):
        if not isinstance(actual, list):
            return [f"{path}: expected list, got {type(actual).__name__}"]
        if len(expected) != len(actual):
            return [f"{path}: length {len(expected)} != {len(actual)}"]
        diffs = []
        for i, (e, a) in enumerate(zip(expected, actual)):
            diffs.extend(_diff(e, a, f"{path}[{i}]"))
        return diffs
    if expected != actual:
        return [f"{path}: expected {expected!r}, got {actual!r}"]
    return []


@pytest.fixture
def tmp_dirs(tmp_path):
    return {
        "state_dir": tmp_path / ".state",
        "download_dir": tmp_path / "tmp",
        "dryrun_log": tmp_path / "inv.json",
    }


def test_envelope_matches_golden(mock_server, tmp_dirs, monkeypatch):
    monkeypatch.setenv("LARK_CLI_DRYRUN", "1")
    monkeypatch.setenv("LARK_CLI_DRYRUN_LOG", str(tmp_dirs["dryrun_log"]))

    form = QuoteForm.model_validate(json.loads(
        Path("examples/form.sample.json").read_text(encoding="utf-8")
    ))
    config = FlowConfig(
        service_url=mock_server,
        service_token="MOCK_BEARER",
        drive_folder_token="fldMOCK",
        base_app_token="bascMOCK",
        base_table_id="tblMOCK",
        im_chat_id="oc_MOCK",
        state_dir=tmp_dirs["state_dir"],
        download_dir=tmp_dirs["download_dir"],
        sales_name="demo",
    )

    actual = Flow(config, form).run()
    expected = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))

    diffs = _diff(expected, actual)
    assert not diffs, (
        "Envelope drifted from golden:\n  "
        + "\n  ".join(diffs)
        + f"\nIf the change is intentional, regenerate {GOLDEN_PATH}"
    )
