"""QuoteForm: pydantic schema matching quanlaidian-quote-service's /v1/quotes body.

Field names are the Chinese keys used by the backend; we expose pythonic
aliases for readability in orchestration code. See quanlaidian-quote-service
`app/api/models.py` for the source of truth.
"""

from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, Field, ConfigDict


class QuoteForm(BaseModel):
    """Backend-compatible form with both Chinese and aliased attribute access."""

    model_config = ConfigDict(populate_by_name=True)

    brand: str = Field(alias="客户品牌名称", min_length=1)
    meal_type: Literal["轻餐", "正餐"] = Field(alias="餐饮类型")
    stores: int = Field(alias="门店数量", ge=1, le=30)
    package: str = Field(alias="门店套餐", min_length=1)
    store_modules: list[str] = Field(alias="门店增值模块", default_factory=list)
    hq_modules: list[str] = Field(alias="总部模块", default_factory=list)
    distribution_centers: int = Field(alias="配送中心数量", default=0, ge=0)
    production_centers: int = Field(alias="生产加工中心数量", default=0, ge=0)
    deal_factor: float = Field(alias="成交价系数", default=1.0, gt=0.0, le=1.0)
    override_reason: str = Field(alias="人工改价原因", default="")
    enable_tiered: bool = Field(alias="是否启用阶梯报价", default=False)
    implementation_type: str = Field(alias="实施服务类型", default="")
    implementation_days: int = Field(alias="实施服务人天", default=0, ge=0)

    def to_backend_body(self) -> dict:
        """Serialize with Chinese keys for the backend POST /v1/quotes body."""
        return self.model_dump(by_alias=True, exclude_defaults=False)


def form_hash(form: QuoteForm) -> str:
    """SHA256 of the canonical form body. Used as X-Idempotency-Key.

    Canonicalization: sort lists and dict keys so equivalent forms hash the same.
    """
    body = form.to_backend_body()
    # Sort module lists so ["KDS","成本管理"] == ["成本管理","KDS"]
    for key in ("门店增值模块", "总部模块"):
        if key in body and isinstance(body[key], list):
            body[key] = sorted(body[key])
    canonical = json.dumps(body, sort_keys=True, ensure_ascii=False)
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()
