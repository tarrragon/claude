# Auto-load Stub 撰寫規範（外移 SOP + 合格 stub 構成）

本檔集中定義「自動載入層速查 stub」的構成標準與「substance 外移 references/」的操作 SOP。

> **適用時機**：(1) 將 `rules/core/` 檔案瘦身為 stub；(2) 新增自動載入層規則；(3) 修改既有 stub。
> **上游原則**：`rules/README.md`「自動載入預算原則」（每回合必要性自問）+ `document-writing-style.md`「載入層邊界」（自動載入層形態為禁令 + 路由）。
> **機器守門**：file-size-guardian SessionStart 量測 auto-load 集合總量（45k 預算 + 差值追蹤）。

---

## 合格 stub 構成

| 必含元素 | 說明 | 反例（不合格） |
|---------|------|---------------|
| 一行定位 + 完整版路徑 | 檔頭 blockquote：「完整規則：`references/xxx-details.md`（按需讀取）」 | 聲稱外移但 substance 仍留半篇主文 |
| 禁令 / 速查表 | 行為約束本身（規則編號 + 一行核心要求），表格優先 | 每條規則展開 Why/Consequence 多段論證 |
| 觸發路由表 | 「何時讀完整版」：情境 → 必讀章節對照表 | 無路由，讀者不知何時需要完整版 |
| 檢查清單（精簡） | 可勾選項，僅保留判斷句 | 清單項內嵌論證 |

**可刪元素**（外移或刪除，不留 stub）：Why/Consequence 多段論證、事件鏈案例敘事（改一行路由指向 PC/IMP error-pattern）、雙向重複的「與其他規則邊界」表（保留單向，另一檔路由）、多代完整版本歷史（footer 只留最新一至兩代，其餘「見 git log」）。

**體量基準**：成功範本 `quality-common.md`（約 0.6k tokens，完全外移）、`ticket-skill-sync-check.md`（約 0.8k，純路由）。stub 超過 2.5k tokens 即應重檢是否殘留 substance。

---

## 外移 SOP（收斂不變量，逐項驗證）

| 步驟 | 動作 | 驗證 |
|------|------|------|
| 1. substance 保全 | 外移內容寫入 `references/<name>-details.md`，stub 保留觸發條件表 + 完整版路徑；禁止直接刪除 substance | details 檔頭註明「本檔為 `<stub path>` 的完整 substance」 |
| 2. hook 錨點保全 | 外移前 grep `.claude/hooks/` 確認 hook 引用的規則編號、章節標題、閾值數字仍在 stub 內 | `grep -rn "<規則檔名\|規則編號\|關鍵錨點字串>" .claude/hooks/` 全數仍可命中 |
| 3. 引用鏈同步 | CLAUDE.md `@` 引用鏈與 `rules/README.md` 檔數描述同步更新 | `grep -rl "<舊路徑或舊描述>" CLAUDE.md .claude/rules/README.md` 歸零 |
| 4. 預算驗證 | 修改後跑 file-size-guardian，確認集合總量未回彈 | `CLAUDE_PROJECT_DIR=$(pwd) uv run --script .claude/hooks/file-size-guardian-hook.py 2>&1 \| tail -3` 顯示值 <= 45k 且符合預期差值 |

**Why（一行）**：步驟 2 缺失會讓 hook 強制層引用失效（靜默失去防護）；步驟 3 缺失重演 stale 描述模式；步驟 4 缺失使收斂無量化收口。

---

## 寫入決策速查（新知識該放哪一層）

| 自問 | 答案 → 去處 |
|------|------------|
| 這是否每回合都需要遵守的行為禁令？ | 是 → `rules/core/`（禁令 + 路由形態）；否 → 下一問 |
| 這是錯誤學習嗎？ | 是 → `error-patterns/`（自動載入層至多加一行路由） |
| 這是特定情境才需要的流程 / 論證 / 案例嗎？ | 是 → `references/` / `methodologies/` / `pm-rules/` / skill |
| 這是專案特定 context 嗎？ | 是 → memory（`project_` 前綴）；升級後從 MEMORY.md 索引移除（pm-quality-baseline 規則 7） |

---

## 相關文件

- `.claude/rules/README.md` — 自動載入預算原則（上游判準）
- `.claude/rules/core/document-writing-style.md` + `references/document-writing-style-details.md`「載入層邊界」 — 三明示適用範圍限定
- `.claude/pm-rules/pm-quality-baseline.md` 規則 7 — 升級目的地預算閘門 + 升級即搬家
- `.claude/hooks/file-size-guardian-hook.py` — 45k 預算機器量測（防回彈強制層）

---

**Last Updated**: 2026-06-12
**Version**: 1.0.0 — 初始建立：W7 token 收斂（82.5k → 41.9k）的 stub 形態與外移 SOP 集中成文，取代散落各 ticket 的收斂不變量（W7-007）
