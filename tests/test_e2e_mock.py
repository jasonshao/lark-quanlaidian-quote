"""End-to-end: run_flow against the mock server with lark-cli in dry-run mode.

Expected invocations of lark-cli (recorded to LARK_CLI_DRYRUN_LOG):
- 2x drive list + 2x drive upload       (pdf, xlsx)
- 1x base search + 1x base create
- 1x im message send
"""

import json
import os
from pathlib import Path

import pytest

from scripts.flow.form import QuoteForm
from scripts.flow.machine import Flow, FlowConfig


@pytest.fixture
def tmp_dirs(tmp_path):
    return {
        "state_dir": tmp_path / ".state",
        "download_dir": tmp_path / "tmp",
        "dryrun_log": tmp_path / "inv.json",
    }


def test_full_flow_mock(mock_server, tmp_dirs, monkeypatch):
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
    flow = Flow(config, form)
    result = flow.run()

    assert result["status"] == "ok", f"expected ok, got: {result}"
    assert result["quote_id"].startswith("q_")
    assert result["totals"]["list"] > 0
    assert any(tmp_dirs["download_dir"].glob("*.pdf"))
    assert any(tmp_dirs["download_dir"].glob("*.xlsx"))

    log = json.loads(tmp_dirs["dryrun_log"].read_text(encoding="utf-8"))
    verbs = [" ".join(e["args"][:3]) for e in log]
    assert verbs.count("drive file list") == 2, f"verbs={verbs}"
    assert verbs.count("drive upload") == 2, f"verbs={verbs}"
    assert verbs.count("base record search") == 1, f"verbs={verbs}"
    assert verbs.count("base record create") == 1, f"verbs={verbs}"
    assert verbs.count("im message send") == 1, f"verbs={verbs}"


def test_resume_skips_done_steps(mock_server, tmp_dirs, monkeypatch):
    """Run once; reset IM to pending; rerun same request_id — only IM should re-fire."""
    monkeypatch.setenv("LARK_CLI_DRYRUN", "1")
    monkeypatch.setenv("LARK_CLI_DRYRUN_LOG", str(tmp_dirs["dryrun_log"]))

    form = QuoteForm.model_validate(json.loads(
        Path("examples/form.sample.json").read_text(encoding="utf-8")
    ))
    config = FlowConfig(
        service_url=mock_server, service_token="T",
        drive_folder_token="fldM", base_app_token="bM", base_table_id="tM",
        im_chat_id="oc_M",
        state_dir=tmp_dirs["state_dir"],
        download_dir=tmp_dirs["download_dir"],
    )
    flow = Flow(config, form)
    first = flow.run()
    assert first["status"] == "ok", f"first run failed: {first}"
    rid = first["request_id"]

    # Reset state's im step to pending
    state_path = tmp_dirs["state_dir"] / f"{rid}.json"
    s = json.loads(state_path.read_text(encoding="utf-8"))
    s["steps"]["im"]["status"] = "pending"
    state_path.write_text(json.dumps(s, ensure_ascii=False), encoding="utf-8")

    # Clear invocation log to count only resume
    tmp_dirs["dryrun_log"].write_text("[]", encoding="utf-8")

    flow2 = Flow(config, form, request_id=rid)
    second = flow2.run()
    assert second["status"] == "ok", f"resume run failed: {second}"

    log = json.loads(tmp_dirs["dryrun_log"].read_text(encoding="utf-8"))
    verbs = [" ".join(e["args"][:3]) for e in log]
    assert verbs == ["im message send"], f"unexpected verbs on resume: {verbs}"
