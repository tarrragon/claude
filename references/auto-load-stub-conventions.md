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

**體量基準**：成功範本 `quality-common.md`（約 0.6k tokens，完全外移）、`skill-cli-sync-check.md`（約 0.8k，純路由）。stub 超過 2.5k tokens 即應重檢是否殘留 substance。

---

## 外移 SOP（收斂不變量，逐項驗證）

| 步驟 | 動作 | 驗證 |
|------|------|------|
| 0. 去處清單（外移前先做） | 以 `grep -n "^#" <舊檔>` 的輸出為骨架建清單，逐列標去處：**全部保留 stub** / **部分保留**（須列子項）/ 移至 `<路徑>` / 刪除（須附依據） | 清單列數 == `grep -c "^#" <舊檔>`（列舉完整性由機械保證，非執行者宣告）；每列去處非空；無「待定」「之後再說」等未決項 |
| 1. substance 保全 | 依清單執行；**未經步驟 0 顯性指派的刪除一律禁止** | 「移至 X」列：逐一在 X 實查命中。「部分保留」與「刪除」列：逐一實查其指定去處或依據。**任何有損壓縮（含保留於 stub、寫入既有壓縮版）須註明捨棄了什麼**，捨棄項回步驟 0 重新指派 |
| 2. hook 錨點保全 | 外移前 grep 確認 hook 引用的規則編號、章節標題、閾值數字仍在 stub 內 | `grep -rn "<規則檔名\|規則編號\|關鍵錨點字串>" .claude/hooks/ .claude/skills/*/hooks/` 全數仍可命中 |
| 3. 引用鏈同步 | 更新 `.claude/` 與 `CLAUDE.md` 中指向舊路徑或舊章節名的引用（`docs/` 內屬歷史敘事，不在範圍） | `grep -rn "<舊路徑>" .claude/ CLAUDE.md` 逐一判定：改指新位置、或確認屬歷史敘事應保留原貌。章節名 grep 僅在該字串具鑑別度時使用（如「核心原則」會回數十筆雜訊） |
| 4. 可達性驗證 | 確認新載體對其**受眾**有入邊——不只是檔案存在，而是受眾讀得到的位置，要有指向它的路由 | 寫出三元組並留在 ticket：受眾是誰 / 該受眾的載入根是什麼 / `grep -rl "<新檔路徑>" .claude/` 的命中結果中哪一處位於該根的可達範圍 |
| 5. 預算驗證 | 修改後跑 file-size-guardian，確認集合總量未回彈 | `CLAUDE_PROJECT_DIR=$(pwd) uv run --script .claude/hooks/file-size-guardian-hook.py 2>&1 \| grep "Auto-load"` 顯示 <= 45k。**差值僅於超標時輸出**，需前後對照時改讀 `.claude/hook-logs/auto-load-budget-state.json` 的 `total_tokens` |

**已知的非送達路徑**（步驟 4 判定時直接排除，勿再逐次重驗）：`.claude/agents/*.md` 主文的 `@path` 以字面字串留存不展開（2026-08-17 三探針實測）；`.claude/references/**` 與 `.claude/pm-rules/**` 非自動載入，僅在被明確指引時讀取。入邊若只落在這些位置，等同無入邊。

**Why**：

- 步驟 0 攔截漏想。舊版驗證為「details 檔頭有註明本檔為完整 substance」——那是執行者自己寫的宣告，漏搬時照樣通過。清單以 grep 產生骨架，使列舉完整性不再依賴執行者記憶。
- 步驟 1 攔截有損壓縮的靜默損失。stub 保留、寫入既有壓縮版都是有損的，「有內容」不等於「等價」。
- 步驟 2 缺失會讓 hook 強制層引用失效且不報錯，grep 範圍須含 skill 內嵌 hooks。
- 步驟 3 缺失重演 stale 描述模式。
- 步驟 4 攔截「內容保全但受眾不可達」——substance 在 repo 中完好，卻只被不送達的載體引用，對其受眾等同不存在。**排在步驟 3 之後**，因為步驟 3 的動作正是在替新檔製造入邊，先驗會產生假失敗。
- 步驟 5 缺失使收斂無量化收口。

**Consequence**：步驟 0、1、4 對應的失效皆為**靜默失敗**——不報錯、不紅燈，內容或路由直接消失，事後只能靠人工逐段比對或委員審查發現。三者在同一 session 內連續發生過。

**攔截範圍與其邊界**：

| 涵蓋 | 不涵蓋 |
|------|--------|
| 章節整段漏搬（步驟 0 機械列舉） | **語意保真**。壓縮時比較運算子轉自然語言等造成的語意變化（如 `> 3` 寫成「3 個以上」使門檻下修一級）無機械判準可攔，仍需逐段比對或 Layer 2 |
| 有損壓縮未申報捨棄項（步驟 1） | 清單填「已移至 X」但實際未移。清單把**漏想**轉為**明知不實而填**，只改變失效性質不消除失效 |
| 新載體無有效入邊（步驟 4） | 章節內子項的遺失，除非該章節被標為「部分保留」而觸發子項列舉 |

**成本**：每次外移新增——列清單（列數 == 舊檔標題數）、步驟 1 對每個「移至 X」與「部分保留」列各一次實查（n 次而非一次）、步驟 4 的 grep 與三元組記錄、步驟 3 範圍由兩個檔擴為 `.claude/` 全樹（常見章節名會回數十筆需逐一判定，故優先以路徑字串 grep）。其中步驟 3 的範圍擴張是增幅最大者。

---

## 寫入決策速查（新知識該放哪一層）

> 本表為「自動載入層判定」的快速子集；完整載體分配（受眾 x 形態十載體地圖）見 `.claude/methodologies/knowledge-carrier-allocation-methodology.md`。

| 自問 | 答案 → 去處 |
|------|------------|
| 這是否每回合都需要遵守的行為禁令？ | 是 → `rules/core/`（禁令 + 路由形態）；否 → 下一問 |
| 這是錯誤學習嗎？ | 是 → `error-patterns/`（自動載入層至多加一行路由） |
| 這是特定情境才需要的流程 / 論證 / 案例嗎？ | 是 → `references/` / `methodologies/` / `pm-rules/` / skill |
| 這是專案特定 context 嗎？ | 是 → memory（`project_` 前綴）；升級後從 MEMORY.md 索引移除（pm-quality-baseline 規則 7） |

---

## 相關文件

- `.claude/methodologies/knowledge-carrier-allocation-methodology.md` — 知識載體頂層責任地圖（本檔為其自動載入層形態的執行規範）
- `.claude/rules/README.md` — 自動載入預算原則（上游判準）
- `.claude/rules/core/document-writing-style.md` + `references/document-writing-style-details.md`「載入層邊界」 — 三明示適用範圍限定
- `.claude/pm-rules/pm-quality-baseline.md` 規則 7 — 升級目的地預算閘門 + 升級即搬家
- `.claude/hooks/file-size-guardian-hook.py` — 45k 預算機器量測（防回彈強制層）

---

**Last Updated**: 2026-08-18
**Version**: 2.0.0 — 外移 SOP 由四步擴為六步（0 至 5），補三個實證缺口：新增步驟 0「去處清單」（舊版步驟 1 的驗證為 details 檔頭自我宣告，漏搬時照樣通過）；步驟 1 補「去處為既有壓縮版時須確認等價」判準；新增步驟 3「可達性驗證」（原無對應步驟——substance 保全但受眾不可達是獨立失效）；原步驟 3 引用鏈同步的 grep 範圍由兩個檔擴為全庫；步驟 2 的 grep 範圍補 skill 內嵌 hooks。三缺口皆有實際案例，回測確認新 SOP 可攔截。
**Version**: 1.0.0 — 初始建立：W7 token 收斂（82.5k → 41.9k）的 stub 形態與外移 SOP 集中成文，取代散落各 ticket 的收斂不變量（W7-007）
