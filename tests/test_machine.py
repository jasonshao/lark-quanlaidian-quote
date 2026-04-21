import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from scripts.flow.form import QuoteForm
from scripts.flow.machine import Flow, FlowConfig
from scripts.flow.state import StepStatus, load_or_init


@pytest.fixture(autouse=True)
def _fast_retry(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda *a, **k: None)


@pytest.fixture
def config(tmp_path):
    return FlowConfig(
        service_url="http://mock.test",
        service_token="T",
        drive_folder_token="fldA",
        base_app_token="bascX",
        base_table_id="tblY",
        im_chat_id="oc_Z",
        state_dir=tmp_path / ".state",
        download_dir=tmp_path / "tmp",
    )


@pytest.fixture
def form():
    return QuoteForm.model_validate({
        "客户品牌名称": "演示正餐火锅",
        "餐饮类型": "正餐",
        "门店数量": 10,
        "门店套餐": "正餐连锁营销旗舰版",
    })


def test_machine_skips_done_steps_on_resume(config, form, monkeypatch):
    from scripts.flow.state import mark_done, save
    from scripts.flow.form import form_hash as fh

    state = load_or_init(config.state_dir,
                         request_id="req_r",
                         form_hash=fh(form))
    mark_done(state, "create", {"quote_id": "q_1", "totals": {"list": 100, "final": 100}})
    mark_done(state, "pdf",    {"file_token": "ft_pdf", "local_path": "/tmp/a.pdf", "filename": "a.pdf"})
    save(config.state_dir, state)

    called = []
    def mock_step(name, result):
        def inner(**kwargs):
            called.append(name)
            return result
        return inner

    flow = Flow(config, form, request_id="req_r")
    flow._create = mock_step("create", {"quote_id": "q_1", "totals": {"list": 100, "final": 100}})
    flow._render = lambda fmt: mock_step(f"render_{fmt}", {"file_token": f"ft_{fmt}", "local_path": Path(f"/tmp/a.{fmt}"), "filename": f"a.{fmt}"})
    flow._drive = mock_step("drive", {"pdf_url": "u1", "xlsx_url": "u2"})
    flow._base = mock_step("base", {"record_id": "rec_1", "url": "rec_url"})
    flow._im = mock_step("im", {"message_id": "om_1"})

    result = flow.run()

    assert result["status"] == "ok"
    assert "create" not in called
    assert "render_pdf" not in called
    assert "render_xlsx" in called
    assert "drive" in called
    assert "base" in called
    assert "im" in called


def test_machine_stops_and_emits_failure_on_step_error(config, form):
    flow = Flow(config, form, request_id="req_f")
    flow._create = lambda: {"quote_id": "q_1", "totals": {"list": 100, "final": 100}}
    flow._render = lambda fmt: (_ for _ in ()).throw(RuntimeError("render broke"))
    flow._drive = flow._base = flow._im = lambda **_: {}

    result = flow.run()

    assert result["status"] == "failed"
    assert result["failed_step"] == "pdf"
    assert "render broke" in result["error"]
