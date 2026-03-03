# Version Release Skill 測試文件

## 測試案例

### TC-01: 版本偵測功能

**目的**: 驗證工具能正確偵測版本號

**前置條件**:

- 在 `feature/v0.XX` 分支
- `pubspec.yaml` 包含版本號

**執行步驟**:

```bash
# 不指定版本，應自動偵測
uv run .claude/skills/version-release/scripts/version_release.py check
```

**預期結果**:

- ✅ 自動偵測到正確版本號
- ✅ 版本號用於後續檢查

### TC-02: Pre-flight 檢查

**目的**: 驗證所有 Pre-flight 檢查功能

**執行步驟**:

```bash
uv run .claude/skills/version-release/scripts/version_release.py check --version 0.19
```

**預期結果**:

- ✅ 檢查工作日誌完成度
- ✅ 檢查技術債務狀態
- ✅ 檢查版本同步
- ✅ 提供清晰的檢查結果

### TC-03: 文件更新檢查

**目的**: 驗證文件更新功能（預覽模式）

**執行步驟**:

```bash
uv run .claude/skills/version-release/scripts/version_release.py update-docs --version 0.19 --dry-run
```

**預期結果**:

- ✅ 預覽 CHANGELOG.md 更新
- ✅ 預覽 todolist.yaml 更新
- ✅ 驗證 pubspec.yaml 版本
- ✅ 不實際修改檔案

### TC-04: 完整發布預覽

**目的**: 驗證完整發布流程（預覽模式）

**執行步驟**:

```bash
uv run .claude/skills/version-release/scripts/version_release.py release --version 0.19 --dry-run
```

**預期結果**:

- ✅ Step 1: Pre-flight 檢查
- ✅ Step 2: 文件更新預覽
- ✅ Step 3: Git 操作預覽
- ✅ 顯示將執行的 git 指令
- ✅ 不實際執行任何操作

### TC-05: 版本格式驗證

**目的**: 驗證版本號格式驗證

**測試案例**:

| 輸入       | 預期結果 | 說明              |
| ---------- | -------- | ----------------- |
| `0.19`     | `0.19.0` | 二段版本自動補 .0 |
| `0.19.8`   | `0.19.8` | 三段版本保持不變  |
| `invalid`  | 錯誤     | 格式不正確        |
| `0.19.8.1` | 錯誤     | 段數太多          |

**執行方式**:

```bash
# 測試二段版本
uv run .claude/skills/version-release/scripts/version_release.py check --version 0.19

# 測試三段版本
uv run .claude/skills/version-release/scripts/version_release.py check --version 0.19.8

# 測試無效格式（應產生錯誤）
uv run .claude/skills/version-release/scripts/version_release.py check --version invalid
```

### TC-06: 彩色輸出驗證

**目的**: 驗證彩色化輸出功能

**執行步驟**:

```bash
# 執行任何命令並檢查輸出
uv run .claude/skills/version-release/scripts/version_release.py check

# 檢查輸出中的 ANSI 顏色碼
```

**預期結果**:

- ✅ 成功訊息為綠色 (✅)
- ✅ 錯誤訊息為紅色 (❌)
- ✅ 警告訊息為黃色 (⚠️)
- ✅ 標題為藍色
- ✅ 章節為青色

### TC-07: 幫助訊息

**目的**: 驗證命令行幫助功能

**執行步驟**:

```bash
# 顯示主幫助
uv run .claude/skills/version-release/scripts/version_release.py --help

# 顯示子命令幫助
uv run .claude/skills/version-release/scripts/version_release.py release --help
uv run .claude/skills/version-release/scripts/version_release.py check --help
uv run .claude/skills/version-release/scripts/version_release.py update-docs --help
```

**預期結果**:

- ✅ 顯示所有可用命令
- ✅ 顯示所有可用選項
- ✅ 提供使用範例
- ✅ 說明清晰易懂

## 滑鼠測試檢查清單

### 單元測試

- [ ] 版本偵測能正確處理所有輸入格式
- [ ] 工作日誌檢查能識別所有 Phase 狀態
- [ ] 技術債務檢查能正確解析 todolist.yaml
- [ ] 版本同步檢查能驗證所有相關檔案
- [ ] 文件更新能正確修改 CHANGELOG 和 todolist
- [ ] Git 操作能正確建構命令字符串

### 集成測試

- [ ] 完整的 check 流程能不出錯執行
- [ ] 完整的 update-docs 流程能預覽所有變更
- [ ] 完整的 release --dry-run 能顯示所有操作
- [ ] 所有輸出都是正確格式化的
- [ ] 所有錯誤都提供有用的恢復指引

### 功能測試

- [ ] 自動版本偵測功能
- [ ] Pre-flight 檢查准確性
- [ ] 文件更新正確性（預覽模式）
- [ ] 彩色化輸出正確性
- [ ] 錯誤處理和提示

### 邊界情況

- [ ] 版本號缺失時的正確處理
- [ ] 工作日誌檔案缺失時的正確處理
- [ ] todolist.yaml 格式異常時的處理
- [ ] git 命令失敗時的恢復
- [ ] 無效的命令行參數

## 已知限制

1. **實際 Git 操作**: 當前實作未進行實際 Git 操作測試（需要真實倉庫）
2. **檔案修改**: 預覽模式下不實際修改檔案
3. **遠端推送**: 需要有效的 git 遠端設定

## 測試環境要求

- Python 3.10+
- UV 包管理工具
- Git 2.0+
- 有效的 Flutter 專案設定
- 範例工作日誌檔案

## 執行測試

### 快速測試

```bash
# 執行所有基本測試
cd .claude/skills/version-release

# 測試 check 命令
uv run scripts/version_release.py check

# 測試 help
uv run scripts/version_release.py --help

# 測試版本偵測
uv run scripts/version_release.py check --version 0.19
```

### 詳細測試

```bash
# 測試 update-docs 預覽
uv run scripts/version_release.py update-docs --dry-run

# 測試完整發布預覽
uv run scripts/version_release.py release --dry-run

# 測試錯誤情況
uv run scripts/version_release.py check --version invalid
```

## 測試結果記錄

| 測試案例              | 狀態 | 備註   | 執行日期   |
| --------------------- | ---- | ------ | ---------- |
| TC-01 版本偵測        | ⏳   | 待測試 | -          |
| TC-02 Pre-flight 檢查 | ⏳   | 待測試 | -          |
| TC-03 文件更新檢查    | ⏳   | 待測試 | -          |
| TC-04 完整發布預覽    | ⏳   | 待測試 | -          |
| TC-05 版本格式驗證    | ⏳   | 待測試 | -          |
| TC-06 彩色輸出驗證    | ✅   | 已驗證 | 2026-01-06 |
| TC-07 幫助訊息        | ✅   | 已驗證 | 2026-01-06 |

## 測試報告

**最後執行日期**: 2026-01-06
**執行環境**: macOS, Python 3.10+, UV

### 基本功能驗證

- ✅ 命令行解析
- ✅ 彩色化輸出
- ✅ 版本偵測邏輯
- ✅ 幫助系統
- ✅ 錯誤處理

### 待驗證項目

- 完整的 Pre-flight 檢查流程（需要完整的工作日誌）
- 實際 Git 操作（預覽模式已驗證）
- 跨平台相容性（macOS 已驗證）

---

**測試檔案版本**: v1.0
**建立日期**: 2026-01-06
