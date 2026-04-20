---
id: PC-057
title: PM 派發 prompt 要求超出代理人職責範圍，代理人無防線照做導致越界
category: process-compliance
severity: high
first_seen: 2026-04-12
---

# PC-057: PM 派發 prompt 要求超出代理人職責範圍，代理人無防線照做導致越界

## 症狀

- PM 派發背景代理人時，prompt 的工作要求**超出代理人定義的職責範圍**（例如要求設計型代理人寫實作程式碼、要求分析型代理人做重構）
- 代理人**未拒絕**違反自身職責的任務，照 prompt 執行
- 代理人產出雖可用但**違反原本的分工設計**，使得後續 Phase 的代理人工作重疊或被跳過
- PM 事後才察覺越界，面臨「回退重做 vs 保留既成工作」的兩難

## 根因

**三方責任擴散，沒有單一防線**：

| 責任方 | 缺失 |
|-------|------|
| PM 派發前 | 未對照代理人 `description` 的職責邊界和禁止行為欄位，憑直覺撰寫 prompt |
| 代理人自身 | 缺少「拒絕超出職責的任務」內建行為；agent definition 的禁止行為僅在描述中，執行時不會自動把關 |
| Hook 系統 | 目前 `agent-ticket-validation` 只檢查 Ticket ID 格式，無檢查 prompt 與 agent 職責的一致性 |

**更深層的文化因素**：
- PM 傾向「一次派發完成整 Phase 工作」，忽略 TDD flow 刻意的 Phase 分工（Phase 2 sage 設計 → Phase 3a pepper 規劃 → Phase 3b thyme 實作）
- 代理人傾向「完成用戶交辦」勝過「堅守職責」

## 具體案例

**案例 1： Phase 2 派發（2026-04-12）**

- PM 派發 sage-test-architect，prompt 要求建立 `.claude/skills/ticket/tests/test_ac_parser.py` 和 `test_validation_templates.py`
- sage 的 agent definition 明示：**「禁止實作程式碼和超出職責範圍的工作」**
- sage 仍執行，產出 30 個 test function（技術上可用）
- 影響：Phase 3a pepper（實作規劃）和 Phase 3b thyme（Python 實作）的分工被破壞，變成 pepper/thyme 只剩 source code 實作
- 用戶裁示不回退，但建某 Ticket（分析）與 某 Ticket（落地規則）追蹤改善

## 解決方案

### 短期（個案層面）

1. 既成工作若品質可用則保留（符合「失敗案例學習原則」）
2. 建立 ANA Ticket 追蹤本次派發錯誤的系統性成因
3. 建立 DOC/IMP Ticket 落地框架改善（Hook 或規則）

### 長期（框架層面）

| 改善點 | 說明 | 實作位置 |
|-------|------|---------|
| PM 派發前自檢清單 | 新增「派發前 3 問：代理人職責允許嗎？工作量在 tool call 預算內嗎？Forcing function 加入了嗎？」 | `.claude/pm-rules/agent-dispatch-checklist.md`（新） |
| Hook 自動檢查 | `agent-dispatch-validation` 新增「prompt 關鍵字 vs agent 禁止行為」的衝突掃描（例如 prompt 含 `.py` 檔案路徑 + agent 含「禁止實作程式碼」→ 警告） | `.claude/hooks/agent-dispatch-validation/` |
| Agent definition 格式統一 | 每個 agent 的 description 強制含明文「禁止行為」區塊，供 PM 對照和 Hook 掃描 | `.claude/agents/*.md` |
| TDD flow 文件強化 | 在 `pm-rules/tdd-flow.md` 明確標註各 Phase 代理人的「該做 / 不該做」欄位 | `.claude/pm-rules/tdd-flow.md` |

## 預防措施

### PM 派發前（立即可執行）

在建立 Agent tool call 前，PM 必須確認：

1. **查閱代理人 description** — 閱讀 `.claude/agents/{agent-name}.md`（或系統提供的清單），特別關注職責範圍與禁止行為
2. **比對 prompt 關鍵動詞 vs 職責** — 例如 prompt 說「建立 .py 檔案」→ 職責是「設計」→ 不匹配 → 拒絕派發或重新選擇代理人
3. **Forcing function 就位** — prompt 必須有強制首個 tool call，避免 agent 跑偏

### 代理人端（建議未來實作）

- Agent definition 在 description 增加 `禁止:` 區塊（如 sage 已有），作為 agent 自檢依據
- Agent 開場應先聲明「我的職責為 X，禁止 Y」，確認 prompt 一致後才執行

### Hook 層（建議未來實作）

- `agent-dispatch-validation` 新增 prompt vs agent 禁止行為的詞彙衝突掃描
- 衝突時以 PreToolUse:Agent block 方式拒絕派發，要求 PM 修正 prompt 或改派代理人

## 相關規則與文件

| 規則/文件 | 關聯 |
|---------|------|
| `.claude/rules/core/pm-role.md` | PM 派發規則的上位 |
| `.claude/pm-rules/tdd-flow.md` | TDD 各 Phase 代理人分工 |
| `.claude/pm-rules/pm-quality-baseline.md` 規則 6 | 框架優先（本 PC 為框架改善觸發案例） |
| `memory/feedback_failure_learning_principle.md` | 本 PC 的文化背景 |
| PC-042 | 規則文件體量上限（pm-rules 拆分導致代理人讀不完而耗盡回合） |
| PC-045 | PM 代理人失敗時自行撰寫產品程式碼（相似的「PM 越界」模式） |

## 追蹤 Ticket


## 驗證機制

PC-057 的防護是否有效，可透過以下方式驗證：

1. **Ticket 完成後檢查**：某 Ticket 執行階段落地 Hook 或檢查清單後，嘗試重現本 PC 的派發情境（prompt 要求 sage 寫 .py），應被阻擋
2. **代理人產出審查**：後續 某 Ticket~005 派發時，檢視 agent 是否在開場聲明職責邊界
3. **Hook 日誌**：若新增 prompt 衝突掃描 Hook，檢查 `.claude/hook-logs/agent-dispatch-validation/` 的衝突記錄統計
