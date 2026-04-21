"""Step ⑤: Write/update a Base record keyed on 报价ID.

Dedup: filter on `报价ID == quote_id`. If a record exists, update it;
otherwise create. This makes reruns idempotent without a UNIQUE constraint
at the Base level.
"""

from __future__ import annotations

import json

from scripts.flow.larkcli import LarkCLI


def upsert_record(
    *,
    cli: LarkCLI,
    app_token: str,
    table_id: str,
    quote_id: str,
    fields: dict,
) -> dict:
    """Return {record_id, url, created: bool}."""
    filter_expr = f'CurrentValue.[报价ID] = "{quote_id}"'
    search = cli.run(
        ["base", "record", "search",
         "--app_token", app_token,
         "--table_id", table_id,
         "--filter", filter_expr],
        dry_run_response={"records": []},
    )
    records = search.get("records", [])

    fields_arg = json.dumps(fields, ensure_ascii=False)

    if records:
        record_id = records[0]["record_id"]
        updated = cli.run(
            ["base", "record", "update",
             "--app_token", app_token,
             "--table_id", table_id,
             "--record_id", record_id,
             "--fields", fields_arg],
            dry_run_response={"record": {"record_id": record_id, "url": records[0].get("url", "")}},
        )
        rec = updated.get("record", {})
        return {
            "record_id": rec.get("record_id", record_id),
            "url": rec.get("url", records[0].get("url", "")),
            "created": False,
        }

    created = cli.run(
        ["base", "record", "create",
         "--app_token", app_token,
         "--table_id", table_id,
         "--fields", fields_arg],
        dry_run_response={"record": {"record_id": "DRY_REC", "url": "https://dry/base/rec"}},
    )
    rec = created.get("record", {})
    return {
        "record_id": rec["record_id"],
        "url": rec.get("url", ""),
        "created": True,
    }
