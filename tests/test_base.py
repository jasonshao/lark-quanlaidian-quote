import pytest

from scripts.flow.larkcli import LarkCLI
from scripts.flow.steps.base import upsert_record


def _mk_payload():
    return {
        "客户品牌": "演示正餐火锅",
        "餐饮类型": "正餐",
        "门店数": 20,
        "套餐": "正餐连锁营销旗舰版",
        "标价合计（元）": 318600,
        "成交价合计（元）": 318600,
        "折扣率": 0.0,
        "PDF链接": "https://drive/pdf",
        "Excel链接": "https://drive/xlsx",
        "报价ID": "q_abc",
        "创建时间": "2026-04-21T12:00:00+00:00",
    }


def test_upsert_creates_when_no_match(monkeypatch):
    monkeypatch.setenv("LARK_CLI_DRYRUN", "1")

    def fake_run(args, *, dry_run_response=None):
        if args[:3] == ["base", "record", "search"]:
            return {"records": []}
        if args[:3] == ["base", "record", "create"]:
            return {"record": {"record_id": "rec_new", "url": "https://base/rec_new"}}
        raise AssertionError(args)

    cli = LarkCLI()
    monkeypatch.setattr(cli, "run", fake_run)

    r = upsert_record(
        cli=cli, app_token="bascnX", table_id="tblY",
        quote_id="q_abc", fields=_mk_payload(),
    )
    assert r["record_id"] == "rec_new"
    assert r["created"] is True


def test_upsert_updates_when_match(monkeypatch):
    monkeypatch.setenv("LARK_CLI_DRYRUN", "1")

    def fake_run(args, *, dry_run_response=None):
        if args[:3] == ["base", "record", "search"]:
            return {"records": [{"record_id": "rec_old", "url": "https://base/rec_old"}]}
        if args[:3] == ["base", "record", "update"]:
            return {"record": {"record_id": "rec_old", "url": "https://base/rec_old"}}
        raise AssertionError(args)

    cli = LarkCLI()
    monkeypatch.setattr(cli, "run", fake_run)

    r = upsert_record(
        cli=cli, app_token="bascnX", table_id="tblY",
        quote_id="q_abc", fields=_mk_payload(),
    )
    assert r["record_id"] == "rec_old"
    assert r["created"] is False
