# Design Doc — `lark-quanlaidian-quote`

> **Status**: v1.0 (frozen for 飞书 CLI Skill 大赛 2026 提交)
> **Owner**: quanlaidian 销售工具组
> **Audience**: 飞书 CLI Skill 评委、未来贡献者、Agent 厂商集成方
> **Scope**: 本文档完整描述 `lark-quanlaidian-quote` Skill 的业务背景、架构、契约与权衡。任何代码改动都应在此回写一笔。

---

## 1. 背景与问题陈述

### 1.1 业务现状

quanlaidian 是一个面向中型连锁餐饮的 SaaS 服务商。销售团队每天会接到 5-15 个**询价请求**：客户（火锅 / 正餐 / 轻餐连锁）告诉销售"我有 N 家门店、想要 X 套餐 + Y 增值模块"，销售需要：

1. 在内部估价表（一个有几百行公式的 Excel 模板）里手填客户参数
2. 找老板审一道（折扣超过 20% 时强制审）
3. 把估价结果导出 PDF + Excel 两份
4. 上传到客户专属云盘文件夹（飞书云盘）
5. 在销售群（飞书 IM）发一条带链接的消息
6. 在销售台账（飞书多维表格）手填一行（12 列：客户、品牌、门店数、套餐、标价、成交价、折扣率、PDF 链接、Excel 链接、销售、跟进状态、下次跟进日期）
7. 在 CRM（外部）记一笔下次跟进

### 1.2 痛点量化

我们采样了 30 单：

| 项目 | 中位耗时 | 75 分位 | 主要时间消耗 |
|---|---|---|---|
| 估价 | 4 min | 7 min | Excel 公式调试、客户参数复核 |
| PDF/Excel 生成 | 3 min | 5 min | "另存为"+ 命名规范、清理批注 |
| 云盘归档 | 5 min | 9 min | 找客户文件夹、检查重名、上传等待 |
| 群通知 | 4 min | 6 min | 复制链接、组织文案、@ 销售 |
| 台账登记 | 6 min | 10 min | 跨窗口复制粘贴、字段对齐 |
| CRM 记录 | 3 min | 5 min | （**本 skill 暂不覆盖**） |
| **合计** | **~25 min** | **~42 min** | 5 个工具 / 窗口 |

错误率：抽样里 8/30 有至少一处复制粘贴错误（数字小数点、链接错配），其中 2 单流到客户后才发现。

### 1.3 我们想拿到什么

* **效率**：把 25 min 的"对话→落地"压到 ≤30 s，并把 2-5 之间的所有窗口切换消灭掉。
* **可审计**：每一单跑完都能在台账里溯源（quote_id、销售、时间、改价原因）。
* **零人为搬运错**：金额/链接全程程序生成，销售只负责"对话收集参数"和"事后核对"。
* **足够轻**：不引入新的 SaaS 后台，不要求销售装 IDE，**复用销售已经在用的飞书 + 一个命令行**。

### 1.4 为什么是"飞书 CLI Skill"而不是其他形态

| 选项 | Pros | Cons | 决策 |
|---|---|---|---|
| 飞书机器人 (webhook) | 不需要任何客户端 | 后台运维负担、状态难持久、无法复用 lark-cli 鉴权、Agent 不可拓展 | ❌ |
| 飞书原生 Bot SDK 嵌进自研服务 | 高定制 | 鉴权/限流自己处理、跨多 domain 凭证管理零散 | ❌ |
| 一个 CLI 脚本 + AI Agent + lark-cli | 销售已经会用对话；lark-cli 一处接管所有 Feishu 鉴权；Agent 可换 (Claude Code / Gemini CLI / Cursor / lark-cli 内置) | 销售机器需装 lark-cli + Python | ✅ **本 skill** |

> 结论：**对话式 + Agent 编排 + CLI 执行**是当下唯一能把"自然语言收集参数"和"飞书三 domain 落地"在 30 s 内串起来、又不引入新后台的形态。这也是飞书 CLI 在 2026/3/28 开源后我们立刻试图填的位。

---

## 2. 目标与非目标

### 2.1 目标 (Goals)

G1. **30 秒端到端**：从销售说完最后一个参数，到飞书里六件事全部落地，p50 ≤ 30 s。
G2. **断点续跑**：任何一步失败，下一次执行可从断点恢复（不重复云盘上传、不重复台账写）。
G3. **幂等**：同一份 form 反复 run 不会产生多份报价 / 多条台账 / 多份 PDF。
G4. **零飞书 SDK 依赖**：所有飞书侧操作只走 `lark-cli` 子进程，便于跨语言/跨 Agent 复用。
G5. **Agent 中立**：`SKILL.md` 不绑定任何特定 AI 厂商；任何支持 "skill / system prompt + tool use" 的 Agent 都能驱动。
G6. **离线可演示**：评审/新销售试用 0 飞书凭证可跑 demo，并能 `diff` 出预期产物。
G7. **隐私安全**：仓库里没有任何真实客户名 / 价格表 / 飞书资源 ID / 个人信息。

### 2.2 非目标 (Non-goals)

NG1. CRM 同步（暂不覆盖；保留作为"故意留缺口"展示 Agent 二次扩展价值）。
NG2. 跨销售并发抢同一报价 ID（业务侧不会发生；不做分布式锁）。
NG3. 跨租户多 app 配置（一个销售团队 = 一个 lark-cli profile = 一个 skill 实例）。
NG4. 报价审批流（重折扣审仍走线下；本 skill 只在 `人工改价原因` 里要求文字解释）。
NG5. 完整的 PDF/Excel 渲染（这是 `quanlaidian-quote-service` 后端的职责，本仓库只负责"调用 + 归档"）。

---

## 3. 顶层架构

```
                  ┌────────────────────────────────────┐
                  │   AI Agent (Claude Code / Gemini   │
                  │   CLI / Cursor / lark-cli 内置 …)  │
                  │   1. 读 SKILL.md                   │
                  │   2. 自然语言收集 form              │
                  │   3. 写 /tmp/quanlaidian-form-*.json│
                  │   4. exec scripts/run_flow.py       │
                  └──────────────┬─────────────────────┘
                                 │ stdin: form.json
                                 │ stdout: 1 line JSON envelope
                                 ▼
        ┌────────────────────────────────────────────────┐
        │  scripts/run_flow.py  (CLI entrypoint)         │
        │     ├─ load_or_init_state(request_id)          │
        │     ├─ Flow.run() 6-step orchestrator          │
        │     │     ├─ ① POST /v1/quotes  (idempotent)   │
        │     │     ├─ ② POST /render/pdf                │
        │     │     ├─ ③ POST /render/xlsx               │
        │     │     ├─ ④ lark-cli drive list+upload      │
        │     │     ├─ ⑤ lark-cli base record search+    │
        │     │     │       create   (upsert by quote_id)│
        │     │     └─ ⑥ lark-cli im message send (card) │
        │     └─ persist state after each step           │
        └──────────────┬───────────────────┬─────────────┘
                       │ HTTP              │ subprocess
                       ▼                   ▼
        ┌────────────────────────┐   ┌────────────────────┐
        │ quanlaidian-quote-     │   │ lark-cli           │
        │ service (algo + render)│   │  (auth via profile)│
        └────────────────────────┘   └────────┬───────────┘
                                              │
                                              ▼
                                     飞书 (Drive / Base / IM)
```

设计要点：

- **唯一对外出口**：`run_flow.py` 是仓库里唯一发 HTTP / 启子进程的地方；其他文件都是纯函数 + dataclass。
- **lark-cli 单边封装**：`scripts/flow/larkcli.py` 是仓库内**唯一**的 `lark-cli` subprocess 调用点，其他 step 文件只调它的 `cli.run([...])`。
- **状态外置**：每个 request 一个 JSON 文件落在 `.quanlaidian-flow-state/`；进程崩 / 机器重启 / 手 Ctrl-C，下次 `resume <request_id>` 可续跑。
- **幂等三道关**：① 后端 `X-Idempotency-Key`；② Drive 通过文件名带 quote_id 去重；③ Base 通过 quote_id 字段先 search 再 create。
- **Agent 是 thin client**：Agent 不知道有几步、不直接发飞书请求，只负责"问问题→写 JSON→读 envelope JSON→中文复述给销售"。

---

## 4. 数据模型

### 4.1 `QuoteForm` （`scripts/flow/form.py`）

输入端 schema，对齐后端 `quanlaidian-quote-service` 的 `/v1/quotes` body。Pydantic 双语：业务侧用中文 alias，代码侧用英文 attr。

| 字段 (alias) | 类型 | 必填 | 校验 | 说明 |
|---|---|---|---|---|
| `客户品牌名称` | str | ✅ | min_length=1 | 显示在 Base 台账"客户品牌"列 |
| `餐饮类型` | Literal[轻餐, 正餐] | ✅ | — | 决定后端走哪张定价表 |
| `门店数量` | int | ✅ | 1 ≤ N ≤ 30 | >30 走人工大客户流程，不在本 skill |
| `门店套餐` | str | ✅ | min_length=1 | 完整套餐名（如"正餐连锁营销旗舰版"） |
| `门店增值模块` | list[str] | ❌ | — | 多选 |
| `总部模块` | list[str] | ❌ | — | 多选 |
| `配送中心数量` | int | ❌ | ≥0 | 仅当勾选配送相关模块时 >0 |
| `生产加工中心数量` | int | ❌ | ≥0 | 同上 |
| `成交价系数` | float | ❌ | (0, 1] | 默认 1.0；<1 时必须填 `人工改价原因` |
| `人工改价原因` | str | ❌ | — | 当 `成交价系数 ≠ 1.0` 时由 SKILL.md 强制收集 |
| `是否启用阶梯报价` | bool | ❌ | — | 后端可选特性 |
| `实施服务类型` | str | ❌ | — | |
| `实施服务人天` | int | ❌ | ≥0 | |

### 4.2 `form_hash` 与 `request_id`

```python
form_hash = "sha256:" + sha256(canonical_json(form))  # canonical: sort lists + sort keys
request_id = "req_" + utc_yyyymmddhhmmss
```

- `form_hash` 由表单内容唯一决定。同样的客户/门店/套餐两次报价 → 同样 hash → 用作后端 `X-Idempotency-Key`。
- `request_id` 由本机时钟生成，不依赖 hash。原因：销售可能"同样的参数再来一遍 just to confirm"，业务上算两个 request；但他们各自向后端打 idempotency key 一致 → 后端去重不重新算。
- **规则**：`load_or_init_state` 检查 state 文件里的 `form_hash` 必须和当次调用的 `form_hash` 一致；不一致直接 raise（防止 resume 时换了表单）。

### 4.3 `FlowState` （`scripts/flow/state.py`）

```python
{
  "request_id": "req_20260501123045",
  "form_hash": "sha256:...",
  "steps": {
    "create": {"status": "done", "data": {"quote_id": "q_...", "totals": {...}}, "attempts": 1, "error": "", "last_at": "..."},
    "pdf":    {"status": "done",   ...},
    "xlsx":   {"status": "done",   ...},
    "drive":  {"status": "done",   "data": {"pdf_url": "...", "xlsx_url": "...", "reused": false}},
    "base":   {"status": "done",   "data": {"record_id": "...", "url": "..."}},
    "im":     {"status": "pending","data": {}},
  }
}
```

- 每步的 `data` 是后续步骤需要的最小集合（不存敏感原始 token / 也不存大对象）。
- `attempts` 累计失败次数；`error` 只存最近一次错误的简短描述（不存堆栈，避免泄露路径/内部主机名）。
- 写盘走 `tempfile + os.replace`，保证原子（防 ctrl-C 写到一半留下残文件）。

### 4.4 Base 台账 schema （`scripts/base_schema.py` 一键创建）

| 字段名 | 类型 | 来源 |
|---|---|---|
| 客户品牌 | 多行文本 | `form.客户品牌名称` |
| 餐饮类型 | 单选 | `form.餐饮类型` |
| 门店数 | 数字 | `form.门店数量` |
| 套餐 | 多行文本 | `form.门店套餐` |
| 标价合计（元） | 数字 | `quote.totals.list` |
| 成交价合计（元） | 数字 | `quote.totals.final` |
| 折扣率 | 数字 | 派生：`1 - final/list` |
| PDF链接 | 链接 | `drive.pdf_url` |
| Excel链接 | 链接 | `drive.xlsx_url` |
| 报价ID | 多行文本 | `quote.quote_id`（**索引列** — 用于 upsert） |
| 创建时间 | 日期 | UTC ISO |
| 销售 | 多行文本 | `env.SALES_NAME` |

---

## 5. 状态机：六步编排

`scripts/flow/machine.py` 中的 `Flow` 是核心。语义：

> 顺序串行 6 步；每步幂等；任意步失败立即停，写状态、退码 1、stdout 是 envelope JSON 含 `status:failed` + `failed_step` + `resume_hint`。`resume <request_id>` 跳过 `done` 步，从第一个非 done 步起跑。

### 5.1 步骤定义

| # | step | 调用 | 幂等机制 | data 输出 |
|---|---|---|---|---|
| 1 | `create` | `POST /v1/quotes` 带 `X-Idempotency-Key: form_hash` | 后端去重 | `{quote_id, totals: {list, final}}` |
| 2 | `pdf` | `POST /render/pdf` 然后 `GET /artifacts/{quote_id}.pdf` | 后端"同 quote_id 同格式只渲染一次"；本地按 `<download_dir>/<quote_id>.pdf` 命名 | `{local_path}` |
| 3 | `xlsx` | 同上 | 同上 | `{local_path}` |
| 4 | `drive` | `lark-cli drive file list --folder_token <fld>` 然后 `lark-cli drive upload --parent <fld> --file <path>` | list 时若 `name == <quote_id>.pdf/xlsx` 则跳过上传 | `{pdf_url, xlsx_url}` |
| 5 | `base` | `lark-cli base record search` 按 `报价ID == quote_id`；命中则跳，否则 `base record create` | 索引列查找 | `{record_id, url}` |
| 6 | `im` | `lark-cli im message send --msg_type interactive --content <card_json>` | 由本步状态文件保护；步骤完成后即不再发 | `{message_id}` |

### 5.2 跳过规则

```python
if state.steps[name].status == StepStatus.DONE:
    return  # 不重发任何 HTTP / 子进程
```

→ 所有外部副作用都被 `done` 标记保护。

### 5.3 重试策略 (`scripts/flow/retry.py`)

固定退避：`(1, 4, 15)` 秒，共 3 次。**不**做指数翻倍；不抖动。理由：

- step 全是同步 HTTP / 子进程；非高并发场景；倒数第一次给"网络抽风" 15 s 已足够。
- 抖动加进来就要进 random，单测变得脆。

仅对**显式声明的可恢复错误**重试（连接超时、5xx、子进程 rc != 0 中的 timeout-like 信息）；4xx、参数错、`form_hash` mismatch 这类**永久错误立即失败**。

### 5.4 错误 envelope

```json
{
  "status": "failed",
  "request_id": "req_...",
  "failed_step": "drive",
  "error": "lark-cli drive upload ... failed (rc=1): network timeout",
  "resume_hint": "python3 scripts/run_flow.py resume req_..."
}
```

Agent 拿到后，用中文告诉销售"第 4 步（云盘上传）超时了，可以一会儿再试这条命令"。**Agent 不要自己马上重试**——这会把退避策略覆写成"三次失败 + 三次再失败 = 6 次连击"。

---

## 6. 幂等 — 三道关

我们对幂等持很高的执着，因为 (a) 销售心理上会反复点；(b) 飞书云盘里两份同名 PDF 是大噪音；(c) 台账重复行老板会立刻发现。

### 6.1 第一关：后端 `/v1/quotes` 的 `X-Idempotency-Key`

```http
POST /v1/quotes
X-Idempotency-Key: sha256:abcd...
{...form body...}
```

后端 (`quanlaidian-quote-service`) 维护一张 `idem_key → quote_id` 的 7-day TTL 表。同 key 直接返回原 quote_id。结果：**form 不变 → quote_id 不变**，下游所有"含 quote_id"的资源命名也不变。

### 6.2 第二关：Drive list + name match

drive 步骤先 `lark-cli drive file list`，遍历 `name`：

```python
for f in listing.get("files", []):
    if f["name"] == local_path.name:  # e.g. "q_2x9k4f.pdf"
        return {"file_token": f["token"], "url": f["url"], "reused": True}
```

由于 `local_path.name = f"{quote_id}.{ext}"`（在 `steps/render.py` 强制），命名空间和 quote_id 严格绑定。

### 6.3 第三关：Base upsert by `报价ID`

```python
existing = cli.run(["base", "record", "search", ..., "--filter", f'报价ID = "{quote_id}"'])
if existing.get("records"):
    return {"record_id": existing["records"][0]["record_id"], "url": ...}
return cli.run(["base", "record", "create", ...])
```

### 6.4 IM 不做幂等

IM 第六步**不**做"同一报价不重复发卡片"——因为状态机本身保护它（step done 不重跑）。如果状态文件被人工删了，那确实会重发；这是预期行为（"删 state = 我想重发"）。

---

## 7. 外部契约

### 7.1 `quanlaidian-quote-service` HTTP

```
POST /v1/quotes
  Headers: Authorization: Bearer <token>, X-Idempotency-Key: <hash>
  Body: <QuoteForm.to_backend_body()>
  → 200 {"quote_id": "q_...", "totals": {"list": int, "final": int}, "items": [...]}

POST /render/{format}
  Path format: pdf | xlsx
  Body: {"quote_id": "q_..."}
  → 200 {"artifact_url": "https://.../q_xxx.pdf"} (后端做格式渲染幂等)

GET /artifacts/{quote_id}.{format}
  → 200 binary (Content-Type 对应)
```

### 7.2 `lark-cli` 子命令

> 我们故意**只**用 `drive`/`base`/`im` 三个 domain。`larkcli.py` 是唯一边界；其他文件不直接调 `subprocess`。

| 子命令 | 用法 | 用途 |
|---|---|---|
| `drive file list --folder_token <fld>` | dedup | 上传前查重名 |
| `drive upload --parent <fld> --file <path>` | upload | 实际归档 |
| `base record search --app_token --table_id --filter "字段=值"` | upsert read | 找已有报价 |
| `base record create --app_token --table_id --fields <json>` | upsert write | 写台账 |
| `im message send --receive_id <chat_id> --msg_type interactive --content <json>` | 群通知 | 发卡片 |

### 7.3 Agent 契约（SKILL.md）

`SKILL.md` 是**唯一**告诉 Agent 怎么用此 skill 的地方。它必须：

- **agent-neutral**：不要用任何厂商专属术语（"Read 工具"、"Tool use"、"function calling"）；用通用动词"读取/打开/写入/执行"。
- **顺序固定**：第 1 节 = "什么时候触发"，第 2 节 = "收什么参数"，第 3 节 = "怎么执行"，第 4 节 = "怎么解读结果"，第 5 节 = "出错怎么办"。
- **禁止清单显式列**：例如"不要自己直接调 lark-cli drive/base/im"。

---

## 8. 安全与隐私

### 8.1 凭证

| 凭证 | 存放 | 备注 |
|---|---|---|
| `QUOTE_SERVICE_TOKEN` | 销售本机 `.env` | 后端组管理员发；建议 30 天轮换 |
| 飞书 user/app token | `lark-cli profile` 内部存储 | **从不**进入仓库 / 状态文件 / 日志 |
| `FEISHU_*_TOKEN` (folder/app/table/chat ID) | `.env` | 是资源 ID（公开可见也能用，但需配合鉴权），仍保密 |

### 8.2 仓库 hygiene

- `.gitignore` 排除 `.env*`、`*.token`、`.lark-cli/`、`tmp/`、`.quanlaidian-flow-state/`
- CI 跑 `gitleaks`（`.github/workflows/ci.yml`）每个 PR 一次
- 仓库 pytest `tests/test_privacy.py` 在每次本地测试时也扫一遍：客户名白名单、电话/邮箱/file_token 模式、Base/Drive ID 模式
- 所有示例 fixture 在 `examples/` 下，客户名一律是 "演示正餐火锅" / "示例轻餐" 等**显式虚构**前缀
- `examples/pricing_baseline.example.json` 不是真定价表（量级正确但绝对值偏移）

### 8.3 日志

- `run_flow.py` stdout = 1 行 JSON envelope；不打 token / 用户名 / 完整 form
- `larkcli.py` dry-run log 只记 `args`（命令行），不记 stdout/stderr
- 失败信息只截前 300 字符，不带堆栈

---

## 9. Agent 中立性

我们刻意让 SKILL.md 在 4 个 Agent 上都通：

| Agent | 我们如何兼容 |
|---|---|
| Claude Code | 默认目标；SKILL.md 写法本身是 Anthropic skills 风格 |
| Cursor | Cursor 支持读项目根 markdown 作 system prompt；SKILL.md 在根目录 ✓ |
| Gemini CLI | 同上 |
| lark-cli 内置 agent | 接受 frontmatter + markdown |

**做到的**：
- 不写 "use the Read tool" 这类厂商动词
- 工作流写"读取 SKILL.md"而非"call file_read function"
- frontmatter 字段集合是公共最小集 (`name`, `version`, `description`, `metadata`)

**没做到 / 需厂商配合**：
- frontmatter 里的 `requires.bins` 字段不是所有 Agent 都识别 — 我们文档化了它，但不强求

---

## 10. 测试策略

### 10.1 测试金字塔

```
        ┌────────────────────┐
        │   e2e-mock + diff  │  test_e2e_mock.py + test_golden.py
        ├────────────────────┤
        │   step contract    │  test_create.py / drive.py / base.py / im.py / render.py
        ├────────────────────┤
        │   unit (pure)      │  test_form.py / state.py / retry.py / machine.py / larkcli.py
        ├────────────────────┤
        │   privacy / lint   │  test_privacy.py
        └────────────────────┘
```

### 10.2 离线 demo 与 Golden file

设计原则：**评委 0 凭证 0 lark-cli 安装**，运行：

```bash
LARK_CLI_DRYRUN=1 python scripts/run_flow.py run --form-json examples/form.sample.json
# 产出 stdout JSON envelope，可与 examples/quote-response.sample.json diff 比较
```

`tests/test_golden.py` 把这一过程用 pytest 固化：

1. 启动 `examples/mock_server.py`（FastAPI，无外部依赖）
2. 用 `examples/form.sample.json` 跑一遍 flow
3. 把得到的 envelope 中**确定性字段**（quote_id pattern、totals.list、totals.final、`drive.pdf_url` 形如 `https://dry/drive/q_...pdf`、各步 url 模板）抽出
4. 和 `examples/quote-response.sample.json` 做断言

**如果 golden 变了**：要么是产品行为变了（更新 sample），要么是 bug。任何 PR 改了 envelope shape 都要在 PR 里解释。

### 10.3 隐私扫描 pytest

`tests/test_privacy.py` 扫整个仓库：

- 禁词列表：客户真实品牌名（外部团队维护的清单 — repo 里只放公开虚构示例）
- 模式扫描：
  - `\b1[3-9]\d{9}\b` 中国大陆手机号
  - `[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[A-Z|a-z]{2,}` 邮箱
  - `bascn[A-Za-z0-9]{14,}` Base app token
  - `tbl[A-Za-z0-9]{14,}` table id
  - `fldb[A-Za-z0-9]{12,}` folder token
  - `oc_[A-Za-z0-9]{20,}` chat id
  - `t-[A-Za-z0-9]{20,}` tenant access token 模式
- 例外白名单：`*.example.json` 内部使用的 `MOCK` / `DRY_*` / 文档片段

---

## 11. 离线演示

### 11.1 Quick demo (无任何凭证)

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python examples/mock_server.py &        # 监听 8000
QUOTE_SERVICE_URL=http://localhost:8000 \
QUOTE_SERVICE_TOKEN=MOCK \
FEISHU_BASE_APP_TOKEN=MOCK FEISHU_BASE_TABLE_ID=MOCK \
FEISHU_DRIVE_FOLDER_TOKEN=MOCK FEISHU_IM_GROUP_CHAT_ID=MOCK \
LARK_CLI_DRYRUN=1 \
  python scripts/run_flow.py run --form-json examples/form.sample.json
```

输出（截）：

```json
{
  "status": "ok",
  "request_id": "req_20260501082314",
  "quote_id": "q_2x9k4f",
  "totals": {"list": 318600, "final": 318600},
  "drive": {"pdf_url": "https://dry/drive/q_2x9k4f.pdf", "xlsx_url": "..."},
  "record": {"url": "https://dry/base/..."},
  "im": {"message_id": "DRY_MSG"}
}
```

### 11.2 Demo 数据策略

- `examples/form.sample.json` 客户名 `演示正餐火锅`（显式标"演示"二字）
- `examples/pricing_baseline.example.json` 是虚构基准表（量级正确，绝对值不准）
- `examples/state.sample.json` 给一份"中途失败、待 resume"的状态，便于演示 resume 路径
- `examples/card.sample.json` 给一份完整 card 渲染结果，便于不连飞书时也能看 UI

### 11.3 故意留缺口（"Agent 价值" 展示）

我们**不**在仓库里实现以下能力，**故意**让 Agent / 评委加进来：

1. **CRM 同步**：基于 envelope 里的 `record.url`，让 Agent 在销售完成对话后追加一个"创建 Salesforce/Notion record"的副流程。
2. **跟进提醒**：state 文件里其实存了 `created_at`；让 Agent 在 7 天后用 lark-cli `calendar` 创建提醒——这一步本 skill 不做，作为 Agent 二次发挥的空间。
3. **多语言销售场景**：现在所有交互是中文；切换到英文销售时，由 Agent 翻译 `SKILL.md` 的提问模板即可。
4. **批量报价**（10 个客户串报）：现在一次跑一单；Agent 可以拿一份 Excel 批量调 `run_flow.py`。

---

## 12. 部署 / 运行环境

| 项 | 要求 |
|---|---|
| Python | 3.10+ |
| 依赖 | 见 `requirements.txt`（pydantic, requests, fastapi, uvicorn, python-dotenv, pytest, httpx） |
| `lark-cli` | 已安装 + `lark-cli profile add <name>` 配过；二进制名假定 `lark-cli` |
| 飞书侧准备 | 1 个文件夹 (folder_token) + 1 张 Base 表（用 `scripts/base_schema.py --app-token <bascnXXX>` 一键创建）+ 1 个销售群 (chat_id) |
| 后端 | `quanlaidian-quote-service` ≥ v0.4 (含 `/v1/quotes` + `/render/{pdf,xlsx}`)；本地 demo 可用 `examples/mock_server.py` |

### 12.1 配置文件

`.env`：
```
QUOTE_SERVICE_URL=...
QUOTE_SERVICE_TOKEN=...
FEISHU_BASE_APP_TOKEN=...
FEISHU_BASE_TABLE_ID=...
FEISHU_DRIVE_FOLDER_TOKEN=...
FEISHU_IM_GROUP_CHAT_ID=...
SALES_NAME=张三   # 可选；缺省 "销售"
```

启动检查：`run_flow.py` 启动时校验所有 `REQUIRED_ENV` 不为空，缺哪个 `exit 2` 并提示。

### 12.2 运行时目录布局

```
<repo-root>/
  .env                        # 个人凭证（gitignored）
  .quanlaidian-flow-state/    # 每 request 一个 JSON（gitignored）
  tmp/                        # 渲染下载的 PDF/Excel（gitignored）
```

---

## 13. 可观测性

- 标准 stdout = 一行 envelope JSON（机器友好）
- 状态目录 `.quanlaidian-flow-state/<request_id>.json` 是事实来源
- 用 `python scripts/run_flow.py status <request_id>` 一行命令查
- 如果接到投诉"我跑了但报价没出来"，运维路径：
  1. `python scripts/run_flow.py status <id>` 看哪步 done / failed
  2. 看 `error` 字段；4xx 类 → 表单问题；5xx / 子进程错 → 网络/lark-cli 问题
  3. 修后 `resume <id> --form-json <same-form-file>`

---

## 14. Roadmap

| 版本 | 主题 | 备注 |
|---|---|---|
| v0.1 (本次提交) | 6 步全通 + e2e mock + golden + privacy | 大赛冻结版本 |
| v0.2 | 大客户流程（>30 门店）路由到人工 | 非本 skill 范围；触发后 Agent 给提示 |
| v0.3 | 跟进提醒（lark-cli calendar）| Agent 已可现场实现，故 v0.x 不内嵌 |
| v0.4 | 批量报价 | 同上 |
| v0.5 | CRM 同步 | 看用户呼声 |

---

## 15. 设计权衡

### 15.1 为什么不用 SDK 而用 lark-cli 子进程？

- 测试简单：`LARK_CLI_DRYRUN=1` 一行环境变量就能跑离线 e2e
- Agent / 多语言生态友好：未来想用 Go / TS 重写 orchestrator，lark-cli 接口不变
- 鉴权解耦：`lark-cli profile` 是销售自己管，本 skill 不需碰 token
- 缺点：subprocess 启动 50–100 ms / 调用，6 步约 0.5 s 损耗 — 在 30 s 目标下完全可接受

### 15.2 为什么状态用 JSON 文件而不是 SQLite？

- 销售机器无 DB 期望；JSON 适合 grep / 直接看
- 单 writer（一次只跑一单）；无并发问题
- 体积小：每文件 < 5 KB
- 缺点：跨机器迁移 / 报表分析弱 — 不在范围

### 15.3 为什么 form_hash 不直接用作 request_id？

- 重复报价是合法业务行为（"同一客户同一报价我再过一遍流程"），需要 2 个 request_id
- request_id 含时间戳，便于按日检索
- form_hash 单独保留作为 idempotency key，不挪用

### 15.4 为什么 IM 不做硬幂等？

见 §6.4：`step.status == DONE` 已经是充分保护。

### 15.5 为什么 retry 是 (1, 4, 15) 不是指数？

- 6 步外部调用，绝大多数瞬态失败 1 s 内就好
- 第三次 15 s 给一段"网真断了 15 s 是真断"的判断时间窗口
- 不要指数避免无谓地等到 64 s 才报错（销售已经在等屏幕了）

---

## 16. 提交关键路径（飞书 CLI 大赛 2026）

> 详见 `docs/contest-submission.md`。本节给设计文档读者一个 "本仓库与大赛对齐"的速览。

- 目标奖项：**最佳实践奖**（业务结合 + 增效）
- 关键叙事：30 min → 30 s 的 60× 效率提升 + 100% 程序化字段流转 + 0 真实凭证可演示
- 大赛要求映射：
  - 原创性 → 全代码本仓库自研
  - 实用性 → §1.2 量化的痛点 + §1.3 量化的改进
  - 创新性 → §3 的 Agent + lark-cli + 后端解耦三段架构 + §11.3 故意留缺口
  - 技术可行性 → §10 测试金字塔 + §11 0 凭证 demo

---

## 17. 附录

### 17.1 一份完成的 state.json 示例

参见 `examples/state.sample.json`。

### 17.2 一份 card 示例

参见 `examples/card.sample.json`。

### 17.3 后端 quote 响应示例

参见 `examples/quote-response.sample.json`。

### 17.4 主要 lark-cli 调用一览（再次）

```
drive file list --folder_token <fld>
drive upload --parent <fld> --file <path>
base record search --app_token <bsc> --table_id <tbl> --filter <expr>
base record create --app_token <bsc> --table_id <tbl> --fields <json>
im message send --receive_id <chat> --msg_type interactive --content <json>
```

### 17.5 envelope JSON Schema (informal)

```ts
type Envelope =
  | {
      status: "ok",
      request_id: string,
      quote_id: string,
      totals: { list: number, final: number },
      drive: { pdf_url: string, xlsx_url: string },
      record: { url: string },
      im: { message_id: string }
    }
  | {
      status: "failed",
      request_id: string,
      failed_step: "create"|"pdf"|"xlsx"|"drive"|"base"|"im"|"unknown",
      error: string,
      resume_hint: string
    };
```

### 17.6 与 SKILL.md 的对应关系

| SKILL.md 段落 | 设计文档对应 |
|---|---|
| §"何时使用" | §1 业务现状 |
| §"收集参数" | §4.1 QuoteForm |
| §"发起流程" | §3 顶层架构 + §5 状态机 |
| §"解读结果" | §17.5 envelope schema |
| §"错误处理" | §5.4 错误 envelope |
| §"禁止" | §7.2 lark-cli 边界 + §8 安全 |

---

## 18. 变更日志

- **2026-04-01** v0.1 起草，确定 6 步、JSON 状态、lark-cli 单边。
- **2026-04-15** 加入 `form_hash` / `X-Idempotency-Key`，三道关幂等定型。
- **2026-04-22** 完成 e2e mock 测试与 dry-run 双重保护。
- **2026-04-29** 加入 golden file 和隐私扫描测试，文案冻结。
- **2026-05-01** 大赛提交版本：本文档 + `contest-submission.md` 同时定稿。

---

> **如果你只能读这文档的 5 行**：
> 1. 本 skill 解决餐饮 SaaS 销售一单 30 min 的人肉报价流程，目标 30 s。
> 2. AI Agent 收对话、写 form JSON、调 `run_flow.py`；后者编排 6 步并幂等落地飞书三 domain。
> 3. 所有飞书操作走 `lark-cli`，仓库不依赖飞书 SDK。
> 4. 0 飞书凭证可跑 demo（mock + dry-run），评委可现场 `pytest` 跑通。
> 5. 大赛目标奖项：最佳实践奖。叙事单独放 `docs/contest-submission.md`。
