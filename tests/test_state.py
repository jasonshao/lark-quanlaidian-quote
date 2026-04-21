import json
from pathlib import Path

from scripts.flow.state import (
    FlowState, StepStatus, load_or_init, save, mark_done, mark_failed,
)


def test_load_or_init_creates_fresh_state(tmp_path):
    state_dir = tmp_path / ".quanlaidian-flow-state"
    state = load_or_init(state_dir, request_id="req_test", form_hash="sha256:abc")

    assert state.request_id == "req_test"
    assert state.form_hash == "sha256:abc"
    assert state.steps["create"].status == StepStatus.PENDING
    assert state.steps["im"].status == StepStatus.PENDING


def test_save_and_reload_roundtrip(tmp_path):
    state_dir = tmp_path / ".quanlaidian-flow-state"
    state = load_or_init(state_dir, request_id="req_r", form_hash="sha256:x")
    mark_done(state, "create", {"quote_id": "q_1"})
    save(state_dir, state)

    reloaded = load_or_init(state_dir, request_id="req_r", form_hash="sha256:x")
    assert reloaded.steps["create"].status == StepStatus.DONE
    assert reloaded.steps["create"].data == {"quote_id": "q_1"}


def test_mark_failed_increments_attempts(tmp_path):
    state_dir = tmp_path / ".quanlaidian-flow-state"
    state = load_or_init(state_dir, request_id="req_f", form_hash="sha256:x")
    mark_failed(state, "drive", error="timeout")
    mark_failed(state, "drive", error="timeout")
    assert state.steps["drive"].status == StepStatus.FAILED
    assert state.steps["drive"].attempts == 2
    assert state.steps["drive"].error == "timeout"


def test_form_hash_mismatch_is_detected(tmp_path):
    state_dir = tmp_path / ".quanlaidian-flow-state"
    s = load_or_init(state_dir, request_id="req_m", form_hash="sha256:orig")
    save(state_dir, s)
    import pytest
    with pytest.raises(ValueError, match="form_hash mismatch"):
        load_or_init(state_dir, request_id="req_m", form_hash="sha256:changed")
