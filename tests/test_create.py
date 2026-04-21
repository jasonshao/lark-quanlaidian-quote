import pytest
import requests

from scripts.flow.form import QuoteForm, form_hash
from scripts.flow.steps.create import create_quote


def _sample_form() -> QuoteForm:
    return QuoteForm.model_validate({
        "客户品牌名称": "演示正餐火锅",
        "餐饮类型": "正餐",
        "门店数量": 20,
        "门店套餐": "正餐连锁营销旗舰版",
    })


def test_create_quote_posts_form_with_idempotency_header(requests_mock):
    form = _sample_form()
    requests_mock.post(
        "http://mock.test/v1/quotes",
        json={
            "request_id": "req_123",
            "quote_id": "q_abc",
            "preview": {"totals": {"list": 318600, "final": 318600}},
            "pricing_version": "small-segment-v2.3",
        },
    )

    result = create_quote(
        service_url="http://mock.test",
        token="BEARER_XYZ",
        form=form,
    )

    assert result["quote_id"] == "q_abc"
    assert result["totals"]["list"] == 318600

    history = requests_mock.request_history
    assert len(history) == 1
    req = history[0]
    assert req.headers["Authorization"] == "Bearer BEARER_XYZ"
    assert req.headers["X-Idempotency-Key"] == form_hash(form)
    body = req.json()
    assert body["客户品牌名称"] == "演示正餐火锅"
    assert body["门店数量"] == 20


def test_create_quote_raises_on_http_error(requests_mock):
    requests_mock.post(
        "http://mock.test/v1/quotes",
        status_code=401,
        json={"detail": "unauthorized"},
    )
    with pytest.raises(requests.HTTPError):
        create_quote(
            service_url="http://mock.test",
            token="bad",
            form=_sample_form(),
        )
