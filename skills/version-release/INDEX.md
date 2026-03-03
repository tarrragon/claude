# Version Release Skill - 檔案索引

## 檔案結構

```
version-release/
├── README.md                         # 快速參考指南
├── SKILL.md                          # 完整功能文件（核心參考）
├── INDEX.md                          # 此檔案（目錄索引）
├── scripts/
│   └── version_release.py            # 主要執行腳本
├── templates/
│   └── release-checklist.md          # 發布檢查清單範本
└── tests/
    └── test_version_release.md       # 測試文件
```

## 快速導覽

### 我是新使用者，想快速上手

→ 閱讀 [`README.md`](./README.md) 的「快速開始」章節

### 我需要完整的功能說明

→ 詳讀 [`SKILL.md`](./SKILL.md)

### 我想了解三步驟發布流程

→ 查看 [`SKILL.md` 的「三步驟發布流程」](./SKILL.md#三步驟發布流程)

### 我需要實際執行發布

→ 按照 [`README.md` 的「使用流程」](./README.md#使用流程)

### 我需要發布檢查清單

→ 複製 [`templates/release-checklist.md`](./templates/release-checklist.md)

### 我想了解技術細節

→ 閱讀 [`scripts/version_release.py`](./scripts/version_release.py) 的原始碼

### 我想測試工具

→ 參考 [`tests/test_version_release.md`](./tests/test_version_release.md)

## 檔案詳細說明

### README.md (快速參考)

- **用途**: 快速參考指南
- **內容**: 快速開始、核心功能、子命令、使用流程
- **適合**: 已了解基本概念，想快速查詢用法的使用者
- **大小**: ~300 行
- **更新頻率**: 低

### SKILL.md (完整文件)

- **用途**: 完整的功能和技術文件
- **內容**: 核心功能、三步驟流程、CLI 設計、版本偵測、輸出範例、錯誤處理、相關工具
- **適合**: 需要完全理解工具功能的開發者
- **大小**: ~650 行
- **更新頻率**: 低
- **對應 Frontmatter**: name, description 等元資料

### version_release.py (主要腳本)

- **用途**: 版本發布自動化工具的核心實現
- **語言**: Python 3.10+
- **模式**: UV Single-File (PEP 723)
- **功能**:
  - 版本偵測和規範化
  - Pre-flight 檢查 (worklog, TD, 版本同步)
  - 文件更新 (CHANGELOG, todolist, pubspec.yaml)
  - Git 操作 (commit, merge, tag, push, cleanup)
  - 彩色化輸出和錯誤報告
- **大小**: ~650 行代碼
- **依賴**: pyyaml

### release-checklist.md (檢查清單範本)

- **用途**: 版本發布前的人工檢查清單
- **內容**: Phase 驗證、技術債務檢查、版本號同步、Git 操作、後續操作
- **使用方式**: 複製並填入版本號，按照清單逐項檢查
- **大小**: ~200 行
- **更新頻率**: 版本變更時

### test_version_release.md (測試文件)

- **用途**: 測試用例和驗證指南
- **內容**: 7 個主要測試案例、檢查清單、測試環境要求、測試結果記錄
- **大小**: ~200 行
- **測試涵蓋範圍**: 版本偵測、Pre-flight、文件更新、彩色輸出、幫助系統

## 使用決策樹

```
我需要發布版本
    ├─ 我想了解工具功能
    │  ├─ 快速參考 → README.md
    │  └─ 完整說明 → SKILL.md
    │
    ├─ 我想執行發布
    │  ├─ 檢查版本準備度 → check 命令
    │  ├─ 預覽發布流程 → release --dry-run 命令
    │  └─ 執行發布 → release 命令
    │
    ├─ 我需要檢查清單
    │  └─ 複製 release-checklist.md
    │
    └─ 我想測試工具
       └─ test_version_release.md
```

## 常見操作指南

### 查詢命令用法

```bash
# 顯示所有子命令
uv run scripts/version_release.py --help

# 查詢特定子命令
uv run scripts/version_release.py release --help
uv run scripts/version_release.py check --help
```

### 查詢三步驟流程

查看 `SKILL.md` 的以下章節：

- 「Step 1: Pre-flight 檢查」
- 「Step 2: 文件更新」
- 「Step 3: Git 操作」

### 查詢輸出範例

查看 `SKILL.md` 的「輸出範例」章節：

- 完整發布流程（release）
- 預覽模式（--dry-run）
- 只檢查（check）
- 錯誤情況

### 查詢常見問題

查看 `SKILL.md` 的「錯誤處理和恢復」章節

### 查詢版本格式規則

查看 `SKILL.md` 的「支援的版本格式」章節

## 檔案維護職責

| 檔案                    | 維護者                   | 更新時機              |
| ----------------------- | ------------------------ | --------------------- |
| README.md               | basil-hook-architect     | 功能變更時            |
| SKILL.md                | basil-hook-architect     | 功能或規格變更時      |
| version_release.py      | basil-hook-architect     | 功能實現或 bug 修復時 |
| release-checklist.md    | rosemary-project-manager | 發布流程變更時        |
| test_version_release.md | pepper-test-implementer  | 新增測試用例時        |

## 版本歷史

| 版本 | 日期       | 主要變更 |
| ---- | ---------- | -------- |
| v1.0 | 2026-01-06 | 初始發布 |

## 相關文件

### 內部參考

- `.claude/skills/tech-debt-capture/SKILL.md` - 技術債務捕捉工具
- `.claude/skills/ticket create/` - Ticket 建立工具

### 外部參考

- `docs/todolist.yaml` - 版本狀態和技術債務追蹤
- `CHANGELOG.md` - 版本變動記錄
- `pubspec.yaml` - 應用程式版本號
- `docs/work-logs/` - 所有 Phase 工作日誌

## 快速命令參考

```bash
# 檢查版本準備度
uv run scripts/version_release.py check

# 預覽發布流程
uv run scripts/version_release.py release --dry-run

# 執行完整發布
uv run scripts/version_release.py release

# 只更新文件（預覽）
uv run scripts/version_release.py update-docs --dry-run

# 查看幫助
uv run scripts/version_release.py --help
```

## 獲取幫助

1. **快速答案** → 查看 README.md
2. **詳細說明** → 查看 SKILL.md
3. **實際例子** → 查看 SKILL.md 的輸出範例
4. **常見問題** → 查看 SKILL.md 的錯誤處理章節
5. **測試方法** → 查看 test_version_release.md

---

**索引檔案版本**: v1.0
**建立日期**: 2026-01-06
**維護者**: basil-hook-architect
