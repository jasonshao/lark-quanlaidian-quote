---
name: lark-quanlaidian-quote
version: 0.1.0
description: "餐饮 SaaS 报价端到端飞书工作流：对话收集 → 算价 → 云盘归档 → 多维表格台账 → 群卡片通知"
metadata:
  requires:
    bins: ["lark-cli", "python3"]
  cliHelp: "lark-cli profile list"
---

# lark-quanlaidian-quote (0.1.0)

**CRITICAL — 开始前 MUST 先用 Read 工具读取 `../lark-shared/SKILL.md`，其中包含认证、权限处理。**

餐饮 SaaS 报价 Agent。销售用自然语言说"给 X 品牌报 N 家店 XX 套餐"，Agent 自动完成：算价 → PDF/Excel 生成 → 飞书云盘归档 → 多维表格台账 → 销售群卡片通知。

## 何时使用此 skill

用户说类似下面的话时触发：
- "给 XX 做个报价"
- "XX 品牌要开 N 家店"
- "帮 XX 算个价"
- "XX 正餐/轻餐 N 店 XX 版"

## 工作流（Agent 必须遵循）

### 1. 收集参数

以下是**必填**字段；缺哪个用最少打字、优先选择的方式追问：

| 字段 | 类型 | 示例 |
|---|---|---|
| 客户品牌名称 | 文本 | `演示正餐火锅` |
| 餐饮类型 | `轻餐` 或 `正餐` | `正餐` |
| 门店数量 | 1-30 的整数 | `20` |
| 门店套餐 | 文本 | `正餐连锁营销旗舰版` |

以下是**选填**字段；不问，除非用户主动提：
- 门店增值模块（多选，如"厨房KDS"、"成本管理"）
- 总部模块（多选）
- 配送中心数量 / 生产加工中心数量（仅当对应模块勾选时问）
- 成交价系数（0.01-1.0，默认 1.0 即无折扣）
- 人工改价原因（仅当成交价系数 ≠ 1.0 时必填）
- 实施服务类型 / 人天

**策略**：一次只问一个字段。能用"A 还是 B"形式就不用开放式。

### 2. 发起流程

参数齐全后，写入临时 JSON 文件并调用 run_flow.py：

```bash
cat > /tmp/quanlaidian-form-$(date +%s).json <<'JSON'
{
  "客户品牌名称": "演示正餐火锅",
  "餐饮类型": "正餐",
  "门店数量": 20,
  "门店套餐": "正餐连锁营销旗舰版",
  "门店增值模块": ["厨房KDS"]
}
JSON

python3 scripts/run_flow.py run --form-json /tmp/quanlaidian-form-*.json
```

### 3. 解读结果

`run_flow.py` stdout 是一行 JSON：

```json
{
  "status": "ok",
  "quote_id": "q_...",
  "totals": {"list": 318600, "final": 318600},
  "drive": {"pdf_url": "...", "xlsx_url": "..."},
  "record": {"record_url": "..."},
  "im": {"message_id": "om_..."}
}
```

用中文告诉销售：标价、成交价、折扣、三个链接（PDF、Excel、台账）。

### 4. 错误处理

如果 stdout 是 `{"status":"failed",...}`，告诉销售"第 N 步失败"，并提示重试命令：

```bash
python3 scripts/run_flow.py resume <request_id>
```

`request_id` 从失败输出里取。

## 禁止

- 不要猜测缺失参数的默认值（除"成交价系数=1.0"这一个默认）
- 不要自己直接调 `lark-cli drive/base/im`；所有飞书动作只能通过 run_flow.py
- 不要在对话里展示 Bearer token 或 file_token
