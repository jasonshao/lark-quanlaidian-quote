"""One-shot helper: create the 销售台账 Base table with 12 fields.

Usage:
    python scripts/base_schema.py --app-token <bascnXXX> [--table-name "销售台账"]

Output: the newly created table_id for .env.
"""

from __future__ import annotations

import argparse
import json
import sys

from scripts.flow.larkcli import LarkCLI, LarkCLIError


# field definitions keyed to Feishu Base column types.
# See https://open.feishu.cn/document/ (Base field types) for `type` codes.
FIELDS = [
    {"field_name": "客户品牌", "type": 1},                        # text
    {"field_name": "餐饮类型", "type": 3,                         # single-select
     "property": {"options": [{"name": "轻餐"}, {"name": "正餐"}]}},
    {"field_name": "门店数", "type": 2},                          # number
    {"field_name": "套餐", "type": 3,
     "property": {"options": [
         {"name": "轻餐连锁营销旗舰版"},
         {"name": "正餐连锁营销旗舰版"},
     ]}},
    {"field_name": "标价合计（元）", "type": 2},
    {"field_name": "成交价合计（元）", "type": 2},
    {"field_name": "折扣率", "type": 2, "property": {"formatter": "0.00%"}},
    {"field_name": "PDF链接", "type": 15},                        # url
    {"field_name": "Excel链接", "type": 15},
    {"field_name": "报价ID", "type": 1},
    {"field_name": "销售", "type": 11},                           # person (user)
    {"field_name": "创建时间", "type": 5},                        # date
]


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--app-token", required=True)
    p.add_argument("--table-name", default="销售台账")
    args = p.parse_args()

    cli = LarkCLI()

    try:
        created = cli.run([
            "base", "table", "create",
            "--app_token", args.app_token,
            "--name", args.table_name,
        ])
    except LarkCLIError as e:
        print(f"table create failed: {e}", file=sys.stderr)
        return 1

    table_id = created.get("table_id") or created.get("table", {}).get("table_id")
    if not table_id:
        print(f"unexpected response (no table_id): {created}", file=sys.stderr)
        return 1

    for field in FIELDS:
        try:
            cli.run([
                "base", "field", "create",
                "--app_token", args.app_token,
                "--table_id", table_id,
                "--field", json.dumps(field, ensure_ascii=False),
            ])
        except LarkCLIError as e:
            print(f"field create {field['field_name']} failed: {e}", file=sys.stderr)
            return 1

    print(json.dumps({"table_id": table_id, "fields": len(FIELDS)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
