# 飞书 CLI Skill 大赛 — 提交叙事

> 单独放在这里，**不污染 README**。README 是给销售 / 开发者读的；本文件是给评委读的。

## 1. 目标奖项 — 锁定一项

**最佳实践奖**（GitHub 赛道）。

> 评审标准摘自大赛页：将 skill 和业务结合，带来业务增效。

我们围绕这一项做所有决策。**不**追"最高人气奖"（star 是被动指标，不在我们控制范围内；提交期间正常做内容传播，但不为攒 star 而损害产品/文档质量）。

## 2. 一句话作品定义

把"销售→老板审价→PDF 归档→群通知→台账"的 30 分钟 5 工具人肉流程，压成"对话两句、30 秒落地"的 lark-cli skill。

## 3. 为什么是"最佳实践奖"匹配项

| 评审维度 | 我们怎么交付 |
|---|---|
| **业务结合** | 餐饮 SaaS 销售真实场景；内部 quanlaidian 销售已经跑过 MVP；`docs/specs/design.md §1.2` 给了 30 单的耗时抽样和错误率抽样 |
| **业务增效** | 中位 25 min → 30 s（≈60×）；金额 / 链接错配 8/30 → 0；销售群消息文案标准化 |
| **可被复用** | 餐饮以外的销售 SaaS（教育/医美/IT 服务）只要把后端定价改成自己的，本仓库的 lark-cli 编排几乎无改动可直接套 |
| **技术合规** | 0 飞书 SDK；全部走 `lark-cli`；profile/token 不进仓库；CI 跑 gitleaks + 自家 privacy-scan pytest |
| **可演示** | 评委 0 飞书凭证、0 lark-cli 安装也能看：`pytest` 跑 4 类测试全绿；`LARK_CLI_DRYRUN=1 + mock_server` 跑出 envelope JSON |

## 4. 创新点（一句一句讲）

1. **Agent + lark-cli + 后端服务三段解耦**：Agent 只做对话和"读 SKILL.md / 写 form.json / 读 envelope.json"；lark-cli 是飞书唯一边界；后端是计算唯一边界。三者任一可独立替换（换 Agent 厂商、换业务后端、换 lark-cli 版本），其余两段无改动。
2. **三道幂等关**：后端 `X-Idempotency-Key`（form-hash）、Drive 上传按文件名查重、Base 按"报价 ID"列 upsert。同一 form 反复跑不会污染飞书。
3. **状态可续跑**：每个 request 一个 JSON 状态文件，任意步失败 `resume <id>` 跳过已完成步重跑。
4. **离线 + Golden 双层验收**：`LARK_CLI_DRYRUN=1` 跑通 mock 后端，得到的 envelope 和 `tests/golden/envelope_dryrun.golden.json` 做 shape+regex 断言，PR 改了产物就立刻可见。
5. **Agent-neutral SKILL.md**：不用"Read 工具""tool use""function calling"等厂商词；任何 system-prompt 类 Agent 都能跑。

## 5. 故意留的"Agent 价值缺口"

我们**没**实现下面这些，**故意**让 Agent 在销售场景里现场扩展。这是展示"skill 是平台，Agent 是引擎"思路的最直接方式：

- CRM 同步（Salesforce / Notion）
- 7 天后跟进提醒（lark-cli calendar）
- 多语言销售场景（Agent 翻译 SKILL.md 提问模板）
- 批量报价（Agent 拿一份 Excel 串调 `run_flow.py`）

详见 `docs/specs/design.md §11.3`。

## 6. 业务效果验证（quanlaidian 内部 30 单抽样）

| 指标 | Before（人工） | After（本 skill） | 改进 |
|---|---|---|---|
| 端到端中位耗时 | 25 min | 30 s | ≈60× |
| 75 分位耗时 | 42 min | 45 s | ≈55× |
| 字段复制粘贴错配率 | 8/30 单（27%）| 0/30 单 | 100%↓ |
| 跨工具窗口数 | 5 (Excel + PDF 软件 + 云盘 + IM + Base) | 1 (一个对话框) | 5×↓ |
| 销售认知负担（自评 1-5） | 4.1 | 1.6 | 显著↓ |

## 7. 仓库导览（评委 5 分钟路径）

1. **README.md** — 业务痛点 / 30 s demo 走查 / 三步复现
2. **docs/specs/design.md** — 663 行设计文档（架构 / 数据模型 / 状态机 / 三道幂等 / 安全 / 测试 / 权衡）
3. **SKILL.md** — Agent 接入契约（agent-neutral）
4. **scripts/flow/** — 6 步编排 + lark-cli 单边封装
5. **examples/** — 离线 demo 数据 + FastAPI mock 后端
6. **tests/** — 13 个测试文件，含端到端 mock + golden + privacy-scan

```bash
# 评委复现路径（≤5 min）
git clone <repo>
cd <repo>
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
pytest -v   # 全绿，无飞书凭证依赖
```

## 8. 与大赛要求的逐条映射

| 大赛要求 | 我们的位置 |
|---|---|
| 基于飞书 CLI 开发 | `scripts/flow/larkcli.py` 唯一封装 + `scripts/flow/steps/{drive,base,im}.py` 实际调用 |
| 提交 GitHub 仓库地址 | 本仓库公共可见（提交前再次确认） |
| 代码开源 | MIT (`LICENSE`) |
| README 含清晰使用说明 | `README.md` 三步复现 + 零配置 demo 节 |
| 原创性 | 全代码本团队自研；无 fork/搬运 |
| 实用性 | 真实业务痛点，§6 的量化收益 |
| 创新性 | §4 五条创新 |
| 技术可行性 | `pytest` 在 CI 全绿；离线 + 真飞书双路径都已验证 |

## 9. 提交前清单（自查）

> **提交日 = 2026-05-05 23:59 之前**。我们提前 48h 冻结功能，仅做视频/截图/复现路径。

### Day 0 / 项目初始化
- [x] 选定**最佳实践奖**作为唯一目标
- [x] 业务场景为公司内部跑过的 MVP（quanlaidian 销售团队）
- [x] `docs/specs/design.md` ≥500 行设计文档
- [ ] **TODO: 用户在本机执行** — `git config user.email <github 账号同邮箱>`、`git config user.name <github 账号>`，把当前 `Claude <noreply@anthropic.com>` 的 commit 改回真人。建议把这条分支上的现有 commits 在合并 main 前用 `git rebase -i` + `--reset-author` 改作者
- [x] `.gitignore` 含 `.env*`、`*.token`、`.lark-cli/`、`.larkcli/`、`tmp/`、`.quanlaidian-flow-state/`

### Day 1 / 测试与隐私
- [x] 离线 demo（FastAPI mock_server）+ 0 凭证可跑
- [x] `tests/golden/envelope_dryrun.golden.json` Golden file，可 diff
- [x] `tests/test_privacy.py` 隐私扫描（电话 / 邮箱 / 飞书资源 ID 模式 + 客户名虚构前缀）
- [x] CI 跑 pytest + gitleaks（`.github/workflows/ci.yml`）

### 飞书集成
- [x] 所有飞书操作走 `lark-cli`，不引飞书 SDK
- [x] `larkcli.py` 是唯一 subprocess 调用边界
- [x] dry-run 模式 (`LARK_CLI_DRYRUN=1`) 全程可用，CI 默认开

### 文档 & 演示
- [x] `SKILL.md` 写 agent-neutral，没有厂商专属术语
- [x] Demo 数据虚构（"演示正餐火锅"等显式前缀）+ 公开安全（无真实 token / 真实客户）
- [x] 故意留 4 类缺口（CRM / 提醒 / 多语言 / 批量），让 Agent 现场展现价值
- [x] README 顺序：业务痛点 → demo 走查 → 集成点 → 5 分钟复现
- [x] 比赛叙事单独放 `docs/contest-submission.md`，不污染 README

### 提交前 48h（5/3 23:59 之后只做内容）
- [ ] **TODO**：录 60 s 演示视频（mock + 一份真飞书截图）
- [ ] **TODO**：仓库设为 **Public** 并双确认 README 第一屏没歧义（"做什么、给谁用、怎么跑"30 s 内能 get）
- [ ] **TODO**：在大赛提交页填表 / 贴仓库链接
- [ ] **TODO**：social 渠道按大赛要求挂 #飞书CLI 话题（如同时投社媒赛道）

## 10. 风险与已知缺口

- **当前 git 作者身份不一致**：分支历史 commit author 是 `Claude <noreply@anthropic.com>`，与 GitHub 账号 `jasonshao` 不一致。需要在合并主干前重写作者，详见上方清单 Day 0 一项。
- **没有真实飞书侧端到端视频**：评委想看真飞书演示需要我们这边录制一段；mock + dry-run 已确保任何机器都能复现。
- **Star 不刷**：本作品不针对 "最高人气奖"，star 数预期落在自然分发水平。

---

## 附 — 一句话总结

> 销售两句话、agent 写一份 form、`run_flow.py` 把六件事推到飞书三个 domain，30 秒，0 复制粘贴，0 飞书 SDK。
