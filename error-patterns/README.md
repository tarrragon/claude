# Error Patterns 錯誤模式歸檔系統

## 系統目的

Error Patterns 是五重文件系統的核心組件之一，用於：
- 記錄開發過程中發現的錯誤模式
- 傳承經驗，避免重複犯錯
- 建立可查詢的錯誤知識庫

## 與 Claude Code 原生 Memory 系統的關係（排除，非互補）

Claude Code 內建原生的 memory 系統（`~/.claude/projects/{project}/memory/`）。**本框架排除該系統作為知識記錄目的地**，改以 `.claude/error-patterns/` 承接其原本要處理的「值得跨 session 保存的判斷」。排除理由是以下結構性差異：

| 面向 | Claude Code 原生 Memory | Error Patterns 系統 |
|------|-----------------|-------------------|
| **儲存位置** | 使用者 home 目錄的專案層級儲存（`~/.claude/projects/<project>/memory/`） | 專案目錄（`.claude/error-patterns/`） |
| **版本控制** | 不納入 git，不隨 `.claude/` sync 到其他專案 | 納入 git，隨專案版本管理，可隨 `.claude/` sync 跨專案複用 |
| **共享範圍** | 單一專案本機，個人可見 | 團隊共享，所有協作者可見，可跨專案複用 |
| **查詢方式** | 系統自動載入相關記憶 | `/error-pattern query` 主動查詢 |

**排除說明**：memory 不納入 git、不隨 `.claude/` sync 到其他專案，與「經驗須跨專案複用」的框架目標根本衝突——寫在 memory 的跨專案原則會在其他專案消失，導致同樣的問題被重複踩雷。因此本框架的知識記錄一律遵循**捕獲時分流判準**：框架相關內容（替換專案名稱與檔案路徑後仍成立）進 `.claude/error-patterns/` 或 `.claude/rules/`、`.claude/methodologies/`、`.claude/references/`；專案相關內容（僅本專案成立）進 `docs/` 或 `CLAUDE.md`；兩者皆非則不記錄。**memory 不是任一分支的合法目的地**。完整判準見 `.claude/pm-rules/pm-quality-baseline.md` 規則 7（`.claude/skills/continuous-learning/skill.md` 為執行工具）。

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
├── process-compliance/    # 流程合規相關錯誤模式
└── process/               # 流程相關錯誤模式（正向 idiom / 跨階段流程問題）
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
| 流程 | PROC | 跨階段流程問題（非流程合規類） |

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
| TEST-BAL-001 | 測試 fixture 用理想化格式，真實輸入格式不同致 validator 靜默假通過 | 高 | v0.1.0 |
| TEST-005 | Mock 錯誤 import 路徑導致真實副作用 | — | — |
| TEST-006 | pytest plugin fixture 使用未宣告依賴導致全類 setup error | — | — |
| TEST-007 | Archived 模組的測試檔處理 idiom（pytestmark.skip + try/except import 雙層保護） | 低 | — |
| TEST-BAL-002 | 測試替身走簡化建構路徑，繞過 production 裝配步驟使缺口對測試不可見 | 高 | — |
| TEST-MON-001 | 硬編碼時間戳 fixture × 時間相對查詢窗 = clock 時間炸彈 | 高 | — |
| TEST-MON-002 | TDD Phase 2 紅燈設計漏 handler/lifecycle 行為測試；GREEN agent confidence<1.0 是補洞訊號 | 中 | — |

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
| DOC-V1-001 | 位置編號引用隨目標文件演進靜默失效（misdirected 比 broken 難偵測） | 中 | v1.0.0 |
| DOC-009 | 「靜默處理」用語誤用 — 混淆「不記錄」與「記錄但不顯示」 | 中 | — |
| DOC-010 | 框架文件引用專案 ticket ID 造成跨專案 sync 誤導 | 中 | — |

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
| ARCH-011 | 框架資產與專案產物混放 | 中 | v0.1.0 |
| ARCH-012 | 代理人專案特定硬編碼 | 中 | v0.1.0 |
| ARCH-013 | ESM/CJS 混合匯出導致 Dead Code | 中 | v0.1.0 |
| ARCH-014 | 跨執行環境共享可變常數物件 | 中 | v0.17.3 |
| ARCH-015 | subagent .claude/ 寫入 hardcoded 保護 | 中 | v0.18.0 |
| ARCH-016 | Hook 過度限制的允許清單 | 中 | v0.18.0 |
| ARCH-017 | 兄弟 Ticket 隱藏依賴 | 中 | v0.18.0 |
| ARCH-018 | Hook 全面性要求與巢狀規則衝突 | 中 | v0.18.0 |
| ARCH-019 | Hook 事件時機不匹配 | 中 | v0.18.0 |
| ARCH-020 | validator 與 hook 重複驗證邏輯 | 中 | v0.18.0 |
| ARCH-021 | 模組組裝遺漏導致功能鏈路靜默斷裂（原 ARCH-010 重編號） | 高 | v0.15.4 |
| ARCH-V1-001 | 同一不變量單點執法、多入口繞過（前門裝鎖、側門敞開） | 中 | v1.0.0 |
| ARCH-V1-002 | 雙向 overlay sync 製造重複 top-level 定義（死碼 shadow 活 bug） | 高 | v1.0.0 |
| ARCH-APP-002 | uv tool install 全域同名 CLI 跨 consumer namespace 碰撞（last-write-wins） | 中 | v0.37.0 |
| ARCH-BAL-001 | 架構依賴方向底線未用程式碼 import 鏈驗證，導致底線與現況矛盾 | 高 | v0.1.0 |
| ARCH-BAL-005 | 自證式豁免——豁免決定與豁免理由在資料結構上分離，理由無消費者亦無時效 | 高 | v0.2.1 |
| ARCH-BAL-006 | 宣告層枚舉窄於執行層判準，讀者據宣告自我豁免（靜默，無撞牆訊號） | 中 | v0.2.1 |
| ARCH-022 | Hook 用 CLI 探測產生跨界隱性副作用 | 中 | — |
| ARCH-APP-001 | 多工具版本偵測邏輯不同步 | 中 | — |
| ARCH-BAL-002 | 識別符雙載體但工具只讀一側，修復動錯側使驗收假通過 | 高 | — |
| ARCH-BAL-003 | 白名單自訂納入判準但成員未同步，判準與名單脫節 | 中 | — |
| ARCH-BAL-004 | 參考文件範例與同檔規則矛盾，範例成為缺陷散播源 | 高 | — |
| ARCH-MON-001 | 多 wave 票各加進同一中心檔，累積 domain 過載而無單票觸發閾值 | 中 | — |
| ARCH-TUNL-001 | settings.local.json 註冊 hook 在 relocate 後成幽靈（sync 無法自癒） | 中 | v1.0.0（1.0.0-W9-001 ANA） |
| ARCH-BAL-007 | 非唯一識別符被當主鍵，集合去重靜默丟棄同鍵資料 | 高 | v0.2.1（0.2.1-W3-110 ANA） |
| ARCH-010 (module-assembly-omission) | 模組組裝遺漏導致功能鏈路靜默斷裂 | 高 | v0.15.4 |
| ARCH-010 (overengineered-state-management) | 過度設計的狀態管理 — 框架機制已解決的問題不需要額外狀態層 | 中 | v0.1.0 |
| ARCH-BAL-008 | 以單一消費者內容覆寫共用覆蓋層，靜默刪除其他消費者的獨有內容 | — | — |

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
| IMP-050 | hook_utils package 路徑誤導 | 中 | v0.17.3 |
| IMP-051 | 新 Hook 未註冊到 settings | 中 | v0.17.3 |
| IMP-052 | 批量遷移缺少 None guard | 中 | v0.17.3 |
| IMP-053 | 一刀切修改忽略程式碼執行路徑差異 | 中 | v0.17.3 |
| IMP-070 | Hook stdin 欄位命名規範混淆（input snake_case vs output camelCase） | 高 | v0.18.0 |
| IMP-078 | CE-Node 環境前提誤判 — Jest 測試綠燈但 CE Runtime 崩潰 | 高 | v0.19.0 |
| IMP-079 | 批次替換工具誤傷偵測目標字面 — regex/meta-test 內嵌待測字元被盲目轉換後語意塌縮 | 中 | v0.19.1 |
| IMP-V1-001 | 估算係數未經實測校準即上線 — 守門機制低估真值提供假安心 | 中 | v1.0.0 |
| IMP-APP-001 | get_project_root 雙實作回傳型別分歧 — consumer 用錯 Path 方法 runtime 才爆 | 中 | v0.37.0 |
| IMP-APP-002 | regex 解析多條目結構化檔案未以條目邊界為先 — DOTALL 跨條目誤配 + 格式漂移致解析恆空靜默失效 | 高 | v0.38.0 |
| IMP-APP-003 | fresh checkout 缺 gitignored 生成產物導致連鎖編譯失敗，並被誤歸因為並行資源耗盡 | 高 | v0.38.0 |
| IMP-054 | Hook 腳本缺少執行權限導致靜默失敗 | 高 | — |
| IMP-055 | PostToolUse Hook stdout 輸出純文字導致 JSON validation failed | 高 | — |
| IMP-056 | chpwd Shell Hook 大量 ls 輸出淹沒代理人工具結果 | 中 | — |
| IMP-057 | grep 單行比對多行 print() 語句產生誤報 | 中 | — |
| IMP-058 | YAML frontmatter 欄位型別假設錯誤（list vs string） | 高 | — |
| IMP-059 | Auto-compaction UTF-8 截斷導致文件中文字元損壞 | 中 | — |
| IMP-060 | Hook error 掃描純字串匹配產生誤報循環 | 中 | — |
| IMP-061 | ticket migrate 產生 parent_id typo 且依賴欄位未同步更新 | 中 | — |
| IMP-062 | Windows 平台 Hook 啟動失敗與編碼斷層 | 高 | — |
| IMP-063 | Hook 路徑分類混淆 context 引用與實作目標 | 高 | — |
| IMP-064 | 函式體 local re-import 遮蔽 unittest.mock.patch | 高 | — |
| IMP-065 | CLI 單檔查詢依賴檔名約定，批量掃描用 field 比對，導致 naming-drift 時靜默失敗 | 中 | — |
| IMP-066 | subagent 在 isolation:worktree 下透過 ticket CLI 看不到主 repo 新建 ticket | 中 | — |
| IMP-067 | Windows NTFS 無 executable bit 導致 git 對新檔 mode 降權為 100644 | 高 | — |
| IMP-068 | sync-push 版號 bump 缺 sanity check 導致異常跳躍靜默 push | 高 | — |
| IMP-069 | PEP 723 inline dependencies 不會從 library 模組傳遞至 entry hook | 高 | — |
| IMP-071 | ticket track append-log 在章節已有 placeholder 時建立重複內容 | 低 | — |
| IMP-072 | ticket create 並行執行時 ID 分配 race condition | 中 | v0.18.0 |
| IMP-073 | Logger 方法解構導致 this 遺失 + Promise hang | 中 | v0.18.0 |
| IMP-074 | Skill 同時用 scripts.* package 入口 + sys.path-mode 測試導致 import 雙模式衝突 | 中 | v0.18.0 |
| IMP-075 | ticket set-acceptance --check 多個 index 參數可能只勾選最後一個 | 低（功能正確性受影響但有 workaround） | v0.19.0 |
| IMP-076 | Skill packaging install/runtime 二態盲點（auto-discover 配置缺失 + __file__ 上溯失效） | 中 | v0.19.0 |
| IMP-077 | 測試 helper 設計反模式（local fork 變死碼 + 同名異介面命名衝突） | 低（功能正常但維護性退化） | v0.19.0 |
| IMP-APP-004 | 防呆判斷取 pipeline 末端命令 exit code——head/tail 恆 0 使守衛必觸發或必靜默 | 中 | — |
| IMP-APP-005 | 驗證工具對空/無效輸入集靜默回報通過——假綠燈侵蝕驗證可信度 | 高 | — |
| IMP-BAL-001 | Hook（PreToolUse / PostToolUse）提前 emit stdout JSON，後續分支 exit 2 時訊號被 runtime 丟棄 | 中 | — |
| IMP-BAL-002 | sync-claude-pull.py 未知參數不報錯，推進 base SHA 卻不套 delta，破壞三方合併基準 | 高 | — |
| IMP-BAL-003 | 稽核 hook 用寬鬆解析器讀 SSOT，對嚴格消費端會失敗的結構錯誤全盲 | 高 | — |
| IMP-MON-001 | 批量 sys.path 修改前未盤點多重依賴導致 import 斷裂 | 中 | — |
| IMP-MON-002 | CC worktree 隔離以遠端預設分支為 base（session 啟動快取），非 origin/main | 高 | — |
| IMP-MON-003 | 貪婪字串替換誤中 URL 子字串 | 中 | — |
| IMP-V1-002 | 跨 repo 交換格式 wire key 命名慣例分歧（DB snake_case 洩漏至 wire format） | 中 | — |
| IMP-V1-003 | Hook 搬移後 sys.path 指向錯誤的 lib 目錄導致 import 失敗 | 中 | — |
| IMP-V1-004 | Hook 內部工具名字面守衛因平台工具改名靜默早退（matcher 別名仍投遞） | 高 | — |
| IMP-V1-005 | index.lock 競爭下 fast-forward 移動 HEAD 但 index 寫入失敗，後續 commit 靜默刪除剛合併的檔案 | 高 | — |
| IMP-V1-006 | 大小寫不敏感檔案系統上 Edit 工具寫入成功，但 git pathspec 以不同大小寫尋址失敗 | 低 | — |
| IMP-049 (hook-error-display-is-cli-bug) | "hook error" 顯示是 Claude Code CLI 已知 Bug，非 Hook 程式碼問題 | 低 | v0.17.3 |
| IMP-049 (undefined-constants-in-hook-source) | Hook 原始碼引用未定義常數 | — | — |

### 流程 (PROC)

| ID | 標題 | 風險 | 來源版本 |
|----|------|------|---------|
| PROC-001 | 錯誤假設執行者能靠經驗彌補文件不足 | — | — |

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
| PC-011 | Ticket 版本歸類錯誤 | 中 | v0.1.0 |
| PC-012 | Complete 前處理 #17 造成死鎖 | 中 | v0.1.0 |
| PC-013 | 重複建立 Ticket 未偵測 | 中 | v0.1.0 |
| PC-014 | 以非正式任務合理化跳過 AskUserQuestion | 中 | v0.1.1 |
| PC-015 | 錯誤提示靜默繞過 | 中 | v0.1.1 |
| PC-016 | Hook 阻止後使用 Bash 工具繞過保護機制 | 高 | v0.1.1 |
| PC-017 | ANA 完成後缺少實作 Ticket | 中 | v0.1.1 |
| PC-021 | Worktree 隔離失敗導致跨 Wave 交叉污染 | 高 | v0.1.2 |
| PC-022 | Subagent 權限不足無法編輯 Hook | 中 | v0.1.2 |
| PC-023 | PM 繞過權限而非修復根因 | 中 | v0.1.2 |
| PC-024 | Subagent 跳過 commit | 中 | v0.2.0 |
| PC-025 | Worktree 合併目標分支狀態不一致 | 高 | v0.2.0 |
| PC-026 | 測試失敗未立即建 Ticket | 高 | v0.2.0 |
| PC-027 | Phase 3b 失敗無 Ticket 直接派發 | 中 | v0.2.0 |
| PC-028 | 代理人報告未驗證假設 | 中 | v0.2.0 |
| PC-029 | 並行代理人共用檔案衝突 | 中 | v0.2.0 |
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
| PC-154 | 派發 worktree agent 前未驗證兩項前置條件（worktree base 完整性 + ticket 已 claim） | 中 | v0.19.0 |
| PC-162 | Ticket 描述含過時環境狀態 + schema 註解 PC 引用語意錯誤 | 中 | v0.19.0 |
| PC-172 | Wrapper command 參數推斷未經 runtime 驗證（只讀底層 binary --help，忽略 wrapper 自動注入參數） | 中 | v0.19.1 |
| PC-176 | 跨環境設定不一致時歸因「環境差異」而非驗證被 git 同步的共用設定本身（便利假設掩蓋一份錯設定的單點根因） | 中 | v0.19.1 |
| PC-180 | 雙專案共用 sync 時混淆「共享 repo 納入範圍」與「本地保留範圍」致框架調整誤失（preserve 清單為根本解） | 中 | v1.0.0 |
| PC-V1-001 | sync-push 無 --help，未知參數當 commit 訊息觸發真實不可逆推送 | 高 | v1.0.0 |
| PC-V1-002 | Ticket ID 引用觸發 agent 自律收尾越權（引用 ≠ 指派缺口） | 高 | v1.0.0 |
| PC-V1-003 | 聯想式檔案參照寫入後個案修補，跳過模式分析 | 中 | v1.0.0 |
| PC-V1-004 | Hook 注入訊息受眾錯配（PM-only 訊息注入 Subagent Context） | 高 | v1.0.0 |
| PC-V1-005 | Acceptance 量化目標設定未考慮 substance 密度上限 | 中 | v1.0.0 |
| PC-V1-006 | 規則變更未盤點既有規則矛盾即上線（有執法者的一方勝出） | 中 | v1.0.0 |
| PC-V1-007 | 確定性 ≠ 準確性 — 量測工具確定化未驗證複現原始分析意圖 | 高 | v1.0.0 |
| PC-V1-008 | lockfile 版本漂移修正被 auto-preserve worktree commit 孤立並險遭當噪音丟棄 | 中 | v1.0.0 |
| PC-V1-009 | 機械缺陷誤診為流程缺陷（import 殘留可由 smoke test 消除卻誤上人工 PR 審查） | 高 | v1.0.0 |
| PC-V1-010 | 子代理人完成摘要把測試總數誤報為通過數，遮蔽紅燈（PM 須獨立重跑讀實跑行） | 高 | v1.0.0 |
| PC-V1-012 | 防護置於便利攔截介面而非狀態變異真實源頭（攔錯攻擊面 + 行為防護冒充結構治本） | 中 | v1.0.0 |
| PC-V1-013 | acceptance 用 lenient build:dev 驗證遮蔽 production-only gate 失敗（驗證路徑 ≠ 出貨路徑） | 中 | v1.0.0 |
| PC-APP-001 | 延後決策綁定的 trigger ticket 引用未查證 scope 一致性（trigger 名存實亡） | 中 | v0.32.0 |
| PC-APP-002 | sync-pull 孤兒清理超出宣稱範圍刪除，preserve 機制未生效致專案特化檔遺失 | 高 | v0.32.0 |
| PC-APP-004 | 症狀緩解累積偏誤——同一根因累積多個緩解機制而非根治 | 中 | v0.37.0 |
| PC-APP-005 | ANA 建議方案的可行性驗證僅跑 happy path，前提與 UX 後果到 IMP 才暴露 | 中 | v0.37.0 |
| PC-APP-007 | 多個 Spawn Request 合併為單票時驗收項遺失與憑空補入（標題宣稱涵蓋、acceptance 未承接） | 高 | v0.38.0 |
| PC-APP-010 | code agent 杜撰 UC- 前綴偽需求 ID——TDD 實作註解未對照 spec use case（code 38 token vs spec 10） | 中 | v0.38.1 |
| PC-MON-001 | 工具防護落地於可繞過的執行點導致復發（version-release pre-flight 防護在手動收尾路徑零次執行） | 中 | v0.3.5 |
| PC-MON-002 | 必填不等於有效——CLI 必填欄位無格式/存在性驗證，自由文字穿透防護（resolved_by=設計決策） | 中 | v0.3.6 |
| PC-BAL-005 | 決斷強制 hook 觸發詞正則誤傷標準章節名「Phase 4 重構評估」（PC-113/138/144 同家族，跨 hook 復發） | 中 | v0.1.0 |
| PC-BAL-010 | 驗證管道對待驗現象不敏感——檢查條件恆真或恆偽（家族層，下位含 TEST-BAL-001 / PC-MON-002 / PC-BAL-005） | 高 | v0.2.1 |
| PC-BAL-011 | 未讀目標載體即斷言缺口存在，據以建票或決策（PC-068 同根因不同載體） | 中 | v0.2.1 |
| PC-BAL-012 | 複合條件搜尋的加總計數遮蔽單一詞項零命中——一項證據被當成多項的覆蓋證明（PC-BAL-010 成員） | 高 | v0.2.1 |
| PC-BAL-013 | 主線程 context 中斷被當成背景代理人已終止，據以重派造成雙寫入者（PC-166 反方向） | 高 | v0.2.1 |
| PC-018 | PM Resume 後未檢查 5W1H 完整性即派發 | — | — |
| PC-091 | ANA Ticket 落地下游用兄弟而非子任務（血緣斷裂） | 中 | — |
| PC-092 | 並行代理人 git index 競爭導致 commit 邊界與訊息不對齊 | 中 | — |
| PC-093 | YAGNI 累積反模式：推測性抽象的延後決策 | 中 | v0.18.0 |
| PC-094 | TD 清單即時校準缺失 | 低-中 | v0.18.0 |
| PC-095 | WRAP W 階段選項池不完備（Claude 預設「新增工具」結構性偏見） | 中（影響 ANA 方向正確性，可能導致投入錯誤類型的 IMP） | — |
| PC-096 | CLI exit code 混淆「程式錯誤」與「業務拒絕」 | 中（影響 shell pipeline 自動化判讀，PM/Hook 無法區分「該重試」與「該停手」） | — |
| PC-097 | 同一資料於同一請求中被兩處 I/O 重複呼叫 | 中（效能損耗 + 兩次取值間資料漂移風險，破壞單次請求內資料一致性） | — |
| PC-098 | PM 撰寫通用規則時本能引用當下任務 ticket ID | — | — |
| PC-099 | Meta-ticket 自我引用造成 Hook 誤報 | 中 | v0.18.0 |
| PC-100 | ANA 衍生 IMP/ADJ 時 PCB 欄位未繼承 source ticket | 高（每次 ANA→IMP 衍生都可能踩） | — |
| PC-101 | 並行代理人結論矛盾時 PM 必須實證仲裁 | 中（僅在並行派發多 subagent 的多視角審查情境出現） | — |
| PC-102 | ANA Solution 修復方向表未逐項轉 spawned ticket | 高（ANA 結論看似完整實則追蹤遺漏） | — |
| PC-103 | 大型類比框架分析時漏排比較維度 | 中（僅在用大型系統做類比分析時觸發） | — |
| PC-104 | Agent 執行邊界誤判導致結果未落地 | 中（subagent hallucinate 系統限制導致結果流失） | — |
| PC-106 | 規則失效跳過讀 code 直接判定規則設計錯誤 | — | — |
| PC-107 | Phase 3b 派發前未走 cognitive-load 拆分檢查 | 高 | — |
| PC-108 | Subagent Commit 後未主動 Complete Ticket | — | — |
| PC-109 | .claude/ Runtime State 類型未評估 Sync 排除 | — | — |
| PC-110 | Body-Check False Negative via Schema Separator | — | — |
| PC-111 | PM 論述編造技術機制 + 根因淺層歸因 | — | — |
| PC-112 | Subagent 對非程式碼檔案誤選 MCP 寫入工具導致 early stop | 高 | — |
| PC-113 | Validator regex 缺字邊界導致 substring 誤判 placeholder | 中 | — |
| PC-114 | .claude/ 修改任務派發雙重阻擋（hook worktree 強制 + ARCH-015 runtime 阻擋） | 中 | — |
| PC-115 | subagent 對 .claude/ Edit 被 runtime 拒絕且無 hook 訊息 | 高 | — |
| PC-116 | 用「偶發/transient/不可重現」當分析失敗的合理化標籤 | 中 | — |
| PC-117 | ANA Solution multi_view_status Nested YAML 結構誤判 | — | — |
| PC-118 | ticket skill 行為變更未同步決策層（行為層 ↔ 決策層耦合鬆散） | 中 | — |
| PC-119 | parallel-evaluation 用法誤解 — PM 單派 linux 視角而非並行三人組 | 中 | — |
| PC-120 | 多視角審查結論未轉換為合法決策狀態 — 「P3 / 不建立 ticket」灰區 | 中 | — |
| PC-121 | PM 推薦框架 ticket 至未來 planned 版本（規則 6 與 version-progression 引用斷裂） | 中 | — |
| PC-122 | 新建 error-pattern 推翻既有 PC 但未同步舊 PC，留下並存衝突源 | 中（並存期間任何 PM 觸發都是潛在 bug 來源） | — |
| PC-123 | 規則存在但 agent 行為層未遵守 — agent-definition-standard 規範與實際輸出落差 | 中 | — |
| PC-124 | uv script header transitive 依賴未宣告 — `lib/` 共用模組引入的 yaml 不會自動安裝 | 中 | — |
| PC-130 | 規範性文字 dogfooding 違規（內容禁止絕對主義，形式採用絕對主義） | — | — |
| PC-131 | 外部工具權威性預設質疑 | 中 | — |
| PC-132 | Hook self-check 警示是被忽視的反推資料源 | 中 | — |
| PC-133 | 代理人對同性質任務的接受/拒絕行為不一致（self-imposed scope rejection） | 中 | — |
| PC-134 | ANA 自我指涉反諷（分析 X 反模式的 ANA 自身重蹈 X） | 高 | — |
| PC-135 | 子代理人 pytest 環境驗證通過但實際 hook 子進程環境失準 | — | — |
| PC-136 | 結構性修復未掃 lib callers 反模式 | — | — |
| PC-137 | 並行派發 subagent 對 `.claude/` Edit 觸發 runtime deny | — | — |
| PC-138 | Validator 將 trade-off 表格的 N/A cell 誤判為 placeholder（PC-113 延伸 false positive） | 中 | — |
| PC-139 | Git index.lock 衝突來源誤判（外部 GUI app fork 漏列） | 低（時間損耗，無資料損害） | — |
| PC-140 | Subagent commit message 與 stage 內容不一致 | 中 | v0.18.0 |
| PC-141 | 監測類 ANA acceptance 未預先區分設計性偏差 vs 失效性訊號 | 中 | v0.18.0 |
| PC-142 | Phase 4 Hook 字面抓觸發詞誤判規則引用為延後話術 | — | — |
| PC-143 | Spec / ANA 規劃引用既有資源（CLI flag / Hook 名稱）未驗證存在性 | — | — |
| PC-144 | Validator `\bTODO\b` 將合法內容中的 TODO/TBD 字面誤判為 placeholder（PC-138 同家族延伸） | 中 | — |
| PC-145 | Stale CLI install 偽裝為 validator bug — 修改源碼後未 reinstall 導致誤判修復未生效 | 中 | — |
| PC-146 | PC-093 exempt marker 位置誤用 — 標記置於章節下方或獨立段落而非命中行緊鄰處 | 低 | — |
| PC-147 | Reference doc 自寫自引導致 confabulation cascade | 高 | — |
| PC-148 | Hook 雙重註冊：settings.local.json python3 直呼繞過 shebang pep723 deps | 中 | — |
| PC-149 | Ticket complete 後合併分支 worktree 無自動清理 | 中 | v0.18.0 |
| PC-150 | Subagent 形似字 normalize 誤替換 | 中（靜默語意錯誤，人工抽查才能發現） | — |
| PC-151 | Stale 測試 exit code 期望未隨 CLI exit code 規範演進同步 | 低 | — |
| PC-152 | ticket migrate 撞既有目標 ID 後靜默覆寫 | 高 | — |
| PC-153 | PM 對 local-command-caveat 包裹的 skill 觸發訊號過度保守解讀 | 中 | — |
| PC-155 | ticket complete auto-stage 與 worktree append-log 並行編輯同一 ticket md 造成 merge conflict | 低 | — |
| PC-156 | PM cwd auto-switch 到 agent worktree | — | — |
| PC-157 | chrome-devtools-mcp install_extension 拒絕非 workspace roots 內路徑（含 /tmp） | 低 | — |
| PC-158 | mint-format-specialist 在視覺標記場景寫入 emoji（違反規則 3） | — | — |
| PC-159 | development-setup IMP 文件安裝指令未在 fresh shell 實機驗證 | — | — |
| PC-160 | PM 跳過升級評估閘門直接寫 memory 處理 session 浮現洞察 | — | — |
| PC-161 | ANA grep 範圍誤判導致「前車之鑑」強論證崩塌 | — | — |
| PC-163 | PM-worktree ticket md 偏離 — PM 在 main repo 跑 ticket CLI 與 agent 在 worktree 作業導致雙邊不同步 | 中 | — |
| PC-164 | MCP binary 名稱假設未實證 — `.mcp.json` 與 detector 同源誤判 | 中 | — |
| PC-165 | False Positive 修復鏈 — 測試綠燈不等於 Runtime 正確 | 高 | — |
| PC-166 | PM 幻覺工具執行結果（confabulated tool result）— git working tree 作為事實基準 | 高 | — |
| PC-167 | 分析代理人 worktree 內無 commit ticket body，PM 接手須 transcribe | 中 | — |
| PC-168 | Flaky Baseline 少量 sample 推導 stable 錯覺 | 高 | — |
| PC-169 | Merge 中斷後以 --no-verify commit 產生 empty merge commit 丟失工作 | 高 | — |
| PC-170 | 第三方 Claude Code skill vendoring 至框架的四個陷阱 | 中 | — |
| PC-173 | 框架文件引用的 MCP 工具名與實機暴露漂移 | — | — |
| PC-174 | 命令閘門 hook 將描述性陳述誤判為命令 + 缺前置條件時硬阻擋而非引導 | — | — |
| PC-175 | 框架跨專案 sync 攜帶來源專案類型專屬資產漏入目標專案 | — | — |
| PC-179 | worktree agent 完成後主線程 cwd 污染致 merge 誤判 | — | — |
| PC-184 | malformed tool-call 被當文字渲染而未執行 | — | — |
| PC-185 | ticket body append-log 寫入後未 commit 被 git 還原覆蓋 | — | — |
| PC-APP-003 | 衝突解決以量取代設計正確性 | — | — |
| PC-APP-006 | .gitignore 排除測試 fixture 導致新環境測試失敗 | 中 | — |
| PC-APP-008 | 外部 API 測試使用虛構測資標籤導致錯誤結論 | 高 | — |
| PC-APP-009 | 規範描述多載體雙寫漂移——方案變更後人工同步只掃部分載體 | 中 | — |
| PC-APP-011 | 驗收者沿用執行者的偵測 pattern——pattern 外缺陷零覆蓋的假陰性驗收 | 高 | — |
| PC-APP-012 | Domain map 將未實作概念列為已實作 bundle，衍生不可執行的測試 ticket | 中 | — |
| PC-BAL-001 | 驗證端清單過期使建立端產出的 canonical 結構被判違規 | — | — |
| PC-BAL-002 | 檔案合併遺漏子功能，但檔頭仍宣稱完整承接 | — | — |
| PC-BAL-003 | 未來工作建為 ticket，並繞過工具守衛使其成立 | — | — |
| PC-BAL-004 | 派發者將未查證的事實寫入 ticket context，成為執行者的錯誤前提 | — | — |
| PC-BAL-006 | 子 shell cd 的 chpwd ls 傾印疊在 CLI 輸出前，被誤診為 CLI 故障而繞道 | 中 | — |
| PC-BAL-007 | 並行文件票各自陳述同一事實時，未實查的一方寫入誤述 | 中 | — |
| PC-BAL-008 | 同 repo 並行 agent 共用 git index，commit 掃入他人已 staged 檔案 | 中 | — |
| PC-BAL-009 | 測試 fixture 用相對路徑觸及專案根資產，同一套件在不同 cwd 給出不同顏色，兩方結果不符但皆屬實 | 高 | — |
| PC-TUNL-001 | monorepo 子端可編譯產物未納入 CI 守門（本機綠燈遮蔽 reproducibility） | 中 | v1.1.0 |
| PC-V1-011 | PM claim 待派發 ticket 導致代理人認領失敗 | 低 | — |
| PC-V1-014 | 為繞過 gate 而改變語意載體（children→spawned_tickets） | 中 | — |
| PC-010 (pm-skipped-checkpoint-after-ticket-complete) | PM 在 ticket complete 後跳過 Checkpoint 流程 | 中 | v0.1.0 |
| PC-010 (task-tracking-in-memory) | 將任務追蹤資訊放入 Memory 而非 Ticket | — | — |
| PC-019 (design-decision-memory-only) | 通用架構決策僅記錄到 Memory 未寫入框架文件 | 中 | v0.1.1 |
| PC-019 (worktree-merge-state-loss) | Worktree 合併流程中 Ticket 狀態遺失 | — | — |
| PC-020 (fix-at-consumer-instead-of-producer) | 修復方向錯誤 — 在消費端補救而非生產端防護 | — | — |
| PC-020 (plan-execution-dispatch-mismatch) | 計畫-執行派發不一致（敘述與實際 agent 數量不符） | 中 | v0.1.2 |
| PC-030 (agent-slash-command-unreachable) | 代理人定義中使用 slash command 引用 Skill，但代理人無法觸發 slash command | 中 | v0.2.0 |
| PC-030 (phase4-unused-code-incomplete-grep) | Phase 4 未使用程式碼判斷未全專案 grep 驗證 | 中 | — |
| PC-105 (feature-implemented-without-doc-integration) | 新功能實作後缺乏文件引導整合 | — | — |
| PC-105 (pm-cli-syntax-autopilot) | PM 對 SKILL CLI 語法的 autopilot 假設 | 中 | v0.18.0 |
| PC-BAL-014 | Skill 註冊表 session 快取遮蔽檔案系統變更 — 同 session 驗證得出假陰性 | 中 | v0.2.1 |

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
