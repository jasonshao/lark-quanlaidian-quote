import json
import os

import pytest

from scripts.flow.larkcli import LarkCLI, LarkCLIError


def test_dry_run_returns_canned_response(monkeypatch):
    monkeypatch.setenv("LARK_CLI_DRYRUN", "1")
    cli = LarkCLI()
    result = cli.run(
        ["drive", "upload", "--parent", "fldXYZ", "--file", "/tmp/a.pdf"],
        dry_run_response={"file_token": "DRY_TOKEN", "url": "https://dry"},
    )
    assert result == {"file_token": "DRY_TOKEN", "url": "https://dry"}


def test_dry_run_records_invocation(monkeypatch, tmp_path):
    log_file = tmp_path / "invocations.json"
    monkeypatch.setenv("LARK_CLI_DRYRUN", "1")
    monkeypatch.setenv("LARK_CLI_DRYRUN_LOG", str(log_file))
    cli = LarkCLI()
    cli.run(
        ["im", "message", "send", "--receive_id", "oc_A", "--msg_type", "text",
         "--content", '{"text":"x"}'],
        dry_run_response={"message_id": "om_dry"},
    )
    log = json.loads(log_file.read_text())
    assert log[-1]["args"][:3] == ["im", "message", "send"]
    assert log[-1]["args"][3:5] == ["--receive_id", "oc_A"]


def test_real_run_raises_on_nonzero_exit(monkeypatch):
    monkeypatch.delenv("LARK_CLI_DRYRUN", raising=False)
    cli = LarkCLI(binary="lark-cli-definitely-not-real")
    with pytest.raises(LarkCLIError):
        cli.run(["doesntmatter"])
