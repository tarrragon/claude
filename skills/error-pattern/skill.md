---
name: error-pattern
description: "錯誤模式知識庫管理工具。Use for: (1) 查詢既有錯誤經驗和防護措施 (query), (2) 記錄新發現的錯誤模式和教訓 (add), (3) Ticket 開始前查詢歷史問題避免再犯, (4) 系統化管理錯誤學習經驗。Use when: user mentions error pattern, 錯誤模式, 教訓, 經驗記錄, 學習經驗, 防護措施, 錯誤紀錄, or needs to avoid recurring issues."
---

# error-pattern SKILL

錯誤模式知識庫管理工具。查詢既有錯誤經驗，記錄新發現的錯誤模式。

## 指令

### `/error-pattern query <關鍵字> [--category <CAT>]`

查詢既有錯誤模式經驗。

**使用時機**：每個 Ticket 開始前

**參數**：
- `<關鍵字>`：搜尋詞（必填）
- `--category <CAT>`：依 category 目錄篩選結果（選填）。有效值：`PC`、`IMP`、`ARCH`、`CQ`、`DOC`、`TEST`、`PROC`。對應 `.claude/error-patterns/` 子目錄（`PC` → `process-compliance/`、`IMP` → `implementation/`、`ARCH` → `architecture/`、`CQ` → `code-quality/`、`DOC` → `documentation/`、`TEST` → `test/`、`PROC` → `process/`）。

**執行流程**：
1. **同義詞擴展**：比對 `references/synonym-map.md` 家族表（11 家族），若用戶關鍵字命中任一家族的同義詞，展開為該家族全部變體的 multi-term OR grep（如 `grep -rli "confabul\|fabricat\|幻覺\|虛構\|腦補"`）。未命中任何家族時使用原始關鍵字。
2. **搜尋範圍**：
   - 未指定 `--category`：搜尋 `.claude/error-patterns/` 全部子目錄
   - 指定 `--category PC`：僅搜尋 `.claude/error-patterns/process-compliance/`
3. 使用展開後的關鍵字匹配錯誤症狀、根因、解決方案
4. **結果排序**：有 YAML frontmatter（`id:`/`title:`/`severity:`）的檔案優先顯示摘要；無 frontmatter 的檔案依標題行顯示
5. 返回匹配的錯誤模式清單

**輸出格式**：
```
找到 N 個相關錯誤模式（共搜尋 M 檔）：
（命中率 > 30% 時追加提示：命中率 X%，建議加 --category 篩選縮小範圍）

--- 有 frontmatter 的結果（優先顯示）---

1. [PC-166] confabulation 觸發鏈與防護 [severity: high]
   - 症狀：簡短描述
   - 路徑：process-compliance/PC-166-...

--- 其餘結果 ---

2. [PC-147] ...（從標題行提取）
   - 路徑：process-compliance/PC-147-...

（無匹配時）
未找到相關錯誤模式。這可能是新發現的問題，請使用 /error-pattern add 記錄。
```

**`severity` 權威來源與更新時機**（0.2.1-W3-106）：內文「基本資訊」區塊的「風險等級」／「嚴重度」欄位是第一手判斷來源（撰寫當下對症狀實際後果的人工評估）；frontmatter `severity` 是供 `query` 排序/顯示讀取的同步鏡射欄位，兩者必須一致。更新時機：

- **新建立時**：撰寫「基本資訊」區塊的內文「風險等級」時，frontmatter `severity` 必須同時填入相同值，禁止 frontmatter 留預設 placeholder 或憑感覺快速填寫後不比對內文。
- **事後修訂內文風險等級時**：必須同步更新 frontmatter `severity`，否則 `query` 排序/顯示會呈現與內文判斷不一致的等級（PC-BAL 類漂移，見 0.2.1-W3-105 診斷）。
- **禁止**片面只改 frontmatter `severity` 而不核對內文——frontmatter 是否正確以「是否忠實反映內文判斷」為準，不是獨立來源。

0.2.1-W3-106 已完成全量覆核修正：381 檔中 15 檔（皆有值可比對者）分歧，14 檔判定內文較準確並已同步更新 frontmatter；1 檔（ARCH-001）判定 frontmatter 較準確而保留原值，內文對應修正已記錄為 spawn-request（SR-1）待後續票處理。

### `/error-pattern add`

互動式記錄新發現的錯誤模式。

**使用時機**：發現新問題時

**執行流程**：

1. **選擇錯誤類別**（對應 `.claude/error-patterns/` 子目錄）
   - architecture: 架構設計相關
   - code-quality: 程式碼品質相關
   - documentation: 文件相關
   - implementation: 實作 bug 相關
   - process-compliance: 流程合規相關
   - test: 測試相關

2. **輸入症狀描述**
   - 錯誤訊息特徵
   - 發生位置類型

3. **分析根因**
   - 為什麼會發生
   - 行為模式分析

4. **記錄解決方案**
   - 具體修復步驟
   - 程式碼範例（如適用）

5. **提出預防措施**
   - 如何避免再次發生
   - 相關 Hook 或檢查機制建議

6. **關聯 Ticket**
   - 輸入相關 Ticket 編號

7. **原子分配並保留來源前綴 ID**（跨專案共享框架必用，0.2.1-W3-271 改接原子版入口）
   - 呼叫 allocator 的 `allocate_and_reserve_pattern_id`：在鎖保護下把「決定編號」與
     「建立佔位檔」合併為單一原子操作。**取代**舊版 `allocate_pattern_id`（僅回傳
     預覽字串、不建檔、不持鎖，並行呼叫下有 TOCTOU 撞號風險，見 0.2.1-W3-167）：
     ```python
     import sys; sys.path.insert(0, ".claude/skills/error-pattern/lib")
     from allocator import identify_project_code, allocate_and_reserve_pattern_id
     proj = identify_project_code(
         ".claude/error-patterns/_project-registry.yaml",
         "<git toplevel>",  # git rev-parse --show-toplevel
     )
     stub_path = allocate_and_reserve_pattern_id(
         "<CATEGORY>", ".claude", proj, reserved_by="<agent-name>"
     )
     pattern_id = stub_path.stem  # 佔位檔檔名（無 slug）即 pattern_id
     ```
   - **佔位檔語意**：函式回傳時，`stub_path` 指向的檔案已實際建立於磁碟（`status:
     reserved` frontmatter + 標題 `(reserved - 內容待補)`）——編號在配號當下即被
     佔用，非僅回傳字串。任何後續並行呼叫的掃描必然看到此佔位檔，不會配出相同編號。
   - **接續動作**：拿到 `stub_path` 後，立即以 **Edit**（非 Write 新檔）把步驟
     2-6 蒐集的症狀/根因/解決方案/預防措施/關聯 Ticket 內容填入該檔案，取代佔位
     內容；填妥後可依慣例將檔名改為 `<CATEGORY>-<PROJ>-NNN-<slug>.md`（純索引可
     讀性，非必要）。**禁止**另外 Write 建立第二個新檔——編號已綁定 `stub_path`
     這個實體檔案，另建新檔會留下未清理的 reserved 空殼。
   - **非 POSIX 降級**：`fcntl`（POSIX 標準庫）不可用時，鎖機制輸出 stderr 警告
     並以無鎖模式續行配號（佔位檔仍會建立，僅失去並行防護）；此環境下應改為
     序列執行 `/error-pattern add`，避免並行呼叫撞號。
   - allocator 自動：以 git toplevel basename 自我識別專案代號 → 掃該專案前綴空間
     取最大號 +1（含既有檔案掃描與 pending ticket 文字引用掃描，flat 凍結 base
     不參與遞增）。
   - **禁止**手動指定 flat `<CATEGORY>-NNN`（凍結 base 不再新增，見編號章節）。

8. **同步 README 索引**（0.2.1-W3-099，取代舊版「手動更新 README.md 統計資訊」）
   - 寫入新錯誤記錄檔案後，呼叫 `readme_index.sync` 做保守 upsert（只新增本次新建
     pattern 的索引列與清掉死連結列，既有列一律不動）：
     ```python
     import sys; sys.path.insert(0, ".claude/skills/error-pattern/lib")
     from readme_index import sync
     _original, _updated, diff = sync(".claude")
     if diff:
         readme_path = ".claude/error-patterns/README.md"
         with open(readme_path, "w", encoding="utf-8") as f:
             f.write(_updated)
     ```
   - 或等效 CLI：`uv run .claude/skills/error-pattern/lib/readme_index.py sync --write`
   - **禁止**手動編輯 README.md 的「現有模式」表格資料列（結構化內容由工具生成，
     見 structured-content-generation 原則）；新增列的風險等級一律取自檔案內文
     「基本資訊」區塊，**不取自 frontmatter `severity`**（0.2.1-W3-105 診斷分歧、
     0.2.1-W3-106 全量覆核並同步兩者後，`readme_index.extract_row` 維持讀內文
     的既有設計不變——內文是第一手來源，frontmatter 是同步鏡射，讀哪一份理論
     上結果相同，維持讀內文可省一次「若未來又漂移」的防呆成本）。

**輸出**：
- 步驟 7 已建立分類檔案（初始檔名 `<CATEGORY>-<PROJ>-NNN.md`），步驟 7 接續動作
  以 Edit 填入實際內容，並可選擇改名為 `<CATEGORY>-<PROJ>-NNN-<slug>.md`
- README.md 索引由步驟 8 的 `readme_index.sync` 自動同步，不需人工步驟。**與步驟
  8 的相容性**：`readme_index.scan_category_rows` 依檔名前綴掃描分類目錄下所有
  `.md` 檔，**不檢查 `status` frontmatter**——若佔位檔仍處於 reserved（內容未填）
  狀態時執行步驟 8，`(reserved - 內容待補)` 的佔位標題會被同步進 README 產生
  空殼列。正確順序：先完成步驟 7 接續動作（Edit 填入實際內容）再執行步驟 8，
  確保 sync 讀到的是完整內容而非佔位符

### `/error-pattern list`

列出所有已記錄的錯誤模式。

**輸出格式**：
```
錯誤模式知識庫統計：

implementation (5)
├─ [IMP-008] Bash 工作目錄污染
├─ [IMP-MON-003] 貪婪字串替換誤中 URL 子字串
└─ ...

process-compliance (12)
├─ [PC-040] 派發前未寫 Context Bundle
├─ [PC-V1-001] sync-push 未知參數被當 commit message
└─ ...
```

---

## 錯誤編號規則

### Category 前綴（依目錄）

| 類別目錄 | 前綴 | 凍結 base 範例 |
|---------|------|---------------|
| architecture | ARCH | ARCH-001 |
| code-quality | CQ | CQ-001 |
| documentation | DOC | DOC-001 |
| implementation | IMP | IMP-001 |
| process | PROC | PROC-001 |
| process-compliance | PC | PC-001 |
| test | TEST | TEST-001 |

### 來源前綴（跨專案共享框架必用）

本框架透過共享 repo 同步至多個專案。為防多專案併發分配同號碰撞，**新增任何
category 的 error-pattern 一律使用來源前綴格式**：

```
<CATEGORY>-<PROJ>-NNN     例：PC-V1-001、IMP-APP-003、ARCH-SCLK-002
```

- 既有 flat `<CATEGORY>-NNN` 為**凍結 canonical base**，原樣保留、不再新增 flat 號。
- `<PROJ>` 取自 `.claude/error-patterns/_project-registry.yaml`（tooling 以 git
  toplevel basename 對應 `dir` 欄自動取得）。
- 完整規則（凍結語意、協議字串豁免、canonical 升格、dedup、rejected options）見
  `.claude/methodologies/error-pattern-numbering-methodology.md`。

> **單一專案使用本框架時**：無碰撞風險，可沿用 flat `<CATEGORY>-NNN`。來源前綴僅在
> 多專案共享同步情境強制。

---

## 整合到工作流程

### Ticket 模板整合

在 Ticket 中加入：
```markdown
## 參考既有錯誤模式
<!-- 執行 /error-pattern query 後填寫 -->
- [ ] 已查詢既有模式
- 匹配模式：[編號] 或「無匹配 - 新發現模式」
```

### Worklog 整合

在工作日誌中記錄：
```markdown
## 錯誤模式學習
- 發現新模式：[編號] 錯誤名稱
- 參考既有模式：[編號] 錯誤名稱
```

---

## 檔案位置

| 檔案 | 用途 |
|------|------|
| `.claude/error-patterns/README.md` | 知識庫索引 |
| `.claude/error-patterns/{category}/*.md` | 各分類錯誤模式檔案 |

---

**Last Updated**: 2026-08-10
**Version**: 1.4.1 — 本 skill 的入口檔由 `skill.md` 更名為 `SKILL.md`（原小寫檔名使各消費端以 `*/SKILL.md` 掃描的產生器與稽核器永久漏掉本 skill）；`lib/severity_audit.py` 內指向該入口檔的路徑引用同步更正。無流程或命令變更
**Version**: 1.4.0 — 步驟 7 改接原子版入口 `allocate_and_reserve_pattern_id`（取代舊版 `allocate_pattern_id`），補佔位檔語意、接續 Edit 動作、非 POSIX 降級說明；步驟「輸出」補與步驟 8 `readme_index.sync` 的相容性提示（reserved 狀態下同步會產生空殼列，需先完成內容填寫再同步）（0.2.1-W3-271，接續 0.2.1-W3-167 allocator 原子化）
**Version**: 1.3.0 — 明訂 `severity` 權威來源與更新時機：內文「風險等級」為第一手來源，frontmatter 為同步鏡射；全量覆核修正 15 檔分歧中的 14 檔（0.2.1-W3-106，接續 0.2.1-W3-105 診斷）
**Version**: 1.2.0 — add 流程新增步驟 8：README 索引同步改由 `readme_index.sync` 保守 upsert CLI 化，取代「更新 README.md 統計資訊」文字指示（0.2.1-W3-099，接線方式經 0.2.1-W3-105 更正）
**Version**: 1.1.0 — query 增強：--category 篩選、同義詞家族 5→11、frontmatter 摘要排序、命中數計數（1.5.0-W5-016）
