"""Per-request state file: resume semantics for the 6-step flow.

File layout: <cwd>/.quanlaidian-flow-state/<request_id>.json

One file per request_id; human-readable JSON; atomic replace on save.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path


STEPS = ["create", "pdf", "xlsx", "drive", "base", "im"]


class StepStatus(str, Enum):
    PENDING = "pending"
    DONE = "done"
    FAILED = "failed"


@dataclass
class StepState:
    status: StepStatus = StepStatus.PENDING
    data: dict = field(default_factory=dict)
    attempts: int = 0
    error: str = ""
    last_at: str = ""


@dataclass
class FlowState:
    request_id: str
    form_hash: str
    steps: dict[str, StepState] = field(default_factory=dict)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _path_for(state_dir: Path, request_id: str) -> Path:
    return state_dir / f"{request_id}.json"


def load_or_init(state_dir: Path, *, request_id: str, form_hash: str) -> FlowState:
    """Load existing state or create a fresh one. Raises if form_hash mismatches."""
    state_dir.mkdir(parents=True, exist_ok=True)
    p = _path_for(state_dir, request_id)
    if p.exists():
        raw = json.loads(p.read_text(encoding="utf-8"))
        if raw["form_hash"] != form_hash:
            raise ValueError(
                f"form_hash mismatch for request_id={request_id}: "
                f"state has {raw['form_hash']}, caller has {form_hash}"
            )
        return FlowState(
            request_id=raw["request_id"],
            form_hash=raw["form_hash"],
            steps={
                name: StepState(
                    status=StepStatus(s["status"]),
                    data=s.get("data", {}),
                    attempts=s.get("attempts", 0),
                    error=s.get("error", ""),
                    last_at=s.get("last_at", ""),
                )
                for name, s in raw["steps"].items()
            },
        )
    # Fresh
    return FlowState(
        request_id=request_id,
        form_hash=form_hash,
        steps={name: StepState() for name in STEPS},
    )


def save(state_dir: Path, state: FlowState) -> None:
    """Atomic write: tmp file + rename."""
    state_dir.mkdir(parents=True, exist_ok=True)
    p = _path_for(state_dir, state.request_id)
    payload = {
        "request_id": state.request_id,
        "form_hash": state.form_hash,
        "steps": {
            name: {
                "status": s.status.value,
                "data": s.data,
                "attempts": s.attempts,
                "error": s.error,
                "last_at": s.last_at,
            }
            for name, s in state.steps.items()
        },
    }
    fd, tmp_path = tempfile.mkstemp(dir=state_dir, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, p)
    except Exception:
        os.unlink(tmp_path)
        raise


def mark_done(state: FlowState, step: str, data: dict) -> None:
    s = state.steps[step]
    s.status = StepStatus.DONE
    s.data = data
    s.last_at = _now_iso()
    s.error = ""


def mark_failed(state: FlowState, step: str, *, error: str) -> None:
    s = state.steps[step]
    s.status = StepStatus.FAILED
    s.attempts += 1
    s.error = error
    s.last_at = _now_iso()
