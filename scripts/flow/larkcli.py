"""Subprocess wrapper around `lark-cli`.

LARK_CLI_DRYRUN=1 short-circuits execution and returns a caller-supplied
canned response. Invocations are appended to LARK_CLI_DRYRUN_LOG (JSON list)
if set, enabling tests to assert on exact flags.
"""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence


class LarkCLIError(RuntimeError):
    def __init__(self, args: Sequence[str], stderr: str, returncode: int):
        self.args = list(args)
        self.stderr = stderr
        self.returncode = returncode
        super().__init__(
            f"lark-cli {' '.join(args)} failed (rc={returncode}): {stderr.strip()[:300]}"
        )


class LarkCLI:
    def __init__(self, binary: str = "lark-cli"):
        self.binary = binary

    def run(self, args: Sequence[str], *, dry_run_response: dict | None = None) -> dict:
        """Invoke lark-cli with args. Returns parsed stdout JSON (or empty dict).

        In dry-run mode: append invocation to LARK_CLI_DRYRUN_LOG (if set),
        return the supplied dry_run_response (defaults to {}).
        """
        if os.environ.get("LARK_CLI_DRYRUN") == "1":
            self._log_dryrun(args)
            return dict(dry_run_response or {})

        try:
            proc = subprocess.run(
                [self.binary, *args],
                capture_output=True,
                text=True,
            )
        except FileNotFoundError as e:
            raise LarkCLIError(args=args, stderr=str(e), returncode=127)

        if proc.returncode != 0:
            raise LarkCLIError(args=args, stderr=proc.stderr, returncode=proc.returncode)

        stdout = proc.stdout.strip()
        if not stdout:
            return {}
        try:
            return json.loads(stdout)
        except json.JSONDecodeError:
            return {"_raw": stdout}

    def _log_dryrun(self, args: Sequence[str]) -> None:
        log_path = os.environ.get("LARK_CLI_DRYRUN_LOG")
        if not log_path:
            return
        p = Path(log_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        existing: list = []
        if p.exists():
            try:
                existing = json.loads(p.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                existing = []
        existing.append({
            "at": datetime.now(timezone.utc).isoformat(),
            "args": list(args),
        })
        p.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
