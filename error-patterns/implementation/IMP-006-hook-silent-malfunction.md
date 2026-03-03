# IMP-006: Hook 隱性故障模式

## 分類
- **類型**: implementation
- **嚴重度**: 中
- **發現版本**: v0.31.1
- **發現日期**: 2026-03-02

## 模式描述

Hook 系統中的錯誤以 "hook error" 統一顯示，無法從 UI 區分具體根因（程式 bug、參數遺漏、超時、plugin 問題）。多個不同根因的 hook error 同時存在時，容易誤判為單一問題。

## 具體案例

### 案例 A：函式參數遺漏（creation-acceptance-gate-hook）

**症狀**：每次 UserPromptSubmit 都出現 hook error

**根因**：`save_check_log(prompt, None, False, 0)` 缺少第 5 個必要參數 `logger`。函式簽名要求 5 個參數，但呼叫端只傳了 4 個。

**位置**：`creation-acceptance-gate-hook.py` 第 453 行

**特徵**：同一檔案的第 471 行有正確的呼叫（含 logger），但第 453 行的早期返回路徑遺漏了。

**修復**：補上 `logger` 參數。commit `3e70e62`。

**教訓**：同一函式在多處呼叫時，每個 call site 都需要驗證參數完整性。Copy-paste 呼叫時特別容易遺漏最後一個參數。

### 案例 B：語義分類錯誤（command-entrance-gate-hook）

**症狀**：探索/分析類的 agent 派發被阻擋，要求先建立 Ticket

**根因**：`ANALYSIS_KEYWORDS`（分析、調查、研究、追蹤）被納入 `DEVELOPMENT_KEYWORDS`，導致分析命令被當作開發命令處理。但決策樹第二層將分析/問題類走「問題處理流程」，不需要 Ticket。

**位置**：`command-entrance-gate-hook.py` 第 106-112 行

**修復**：從 `DEVELOPMENT_KEYWORDS` 移除 `ANALYSIS_KEYWORDS`，改加入 `is_management_operation()` 的白名單作為 `exploration_patterns`。commit `d806140`。

**教訓**：Hook 的關鍵字分類必須與決策樹語義一致。當 Hook 行為與決策樹矛盾時，應修改 Hook（Hook 是決策樹的實作，不是獨立規則）。

### 案例 C：Plugin timeout 過低（hookify）

**症狀**：間歇性 PreToolUse:Read hook error 和 UserPromptSubmit hook error

**根因**：hookify plugin 的 hooks.json 設定 `"timeout": 10`（10 毫秒），但 Python 啟動需要 ~24ms，完整執行需要 ~49ms。超時後進程被 kill，顯示為 hook error。

**特徵**：
- 4 個事件（PreToolUse/PostToolUse/UserPromptSubmit/Stop）全部 timeout: 10ms
- 無 matcher（匹配所有工具），放大了觸發頻率
- 專案無 `.claude/hookify.*.local.md` 規則檔案，hookify 做的是完全無用的工作
- 間歇性發生（OS 快取有時讓執行壓縮到 10ms 內）

**修復**：使用 `/plugin` 指令 uninstall hookify。

**教訓**：
1. 第三方 plugin 的 timeout 設定可能不合理（10ms 對 Python 腳本等同「不允許執行」）
2. Plugin hook 和專案 hook 的 error 在 UI 上無法區分
3. 安裝 plugin 前應檢查其 hooks.json 的 timeout 和 matcher 配置
4. 不使用的 plugin 應及時移除，避免產生無意義的 hook 執行和 error

### 案例 D：有意阻止路徑遺漏 stderr 輸出（agent-ticket-validation-hook）

**症狀**：PM 派發 Agent 被攔截時，Claude Code 顯示 `"No stderr output"`，無法得知被攔截的具體原因

**根因**：`main()` 的 exit code 2 返回路徑只將錯誤原因放在 stdout JSON 的 `permissionDecisionReason` 欄位，未寫入 stderr。同檔案的 `_log_exception()`（未預期異常路徑）已正確寫入 stderr，但有意阻止路徑遺漏了。

**位置**：`agent-ticket-validation-hook.py` 第 522-524 行

**特徵**：Hook 有兩條錯誤路徑 — (1) 未預期異常（exception）已有 stderr 輸出，(2) 有意阻止（業務邏輯拒絕）無 stderr 輸出。開發者只覆蓋了第一條路徑。

**修復**：在 exit code 2 路徑新增 `print(f"[Agent Ticket Validation] 派發被拒絕: {error_message}", file=sys.stderr)`。

**教訓**：Hook 的「有意阻止」和「未預期異常」是兩條獨立的錯誤路徑，兩者都需要 stderr 輸出。品質基線規則 4（Hook 失敗必須可見）適用於所有非成功路徑，不僅限於 exception。

## 共通模式

四個案例的共通點：

| 共通點 | 說明 |
|-------|------|
| UI 無差異化 | "hook error" 訊息不區分根因類型 |
| 多源疊加 | 多個不同 hook 的 error 同時出現，容易誤判 |
| 靜默降級 | hook error 不阻止操作，但也不告訴你哪個 hook 出了問題 |
| 路徑遺漏 | 多條錯誤路徑中只覆蓋部分（如只覆蓋 exception，遺漏業務拒絕） |

## 防護措施

### 開發 Hook 時
- [ ] 同一函式的所有 call site 參數完整性檢查（案例 A）
- [ ] Hook 關鍵字分類與決策樹語義一致性驗證（案例 B）
- [ ] 所有非成功路徑（exception + 業務拒絕）都有 stderr 輸出（案例 D）
- [ ] 新 Hook 加入後執行 3 種場景手動測試

### 安裝 Plugin 時
- [ ] 檢查 plugin 的 hooks.json timeout 設定（>= 1000ms 才合理）
- [ ] 檢查 matcher 設定（無 matcher = 匹配所有工具）
- [ ] 確認 plugin 有實際使用的規則/配置

### 排查 hook error 時
- [ ] 先區分 error 來源（專案 hook vs plugin hook）
- [ ] 檢查 `~/.claude/plugins/cache/` 中的 plugin hooks
- [ ] 用 `echo '{}' | python3 <hook.py>` 手動測試各 hook
- [ ] 測量 hook 執行時間，比對 timeout 設定

## 相關錯誤模式
- IMP-003: 重構引用更新不完整（與案例 A 的 call site 遺漏相似）
- IMP-005: 模組遷移後 import 未同步（同屬「修改後未完整驗證」類型）

## 相關文件
- `.claude/hooks/command-entrance-gate-hook.py` - 案例 B 修復位置
- `.claude/hooks/creation-acceptance-gate-hook.py` - 案例 A 修復位置
- `~/.claude/plugins/cache/claude-plugins-official/hookify/` - 案例 C 來源（已移除）
- `.claude/hooks/agent-ticket-validation-hook.py` - 案例 D 修復位置
