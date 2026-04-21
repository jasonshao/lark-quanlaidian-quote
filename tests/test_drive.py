import json
import os
from pathlib import Path

import pytest

from scripts.flow.larkcli import LarkCLI
from scripts.flow.steps.drive import upload_with_dedup


def test_upload_when_file_not_present(monkeypatch, tmp_path):
    monkeypatch.setenv("LARK_CLI_DRYRUN", "1")
    log = tmp_path / "inv.json"
    monkeypatch.setenv("LARK_CLI_DRYRUN_LOG", str(log))

    pdf = tmp_path / "演示-q_abc.pdf"
    pdf.write_bytes(b"%PDF-1.4")

    call_counter = {"n": 0}

    def fake_run(args, *, dry_run_response=None):
        call_counter["n"] += 1
        if args[:3] == ["drive", "file", "list"]:
            return {"files": []}
        if args[:2] == ["drive", "upload"]:
            return {"file_token": "ft_up", "url": "https://drive/演示-q_abc.pdf"}
        raise AssertionError(f"unexpected args: {args}")

    cli = LarkCLI()
    monkeypatch.setattr(cli, "run", fake_run)

    result = upload_with_dedup(
        cli=cli,
        folder_token="fldXYZ",
        local_path=pdf,
        quote_id="q_abc",
    )
    assert result["url"] == "https://drive/演示-q_abc.pdf"
    assert call_counter["n"] == 2  # list + upload


def test_upload_reuses_when_existing(monkeypatch, tmp_path):
    monkeypatch.setenv("LARK_CLI_DRYRUN", "1")
    pdf = tmp_path / "演示-q_abc.pdf"
    pdf.write_bytes(b"%PDF-1.4")

    def fake_run(args, *, dry_run_response=None):
        if args[:3] == ["drive", "file", "list"]:
            return {"files": [{"name": "演示-q_abc.pdf", "token": "ft_old", "url": "https://drive/existing"}]}
        raise AssertionError("upload should not be called")

    cli = LarkCLI()
    monkeypatch.setattr(cli, "run", fake_run)

    result = upload_with_dedup(
        cli=cli, folder_token="fldXYZ", local_path=pdf, quote_id="q_abc",
    )
    assert result["url"] == "https://drive/existing"
    assert result["reused"] is True
