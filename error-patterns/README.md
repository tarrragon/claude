# Error Patterns 錯誤模式歸檔系統

## 系統目的

Error Patterns 是五重文件系統的核心組件之一，用於：
- 記錄開發過程中發現的錯誤模式
- 傳承經驗，避免重複犯錯
- 建立可查詢的錯誤知識庫

## 與 Claude Code 官方 Memory 系統的差異

Claude Code 內建了官方的 memory 系統（`~/.claude/projects/{project}/memory/`），本專案的 Error Patterns 系統與其定位不同：

| 面向 | 官方 Memory 系統 | Error Patterns 系統 |
|------|-----------------|-------------------|
| **儲存位置** | 用戶 home 目錄（`~/.claude/`） | 專案目錄（`.claude/error-patterns/`） |
| **版本控制** | 不納入 git | 納入 git，隨專案版本管理 |
| **共享範圍** | 個人，跨 session 持久化 | 團隊，所有協作者共享 |
| **內容類型** | 用戶偏好、反饋、專案狀態 | 結構化錯誤模式（症狀/根因/解決方案/預防） |
| **查詢方式** | 系統自動載入相關記憶 | `/error-pattern query` 主動查詢 |
| **適用場景** | 「記住我喜歡 X 做法」 | 「上次遇到 Y 問題的根因和防護」 |

**協作關係**：兩個系統互補。Memory 記錄個人的行為反饋（如「禁止用 Bash 繞過 Hook」），Error Patterns 記錄團隊的結構化知識（如「PC-016: Hook 繞過的根因分析和防護措施」）。同一事件可能同時產生兩種記錄。

---

## 目錄結構

```
.claude/error-patterns/
├── README.md              # 本文件
├── test/                  # 測試相關錯誤模式
├── documentation/         # 文件相關錯誤模式
├── architecture/          # 架構相關錯誤模式
├── implementation/        # 實作相關錯誤模式
├── code-quality/          # 程式碼品質相關錯誤模式
└── process-compliance/    # 流程合規相關錯誤模式
```

---

## 命名規範

**格式**: `{CATEGORY}-{NNN}-{short-description}.md`

| 分類 | 前綴 | 說明 |
|------|------|------|
| 測試 | TEST | 測試設計、執行相關 |
| 文件 | DOC | 文件格式、規範相關 |
| 架構 | ARCH | 架構設計相關 |
| 實作 | IMP | 程式碼實作相關 |
| 程式碼品質 | CQ | 程式碼品質、設計模式相關 |
| 流程合規 | PC | 流程合規相關 |

**範例**:
- `TEST-001-wrong-wait-mechanism.md`
- `DOC-001-emoji-in-handover-docs.md`
- `ARCH-001-circular-dependency.md`

---

## 文件格式

每個錯誤模式文件必須包含以下章節：

```markdown
# [Pattern ID]: [簡短標題]

## 基本資訊

- **Pattern ID**: {CATEGORY}-{NNN}
- **分類**: {分類名稱}
- **來源版本**: {發現時的版本}
- **發現日期**: YYYY-MM-DD
- **風險等級**: 高/中/低

## 問題描述

### 症狀
[描述問題的外在表現]

### 根本原因 (5 Why 分析)
1. Why 1: ...
2. Why 2: ...
3. Why 3: ...
4. Why 4: ...
5. Why 5: (根本原因)

## 解決方案

### 正確做法
[描述正確的實作方式]

### 錯誤做法 (避免)
[描述應該避免的做法]

## 抽象層級分析（必填）

> **目的**：防止讀者把實作層 / 工具層 / 協作層素材跨層誤推至認知層 / 架構層論述（PC-111 R5）。撰寫者必須顯性標記症狀與根因所在層級，跨層提升必須說明支撐文件來源。

| 欄位 | 內容 | 範例 |
|------|------|------|
| 症狀層級 | 外在表現所在抽象層 | 工具層（subagent transcript 局部視角） |
| 根因層級 | 5 Why 終點所在抽象層 | 協作層（teammate 之間 state 不共享） |
| 跨層路徑 | 症狀層 → 根因層的層級差，若同層填「N/A；症狀與根因同層」 | 工具層 → 協作層（向上 1 層） |
| 防護層級 | 防護措施作用的抽象層（含支撐文件路徑） | 協作層；落地至 `.claude/skills/agent-team/SKILL.md` |
| 跨層警示 | 本 PC 素材若被引用，禁止跨層提升至哪些層級；若無填「無」 | 禁止提升至認知層（讀者可能誤推為「working memory 競爭」，無支撐文件） |

**層級分類參考**（細節見 `.claude/methodologies/pm-judgment-interference-map.md` 因子 1.4）：

- **實作層**：具體程式碼、git index、檔案系統、單一函式行為
- **工具層**：CLI / Hook / subagent transcript / runtime API
- **協作層**：多代理人協調、Ticket / Task 介面、shared state 設計
- **認知層**：working memory、注意力分配、判斷品質、心智模型
- **架構層**：系統邊界、模組依賴、資料流、契約

## 相關資源

- [相關文件連結]
- [參考案例]

## 標籤

`#標籤1` `#標籤2`
```

---

## 新增錯誤模式流程

1. **識別錯誤模式**: 在開發過程中發現重複或重要的錯誤
2. **確定分類**: 根據錯誤類型選擇適當的目錄
3. **分配編號**: 查看該分類下最大編號，加 1
4. **撰寫文件**: 使用標準格式撰寫
5. **更新索引**: 在本 README 的「現有模式」章節新增條目

---

## 現有模式

### 測試 (TEST)

| ID | 標題 | 風險 | 來源版本 |
|----|------|------|---------|
| TEST-001 | 錯誤的等待機制 | 高 | v0.6.2 |
| TEST-002 | 測試流程不完整 | 高 | v0.6.2 |
| TEST-003 | 過度驗證超出責任 | 中 | v0.6.2 |
| TEST-004 | 重構引入 Wrapper 後 Mock Patch 路徑失效 | 高 | v0.1.0 |

### 文件 (DOC)

| ID | 標題 | 風險 | 來源版本 |
|----|------|------|---------|
| DOC-001 | 交接文件使用 emoji | 低 | v0.25.x |
| DOC-002 | 衛星文件引用不存在 | 中 | v0.28.0 |
| DOC-003 | Skill 觸發關鍵字不足導致匹配失敗 | 中 | v0.31.0 |
| DOC-004 | CLI 命令通配符表示導致 Agent 錯誤類推 | 中 | v0.31.1 |
| DOC-005 | 新增原則時跨文件未同步更新 | 中 | feat/workflow-improvement |
| DOC-006 | 規則文件局部更新後，同檔案總覽圖與入口文件未同步 | 中 | 0.1.1 |
| DOC-007 | append-log section 參數值大小寫不一致 | 低 | v0.1.0 |
| DOC-008 | 同一文件內定義替換遺漏（局部替換未使用全局 replace） | 中 | v0.1.0 |

### 架構 (ARCH)

| ID | 標題 | 風險 | 來源版本 |
|----|------|------|---------|
| ARCH-001 | 配置與程式碼混合 | 高 | v0.28.0 |
| ARCH-002 | Plugin 清理只刪快取未移除訂閱源 | 中 | v0.31.1 |
| ARCH-003 | 並行代理人持久化落差 | 高 | v0.31.0 |
| ARCH-004 | 批量拆分檔案所有權重疊 | 高 | v0.31.0 |
| ARCH-005 | 代理人定義衝突導致派發職責不清 | 中 | v0.31.0 |
| ARCH-006 | 環境配置作用域錯誤 | 中 | v0.31.1 |
| ARCH-007 | Per-project 追蹤檔追蹤全域資源 | 中 | v0.1.0 |
| ARCH-008 | 依賴全域狀態推斷而非從本地資料提取 | 中 | v0.1.0 |
| ARCH-009 | 將決策邏輯集中到單一 skill 造成 context 膨脹 | 中 | v0.1.0 |
| ARCH-010 | 模組組裝遺漏導致功能鏈路靜默斷裂 | 高 | v0.1.0 |
| ARCH-010 | 過度設計的狀態管理（編號重複，待整併） | 中 | v0.1.0 |
| ARCH-011 | 框架資產與專案產物混放 | 中 | v0.1.0 |
| ARCH-012 | 代理人專案特定硬編碼 | 中 | v0.1.0 |
| ARCH-013 | ESM/CJS 混合匯出導致 Dead Code | 中 | v0.1.0 |
| ARCH-014 | 跨執行環境共享可變常數物件 | 中 | v0.17.3 |
| ARCH-015 | subagent .claude/ 寫入 hardcoded 保護 | 中 | v0.18.0 |

### 程式碼品質 (CQ)

| ID | 標題 | 風險 | 來源版本 |
|----|------|------|---------|
| CQ-001 | 私有函式跨模組引用導致封裝破壞 | 中 | v0.1.0 |
| CQ-002 | Positional Argument 作為子命令偵測導致路由不一致 | 中 | v0.1.0 |
| CQ-003 | Exception 定義後無實際拋出點（設計意圖未實現） | 中 | v0.1.0 |
| CQ-004 | namedtuple 早退路徑返回裸型別 | 高 | v0.1.0 |
| CQ-005 | Mock 路徑未隨函式遷移同步更新 | 中 | v0.1.0 |
| CQ-006 | 純工具函式定義在 commands/ 層阻礙複用 | 中 | v0.1.0 |

### 實作 (IMP)

| ID | 標題 | 風險 | 來源版本 |
|----|------|------|---------|
| IMP-001 | 重複程式碼散落各處 | 中 | v0.28.0 |
| IMP-002 | 魔法數字 | 低 | v0.28.0 |
| IMP-003 | 重構作用域迴歸 | 高 | v0.31.0 |
| IMP-004 | Hook 白名單不完整 | 中 | v0.31.0 |
| IMP-005 | 模組遷移 Import 未同步 | 高 | v0.31.0 |
| IMP-006 | Hook 靜默失效 | 高 | v0.31.0 |
| IMP-007 | 非對稱邊界更新 | 中 | v0.31.0 |
| IMP-008 | Bash 工作目錄污染 | 中 | v0.31.0 |
| IMP-009 | TaskOutput 混淆 | 低 | v0.31.0 |
| IMP-010 | GC 狀態語義衝突導致誤刪 | 高 | v0.31.1 |
| IMP-011 | 修復中引入新的格式假設錯誤 | 高 | v0.31.1 |
| IMP-012 | 重新發明標準庫功能而不初始化 | 中 | v0.31.1 |
| IMP-013 | 重構設計意圖盲視 | 中 | v0.31.1 |
| IMP-014 | Stop Hook reason 欄位被 Claude 解讀為命令 | 中 | v0.3.0 |
| IMP-015 | 腳本自我刪除導致執行中斷 | 中 | v0.31.1 |
| IMP-016 | Lock 檔案未隨配置檔同步更新 | 中 | v0.31.1 |
| IMP-017 | 全局 CLI 未隨原始碼修復更新 | 中 | v0.31.1 |
| IMP-018 | 生命週期不完整清理 | 中 | v0.1.0 |
| IMP-019 | 資料結構投射到 CLI 介面假設錯誤 | 低 | v0.1.0 |
| IMP-020 | PostToolUse Hook 共存時的觸發碰撞 | 中 | v0.1.0 |
| IMP-021 | 手動文字解析結構化格式 | 中 | v0.1.0 |
| IMP-022 | 內聯 __import__ 重複實作共用邏輯 | 低 | v0.1.0 |
| IMP-023 | uv tool install --force 不更新已安裝套件程式碼 | 中 | v0.3.0 |
| IMP-024 | phase-completion-gate-hook 在編輯 tdd_phase 欄位時誤觸 Phase 3b 完成警告 | 低 | v0.1.0 |
| IMP-025 | 新模組引入 except Exception: pass 靜默吞掉異常 | 中 | v0.1.0 |
| IMP-026 | 新建 Hook 檔案後未設定執行權限（+x） | 高 | v0.1.1 |
| IMP-027 | 跨 Context 函式庫與 Hook 邏輯重複 | 低 | v0.1.0 |
| IMP-028 | Hook 提前返回與 API 簽名漂移 | 中 | v0.1.0 |
| IMP-029 | 強制 logger 參數破壞共用工具重用性 | 中 | v0.1.0 |
| IMP-030 | Agent 測試 importlib 缺少 exec_module | 中 | v0.1.0 |
| IMP-031 | Agent 部分完成後偽報告成功 | 中 | v0.1.0 |
| IMP-032 | Hook 傳遞 CLI 不支援的參數 | 中 | v0.1.1 |
| IMP-033 | 版本比對時 source 掃描範圍與 installed 不對齊 | 中 | v0.1.1 |
| IMP-034 | init.py transitive import breakage | 中 | v0.1.1 |
| IMP-035 | Guard clause 與篩選狀態衝突 | 中 | v0.1.1 |
| IMP-036 | Hook 絕對路徑豁免不匹配 | 中 | v0.1.1 |
| IMP-037 | Hook 缺少 subagent 環境判斷 | 中 | v0.1.2 |
| IMP-038 | hook_utils YAML 列表欄位回傳為字串 | 低 | v0.1.2 |
| IMP-039 | Phase 4b context 耗盡（開放式 prompt） | 中 | v0.1.2 |
| IMP-040 | 狀態機終態未受保護 | 中 | v0.1.2 |
| IMP-041 | Go build binary 未清理 | 低 | v0.2.0 |
| IMP-042 | 刪除操作後殘留引用未同步清理 | 中 | v0.2.0 |
| IMP-043 | 函式實作完整但呼叫端未接線 | 高 | v0.2.0 |
| IMP-044 | 生命週期階段缺乏可觀測性 | 中 | v0.2.0 |
| IMP-045 | 伺服器重啟 port 佔用靜默失敗 | 中 | v0.2.0 |
| IMP-046 | — | — | — |
| IMP-047 | — | — | — |
| IMP-048 | Hook stderr 輸出觸發 hook error 顯示 | 低 | v0.17.2 |
| IMP-049 | hook error 顯示是 CLI 已知 Bug | 低 | v0.17.3 |
| IMP-050 | hook_utils package 路徑誤導 | 中 | v0.17.3 |
| IMP-051 | 新 Hook 未註冊到 settings | 中 | v0.17.3 |
| IMP-052 | 批量遷移缺少 None guard | 中 | v0.17.3 |
| IMP-053 | 一刀切修改忽略程式碼執行路徑差異 | 中 | v0.17.3 |

### 流程合規 (PC)

| ID | 標題 | 風險 | 來源版本 |
|----|------|------|---------|
| PC-001 | 保護分支上編輯被靜默還原導致工作浪費 | 高 | feat/workflow-improvement |
| PC-002 | Ticket 設計建立新功能時未確認現有類似實作 | 中 | v0.31.1 |
| PC-003 | 跨版本未完成任務靜默遺漏 | 高 | v0.2.0 |
| PC-004 | 跳過分析審核直接派發修復導致迴歸 | 高 | v0.31.1 |
| PC-005 | CLI 失敗時基於假設歸因 | 中 | v0.1.0 |
| PC-006 | 過早統一抽象（DRY 誤用） | 中 | v0.1.0 |
| PC-007 | Command 引導與腳本實作行為不符 | 中 | v0.3.0 |
| PC-008 | Stub Ticket 驗收條件未更新 | 中 | v0.1.0 |
| PC-009 | Handoff 對已完成 Ticket 使用錯誤 flag | 中 | v0.1.0 |
| PC-010 | PM 跳過 Ticket 完成後 Checkpoint | 中 | v0.1.0 |
| PC-011 | Ticket 版本歸類錯誤 | 中 | v0.1.0 |
| PC-012 | Complete 前處理 #17 造成死鎖 | 中 | v0.1.0 |
| PC-013 | 重複建立 Ticket 未偵測 | 中 | v0.1.0 |
| PC-014 | 以非正式任務合理化跳過 AskUserQuestion | 中 | v0.1.1 |
| PC-015 | 錯誤提示靜默繞過 | 中 | v0.1.1 |
| PC-016 | Hook 阻止後使用 Bash 工具繞過保護機制 | 高 | v0.1.1 |
| PC-017 | ANA 完成後缺少實作 Ticket | 中 | v0.1.1 |
| PC-018 | 並行代理人重複建立後續 Ticket | 中 | v0.1.1 |
| PC-019 | 設計決策只存 memory 未建 Ticket | 中 | v0.1.1 |
| PC-020 | Plan 派發與實際執行不一致 | 中 | v0.1.2 |
| PC-021 | Worktree 隔離失敗導致跨 Wave 交叉污染 | 高 | v0.1.2 |
| PC-022 | Subagent 權限不足無法編輯 Hook | 中 | v0.1.2 |
| PC-023 | PM 繞過權限而非修復根因 | 中 | v0.1.2 |
| PC-024 | Subagent 跳過 commit | 中 | v0.2.0 |
| PC-025 | Worktree 合併目標分支狀態不一致 | 高 | v0.2.0 |
| PC-026 | 測試失敗未立即建 Ticket | 高 | v0.2.0 |
| PC-027 | Phase 3b 失敗無 Ticket 直接派發 | 中 | v0.2.0 |
| PC-028 | 代理人報告未驗證假設 | 中 | v0.2.0 |
| PC-029 | 並行代理人共用檔案衝突 | 中 | v0.2.0 |
| PC-030 | 代理人定義 slash command 引用無法執行 | 中 | v0.2.0 |
| PC-031 | error-pattern SKILL 引用錯誤的知識庫路徑 | 中 | v0.2.0 |
| PC-032 | 版本完成後跳過 release flow | 中 | v0.2.0 |
| PC-033 | worklog 過時阻塞 release | 中 | v0.2.0 |
| PC-034 | 工作流輸出無持久化 | 中 | v0.2.0 |
| PC-035 | 版本狀態與 Ticket 狀態脫鉤 | 中 | v0.2.0 |
| PC-036 | Worktree base commit 過舊導致無效工作 | 中 | v0.2.0 |
| PC-037 | 背景代理人未完成即提前驗證 | 中 | v0.2.0 |
| PC-038 | 新版本開始時未同步更新 todolist.yaml | 高 | v0.17.2 |
| PC-039 | — | — | — |
| PC-040 | — | — | — |
| PC-041 | — | — | — |
| PC-042 | — | — | — |
| PC-043 | PM 執行跳過 phase 轉換 | 中 | v0.17.3 |
| PC-044 | — | — | — |
| PC-045 | PM 代理人失敗時自行撰寫產品程式碼 | 中 | v0.17.3 |
| PC-046 | 不必要的 cd 操作全域 CLI | 中 | v0.17.3 |
| PC-047 | Prompt 導致代理人過度讀取 | 中 | v0.17.3 |
| PC-048 | — | — | — |
| PC-049 | — | — | — |
| PC-050 | 過早判斷代理人完成 | 中 | v0.17.3 |
| PC-051 | 過早宣稱不可能 | 中 | v0.17.3 |
| PC-052 | 忽略既有 error-pattern 警告直接實作 | 中 | v0.17.3 |
| PC-053 | PM 對「小修改」跳過 Ticket 和 error-pattern 記錄 | 中 | v0.18.0 |
| PC-054 | 分析視角錨定在防禦性限制而非品質目標 | 中 | v0.18.0 |
| PC-055 | Ticket AC 與實況漂移未被系統偵測 | 中 | v0.18.0 |
| PC-056 | parallel-evaluation 強勢視角結論直接轉執行 Ticket 而未經 WRAP 驗證 | 中 | v0.18.0 |
| PC-057 | PM 派發 prompt 要求超出代理人職責範圍，代理人無防線照做導致越界 | 中 | v0.18.0 |
| PC-058 | ANA 代理人建立 follow-up Ticket 的 metadata 權威性不足 | 中 | v0.18.0 |
| PC-059 | 代理人 frontmatter Tools 宣告 ≠ 實際 runtime 權限 | 中 | v0.18.0 |
| PC-060 | 未使用 ToolSearch 發現 Claude Code deferred tools 導致採限制性解法 | 中 | v0.18.0 |
| PC-061 | Memory 寫入後未評估升級為框架規則 | 中 | v0.18.0 |
| PC-062 | 派發後焦慮性檢查違規 | 中 | v0.18.0 |
| PC-063 | ANA 階段過早收斂於假設方案，未做重現實驗驗證根因 | 中 | v0.18.0 |
| PC-064 | PM 列純文字選項而未使用 AskUserQuestion | 中 | v0.18.0 |
| PC-065 | PM 並行派發多代理人時 prompt 模板遺漏 Ticket ID 格式 | 低 | v0.18.0 |
| PC-066 | 輔助決策系統未在 Context 沉重時主動觸發 | 中 | v0.18.0 |
| PC-067 | 執行 ANA 規劃時未質疑規劃本身的設計品質 | 中 | v0.18.0 |
| PC-068 | Phase 3a 規劃新建既有 utility 而未先掃描重用 | 中 | v0.18.0 |
| PC-069 | Subagent 被擋時多檔案機械性修改的批次腳本策略 | 中 | v0.18.0 |
| PC-070 | PM 用 Hook 廣播訊號推論代理人失敗（跳過 TaskOutput status 查詢） | 中 | v0.18.0 |
| PC-071 | 個人化建議未詢問當事人條件（視野狹窄偏誤） | 中 | v0.18.0 |
| PC-072 | AskUserQuestion payload 生成時混入簡體字與 emoji | 中 | v0.18.0 |
| PC-073 | ANA 衍生 IMP Ticket 誤用 --parent 導致 children 關係，complete 時被 acceptance-gate 擋下 | 低 | v0.18.0 |
| PC-074 | 字元集守衛 Hook 實作時的繁簡共用字 false positive | 低 | v0.18.0 |
| PC-075 | spawned 與 children 狀態檢查語義不對稱（含四軸下游傳播路徑：decision-tree / priority / Wave / handoff） | 高 | v0.18.0 |
| PC-076 | Session 間未 commit 變更在後續 session 執行中意外浮現 | 中 | v0.18.0 |
| PC-077 | Hook 強制 worktree vs ARCH-015 `.claude/` 保護的派發死結 | 中 | v0.18.0 |
| PC-078 | 並行 terminal/session 的 Ticket 狀態異動被誤判為前 session 遺留 | 高 | v0.18.0 |
| PC-079 | Bash CLI 參數含 backtick 被解析為 command substitution | 中 | v0.18.0 |
| PC-080 | WRAP A 階段未檢查問題框架（選項全在同一框架內，違反 Consider the Opposite） | 中 | v0.18.0 |
| PC-081 | PM 自我檢查標準比用戶規則更嚴格（保守偏見導致過早收斂） | 中 | v0.18.0 |
| PC-082 | 修復 regression 時選還原舊值而非移除（忽略全域規則適用範圍） | 中 | v0.18.0 |
| PC-083 | framework 檔案 footer/metadata 誤寫專案 Wave/Patch 識別符 | 低 | v0.18.0 |
| PC-084 | 日文漢字清單誤列繁日共用字 false positive | 低 | v0.18.0 |
| PC-085 | CJK 漢字相鄰 codepoint 在 XXXX escape 中的肉眼混淆 | 低 | v0.18.0 |
| PC-086 | Subagent 建 Hook 腳本缺執行權限（exec bit） | 中 | v0.18.0 |
| PC-087 | PM 寫 /tmp 中介檔作為 ticket 內容寫入繞路 | 中 | v0.18.0 |
| PC-088 | LLM 對 tool call 路徑的步驟數估算偏誤 | 中 | v0.18.0 |
| PC-089 | Hook 豁免路徑與 Ticket 寫入範圍不一致 | 中 | v0.18.0 |
| PC-090 | 推延性 close 反模式 | 中 | v0.18.0 |
| PC-105 | PM 對 SKILL CLI 語法的 autopilot 假設（同 session 多次撞 hook 警告後仍嘗試相似變體） | 中 | v0.18.0 |

---

## 查詢方法

**按分類查詢**:
```bash
ls .claude/error-patterns/test/
```

**全文搜尋**:
```bash
grep -r "關鍵字" .claude/error-patterns/
```

**按標籤查詢**:
```bash
grep -l "#測試" .claude/error-patterns/**/*.md
```

---

## 重要規範

1. **禁止使用 emoji**: 所有 error-patterns 文件禁止使用 emoji
2. **使用繁體中文**: 遵循專案語言規範
3. **完整填寫**: 不可省略任何必要章節
4. **及時更新**: 發現新模式應立即記錄

---

*建立日期: 2026-01-14*
*維護者: rosemary-project-manager*
