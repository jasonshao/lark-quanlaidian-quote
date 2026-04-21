"""Minimal FastAPI mock of quanlaidian-quote-service for local demos and CI.

Implements just the endpoints run_flow.py calls:
- POST /v1/quotes                           → QuoteCreated
- POST /v1/quotes/{qid}/render/{pdf|xlsx}   → FileRef
- GET  /files/{token}/{filename}            → bytes
- GET  /health                              → {"ok": true}

Pricing is a trivial linear model (stores × per_store_rate), no real baseline
data. Fake files are 4-byte stubs (real format not required for the flow).

Run:
    python examples/mock_server.py
    # listens on http://localhost:8000
"""

from __future__ import annotations

import hashlib
import time

from fastapi import FastAPI, Header, HTTPException, Response
from pydantic import BaseModel


app = FastAPI(title="quanlaidian-quote-service MOCK")

# In-memory store keyed by idempotency hash for realistic idempotency
_QUOTES: dict[str, dict] = {}
_RENDERS: dict[tuple[str, str], dict] = {}


def _compute_totals(form: dict) -> dict:
    stores = int(form["门店数量"])
    per_store = 15000 if form["餐饮类型"] == "正餐" else 12000
    list_total = per_store * stores
    final_total = int(list_total * float(form.get("成交价系数", 1.0)))
    return {"list": list_total, "final": final_total}


@app.post("/v1/quotes")
def create_quote(form: dict, x_idempotency_key: str = Header(default="")):
    if x_idempotency_key and x_idempotency_key in _QUOTES:
        return _QUOTES[x_idempotency_key]

    stamp = time.strftime("%Y%m%d%H%M%S")
    seed = x_idempotency_key or str(time.time())
    qid = f"q_{stamp}_{hashlib.sha1(seed.encode()).hexdigest()[:8]}"
    totals = _compute_totals(form)

    envelope = {
        "request_id": f"req_{stamp}",
        "quote_id": qid,
        "preview": {
            "brand": form["客户品牌名称"],
            "meal_type": form["餐饮类型"],
            "stores": form["门店数量"],
            "package": form["门店套餐"],
            "discount": 1 - (totals["final"] / totals["list"]) if totals["list"] else 0,
            "totals": totals,
            "items": [],
        },
        "approval": {"required": False, "state": "not_required", "reasons": []},
        "pricing_version": "mock-v1",
    }
    if x_idempotency_key:
        _QUOTES[x_idempotency_key] = envelope
    return envelope


@app.post("/v1/quotes/{quote_id}/render/{fmt}")
def render(quote_id: str, fmt: str):
    if fmt not in {"pdf", "xlsx", "json"}:
        raise HTTPException(404, "unsupported format")
    key = (quote_id, fmt)
    if key in _RENDERS:
        return _RENDERS[key]

    token = f"ft_{quote_id}_{fmt}"
    filename = f"mock-{quote_id}.{fmt}"
    ref = {
        "file_token": token,
        "filename": filename,
        "url": f"http://localhost:8000/files/{token}/{filename}",
    }
    _RENDERS[key] = ref
    return ref


@app.get("/files/{token}/{filename}")
def download(token: str, filename: str):
    if filename.endswith(".pdf"):
        return Response(content=b"%PDF-1.4 mock", media_type="application/pdf")
    if filename.endswith(".xlsx"):
        return Response(content=b"PK\x03\x04 mock", media_type="application/octet-stream")
    return Response(content=b"{}", media_type="application/json")


@app.get("/health")
def health():
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
