# TDD-Ticket 整合方法論（30 秒核心）

> **本檔已瘦身（W8-018.2）**：3b 拆分評估（檔案數 / 認知負擔 / 跨層級觸發條件）已在 `/tdd` skill 的 `.claude/skills/tdd/references/phase3-implementation.md`「3b 拆分評估」；單一職責四大檢查的完整定義在 `.claude/methodologies/atomic-ticket-methodology.md`。本檔僅保留 distinct 核心：Phase 3a 是唯一 Ticket 決策點，以單一職責四大檢查作為唯一拆分標準。

本方法論定義 Ticket 系統與 TDD 流程的整合機制：在 Phase 3a 設立強制單一職責評估，確保每個功能開發都經過適當的拆分評估。

---

## 核心原則（distinct 核心）

### Phase 3a 是唯一 Ticket 決策點

Ticket 設計決策只在 Phase 3a 進行：

| TDD 階段 | Ticket 決策 | 說明 |
|---------|------------|------|
| Phase 1 / 2 | 不進行 | 專注功能設計 / 測試設計 |
| Phase 3a | 執行 | 強制單一職責評估 |
| Phase 3b | 不進行 | 按評估結果執行 |
| Phase 4 | 不進行 | 跨 Ticket 重構（不新增 Ticket，除非發現新功能需求） |

### 唯一評估標準：單一職責四大檢查

**禁止使用量化指標**（時間估計、測試案例數、程式碼行數、檔案數量）作拆分依據——這些只反映工作量大小，不反映職責是否單一。唯一標準是四大檢查：

| 檢查項目 | 問題 | 通過標準 |
|---------|------|---------|
| 語義檢查 | 能用「動詞 + 單一目標」表達嗎？ | 只有一個目標 |
| 修改原因檢查 | 只有一個修改原因嗎？ | 只有一個原因會觸發修改 |
| 驗收一致性 | 所有驗收條件指向同一目標嗎？ | 全部指向同一目標 |
| 依賴獨立性 | 拆分後不會產生循環依賴嗎？ | 無循環依賴 |

**決策邏輯**：四項都通過 → 單一 Ticket（或直接執行）；任一未通過 → 必須拆分為多個 Atomic Tickets。不確定某項是否通過時，預設為未通過並拆分（寧可過度拆分，不讓職責混亂的 Ticket 進入實作）。

> **框架整合**：任一檢查未通過時執行 `/ticket create`；拆分後 PM 審核確認單一職責，按 Wave 順序執行。狀態對應：建立後 `pending` → `/ticket track claim` 後 `in_progress` → `/ticket track complete` 後 `completed`。

---

## 路由

| 需求 | 讀這裡 |
|------|--------|
| 單一職責四大檢查完整定義、Ticket ID 命名規範、Wave 依賴定義 | `.claude/methodologies/atomic-ticket-methodology.md` |
| 3b 拆分評估（檔案數 / 認知負擔 / 跨層級觸發條件、並行安全檢查） | `.claude/skills/tdd/references/phase3-implementation.md`「3b 拆分評估」 |
| TDD 四階段流程主體 | `.claude/skills/tdd/SKILL.md` |
| Ticket 5W1H 設計與派工驗收 | `.claude/methodologies/ticket-design-dispatch-methodology.md` |
| 狀態管理與指令 | `.claude/methodologies/frontmatter-ticket-tracking-methodology.md` |

---

**Last Updated**: 2026-06-13
**Version**: 2.0.0 — W8-018.2 整併瘦身：3b 拆分評估路由至 `/tdd` skill phase3-implementation.md，四大檢查完整定義路由至 atomic-ticket-methodology.md，保留 distinct 核心「Phase 3a 唯一決策點 + 四大檢查唯一標準」為 30 秒核心 + 路由。歷史 1.0.0 完整版（含決策流程圖、四大檢查執行細節、Phase 4 經驗捕獲、常見問題）見 git log。
