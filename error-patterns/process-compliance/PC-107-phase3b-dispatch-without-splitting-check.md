---
id: PC-107
title: Phase 3b 派發前未走 cognitive-load 拆分檢查
category: process-compliance
severity: high
status: active
created: 2026-04-20
---

# PC-107: Phase 3b 派發前未走 cognitive-load 拆分檢查

## 症狀

PM 將 TDD Phase 3b 視為單一派發單位派發給實作代理人，未評估實作範圍（新模組 + 多 CLI 檔修改 + 多測試場景 + 可選 API 擴充）是否超過：

- subagent ~20 tool call 限制（PC-042）
- `.claude/rules/core/cognitive-load.md` 任務拆分閾值

典型訊號：

- Phase 3a 策略產出「單檔 lib + CLI 侵入多處」— PM 誤讀為「連貫 → 可一次派發」
- Phase 2 測試規格含 10+ 場景，但 PM 未評估測試撰寫成本
- Prompt 列出 3+ 個 Edit/Write 目標檔案但 PM 未觸發拆分

## 根因

1. **TDD Phase 觀念誤解**：PM 把「Phase 3b」當作不可分單位；實際上 Phase 3b 可拆多個子 ticket（例如 .a lib + .b CLI 整合 + .c API 擴充）
2. **連貫性偏誤**：Phase 3a 策略描述看起來連貫（一個模組 + 兩個 CLI 侵入點）就誤判為原子
3. **PM 主動檢查缺失**：派發前未呼叫 `cognitive-load-assessment` skill 或 `decision-tree-helper`
4. **現有 hook 僅檔 prompt 長度（PC-040 / 30 行），未檢查實作範圍**

## 實際案例

**W17-002 Phase 3b 派發 thyme-python-developer**（2026-04-20）：

任務範圍：
- 新建 `context_bundle_extractor.py`（4 公開函式）
- 修改 `commands/create.py`（CLI 末端整合）
- 修改 `commands/track.py`（claim path）
- 可能修改 `track_acceptance.execute_append_log`（新增 replace_section flag）
- 實作 15 場景測試（Phase 2 v2 規格）
- 多次 iteration 直到 100% 通過

估計 tool call：18-25 次（Read + Write + Edit + Bash test runs + commit + append-log）→ 超過 subagent ~20 tool call 限制。

**正確拆分應為**：
- W17-002.a: extractor lib 4 函式 + 單元測試 13 場景（L1）
- W17-002.b: execute_append_log replace_section flag 擴充（前置）
- W17-002.c: create.py CLI 整合 + 整合測試 + --quiet/--verbose
- W17-002.d: track.py claim path 整合

## 防護

### 1. PM 派發前強制檢查（人工）

Phase 3b 派發前對照 `cognitive-load.md` 閾值表：

| 指標 | 閾值 | 超標即拆 |
|------|------|---------|
| 修改檔案數 | > 5 必拆 / > 3 考慮拆 | 是 |
| 跨架構層級 | > 2 必拆 | 是 |
| 需追蹤概念數 | > 7 必拆 | 是 |
| 新模組 + 多處整合 | 三個以上串接點 | 是 |
| 預估 subagent tool call | > 18 | 是（考量 PC-042） |

### 2. Phase 3a 產出格式擴充（pepper 責任）

`pepper-test-implementer` Phase 3a 策略產出必須包含「拆分建議」段落：

```markdown
## 拆分建議

| 子任務 | 範圍 | 預估 tool call |
|-------|------|--------------|
| .a | extractor lib + 單元測試 | 10-12 |
| .b | CLI 整合 | 6-8 |
...
```

### 3. Hook 層自動檢查（未來）

新增 dispatch guard hook 或擴充 `agent-prompt-length-guard-hook`：

- Phase 3b 派發偵測 prompt 內 `.py` / `.dart` / `.go` 檔案提及次數 > 3
- 偵測「新建 X.py + 修改 Y.py + 修改 Z.py」模式
- 警告或要求確認拆分決策

## 與既有規則的關係

| 規則 | 關係 |
|------|------|
| PC-042（subagent tool call 限制） | 本 pattern 是 PC-042 的上游預防 |
| `.claude/rules/core/cognitive-load.md` | PM 未主動套用閾值表 |
| quality-baseline 規則 6 | 發現失誤後不回退既成工作，提煉本 pattern |

## 修復方向

- **W17-002 個案**：保留 thyme 繼續執行（規則 6）；若 NeedsContext 中斷則拆 .a/.b/.c/.d 續接
- **框架層**：擴充 Phase 3a 產出 schema；評估 dispatch guard hook 可行性

## 相關 Ticket

- 0.18.0-W17-002（本 pattern 的動機案例）

## 相關 error-patterns

- PC-042（subagent tool call 限制）
- PC-040（context 存 ticket 不存 prompt）
