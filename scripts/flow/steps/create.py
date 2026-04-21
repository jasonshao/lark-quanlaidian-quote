"""Step ①: POST /v1/quotes to create a persisted quote.

Backend docs: quanlaidian-quote-service/app/api/quotes.py (POST /v1/quotes).
Returns QuoteCreated envelope with quote_id, preview.totals, pricing_version.
"""

from __future__ import annotations

import requests

from scripts.flow.form import QuoteForm, form_hash


def create_quote(*, service_url: str, token: str, form: QuoteForm) -> dict:
    """POST the form; return a dict with keys: quote_id, totals, pricing_version."""
    url = service_url.rstrip("/") + "/v1/quotes"
    resp = requests.post(
        url,
        json=form.to_backend_body(),
        headers={
            "Authorization": f"Bearer {token}",
            "X-Idempotency-Key": form_hash(form),
            "Content-Type": "application/json",
        },
        timeout=30,
    )
    resp.raise_for_status()
    body = resp.json()
    return {
        "quote_id": body["quote_id"],
        "totals": body["preview"]["totals"],
        "pricing_version": body.get("pricing_version"),
        "request_id": body.get("request_id"),
    }
