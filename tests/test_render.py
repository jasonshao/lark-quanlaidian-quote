from pathlib import Path

import pytest

from scripts.flow.steps.render import render_and_download


def test_render_pdf_downloads_to_tmp_dir(requests_mock, tmp_path):
    requests_mock.post(
        "http://mock.test/v1/quotes/q_abc/render/pdf",
        json={
            "file_token": "ft_pdf",
            "filename": "演示正餐火锅-全来店-报价单-20260421.pdf",
            "url": "http://mock.test/files/ft_pdf/演示.pdf",
        },
    )
    requests_mock.get(
        "http://mock.test/files/ft_pdf/演示.pdf",
        content=b"%PDF-1.4 fake content",
    )

    result = render_and_download(
        service_url="http://mock.test",
        token="BEARER",
        quote_id="q_abc",
        format="pdf",
        download_dir=tmp_path,
    )

    assert result["file_token"] == "ft_pdf"
    assert result["local_path"].exists()
    assert result["local_path"].read_bytes().startswith(b"%PDF")
    assert result["filename"].endswith(".pdf")


def test_render_xlsx_uses_force_false_by_default(requests_mock, tmp_path):
    # Backend idempotency: render_format(force=False) reuses existing render.
    # We must NOT pass force=true.
    requests_mock.post(
        "http://mock.test/v1/quotes/q_abc/render/xlsx",
        json={"file_token": "ft_xlsx", "filename": "x.xlsx", "url": "http://mock.test/files/ft_xlsx/x.xlsx"},
    )
    requests_mock.get("http://mock.test/files/ft_xlsx/x.xlsx", content=b"PK\x03\x04")

    render_and_download(
        service_url="http://mock.test",
        token="BEARER",
        quote_id="q_abc",
        format="xlsx",
        download_dir=tmp_path,
    )

    req = requests_mock.request_history[0]
    assert "force" not in req.qs
