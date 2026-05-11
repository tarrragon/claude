# Ticket 六欄位詳解：正確範例與常見混淆（12 項）

本文件為 `designing-fields.md` §6 的詳細附錄。
每個欄位提供 1 個正確範例 + 1 個常見混淆範例，共 12 項。

> **前置閱讀**：先讀 `designing-fields.md` §6「六欄位角度總表」，理解六個欄位的角色分工後再閱讀本文件。

---

## `what` 欄位

### 正確範例

**欄位提問**：這個 ticket 要做什麼？（描述動作/內容，不含動機）

```yaml
what: "在使用者設定頁新增「雙因素驗證（2FA）」開關，支援 TOTP 與 email 驗證碼兩種方式"
```

**為什麼正確**：

- 描述「做了什麼」（新增開關、支援兩種方式）
- 不解釋為什麼做（動機屬於 `why`）
- 不描述怎麼做（實作策略屬於 `how`）
- 範圍具體（使用者設定頁、TOTP + email），閱讀者能立刻想像成品

### 常見混淆：把動機寫進 what

```yaml
# 錯誤
what: "因為最近有用戶帳號被盜，所以要加強安全，做一個 2FA"
```

**為什麼混淆**：

- 「因為...所以」的結構顯示這是動機（why），不是動作（what）
- 讀者需要剝離「因為...」才能看到真正的動作
- 與 `why` 欄位內容重複，降低欄位密度
- 查詢「做了什麼」時會讀到動機雜訊

**改善**：動機搬到 `why`，`what` 只留動作：

```yaml
what: "新增 2FA 設定開關，支援 TOTP 與 email 驗證碼"
why:  "最近三個月有 N 起帳號盜用事件，2FA 可降低風險"
```

---

## `why` 欄位

### 正確範例

**欄位提問**：為什麼需要做這件事？（業務動機，不含實作原因）

```yaml
why: "過去三個月登入頁崩潰影響 8% 活躍用戶，平均每位受影響用戶嘗試 3 次才成功登入。修復後預期可提升首週留存 1.5 個百分點，並減少客服工單量（當前每週 40 張與登入相關）"
```

**為什麼正確**：

- 陳述業務動機（用戶影響、留存、客服成本）
- 含具體數字讓重要性可衡量
- 不解釋「怎麼修」（那是 how 的責任）
- 不描述「做什麼」（那是 what 的責任）

### 常見混淆：把 what 寫進 why

```yaml
# 錯誤
why: "要修復登入頁的崩潰 bug，會修改 auth.py 第 42 行並加 try-catch"
```

**為什麼混淆**：

- 「修復崩潰 bug」是 what，不是 why
- 「修改 auth.py 第 42 行」是 how（實作細節）
- 完全沒回答「為什麼要修」的業務問題
- 讀者讀完 `why` 仍不知道這個 ticket 的價值在哪

**改善**：動機與實作各歸各位：

```yaml
why:  "登入崩潰導致 8% 用戶流失，每週產生 40 張客服工單"
what: "修復登入頁 authentication flow 的 null pointer"
how:  "在 auth.py token 解析前加 guard clause；補 unit test 覆蓋 null token 情境"
```

---

## `when` 欄位

### 正確範例

**欄位提問**：什麼時候觸發/執行這個 ticket？（條件/時機，不是動作內容）

```yaml
when: "v1.2.0 發佈前（預計 2026-05-10），依賴 W03-021 架構草案完成後即可啟動" # portability-allow: educational when-field example
```

**為什麼正確**：

- 回答「什麼時候」的問題（版本截止、前置依賴）
- 條件可被驗證（檢查 W03-021 狀態即可）<!-- portability-allow: educational reference example -->
- 不混入「要做什麼」或「為什麼」

### 常見混淆：把 what 重述一遍

```yaml
# 錯誤
when: "當使用者點擊登入按鈕時，系統會驗證帳密並嘗試登入"
```

**為什麼混淆**：

- 這描述的是**產品行為的觸發時機**，不是 ticket 執行的時機
- 把 `what`（驗證流程）用時序包裝後重述
- 真正的 `when`（ticket 啟動條件）完全缺失
- 讀者不知道何時該開始做這個 ticket

**改善**：分清「ticket 啟動時機」與「產品行為時機」：

```yaml
when: "登入崩潰回報量超過每週 20 起即啟動；最遲在下一個 minor 版本發佈前完成"
what: "修復登入流程：驗證帳密 → 產生 session → 導向首頁"
```

---

## `where` 欄位

### 正確範例

**欄位提問**：影響哪些檔案/模組/層級？（範圍定位，不是做什麼）

```yaml
where:
  layer: Application
  files:
    - src/auth/login_service.py
    - src/auth/session_manager.py
    - tests/auth/test_login_flow.py
```

**為什麼正確**：

- 明確列出修改範圍（檔案 + 層級）
- 讓驗收者知道要檢查哪些檔案
- 協作者能預判 merge 衝突
- 不混入動作描述

### 常見混淆：寫抽象功能而非具體位置

```yaml
# 錯誤
where: "使用者登入流程相關的所有地方"
```

**為什麼混淆**：

- 「所有地方」無法定位，等於沒說
- 驗收者無法確認範圍是否完整
- 協作者無法預判衝突
- 若未來 refactor，沒有具體檔案可追溯

**改善**：改為具體檔案清單與層級：

```yaml
where:
  layer: Application + Infrastructure
  files:
    - src/auth/login_service.py        # 主邏輯
    - src/auth/token_validator.py      # token 驗證
    - src/infra/redis_session_store.py # session 儲存
```

---

## `how` 欄位

### 正確範例

**欄位提問**：用什麼策略/順序實作？（實作計畫，不是業務內容）

```yaml
how:
  task_type: Implementation
  strategy: |
    1. 在 token_validator 加 guard clause 處理 null/malformed token
    2. 將 session_manager 的錯誤處理改為 Result 模式而非例外
    3. 補 unit test 覆蓋 6 種失敗情境（null / expired / malformed / revoked / ip_mismatch / ua_mismatch）
    4. 跑 integration test 驗證與 Redis 互動正確
```

**為什麼正確**：

- 提供實作步驟與順序
- 選擇具體技術方案（guard clause、Result 模式）
- 不重述業務需求（那是 what）
- 不寫動機（那是 why）

### 常見混淆：把 acceptance 寫進 how

```yaml
# 錯誤
how:
  strategy: "做完要通過所有單元測試，且 login 成功率回到 99.5% 以上"
```

**為什麼混淆**：

- 「通過測試」「成功率 99.5%」是驗收條件（acceptance），不是實作策略
- 沒回答「怎麼做」的問題
- 讀者不知道實際要改什麼
- 驗收與實作責任混淆

**改善**：分離「做法」與「驗收標準」：

```yaml
how:
  strategy: "先加 guard clause → 改為 Result 模式 → 補單元測試 → 跑整合測試"
acceptance:
  - "[ ] 所有單元測試通過"
  - "[ ] Staging 環境 login 成功率 ≥ 99.5%（觀察 24 小時）"
```

---

## `acceptance` 欄位

### 正確範例

**欄位提問**：怎樣算完成？（可驗證的條件清單）

```yaml
acceptance:
  - "[ ] auth 模組所有單元測試通過（含新增的 6 個失敗情境測試）"
  - "[ ] Staging 環境連續 24 小時 login 成功率 ≥ 99.5%"
  - "[ ] 客服工單中「登入無法使用」類別在部署後 7 天內下降 ≥ 50%"
  - "[ ] Code review 由另一位後端工程師核可（需涵蓋錯誤處理章節）"
```

**為什麼正確**：

- 每條都**可驗證**（有明確判斷標準）
- 每條都**可觀察**（測試結果、指標、核可紀錄）
- 數字具體（99.5%、24 小時、50%、7 天）
- 不抽象（沒有「讓系統更穩定」這種不可驗證的描述）

### 常見混淆：不可驗證的模糊條件

```yaml
# 錯誤
acceptance:
  - "[ ] 使用者體驗變好"
  - "[ ] 程式碼品質提升"
  - "[ ] 沒有引入新的 bug"
```

**為什麼混淆**：

- 「體驗變好」無法量測（多好算好？）
- 「品質提升」主觀（誰評？）
- 「沒有新 bug」無法證明（只能證偽）
- 驗收者無法勾選，ticket 永遠完不成或隨意完成

**改善**：每條都要能「勾得下去」：

```yaml
acceptance:
  - "[ ] 登入完成時間 p95 從 3.2s 降至 ≤ 1.5s（1 週平均）"
  - "[ ] Linter 無新增 warning；cyclomatic complexity 不增加"
  - "[ ] 迴歸測試套件（237 個）全數通過，且新增至少 6 個測試"
```

---

## 速查表

| 欄位         | 常見混淆模式                                           | 判斷快問                          |
| ------------ | ------------------------------------------------------ | --------------------------------- |
| `what`       | 把 `why`（動機）塞進來，用「因為...所以...」開頭       | 有「因為」→ 搬到 `why`            |
| `why`        | 把 `what`（動作）和 `how`（實作）寫進來                | 有動詞動作 → 搬到 `what` 或 `how` |
| `when`       | 描述產品行為時序（用戶點了什麼），不是 ticket 啟動條件 | 主詞是「用戶」→ 可能寫錯了        |
| `where`      | 寫「所有相關地方」等抽象描述，不列具體檔案             | 沒有路徑 → 補具體清單             |
| `how`        | 把驗收條件（pass/fail 判斷）混入實作計畫               | 有「要通過」→ 搬到 `acceptance`   |
| `acceptance` | 寫「變好」「提升」「沒有新問題」等不可驗證描述         | 無法勾選 → 加量化指標或可觀察證據 |

---

**來源**：從 `designing-fields.md` §6.1–§6.12 獨立拆出，保留全部詳細範例
**Last Updated**: 2026-04-18
**Version**: 1.0.0
