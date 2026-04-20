# Meta — Compositional Writing Quality Metrics

本 reference 定義 compositional-writing Skill 的品質量化驗收方式。寫得好不好是主觀判斷，metric 讓它變成可重複驗證的客觀評估。

> **核心理念**：Metric 是自評工具，不是硬性 KPI。目的是讓「達成/未達成」可被重複驗證，並在 Skill 演化過程中守住設計底線。

---

## 何時參閱本檔

| 觸發情境 | 動作 |
|---------|------|
| 驗收本 Skill 新增或修改的 reference | 跑 M1-M2 檢查 |
| 決定是否拆分/合併 reference | 用 M2 評估獨立理解率 |
| 懷疑 SKILL.md 路由設計失靈 | 用 M1 跑 6 情境預期路徑 |
| Skill 發布前的品質門 | M1 + M2 全綠才允許發布（M3-M5 待定後納入） |

---

## Metric 總覽

| ID | 名稱 | 類別 | 目標值 | 量測方式 | 狀態 |
|----|------|------|-------|---------|------|
| M1 | 找到答案路徑長度 | 認知負擔 | ≤ 2 個檔案 | 6 情境預期路徑對照 | 正式 |
| M2 | reference 獨立理解率 | 認知負擔 | 100% | 逐 reference 獨立閱讀檢查 | 正式 |
| M3 | SKILL.md 主檔 token 上限 | Token | ≤ 5000 tokens（候選） | Tokenizer 計數 | 未決（待實際範例後定） |
| M4 | 單一 reference 觸發載入 token | Token | ≤ 3000 tokens（候選） | Tokenizer 計數 | 未決（待實際範例後定） |
| M5 | grep 定位問題的 token 成本 | Token | < 500 tokens（候選） | grep + tokenizer 實測 | 未決（待實際範例後定） |

認知負擔類（M1-M2）為本版正式 metric；Token 類（M3-M5）為候選，待 references/ 內容穩定後再定最終閾值。

---

## M1 — 找到答案路徑長度

### 定義

讀者帶著一個寫作問題從 SKILL.md 開始，**需要開啟幾個檔案**才能解決問題。路徑長度 = SKILL.md 外額外開啟的 reference 檔案數。

- 路徑 1：只讀 SKILL.md 就解決（極罕見，只適用於速查表即可回答的問題）
- 路徑 2：SKILL.md 指引 → 開啟 1 個 reference（預期主流）
- 路徑 3+：SKILL.md → reference A → reference B（違反本 metric）

### 目標值

**≤ 2**（SKILL.md + 1 個 reference 即解決）。

### 量測方式

針對本 Skill 支援的 6 個觸發情境，逐一演練：

1. 模擬讀者帶著該情境的問題進入 SKILL.md
2. 依照 SKILL.md 觸發路由表選擇 reference
3. 計算需開啟的檔案總數（含 SKILL.md）
4. 任一情境路徑長度 > 2 即 M1 FAIL

### 6 個觸發情境的預期路徑

| # | 觸發情境 | 典型讀者問題 | 預期路徑 | 路徑長度 |
|---|---------|------------|---------|---------|
| 1 | 要寫一段程式碼註解 | 「這個函式的註解該寫什麼？doc comment 和 inline 要怎麼選？」 | SKILL.md → writing-code-comments.md | 2 |
| 2 | 要起草一份文件（worklog/markdown） | 「章節怎麼切？哪些資訊該放、哪些不該放？」 | SKILL.md → writing-documents.md | 2 |
| 3 | 要設計 log 訊息 | 「這個 log 要寫什麼關鍵字才搜得到？」 | SKILL.md → writing-logs.md | 2 |
| 4 | 要撰寫 prompt | 「怎麼讓 prompt 更省 token 又講清楚意圖？」 | SKILL.md → writing-prompts.md | 2 |
| 5 | 要設計 ticket/schema 欄位 | 「what 和 why 欄位怎麼分？frontmatter 要有哪些欄位？」 | SKILL.md → designing-fields.md | 2 |
| 6 | 要驗證寫作品質（自評） | 「我寫完了，怎麼知道有沒有達標？」 | SKILL.md → meta-metrics.md | 2 |

**預期總平均**：2（所有情境都是 SKILL.md + 1 個 reference）。

### 量測通過條件

- [ ] 6 個情境逐一演練，每個路徑長度 ≤ 2
- [ ] 無需開啟 reference 後再被引導到另一個 reference（禁止鏈式引用）
- [ ] SKILL.md 的觸發路由表涵蓋 6 個情境，且每個情境對應唯一 reference

### 量測失敗的典型訊號

| 訊號 | 根因 | 對應修正 |
|------|------|---------|
| 讀者讀完某 reference 仍需再開第二個 reference | reference 未自包含，資訊散落 | 把缺漏的原則說明直接寫入該 reference |
| 同一問題在 SKILL.md 路由表找到兩個候選 reference | 情境切分重疊 | 重新畫 reference 邊界，情境不重複 |
| 某情境找不到對應 reference | 情境覆蓋不足 | 新增 reference 或擴充最近情境的覆蓋範圍 |

---

## M2 — reference 獨立理解率

### 定義

隨機挑選一個 reference，讀者**不看其他 reference、不看 SKILL.md** 的情況下，能否獨立理解該 reference 的完整意義並套用到寫作情境。

### 目標值

**100%**（每個 reference 都必須能獨立理解）。

### 量測方式

對每個 reference 執行「獨立閱讀檢查」：

1. 隨機挑一個 reference（不提供 SKILL.md 和其他 reference）
2. 讀完後自問以下四個問題：
   - 我能否說出這份 reference 在講什麼情境？
   - 我能否判斷自己遇到的問題適不適合用這份 reference？
   - 我能否直接套用它給出的原則到我的寫作？
   - 我是否需要去翻其他檔案才能理解某個名詞或規則？
3. 任一問題答案為「否」（第 4 題為「是」也算否）即 M2 FAIL

### 量測通過條件

- [ ] 每個 reference 內部有完整的「情境說明」章節，讀者不看 SKILL.md 也能判斷適用性
- [ ] 所有五大原則（原子化、索引、意圖顯性與商業邏輯、可查詢性、欄位設計）在該 reference 需要時**就地說明**（不引用其他 reference）
- [ ] 專有名詞（Zettelkasten/MOC/原子化等）在首次出現時給出就地定義或連結到外部公認資源
- [ ] reference 間無內部交叉引用（禁止 A→B→C 鏈式）

### 獨立理解率計算

```
獨立理解率 = 通過檢查的 reference 數 / reference 總數 × 100%
```

目標 100%，任一 reference 失敗即整體 M2 FAIL。

### 量測失敗的典型訊號

| 訊號 | 根因 | 對應修正 |
|------|------|---------|
| 讀者讀完後說「我要先去看另一個 reference 才懂」 | 內部交叉引用 | 把被引用的原則說明複製/濃縮到本 reference |
| 讀者無法判斷「這份 reference 講的是什麼情境」 | 情境說明章節缺失或模糊 | 開頭新增「何時參閱本檔」或「適用情境」章節 |
| 讀者看到專有名詞卡住 | 未就地定義 | 在首次出現處加一行解釋或外部連結 |

---

## M3 — SKILL.md 主檔 token 上限（候選，未決）

### 定義

SKILL.md 主檔被 Claude 載入時的 token 消耗總量。

### 候選目標值

**≤ 5000 tokens**（對齊 Anthropic 官方建議：SKILL.md body < 5k tokens）。

### 量測方式（候選）

1. 用 Anthropic tokenizer 或 Claude Code 內建計數計算 SKILL.md 全文 token 數
2. 扣除 YAML frontmatter（frontmatter 常駐 system prompt，另計）
3. body token 數須 ≤ 5000

### 狀態

**未決**。實際閾值待 SKILL.md 與各 reference 完成後，量測實際 token 數再定最終值。可能調整方向：

- 若實際 SKILL.md 穩定在 2000 tokens 內，閾值可降為 3000 tokens 作為緩衝
- 若 SKILL.md 接近 5000 tokens，需拆分更多內容到 references 而非放寬閾值

---

## M4 — 單一 reference 觸發載入 token（候選，未決）

### 定義

單一 reference 被 Claude 按需載入時的 token 消耗量。

### 候選目標值

**≤ 3000 tokens**（避免單一 reference 過大，讓讀者/Claude 只能全讀）。

### 量測方式（候選）

1. 對每個 reference 計算 token 數
2. 任一 reference > 3000 tokens 即 FAIL
3. 超標的 reference 應檢討：是否混入多個情境？是否能切分？

### 狀態

**未決**。實際閾值待所有 reference 完成後依分佈定案。候選分級：

- 嚴格（< 2000）：強制 reference 高度原子化
- 寬鬆（< 4000）：允許情境 reference 包含更多實例
- 最終選擇依 Skill 各 reference 完成後的實測資料定

---

## M5 — grep 定位問題的 token 成本（候選，未決）

### 定義

讀者/AI 用 grep + 關鍵字在 Skill 內定位到答案時，所讀取的 token 總成本。

### 候選目標值

**< 500 tokens**（grep 結果片段 + 關鍵命中行的上下文即能回答問題）。

### 量測方式（候選）

1. 挑選 10 個代表性寫作問題
2. 用對應關鍵字 grep 全 Skill 內容
3. 取前 N 個命中（N=3），計算閱讀命中上下文所需 token
4. 任一問題 > 500 tokens 即 FAIL

### 狀態

**未決**。此 metric 需要：

- 先建立「代表性問題」清單（10-20 個）
- 實測 grep 命中品質（關鍵字設計是否到位）
- 依實測結果決定 500/1000/2000 tokens 哪個是可行閾值

---

## 自評流程

### 何時執行

| 場景 | 執行的 Metric |
|------|-------------|
| 新增 reference 時 | M1（新增情境路徑）+ M2（新 reference 獨立理解率） |
| 修改 reference 內容時 | M2（該 reference 獨立理解率）+ M1（若觸發路由變動） |
| 修改 SKILL.md 路由表時 | M1 全 6 情境重測 |
| Skill 版本發布前 | M1 + M2 全綠（M3-M5 定案後納入） |
| 定期健檢（每季） | 全部 metric 重跑 |

### 由誰執行

- 撰寫者自評：寫完立即跑 M1 + M2
- 審查者覆核：Skill PR/Ticket 驗收時跑全 metric
- 跨專案使用者：在 marketplace 下載 Skill 後，建議跑 M2 確認獨立理解率

### 用什麼工具

| Metric | 工具 |
|--------|------|
| M1 | 手動演練（6 情境對照表）+ 本檔「量測通過條件」清單 |
| M2 | 手動獨立閱讀 + 四問檢查清單 |
| M3 | Anthropic tokenizer / Claude Code 內建 token 計數 |
| M4 | 同 M3，per-file 計數 |
| M5 | grep（或 ripgrep）+ tokenizer |

### 自評產出格式

建議自評結果以下表記錄（貼到 Skill 或相關 ticket 的驗收區）：

```
Metric 自評結果（日期 / 執行者）

| Metric | 結果 | 備註 |
|--------|------|------|
| M1 | PASS (所有情境 ≤ 2) | — |
| M2 | PASS (6/6 reference 獨立理解) | — |
| M3 | N/A（未決） | SKILL.md 實測 XXXX tokens |
| M4 | N/A（未決） | 最大 reference XXXX tokens |
| M5 | N/A（未決） | 待關鍵字清單定案 |

整體結論：PASS / FAIL + 須修正項目清單
```

---

## Metric 間的優先級

當 metric 之間出現張力時，依下列順序取捨：

1. **M2 > M1**：若為了降低路徑長度而讓某 reference 依賴另一個 reference，優先維持獨立理解（M2），重新設計路由而非犧牲獨立性
2. **M1 > M3/M4**：若為了壓 token 而切得太細導致路徑長度 > 2，優先維持 M1，放寬單檔 token 閾值
3. **M2 > M5**：若為了 grep 定位成本而在多處重複同一關鍵說明，優先維持 M2（獨立理解），允許 grep 命中多個檔案但每個命中都能獨立看懂

**核心排序**：M2 > M1 > M5 > M3 ≈ M4

這個排序反映：獨立理解是 compositional writing 的命脈（卡片盒核心），路徑長度是讀者體驗，token 是工程成本；若三者衝突，優先守住可理解性。

---

## 與上層原則的對應

| Metric | 守護的寫作原則 |
|--------|--------------|
| M1 | 情境匹配度（一個情境對應一張卡） |
| M2 | 原子化（一張卡獨立自足）+ 可查詢性（就地定義） |
| M3 | 精簡至上（Concise is Key） |
| M4 | 原子化（reference 不過度肥大） |
| M5 | 可查詢性（關鍵字設計到位） |

---

## 變更歷史

| 版本 | 變更 | 日期 |
|------|------|------|
| 0.1.0 | 初版，M1-M2 正式、M3-M5 候選未決 | 2026-04-16 |
