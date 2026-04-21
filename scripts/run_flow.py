"""CLI entrypoint. Subcommands: run, resume, status.

Config is loaded from .env in the repo root (or CWD). All required keys
must be present; missing keys print a clear error and exit 2.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from scripts.flow.form import QuoteForm
from scripts.flow.machine import Flow, FlowConfig


REQUIRED_ENV = [
    "QUOTE_SERVICE_URL",
    "QUOTE_SERVICE_TOKEN",
    "FEISHU_BASE_APP_TOKEN",
    "FEISHU_BASE_TABLE_ID",
    "FEISHU_DRIVE_FOLDER_TOKEN",
    "FEISHU_IM_GROUP_CHAT_ID",
]


def _load_config(state_dir: Path, download_dir: Path) -> FlowConfig:
    load_dotenv()
    missing = [k for k in REQUIRED_ENV if not os.environ.get(k)]
    if missing:
        print(f"error: missing required env vars: {', '.join(missing)}", file=sys.stderr)
        print("hint: cp .env.example .env and fill in the values", file=sys.stderr)
        sys.exit(2)

    sales_name = os.environ.get("SALES_NAME", "销售")
    return FlowConfig(
        service_url=os.environ["QUOTE_SERVICE_URL"],
        service_token=os.environ["QUOTE_SERVICE_TOKEN"],
        drive_folder_token=os.environ["FEISHU_DRIVE_FOLDER_TOKEN"],
        base_app_token=os.environ["FEISHU_BASE_APP_TOKEN"],
        base_table_id=os.environ["FEISHU_BASE_TABLE_ID"],
        im_chat_id=os.environ["FEISHU_IM_GROUP_CHAT_ID"],
        state_dir=state_dir,
        download_dir=download_dir,
        sales_name=sales_name,
    )


def cmd_run(args) -> int:
    form_data = json.loads(Path(args.form_json).read_text(encoding="utf-8"))
    form = QuoteForm.model_validate(form_data)
    config = _load_config(
        state_dir=Path(".quanlaidian-flow-state"),
        download_dir=Path("tmp"),
    )
    flow = Flow(config, form)
    result = flow.run()
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] == "ok" else 1


def cmd_resume(args) -> int:
    state_dir = Path(".quanlaidian-flow-state")
    state_path = state_dir / f"{args.request_id}.json"
    if not state_path.exists():
        print(f"error: state not found: {state_path}", file=sys.stderr)
        return 2
    if not args.form_json:
        print("error: resume requires --form-json (same form used to start the run)",
              file=sys.stderr)
        return 2
    form_data = json.loads(Path(args.form_json).read_text(encoding="utf-8"))
    form = QuoteForm.model_validate(form_data)
    config = _load_config(
        state_dir=state_dir,
        download_dir=Path("tmp"),
    )
    flow = Flow(config, form, request_id=args.request_id)
    result = flow.run()
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] == "ok" else 1


def cmd_status(args) -> int:
    state_path = Path(".quanlaidian-flow-state") / f"{args.request_id}.json"
    if not state_path.exists():
        print(f"error: state not found: {state_path}", file=sys.stderr)
        return 2
    print(state_path.read_text(encoding="utf-8"))
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="run_flow")
    sub = p.add_subparsers(dest="cmd", required=True)

    run_p = sub.add_parser("run", help="Start a new flow from a form JSON")
    run_p.add_argument("--form-json", required=True)
    run_p.set_defaults(func=cmd_run)

    resume_p = sub.add_parser("resume", help="Resume an existing flow by request_id")
    resume_p.add_argument("request_id")
    resume_p.add_argument("--form-json", required=True,
                          help="Same form JSON used when starting the run")
    resume_p.set_defaults(func=cmd_resume)

    status_p = sub.add_parser("status", help="Print the state file JSON")
    status_p.add_argument("request_id")
    status_p.set_defaults(func=cmd_status)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
