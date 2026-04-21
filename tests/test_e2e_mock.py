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
    # "Verb" = first 2 or 3 args; some lark-cli commands have 3-word verbs
    # (e.g., "drive file list"), others have 2 ("drive upload"). We detect by
    # looking at specific prefixes.
    def count_prefix(prefix: tuple[str, ...]) -> int:
        n = len(prefix)
        return sum(1 for e in log if tuple(e["args"][:n]) == prefix)

    assert count_prefix(("drive", "file", "list")) == 2, f"log={log}"
    assert count_prefix(("drive", "upload")) == 2, f"log={log}"
    assert count_prefix(("base", "record", "search")) == 1, f"log={log}"
    assert count_prefix(("base", "record", "create")) == 1, f"log={log}"
    assert count_prefix(("im", "message", "send")) == 1, f"log={log}"


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
    assert len(log) == 1, f"expected only 1 invocation, got: {log}"
    assert tuple(log[0]["args"][:3]) == ("im", "message", "send"), (
        f"unexpected invocation on resume: {log[0]}"
    )
