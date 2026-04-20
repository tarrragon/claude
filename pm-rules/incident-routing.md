# 決策樹 — 事件回應路由

> 接收到錯誤/失敗訊息時的路由流程。
>
> 路由入口：.claude/pm-rules/decision-tree.md
> 來源：決策樹二元化拆分

---

## 事件回應路由

```
錯誤/失敗發生
    |
    v
[強制] WRAP 快速模式（W 擴增 + R 基本率）
    |   防止衝動歸因
    |   問：「還有什麼其他原因可能導致這個錯誤？」
    |
    v
是工具/CLI 本身報錯? ─是→ [CLI 調查流程]
    |                       → --help → 字面解讀 → 比對狀態 → 歸因
    |                       → 語法問題 → 修正後重試
    |                       → 確認非語法問題 → 進入下方邏輯錯誤流程
    |
    +─── 否（程式碼/邏輯錯誤）→ [強制] /pre-fix-eval
                                → 派發 incident-responder
                                → 建立 Ticket → 對應代理人修復

是代理人失敗? ─是→ [強制] 先執行 agent-failure-sop.md Step -1~4 前置步驟
    |               → hook-logs 檢查（Step -1）
    |               → dispatch-active.json（Step 0）
    |               → 分支/worktree 確認（Step 1-4）
    |               → 全部排除後才能判定失敗
```

---

## 入口條件

本路由在以下情境被觸發：

| 入口 | 來源 | 觸發者 |
|------|------|--------|
| 第零層明確錯誤關鍵字 | decision-tree.md 明確性檢查 | PM 收到用戶訊息時 |
| 命令路由除錯判斷 | command-routing.md 除錯命令分支 | PM 識別命令類型時 |
| 測試失敗回報 | Agent 執行結果包含 FAIL | Agent 完成後 PM 驗收時 |
| Hook 攔截 | 自動化 Hook 偵測到錯誤 | Hook 自動觸發 |

---

## 強制規則

| 規則 | 說明 |
|------|------|
| /pre-fix-eval 必須執行 | 程式碼/邏輯錯誤禁止直接修復 |
| incident-responder 必須派發 | 禁止 PM 直接修復（skip-gate 防護） |
| Ticket 必須建立 | 所有事件都需要追蹤 |

---

## 相關文件

- .claude/pm-rules/incident-response.md - CLI 調查流程、錯誤分類和派發對應表
- .claude/pm-rules/skip-gate.md - Skip-gate 防護機制
- .claude/pm-rules/decision-tree.md - 路由索引

---

**Last Updated**: 2026-04-09
**Version**: 1.0.0 - 從 decision-tree.md 拆分（決策樹二元化拆分）
