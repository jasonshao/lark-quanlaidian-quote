# lark-quanlaidian-quote

飞书 CLI Skill：餐饮 SaaS 报价端到端工作流（对话 → 算价 → 云盘 → 台账 → 群通知）。

> **一句话**：销售说两句话，飞书里六件事自动发生 —— 30 秒从"客户要报价"到"PDF 归档 + 台账落地 + 群消息通知"全部完成。

## 谁在用

内部餐饮 SaaS 销售团队。原手工流程约 30 分钟、涉及 5+ 工具窗口：手填 Excel → 老板审价 → 导 PDF → 发群/邮件 → 手工登台账 → 排下次跟进。接入本 skill 后：**一次对话，端到端 30 秒完成**，工作流效率提升约 60 倍。

## 它是什么

基于 [larksuite/cli](https://github.com/larksuite/cli) 和自研 `quanlaidian-quote-service` 后端（算价 + PDF/Excel 渲染），编排三个飞书 domain：

- **Drive**：PDF/Excel 自动归档到客户文件夹
- **Base**：销售台账一行自动写入（12 字段含金额、链接、销售）
- **IM**：销售群自动推送 interactive 卡片（品牌/金额/三个跳转按钮）

## 架构

```
[Claude Code / lark-cli agent]
      │ 读 SKILL.md 对话收集参数
      ▼
scripts/run_flow.py
  ├─ POST /v1/quotes       → quanlaidian-quote-service
  ├─ POST /render/{pdf,xlsx}
  ├─ lark-cli drive upload → 飞书云盘
  ├─ lark-cli base record  → 飞书多维表格
  └─ lark-cli im message   → 飞书 IM
```

所有对外调用在 `run_flow.py` 一处；前向状态机 + 幂等，失败可从断点续跑。

## 安装与使用

### 前置

- Python 3.10+
- [lark-cli](https://github.com/larksuite/cli) 已安装 + `lark-cli profile add <name>` 配好测试或生产飞书应用
- `quanlaidian-quote-service` 后端可访问（本仓库 `examples/mock_server.py` 提供零配置 demo 版本）

### 三步跑通

```bash
# 1. 克隆 & 装依赖
git clone https://github.com/<you>/lark-quanlaidian-quote
cd lark-quanlaidian-quote
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. 配置（复制模板，填入 6 项资源）
cp .env.example .env
$EDITOR .env
# 首次还需创建 Base 台账表：
python scripts/base_schema.py --app-token <bascnXXX>

# 3. 跑一次
python scripts/run_flow.py run --form-json examples/form.sample.json
# 期望 stdout: {"status":"ok",...} 同时飞书云盘/Base/群都有变化
```

### 想零配置先看看？

```bash
# 启动 mock 后端 + 用 dry-run 模式跑 lark-cli
python examples/mock_server.py &
QUOTE_SERVICE_URL=http://localhost:8000 \
QUOTE_SERVICE_TOKEN=MOCK \
FEISHU_BASE_APP_TOKEN=MOCK FEISHU_BASE_TABLE_ID=MOCK \
FEISHU_DRIVE_FOLDER_TOKEN=MOCK FEISHU_IM_GROUP_CHAT_ID=MOCK \
LARK_CLI_DRYRUN=1 \
  python scripts/run_flow.py run --form-json examples/form.sample.json
# 输出 status:ok 的同时，所有飞书动作都是 dry-run，无实际副作用
```

## 和 Agent 结合

`SKILL.md` 让任何支持 skills 的 AI agent（Claude Code、Cursor、Gemini CLI、或 lark-cli 内置）理解这个技能：

```
销售: 给演示正餐火锅做个报价，20 家店，正餐旗舰版
Agent: 需要加什么增值模块吗？
销售: 加厨房KDS就行
Agent: [自动调用 run_flow.py...]
Agent: 报价已出：标价 ¥31.86 万 → 成交 ¥22.30 万（折扣 30%）。
       PDF: https://...  Excel: https://...  台账: https://...
       销售群已通知。
```

## 开发

```bash
pytest              # 全绿，0 飞书 token 依赖
pytest -v tests/test_e2e_mock.py  # 端到端（mock + dry-run）
```

CI 见 `.github/workflows/ci.yml`：pytest + gitleaks。

## 安全

- 所有敏感值在 `.env`（被 `.gitignore` 忽略）
- 真实客户名、价格表、飞书资源 ID 全部从仓库剥离；`examples/` 使用脱敏演示数据
- 飞书用户 token 由 `lark-cli profile` 管理，代码不落 token

## 许可

MIT
