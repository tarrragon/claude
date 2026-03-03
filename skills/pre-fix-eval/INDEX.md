# Pre-Fix Eval SKILL - 檔案索引

**版本**: v1.0 | **狀態**: ✅ 完成 | **建立**: 2025-01-12

## 目錄結構

```
.claude/skills/pre-fix-eval/
├── SKILL.md                           # ⭐ 完整 SKILL 定義（核心檔案）
├── README.md                          # 快速開始指南
├── INDEX.md                           # 此檔案 - 索引說明
├── templates/
│   └── fix-ticket.template           # 修復 Ticket 模板
├── references/
│   ├── decision-matrix.md            # 決策矩陣完整參考
│   ├── pre-fix-evaluation-implementation.md      # 技術實作細節
│   └── pre-fix-evaluation-acceptance-report.md   # 驗收報告
└── scripts/                           # 預留目錄（未來擴展）
```

## 檔案說明

### 核心檔案

#### SKILL.md (⭐ 必讀)
- **大小**: ~2500 行
- **用途**: 完整的 Pre-Fix Eval SKILL 定義
- **包含內容**:
  - Frontmatter (名稱、描述、類別)
  - 概述和核心功能
  - 自動錯誤分類
  - 六階段評估流程詳細說明
  - 錯誤分類優先級
  - 修復決策矩陣
  - 常見情況處理指南 (5 種場景)
  - 禁止行為清單
  - 自動化觸發機制
  - 錯誤模式識別參考
  - 修復品質檢查清單
  - 完整的 Reference 連結

**何時使用**:
- 需要完整理解評估流程
- 查詢詳細的決策邏輯
- 了解所有支援的錯誤類型

### 快速入門文件

#### README.md
- **大小**: ~300 行
- **用途**: 快速開始和常用參考
- **包含內容**:
  - 三步驟工作流 (自動偵測 → 評估 → 執行)
  - 錯誤分類速查表
  - 禁止行為清單
  - 修復決策矩陣 (簡化版)
  - Ticket 快速模板
  - Hook 輸出識別
  - 常見情況說明
  - 測試 Hook 功能的步驟
  - 快速除錯指南
  - 最佳實踐

**何時使用**:
- 第一次使用本系統
- 快速查詢常見情況
- 尋找快速檢查清單

#### INDEX.md
- **此檔案**
- **用途**: 說明 SKILL 目錄結構和檔案用途
- **適用**: 尋找特定檔案時

### 模板檔案

#### templates/fix-ticket.template
- **大小**: ~200 行
- **用途**: 修復 Ticket 的建立模板
- **包含內容**:
  - Stage 1-6 的檔案佔位符
  - 錯誤分類章節
  - BDD 分析章節
  - 文件查詢章節
  - 根因定位章節
  - 修復策略章節
  - 分派執行章節
  - 驗收條件清單
  - 5W1H 決策分析

**使用方式**:
```bash
# 複製模板建立新 Ticket
cp .claude/skills/pre-fix-eval/templates/fix-ticket.template /tmp/my-ticket.md

# 或在建立 Ticket 時參考此檔案的結構
```

**何時使用**:
- 使用 `/ticket create` 建立修復 Ticket
- 參考 Ticket 應該包含的章節和內容

### 參考檔案

#### references/decision-matrix.md
- **大小**: ~400 行
- **用途**: 完整的決策矩陣和邏輯樹參考
- **包含內容**:
  - 修復決策矩陣 (5 種情況)
  - 代理人分派決策樹 (完整的決策邏輯)
  - 根因分析決策樹
  - 錯誤類型優先級
  - 常見根因分析對應表
  - 根因 → 決策映射表
  - Ticket 決策判斷樹
  - 修復驗收檢查清單
  - 版本發布統計模板

**何時使用**:
- 需要做複雜的根因分析決策
- 查詢所有可能的代理人分派情況
- 設計發布版本的修復統計

#### references/pre-fix-evaluation-implementation.md
- **大小**: ~430 行
- **用途**: Hook 和 Skill 的完整技術實作說明
- **包含內容**:
  - 概述和核心功能
  - 檔案清單
  - Hook 腳本技術細節
  - Skill 檔案說明
  - 配置更新記錄
  - 13 個驗證測試案例
  - 正則表達式模式驗證
  - 配置詳情
  - 日誌系統說明
  - 故障排除指南
  - 驗收條件檢查清單
  - 後續改進方向

**何時使用**:
- 需要理解 Hook 如何工作
- 查看技術驗證測試結果
- 了解正則表達式模式
- 除錯 Hook 相關問題

#### references/pre-fix-evaluation-acceptance-report.md
- **大小**: ~500 行
- **用途**: 完整的驗收報告和質量保證文檔
- **包含內容**:
  - 驗收范圍和基準
  - 7 大驗收結果部分:
    - Hook 腳本正確性
    - 錯誤分類功能
    - 語法錯誤直接分派
    - 非語法錯誤強制 Ticket
    - Skill 檔案完整性
    - settings.json 配置
    - 技術文件完整性
  - 驗收統計表
  - 驗收結論
  - 簽核和日期
  - 後續事項和改進方向

**何時使用**:
- 確認系統已通過質量驗收
- 查看具體的測試案例和結果
- 了解系統的驗收標準

## 文件關係圖

```
外部系統
    ↓
Hook 腳本 (.claude/hooks/pre-fix-evaluation-hook.py)
    ↓
自動分類錯誤 (SYNTAX/COMPILATION/TEST_FAILURE/WARNING)
    ├─ 語法錯誤 → 簡化流程 (無需 Ticket)
    └─ 其他錯誤 → 強制評估提示
         ↓
    SKILL 啟動 (/pre-fix-eval)
    使用: SKILL.md + README.md
         ↓
    六階段評估流程
    參考: SKILL.md 各章節 + decision-matrix.md
         ↓
    開 Ticket (/ticket create)
    模板: fix-ticket.template
         ↓
    分派執行
    決策: decision-matrix.md
         ↓
    修復完成
    檢查: fix-ticket.template 驗收條件
```

## 使用場景對應

### 場景 1: 第一次使用本系統
1. 讀 README.md (10 分鐘)
2. 執行一個簡單測試 (5 分鐘)
3. 完成一個評估流程 (20 分鐘)

**使用檔案**: README.md, SKILL.md

### 場景 2: 遇到複雜錯誤需要分派決策
1. 讀 SKILL.md 中的相關常見情況 (10 分鐘)
2. 查詢 decision-matrix.md 確認決策 (5 分鐘)
3. 建立 Ticket (10 分鐘)

**使用檔案**: SKILL.md, decision-matrix.md, fix-ticket.template

### 場景 3: Hook 未觸發或行為異常
1. 查看 README.md 的快速除錯 (5 分鐘)
2. 查詢 implementation.md 的故障排除 (10 分鐘)
3. 檢查 settings.json 和日誌 (5 分鐘)

**使用檔案**: README.md, pre-fix-evaluation-implementation.md

### 場景 4: 需要理解技術細節
1. 讀 implementation.md (20 分鐘)
2. 查看驗收報告的測試案例 (10 分鐘)
3. 檢查 Hook 腳本本身 (15 分鐘)

**使用檔案**: pre-fix-evaluation-implementation.md, pre-fix-evaluation-acceptance-report.md

## 整合檔案清單

本 SKILL 與以下檔案整合：

### Hook 系統檔案
- **Hook 腳本**: `.claude/hooks/pre-fix-evaluation-hook.py`
  - 自動分類錯誤的 Python 腳本
  - 觸發條件: PostToolUse (Bash, mcp__dart__run_tests)

- **命令別名**: `.claude/commands/pre-fix-eval.md`
  - 用於執行 `/pre-fix-eval` 命令
  - 作為 SKILL 的進入點

### 配置檔案
- **Hook 配置**: `.claude/settings.json`
  - PostToolUse Hook 配置
  - 路徑: `hooks > PostToolUse`

### 方法論檔案
- **敏捷重構方法論**: `.claude/methodologies/agile-refactor-methodology.md`
- **Ticket 生命週期**: `.claude/methodologies/ticket-lifecycle-management-methodology.md`
- **Atomic Ticket**: `.claude/methodologies/atomic-ticket-methodology.md`

## 檔案大小統計

```
總大小: ~4000 行, ~350 KB

核心檔案:
├─ SKILL.md: 2500+ 行 (完整定義)
├─ README.md: 300+ 行 (快速參考)
└─ INDEX.md: 300+ 行 (此檔案)

模板和參考:
├─ fix-ticket.template: 200+ 行
├─ decision-matrix.md: 400+ 行
├─ pre-fix-evaluation-implementation.md: 430+ 行
└─ pre-fix-evaluation-acceptance-report.md: 500+ 行
```

## 維護和更新

### 版本記錄
- **v1.0** (2025-01-12): 初始版本，包含完整的六階段流程

### 預計改進 (v1.1+)
- 新增更多語言支援 (JavaScript, TypeScript)
- 改進錯誤訊息翻譯
- 與 Ticket Tracker 深度整合
- 修復效率統計

### 文件維護指南
1. 每當 Hook 更新時，同步更新 implementation.md
2. 每當新增常見情況時，更新 decision-matrix.md
3. 每個版本發布時，更新 SKILL.md 版本號
4. 驗收報告為只讀，不應修改（新驗收用新檔案）

## 快速鏈接

- **完整 SKILL**: [SKILL.md](./SKILL.md)
- **快速開始**: [README.md](./README.md)
- **決策矩陣**: [references/decision-matrix.md](./references/decision-matrix.md)
- **技術細節**: [references/pre-fix-evaluation-implementation.md](./references/pre-fix-evaluation-implementation.md)
- **驗收報告**: [references/pre-fix-evaluation-acceptance-report.md](./references/pre-fix-evaluation-acceptance-report.md)
- **Ticket 模板**: [templates/fix-ticket.template](./templates/fix-ticket.template)

## 支援和反饋

遇到問題或有建議？

1. 查看 README.md 的常見問題
2. 查看 implementation.md 的故障排除
3. 查看 decision-matrix.md 的決策邏輯
4. 查看 Hook 日誌: `.claude/hook-logs/pre-fix-evaluation-*.json`
5. 啟用 debug 模式: `HOOK_DEBUG=true`

---

**此 SKILL 已完全整合和驗收，可投入使用。**
