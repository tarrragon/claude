---
id: DOC-010
title: 框架文件引用專案 ticket ID 造成跨專案 sync 誤導
category: documentation
severity: medium
first_seen: "2026-04-13"
occurrences: 1
status: active
related:
  - DOC-005
---

# DOC-010: 框架文件引用專案 ticket ID 造成跨專案 sync 誤導

## 現象

修改 `.claude/` 框架文件（rules/、pm-rules/、references/、error-patterns/、methodologies/ 等）時，在內容中加入 `（來源：0.18.0-W4-002）`、`（W5-021 教訓）`、`**Ticket**: 0.17.3-W12-001` 等專案 ticket ID 引用。這些引用在當前專案能查到對應 ticket 檔案，但 `.claude/` 透過 sync 機制（`sync-push`/`sync-pull`）同步到其他專案時，ticket ID 在目標專案並不存在，變成死連結和誤導性「來源」。

## 觸發情境

PM 或代理人在以下情境容易犯此錯：

1. **規則/方法論更新時**：想標注「這條規則的起源」→ 寫入專案 ticket ID
2. **error-pattern 撰寫時**：「實際案例」表格列出各次觸發的專案 ticket 編號
3. **Version footer**：`Version: 3.4.0 - XX 更新（W6-006 / W7-001）`
4. **Python hook 程式碼 docstring**：`# 來源: 0.17.2-W8-005`
5. **memory 記錄「已落實」**：誤以為 memory 足以承擔跨專案原則傳遞

## 根因分析

### 誤解 1：認為「來源標註」是好文件習慣

規則 7（reference-stability-rules）允許**規格文件**在變更歷史中記錄 ticket ID 作為歷史標注。但規則 7 的適用對象是 `docs/spec/`（專案內部），不是 `.claude/`（跨專案框架）。混淆兩者的穩定性來源，把規格文件的規則套用到框架文件。

### 誤解 2：認為 memory 足以跨專案傳遞原則

Auto-memory 位於 `~/.claude/projects/<project>/memory/`，**依專案隔離儲存**，不會 sync 到其他專案。和 ticket 一樣是專案層級識別符。想讓原則跨專案落實，**必須**寫入 `.claude/rules/` / `.claude/error-patterns/` / `.claude/methodologies/` 之一。

### 誤解 3：以為框架文件是「給當前專案看的」

框架文件（`.claude/`）設計目標是**跨專案共用**，透過 sync 機制傳遞最佳實踐。在其他專案查閱時應該提供抽象原則和指引，而非專案特定歷史。

## 防護措施

### 規則（已寫入框架）

- `.claude/references/reference-stability-rules.md` 規則 8：框架文件禁止引用專案層級識別符

### PM / 代理人自檢清單

修改 `.claude/` 文件前自問：

| 問題 | 若答「是」 | 行動 |
|------|-----------|------|
| 我寫的內容含 `0.XX.X-WX-YYY` 或 `W{n}-{nnn}` 格式的 ticket ID？ | 是 | 改為抽象場景描述 |
| 我寫了 `PROP-XXX` 但內容未提煉為方法論？ | 是 | 移除引用或先完成提煉 |
| 我寫了 commit hash？ | 是 | 移除 |
| 我寫了 `docs/work-logs/` 路徑？ | 是 | 改引用對應的 spec 或框架文件 |
| 我把重要原則只寫入 memory？ | 是 | 追加到 rules 或 error-pattern |

### CLAUDE.md 章節外移時的目標選擇

縮減 `CLAUDE.md` 體量時，外移目標誤選 `.claude/references/`（跨專案 sync 範圍）會觸發本 error-pattern 的延伸子模式：原意是「縮減 `CLAUDE.md` 不違反任何規則」，但因外移目標放錯範圍，反而新增規則 8 違反。完整決策樹見 `.claude/references/reference-stability-rules.md` §「CLAUDE.md 章節外移決策樹」。

**簡化規則**：

| 章節內容性質 | 外移目標 |
|------------|---------|
| 含 `src/` 路徑、產品名稱、專案 ticket ID | `docs/<檔名>.md`（專案內部，不 sync） |
| 純技術速查、跨專案可複用 | `.claude/references/<檔名>.md`（並通過規則 8 自檢） |
| 混合內容 | 拆檔處理，禁止打包混放 |

### 允許的例外

| 允許保留 | 原因 |
|---------|------|
| error-pattern 檔名（如 `PC-050-xxx.md`） | 框架內部分類，跨專案一致 |
| CC 版本號（如「CC 2.1.97 新增」） | 外部平台能力，所有專案共通 |
| 觸發日期（如「2026-04-12 新增」） | 日期不是專案識別符 |
| `.claude/handoff/archive/` 下的歷史紀錄 | 歷史檔案，sync 不會傳遞 |

### 撰寫時的替換範例

| 原本寫法（禁止） | 改為 |
|---------------|------|
| `**（來源：0.18.0-W4-002）**：Hook error 干擾代理人判斷` | `（防範 Hook error 干擾代理人判斷）` |
| `W5-001 Phase 1 誤判案例` | `看 transcript 中間狀態誤判案例` |
| `PC-050 模式 D（0.17.3-W12-001）` | `PC-050 模式 D` |
| `Version: 3.4.0 - 失敗判斷新增 Step 0.5（W6-006 / W7-001）` | `Version: 3.4.0 - 失敗判斷新增 Step 0.5（TaskOutput 狀態查詢整合）` |

## 觸發案例（日期 + 模式統計）

| 日期 | 模式 | 規模 |
|------|------|------|
| 2026-04-13 | PM 修改 pm-role.md + PC-050 + 新建 pm-agent-observability.md 時加入 ~18 處 ticket 引用 | 3 檔案 × 6 平均引用 |
| 2026-05-11 | 縮減 CLAUDE.md 時將專案規範（含 `src/core/errors/` 路徑、產品名稱）誤外移到 `.claude/references/project-specific-conventions.md`，並將含產品名稱的 Chrome Extension 速查放在 `.claude/references/chrome-extension-quickref.md`；後修正：強違反檔遷移至 `docs/project-conventions.md`、弱違反檔泛化保留並引用「CLAUDE.md 章節外移決策樹」 | 2 檔案違反規則 8（強 + 弱各 1） |

## 檢測方式

```bash
# 掃描所有 .claude/ 文件（排除 handoff archive）的專案 ticket ID 引用
grep -rnE '[0-9]+\.[0-9]+\.[0-9]+-W[0-9]+-[0-9]+' .claude/ \
  --include="*.md" --exclude-dir=handoff | head -20

# 也搜尋獨立 W 編號格式
grep -rnE '(?:^|[^-])W[0-9]+-[0-9]{3}(?:[^0-9]|$)' .claude/ \
  --include="*.md" --exclude-dir=handoff | head -20
```

## 關聯

- **相關規則**: `.claude/references/reference-stability-rules.md` 規則 7（規格文件引用穩定性）、規則 8（框架文件禁引用專案識別符）
- **相關模式**: DOC-005（跨文件原則不同步）
- **相關 memory**: `feedback_framework_product_separation.md` 延伸

---

**Created**: 2026-04-13
**Category**: documentation
**Severity**: medium（誤導風險高但不阻塞開發）
**Key Lesson**: `.claude/` 是跨專案框架，memory 和 ticket 都是專案層級，想讓原則跨專案落實必須寫入 rules/error-patterns/methodologies。
