# Hook 治理規則

Hook 是系統治理的核心基礎設施。本文件涵蓋 Hook 修改審核和 SessionStart 效能監控。

---

## Hook 配置治理

### Handler 類型

| 類型 | 用途 | 治理規則 |
|------|------|---------|
| `command` | 執行 shell / Python / Bash script | 預設選擇；需有測試或 smoke check |
| `http` | 將 hook input 以 HTTP POST 傳給服務 | 僅用於本機或受控服務；需記錄 timeout 與失敗行為 |
| `prompt` | 讓模型做單輪 yes/no 判斷 | 僅用於語意判斷；不得取代 deterministic script |
| `agent` | 派 subagent 讀檔、grep、驗證條件 | 實驗性；需明確限制 scope 與 timeout |

### `if` 條件

`if` 用於縮小 hook handler 的啟動範圍，降低無效 spawn 成本。

| 規則 | 說明 |
|------|------|
| 適用事件 | 只用於 `PreToolUse`、`PostToolUse`、`PostToolUseFailure`、`PermissionRequest` |
| 語法 | 使用 permission rule syntax，如 `Bash(git *)`、`Edit(*.ts)` |
| 組合方式 | 單一 `if` 只放一條 rule；需要多條件時拆成多個 handler |
| 非 tool event | 不設定 `if`；非 tool event 上的 `if` 不會執行 |

**範例**：

```json
{
  "type": "command",
  "if": "Bash(git push *)",
  "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/pre-push-check.py"
}
```

```json
{
  "type": "command",
  "if": "Edit(*.md)",
  "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/markdown-policy-check.py"
}
```

```json
{
  "type": "command",
  "if": "Bash(uv run *)",
  "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/test-command-check.py"
}
```

### HTTP hooks

HTTP hook 將事件 JSON 作為 `Content-Type: application/json` 的 POST body 送到 `url`。

**使用規則**：

- 優先使用本機 loopback 或受控內網 endpoint。
- 不把 secrets 寫死在 URL 或 headers；需要 header token 時使用 `allowedEnvVars` 白名單。
- 非 2xx、連線失敗、timeout 都視為 non-blocking error；需要阻擋時，endpoint 必須回 2xx 且 JSON body 含 block/deny 決策。
- HTTP hook 必須設定合理 timeout，避免拖慢 agent loop。

**範例**：

```json
{
  "type": "http",
  "url": "http://localhost:8080/hooks/pre-tool-use",
  "timeout": 30,
  "headers": {
    "Authorization": "Bearer $HOOK_TOKEN"
  },
  "allowedEnvVars": ["HOOK_TOKEN"]
}
```

### Prompt / agent hooks

| 類型 | 適用 | 禁止 |
|------|------|------|
| `prompt` | 語意分類、文件品質判斷、需要模型理解的 yes/no gate | 檔案狀態檢查、可用 grep/script 決定的條件 |
| `agent` | 需要 Read/Grep/Glob 多步查證的複合條件 | 大範圍重構、無 timeout 的長任務、會寫檔的驗證 |

Prompt / agent hook 必須在設計文件中說明為何 deterministic script 不足。

---

## Hook 修改審核

### 審核層級

| 修改類型 | 審核要求 |
|---------|---------|
| 新增 Hook | PM 評估必要性 + 測試驗證 |
| 修改既有 Hook 行為 | PM 確認影響範圍 + AST 語法驗證 |
| 刪除 Hook | PM 確認無依賴 + 記錄刪除原因 |
| 降級 Hook（如 AUTO→WARN） | 建立 Ticket 追蹤，記錄降級原因 |

### 驗證清單

- [ ] Python AST 語法驗證通過
- [ ] Hook 不影響其他 Hook 的運作
- [ ] settings.json 中的 Hook 註冊已更新（如適用）
- [ ] 修改原因已記錄在 Ticket 或 commit 訊息中

---

## SessionStart 效能監控

SessionStart Hook 數量多（目前 13 個），累積延遲影響用戶體驗。

### 效能閾值

| 指標 | 閾值 | 超過時處理 |
|------|------|-----------|
| 單一 Hook 執行時間 | 5 秒 | 優化或降級 |
| 所有 SessionStart Hook 總時間 | 15 秒 | 評估哪些可移至背景 |
| Hook 數量 | 15 個 | 評估合併或移除 |

### 監控方式

使用 hook-health-check 輸出的時間戳評估 SessionStart 總延遲。

**執行指令**：

```bash
# 查看 SessionStart Hook 執行時間（從 hook-health-check 輸出中提取）
# hook-health-check 在每次 SessionStart 時自動執行，輸出包含每個 Hook 的時間戳

# 手動檢查所有 SessionStart Hook 數量
grep -c '"SessionStart"' .claude/settings.json

# 檢查 Hook 健康狀態輸出
# SessionStart 時自動輸出，格式：[timestamp] [INFO] [OK] hook-name.py (last update: Xh ago)
```

**檢查頻率**：

| 頻率 | 觸發條件 |
|------|---------|
| 每次新增 Hook 後 | 確認總數未超過 15 個閾值 |
| 版本收尾時 | 評估是否有可合併或移除的 Hook |
| 用戶反饋啟動慢時 | 即時排查 |

### 優化策略

| 策略 | 適用場景 |
|------|---------|
| 快取結果 | 每次都重新計算但結果很少變化的 Hook |
| 合併 Hook | 功能相近的多個 Hook 合併為一個 |
| 延遲載入 | 非關鍵的檢查移至首次需要時執行 |

---

## 相關文件

- .claude/rules/core/quality-baseline.md - 品質基線（規則 4：Hook 失敗必須可見）
- .claude/pm-rules/incident-response.md - 事件回應流程

---

**Last Updated**: 2026-03-28
**Version**: 1.0.0 - 合併 hook-change-review.md + session-start-performance.md
