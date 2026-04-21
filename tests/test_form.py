import pytest
from scripts.flow.form import QuoteForm, form_hash


def test_form_parses_minimal_required_fields():
    form = QuoteForm.model_validate({
        "客户品牌名称": "演示正餐火锅",
        "餐饮类型": "正餐",
        "门店数量": 20,
        "门店套餐": "正餐连锁营销旗舰版",
    })
    assert form.brand == "演示正餐火锅"
    assert form.meal_type == "正餐"
    assert form.stores == 20
    assert form.package == "正餐连锁营销旗舰版"
    assert form.store_modules == []
    assert form.hq_modules == []


def test_form_rejects_stores_out_of_range():
    with pytest.raises(Exception):
        QuoteForm.model_validate({
            "客户品牌名称": "x", "餐饮类型": "正餐",
            "门店数量": 99, "门店套餐": "y",
        })


def test_form_hash_is_deterministic_and_order_independent():
    a = QuoteForm.model_validate({
        "客户品牌名称": "X", "餐饮类型": "正餐",
        "门店数量": 10, "门店套餐": "Y",
        "门店增值模块": ["KDS", "成本管理"],
    })
    b = QuoteForm.model_validate({
        "客户品牌名称": "X", "餐饮类型": "正餐",
        "门店数量": 10, "门店套餐": "Y",
        "门店增值模块": ["成本管理", "KDS"],
    })
    assert form_hash(a) == form_hash(b)


def test_form_hash_differs_on_content_change():
    a = QuoteForm.model_validate({
        "客户品牌名称": "X", "餐饮类型": "正餐",
        "门店数量": 10, "门店套餐": "Y",
    })
    b = QuoteForm.model_validate({
        "客户品牌名称": "X", "餐饮类型": "正餐",
        "门店数量": 11, "门店套餐": "Y",
    })
    assert form_hash(a) != form_hash(b)
