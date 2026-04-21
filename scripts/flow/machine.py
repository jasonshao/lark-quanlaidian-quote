"""Orchestrator: wires steps with state persistence and retry.

Responsibilities:
- Compute form_hash, derive request_id
- Load or init state
- For each step in order: skip if done; else try with retry; record result; persist state
- Emit a single JSON envelope to stdout at the end
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.flow.form import QuoteForm, form_hash
from scripts.flow.larkcli import LarkCLI
from scripts.flow.retry import retry, RetryExhausted
from scripts.flow.state import (
    FlowState, StepStatus, STEPS,
    load_or_init, save, mark_done, mark_failed,
)
from scripts.flow.steps.create import create_quote
from scripts.flow.steps.render import render_and_download
from scripts.flow.steps.drive import upload_with_dedup
from scripts.flow.steps.base import upsert_record
from scripts.flow.steps.im import build_card, send_card


BACKOFF = (1, 4, 15)


@dataclass
class FlowConfig:
    service_url: str
    service_token: str
    drive_folder_token: str
    base_app_token: str
    base_table_id: str
    im_chat_id: str
    state_dir: Path
    download_dir: Path
    sales_name: str = "销售"


def _gen_request_id() -> str:
    return "req_" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")


class Flow:
    def __init__(self, config: FlowConfig, form: QuoteForm, request_id: str | None = None):
        self.config = config
        self.form = form
        self.request_id = request_id or _gen_request_id()
        self._cli = LarkCLI()

        self.state: FlowState = load_or_init(
            config.state_dir,
            request_id=self.request_id,
            form_hash=form_hash(form),
        )

        # Step hooks — overridable in tests
        self._create = self.__create
        self._render = self.__render_for
        self._drive = self.__drive
        self._base = self.__base
        self._im = self.__im

    # --- step bodies (real implementations) ---

    def __create(self) -> dict:
        return create_quote(
            service_url=self.config.service_url,
            token=self.config.service_token,
            form=self.form,
        )

    def __render_for(self, fmt: str):
        def _do():
            quote_id = self.state.steps["create"].data["quote_id"]
            return render_and_download(
                service_url=self.config.service_url,
                token=self.config.service_token,
                quote_id=quote_id,
                format=fmt,
                download_dir=self.config.download_dir,
            )
        return _do

    def __drive(self) -> dict:
        quote_id = self.state.steps["create"].data["quote_id"]
        pdf_local = Path(self.state.steps["pdf"].data["local_path"])
        xlsx_local = Path(self.state.steps["xlsx"].data["local_path"])

        pdf_res = upload_with_dedup(
            cli=self._cli,
            folder_token=self.config.drive_folder_token,
            local_path=pdf_local,
            quote_id=quote_id,
        )
        xlsx_res = upload_with_dedup(
            cli=self._cli,
            folder_token=self.config.drive_folder_token,
            local_path=xlsx_local,
            quote_id=quote_id,
        )
        return {"pdf_url": pdf_res["url"], "xlsx_url": xlsx_res["url"]}

    def __base(self) -> dict:
        quote_id = self.state.steps["create"].data["quote_id"]
        totals = self.state.steps["create"].data["totals"]
        pdf_url = self.state.steps["drive"].data["pdf_url"]
        xlsx_url = self.state.steps["drive"].data["xlsx_url"]
        discount = 0.0 if totals["list"] == 0 else 1 - totals["final"] / totals["list"]

        fields = {
            "客户品牌": self.form.brand,
            "餐饮类型": self.form.meal_type,
            "门店数": self.form.stores,
            "套餐": self.form.package,
            "标价合计（元）": totals["list"],
            "成交价合计（元）": totals["final"],
            "折扣率": round(discount, 4),
            "PDF链接": pdf_url,
            "Excel链接": xlsx_url,
            "报价ID": quote_id,
            "创建时间": datetime.now(timezone.utc).isoformat(),
        }
        return upsert_record(
            cli=self._cli,
            app_token=self.config.base_app_token,
            table_id=self.config.base_table_id,
            quote_id=quote_id,
            fields=fields,
        )

    def __im(self) -> dict:
        quote_id = self.state.steps["create"].data["quote_id"]
        totals = self.state.steps["create"].data["totals"]
        pdf_url = self.state.steps["drive"].data["pdf_url"]
        xlsx_url = self.state.steps["drive"].data["xlsx_url"]
        record_url = self.state.steps["base"].data["url"]
        now_h = datetime.now().strftime("%Y-%m-%d %H:%M")

        card = build_card(
            brand=self.form.brand,
            stores=self.form.stores,
            package=self.form.package,
            list_total=totals["list"],
            final_total=totals["final"],
            pdf_url=pdf_url,
            xlsx_url=xlsx_url,
            record_url=record_url,
            sales_name=self.config.sales_name,
            created_at_human=now_h,
        )
        msg_id = send_card(cli=self._cli, chat_id=self.config.im_chat_id, card=card)
        return {"message_id": msg_id}

    # --- step runner with retry ---

    @staticmethod
    def _serialize(obj: Any) -> Any:
        """Recursively convert non-JSON-serializable values (e.g. Path) to str."""
        if isinstance(obj, Path):
            return str(obj)
        if isinstance(obj, dict):
            return {k: Flow._serialize(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [Flow._serialize(v) for v in obj]
        return obj

    def _run_step(self, name: str, body) -> dict:
        """Execute body() with retry, update state, persist. Returns the result dict."""
        wrapped = retry(attempts=3, backoff=BACKOFF)(body)
        try:
            result = Flow._serialize(wrapped())
            mark_done(self.state, name, result)
            save(self.config.state_dir, self.state)
            return result
        except RetryExhausted as e:
            mark_failed(self.state, name, error=str(e.last_error))
            save(self.config.state_dir, self.state)
            raise

    def _maybe_run(self, name: str, body) -> None:
        if self.state.steps[name].status == StepStatus.DONE:
            return
        self._run_step(name, body)

    # --- top-level orchestration ---

    def run(self) -> dict:
        try:
            self._maybe_run("create", self._create)
            self._maybe_run("pdf",    self._render("pdf"))
            self._maybe_run("xlsx",   self._render("xlsx"))
            self._maybe_run("drive",  self._drive)
            self._maybe_run("base",   self._base)
            self._maybe_run("im",     self._im)
        except Exception as e:
            failed = next((s for s in STEPS if self.state.steps[s].status != StepStatus.DONE), "unknown")
            return {
                "status": "failed",
                "request_id": self.request_id,
                "failed_step": failed,
                "error": str(e),
                "resume_hint": f"python3 scripts/run_flow.py resume {self.request_id}",
            }

        totals = self.state.steps["create"].data["totals"]
        return {
            "status": "ok",
            "request_id": self.request_id,
            "quote_id": self.state.steps["create"].data["quote_id"],
            "totals": totals,
            "drive": {
                "pdf_url": self.state.steps["drive"].data["pdf_url"],
                "xlsx_url": self.state.steps["drive"].data["xlsx_url"],
            },
            "record": {"url": self.state.steps["base"].data["url"]},
            "im": {"message_id": self.state.steps["im"].data["message_id"]},
        }
