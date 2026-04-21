"""Step ⑥: build and send an interactive card to the sales group.

Card schema ref: https://open.feishu.cn/document/ (interactive messages).
We use the minimal "elements" layout with title, content, buttons.
"""

from __future__ import annotations

import json

from scripts.flow.larkcli import LarkCLI


def _fmt_money(n: int) -> str:
    return f"¥{n:,}"


def _fmt_pct(list_total: int, final_total: int) -> str:
    if list_total == 0:
        return "—"
    pct = (1 - final_total / list_total) * 100
    return f"{pct:.1f}%"


def build_card(
    *,
    brand: str,
    stores: int,
    package: str,
    list_total: int,
    final_total: int,
    pdf_url: str,
    xlsx_url: str,
    record_url: str,
    sales_name: str,
    created_at_human: str,
) -> dict:
    """Return an interactive message envelope ready for `im message send --content <...>`.

    Shape: {msg_type, card: {header, elements}} — the `content` field passed to
    lark-cli is typically the `card` sub-object serialized, but we return the
    full envelope for clarity; the caller extracts what lark-cli wants.
    """
    discount = _fmt_pct(list_total, final_total)

    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {
                "tag": "plain_text",
                "content": f"🧾 新报价 · {brand}",
            },
            "template": "blue",
        },
        "elements": [
            {
                "tag": "div",
                "fields": [
                    {"is_short": True, "text": {"tag": "lark_md", "content": f"**门店**\n{stores}"}},
                    {"is_short": True, "text": {"tag": "lark_md", "content": f"**套餐**\n{package}"}},
                    {"is_short": True, "text": {"tag": "lark_md",
                        "content": f"**标价**\n{_fmt_money(list_total)}"}},
                    {"is_short": True, "text": {"tag": "lark_md",
                        "content": f"**成交价**\n{_fmt_money(final_total)}"}},
                    {"is_short": False, "text": {"tag": "lark_md", "content": f"**折扣** {discount}"}},
                ],
            },
            {
                "tag": "action",
                "actions": [
                    {"tag": "button", "text": {"tag": "plain_text", "content": "查看 PDF"},
                     "type": "primary", "url": pdf_url},
                    {"tag": "button", "text": {"tag": "plain_text", "content": "Excel"},
                     "type": "default", "url": xlsx_url},
                    {"tag": "button", "text": {"tag": "plain_text", "content": "台账记录"},
                     "type": "default", "url": record_url},
                ],
            },
            {
                "tag": "note",
                "elements": [
                    {"tag": "plain_text", "content": f"by {sales_name} · {created_at_human}"},
                ],
            },
        ],
    }
    return {"msg_type": "interactive", "card": card}


def send_card(*, cli: LarkCLI, chat_id: str, card: dict) -> str:
    """Send the card to chat_id, return message_id."""
    content = json.dumps(card["card"], ensure_ascii=False)
    result = cli.run(
        ["im", "message", "send",
         "--receive_id", chat_id,
         "--msg_type", "interactive",
         "--content", content],
        dry_run_response={"message_id": "DRY_MSG"},
    )
    return result.get("message_id") or result.get("message", {}).get("message_id", "")
