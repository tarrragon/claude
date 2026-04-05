# Context Bundle 規範

> **目標**：PM 在派發代理人前，將該代理人需要的所有資訊寫入 Ticket，代理人只需讀取 Ticket 即可開始工作。

---

## 定義

**Context Bundle** 是 Ticket 執行日誌中的一個區段。PM 在派發代理人前，透過 `ticket track append-log --section "Context Bundle"` 寫入下一階段代理人所需的前置資訊。

---

## 核心原則

1. **Inline 優先**：關鍵資訊直接寫入，不是只給路徑讓代理人自己讀
2. **1 Read 原則**：代理人只需 1 次 Read Ticket 就能獲得全部 context
3. **簡短有效**：不超過 5K tokens，只寫代理人真正需要的

---

## 通用模板

所有 Phase 轉換和任務派發使用同一模板，PM 按需填寫相關欄位：

```markdown
### Context Bundle

**需求摘要**: {一句話描述代理人要做什麼}
**API 簽名**: {代理人需要知道的介面，inline}
**相關檔案**: {路徑 + 一句話說明，只列代理人必須讀的}
**驗收條件**: {從 Ticket 5W1H 提取}
**約束**: {代理人應知道的限制或注意事項}
**測試指令**: {如適用}
```

欄位按需填寫，不強制全填。各 Phase 有特定的額外欄位建議，詳見 `.claude/references/context-bundle-phase-guide.md`。

---

## PM 填寫流程

```
代理人完成 Phase N → PM 讀取回報 → 提取關鍵資訊 → 寫入 Context Bundle → 派發下一階段
```

**派發 prompt 只需**：Ticket 路徑 + 動作指令 + 「Context Bundle 已準備，讀取 Ticket 後開始」。

---

## 禁止行為

| 禁止 | 原因 |
|------|------|
| 只給路徑不給內容 | 代理人還是要花 tool calls 讀檔案 |
| 要求代理人「自行探索」 | 浪費 50%+ tool calls |
| 跳過 Context Bundle 直接派發 | subagent ~20 tool calls 預算，探索就耗盡 |

---

## 與現有規則的關係

- `tdd-flow.md` — 階段轉換時 PM 填寫 Context Bundle 為強制動作
- `decision-tree.md` — 派發前檢查 Context Bundle 是否已填寫
- `two-stage-dispatch.md` — 任務 A 產出寫入 Context Bundle
- `claude-code-platform-limits.md` — 背景約束（~20 tool calls、32K output）

---

**Last Updated**: 2026-04-06
**Version**: 2.0.0 - 精簡重寫：6 個模板合併為 1 個通用模板，移除產出契約（多視角審查修正）
