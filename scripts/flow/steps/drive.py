"""Step ④: upload PDF/Excel to Feishu Drive with dedup.

Dedup strategy: filename includes quote_id suffix. Before upload, list the
target folder and skip if a file with the same name exists.

Expected lark-cli commands:
  lark-cli drive file list --folder_token <fld...>
    → {"files": [{"name":..., "token":..., "url":...}, ...]}
  lark-cli drive upload --parent <fld...> --file <path>
    → {"file_token":..., "url":...}
"""

from __future__ import annotations

from pathlib import Path

from scripts.flow.larkcli import LarkCLI


def upload_with_dedup(
    *,
    cli: LarkCLI,
    folder_token: str,
    local_path: Path,
    quote_id: str,
) -> dict:
    """Return {file_token, url, reused: bool}. Filename is local_path.name.

    The caller is expected to have named local_path with `quote_id` in it
    (see scripts/flow/steps/render.py). That makes listing-based dedup safe.
    """
    name = local_path.name
    if quote_id not in name:
        raise ValueError(
            f"local_path.name {name!r} must include quote_id {quote_id!r} for dedup"
        )

    listing = cli.run(
        ["drive", "file", "list", "--folder_token", folder_token],
        dry_run_response={"files": []},
    )
    for f in listing.get("files", []):
        if f.get("name") == name:
            return {
                "file_token": f["token"],
                "url": f["url"],
                "reused": True,
            }

    uploaded = cli.run(
        ["drive", "upload",
         "--parent", folder_token,
         "--file", str(local_path)],
        dry_run_response={"file_token": "DRY_FT", "url": "https://dry/drive/" + name},
    )
    return {
        "file_token": uploaded["file_token"],
        "url": uploaded["url"],
        "reused": False,
    }
