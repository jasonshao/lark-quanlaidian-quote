import json

from scripts.flow.larkcli import LarkCLI
from scripts.flow.steps.im import build_card, send_card


def test_build_card_contains_totals_and_links():
    card = build_card(
        brand="演示正餐火锅",
        stores=20,
        package="正餐连锁营销旗舰版",
        list_total=318600,
        final_total=223020,
        pdf_url="https://drive/pdf",
        xlsx_url="https://drive/xlsx",
        record_url="https://base/rec",
        sales_name="张三",
        created_at_human="2026-04-21 20:00",
    )
    s = json.dumps(card, ensure_ascii=False)
    assert "演示正餐火锅" in s
    assert "318,600" in s or "318600" in s
    assert "223,020" in s or "223020" in s
    assert "https://drive/pdf" in s
    assert "https://drive/xlsx" in s
    assert "https://base/rec" in s
    assert card["msg_type"] == "interactive"


def test_send_card_calls_lark_cli_with_right_args(monkeypatch):
    monkeypatch.setenv("LARK_CLI_DRYRUN", "1")
    calls = []

    def fake_run(args, *, dry_run_response=None):
        calls.append(args)
        return {"message_id": "om_dry"}

    cli = LarkCLI()
    monkeypatch.setattr(cli, "run", fake_run)

    msg_id = send_card(
        cli=cli,
        chat_id="oc_group",
        card={"msg_type": "interactive", "card": {"elements": []}},
    )
    assert msg_id == "om_dry"
    args = calls[0]
    assert args[:3] == ["im", "message", "send"]
    assert "--receive_id" in args and "oc_group" in args
    assert "--msg_type" in args and "interactive" in args
