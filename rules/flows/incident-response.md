# 事件回應流程

Skip-gate 防護機制的核心流程。

---

## 強制流程

```
錯誤發生 → /pre-fix-eval → 派發 incident-responder → 分析分類
→ 建立 Ticket → PM 決定派發 → 對應代理人修復
```

---

## 強制觸發條件

| 觸發情境 | 識別關鍵字 |
|---------|-----------|
| 測試失敗 | "test failed", "測試失敗", "FAILED" |
| 編譯錯誤 | "compile error", "編譯錯誤", "build failed" |
| 執行時錯誤 | "runtime error", "exception", "crash" |
| 用戶回報問題 | "bug", "問題", "不正常", "出錯" |

---

## 派發對應表

| 錯誤分類 | 子分類 | 派發代理人 |
|---------|-------|-----------|
| 編譯錯誤 | 依賴問題 | system-engineer |
| 編譯錯誤 | 類型錯誤 | parsley-flutter-developer |
| 測試失敗 | 測試本身問題 | sage-test-architect |
| 測試失敗 | 實作與預期不符 | parsley-flutter-developer |
| 測試失敗 | 設計邏輯錯誤 | system-analyst |
| 執行時錯誤 | 環境問題 | system-engineer |
| 執行時錯誤 | 資料問題 | data-administrator |
| 執行時錯誤 | 程式錯誤 | parsley-flutter-developer |
| 效能問題 | - | ginger-performance-tuner |
| 安全問題 | - | security-reviewer |

---

## 禁止行為

| 禁止 | 說明 |
|------|------|
| 直接修改程式碼 | 只能分析，不能修復 |
| 跳過 Ticket 建立 | 必須建立 Ticket |
| 自行決定派發 | 只提供建議，PM 決定 |

---

## 相關文件

- .claude/references/incident-response-details.md - 詳細規則（多視角分析、安全等級、報告格式）
- .claude/agents/incident-responder.md - 代理人定義
- .claude/rules/forbidden/skip-gate.md - Skip-gate 防護
- .claude/rules/core/decision-tree.md - 主線程決策樹

---

**Last Updated**: 2026-03-02
**Version**: 3.0.0 - Progressive Disclosure 精簡，詳細內容移至 references/
