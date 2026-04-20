# PC-098: PM 撰寫通用規則時本能引用當下任務 ticket ID

## 錯誤症狀

PM 在 `.claude/rules/`、`.claude/methodologies/`、`.claude/error-patterns/`、`.claude/skills/` 等框架層檔案中，將當下執行任務的 Ticket ID（如 `W10-011`、`W10-011.1`）寫入規則本文，作為「動機案例」「驗證樣本」或「銜接說明」的引用標記。

典型表現：
1. **規則內文嵌入 ticket ID**：規則段落直接寫「W10-011 為註解專項套用」「W10-011.1 落地」等
2. **相關文件章節列 ticket ID**：「相關文件」段落列「W10-011（擴充註解規則）」「W10-011.2（驗證樣本）」
3. **Version footer 紀念當下 ticket**：`Version: 1.0.0 — W10-011.1 落地`
4. **Source 章節引用 ticket 鏈**：`Source: W10-011 系列（父子銜接見...）`

## 根因分析

### 表層原因：撰寫脈絡與成品脈絡未分離

PM 撰寫規則時心智狀態是「我在執行 W10-011.1 任務、它的父是 W10-011、它的兄弟是 W10-011.2」。此脈絡是當下 PM 工作的真實情境。

撰寫時 PM 將此脈絡直接寫入規則內文，視為「正當的因果連結」。

### 深層原因：規則的時間維度斷裂

| 維度 | 撰寫當下 | 6 個月後 | 跨專案 sync |
|------|---------|---------|------------|
| Ticket ID 含義 | PM 與用戶共同記憶的具體任務 | 已歸檔的歷史編號，需查 ticket md 才知意圖 | 完全失效（其他專案無此 Ticket） |
| 規則文字含義 | 鮮活、有指向 | 文字仍在但 ticket 引用變成「死連結」 | 規則被 sync 後 ticket 引用變成「不存在的編號」 |
| 讀者體驗 | PM 能解釋連結的意義 | 讀者必須跳轉 ticket 才能理解規則為何如此寫 | 讀者完全無法解析規則內的編號 |

規則的時間範圍是「跨 session、跨版本、跨專案」。Ticket ID 的時間範圍是「該專案該版本的工作排程」。將後者寫入前者，等於把短壽命標記焊進長壽命載體。

### 次要原因：「相關文件」章節範本誤導

許多既有規則檔的「相關文件」章節列出了 Ticket ID（屬歷史遺留違規）。PM 撰寫新規則時複用範本結構，順手把當下 ticket 填入。

### 第三層原因：規則 8（reference-stability-rules）非 auto-load

`.claude/references/reference-stability-rules.md` 規則 8（框架禁引用專案層級識別符）為按需讀取，PM 撰寫規則時若未主動觸發載入，本能寫法不會被自我檢查擋下。

## 實際案例

### 案例 1：建立 document-writing-style.md 時嵌入 10 處 ticket ID

PM 撰寫 `.claude/rules/core/document-writing-style.md`（文件撰寫明示性規則），首次 Write 時包含以下引用：

- 適用範圍表格：「程式碼短註解（W10-011 專項）」
- 與其他規則邊界表格：「W10-011 為註解專項套用」「W10-011 註解規則」
- 銜接章節：「DRY 銜接：W10-011 註解規則...」
- quality-baseline 銜接 Action：「如 W10-011.2 之於 PC-066」
- 相關文件章節：「W10-011（擴充 註解撰寫原則）」「W10-011.2（重寫 PC-066 作明示性驗證）」
- Footer：「Version: 1.0.0 — W10-011.1 落地」「Source: PC-066 + W10-011 系列」

`boundary-validation hook` 攔截 10 處警告 `[WARNING] Layer 1/2 邊界驗證警告 / 禁止項：Wave/Patch 版本概念 / 內容：W10`。

PM 修正後改用：
- 抽象角色稱呼（「註解專項規則」）
- 檔案路徑引用（`comment-writing-methodology.md`）
- 抽象描述（「PC-066 重寫工作」「驗證樣本工作」）

修正後規則跨時間 / 跨專案 sync 都能保持有效。

## 防護措施

### 措施 1：boundary-validation hook（已存在，外部防護）

`.claude/hooks/` 中的邊界驗證 hook 在 PostToolUse:Write 時掃描 `.claude/rules/`、`.claude/methodologies/` 等框架資產，偵測 `W\d+`、`Wave\s*\d+` 模式，命中即輸出 `[WARNING] Layer 1/2 邊界驗證警告` + 行列定位 + 修正建議。

**Why**: PM 本能寫法在自律檢查前已落入檔案，外部 hook 是最後防護網。
**Action**: 收到 hook 警告時，逐項替換為抽象描述或檔案路徑引用，重新 Write 驗證。

### 措施 2：規則 8 升級為 auto-load 候選（待評估）

當前 `.claude/references/reference-stability-rules.md` 規則 8 為按需讀取。考量本案例顯示「規則 8 未在 PM 撰寫規則時主動載入」，可評估升級為 `.claude/rules/core/` 自動載入。

**Why**: auto-load 規則是 PM session 啟動時即進入工作記憶；按需讀取需 PM 主動觸發，撰寫規則時容易遺漏。
**Consequence**: 不升級則 hook 仍是唯一防護點，PM 自律機制無預先警告。
**Action**: 建議建立 ANA Ticket 評估升級成本與收益（規則檔大小 / auto-load 預算 / hook 重複度）。

### 措施 3：規則範本「相關文件」章節去 ticket 化（待落地）

既有規則檔的「相關文件」章節若仍含歷史 ticket ID 引用，視為違規遺留。PM 在修訂既有規則時順手清理；新建規則時範本不含 ticket ID 樣式。

**Why**: 範本誤導是次要根因；範本去 ticket 化從源頭防止複製貼上違規。
**Action**: 維護範本時明示「相關文件」應用檔案路徑或抽象角色稱呼，不用 ticket ID。

### 措施 4：撰寫規則前自檢清單（人工 fallback）

PM 撰寫規則 / 方法論 / PC error-pattern 前自問：

- [ ] 我即將寫的引用是否包含 Ticket ID（W\d+、版本號、Wave 編號）？
- [ ] 該引用 6 個月後 / 跨專案 sync 後是否仍可解析？
- [ ] 是否可改用檔案路徑、抽象角色稱呼、或 PC 編號替代？

## 自我檢查清單

PM 在撰寫框架資產前自問：

- [ ] 本檔案位於 `.claude/rules/`、`.claude/methodologies/`、`.claude/error-patterns/`、`.claude/skills/`？（屬框架資產）
- [ ] 我是否準備寫入當下任務的 Ticket ID 作為「動機」「銜接」「驗證」？
- [ ] 該 Ticket ID 在跨 session、跨版本、跨專案後是否仍有意義？
- [ ] 是否可改用：檔案路徑（`xxx.md`）、抽象角色（「註解專項規則」）、PC 編號（屬框架層）、或完全省略？

## 關聯

- **相關規則**：`.claude/references/reference-stability-rules.md` 規則 8（框架禁引用專案層級識別符）
- **相關規則**：`.claude/rules/core/document-format-rules.md`（規則 6 引用路徑格式）
- **相關 Hook**：`boundary-validation hook`（PostToolUse:Write 偵測層）
- **首次案例**：建立 `.claude/rules/core/document-writing-style.md`（10 處違規 + 修正過程）
- **相關模式**：PC-061（Memory 升級未評估，「原則建立後執行斷裂」）— 本模式為「原則建立過程的脈絡污染」
- **相關模式**：PC-066（決策品質自動駕駛）— 本模式為「文件撰寫的自動駕駛變體」

---

**Created**: 2026-04-19
**Last Updated**: 2026-04-19
**Category**: process-compliance
**Severity**: P2（hook 已作外部防護，但 PM 本能反應仍會頻繁觸發 warning，影響工作節奏）
**Key Lesson**: 規則文字的時間範圍是「跨 session、跨版本、跨專案」；Ticket ID 的時間範圍是「該專案該版本的工作排程」。將後者寫入前者，等於把短壽命標記焊進長壽命載體。**正確修正方向**：撰寫框架資產時改用檔案路徑、抽象角色稱呼、或 PC 編號（屬框架層）。
**Meta Lesson**: PM 撰寫規則時的脈絡是當下任務情境，本能會把該情境寫入規則作為「正當因果連結」。Hook 攔截是最後防護網；自律機制需在撰寫前主動觸發規則 8 自檢。Hook 警告是訊號，提示「我又進入了 PM 撰寫規則的本能模式」。
