"""Steps ②③: render one format and download the file locally.

Backend idempotency: POST /render/{format} with force=false (default) reuses
the existing render if one exists for (quote_id, format). See
quanlaidian-quote-service/app/domain/quote_service.py::render_format.
"""

from __future__ import annotations

from pathlib import Path

import requests


def render_and_download(
    *,
    service_url: str,
    token: str,
    quote_id: str,
    format: str,
    download_dir: Path,
) -> dict:
    """Render format on backend, download the file, return {file_token, filename, local_path}."""
    if format not in {"pdf", "xlsx"}:
        raise ValueError(f"unsupported format for this flow: {format}")

    render_url = f"{service_url.rstrip('/')}/v1/quotes/{quote_id}/render/{format}"
    resp = requests.post(
        render_url,
        headers={"Authorization": f"Bearer {token}"},
        timeout=60,
    )
    resp.raise_for_status()
    ref = resp.json()

    download_dir.mkdir(parents=True, exist_ok=True)
    local = download_dir / ref["filename"]
    dl = requests.get(
        ref["url"],
        headers={"Authorization": f"Bearer {token}"},
        timeout=120,
        stream=True,
    )
    dl.raise_for_status()
    with open(local, "wb") as f:
        for chunk in dl.iter_content(chunk_size=64 * 1024):
            if chunk:
                f.write(chunk)

    return {
        "file_token": ref["file_token"],
        "filename": ref["filename"],
        "local_path": local,
    }
