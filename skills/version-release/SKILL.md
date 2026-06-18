---
name: version-release
description: "版本發布整合工具。Use for: (1) 發布新版本（合併到 main、打 Tag、推送）, (2) 發布前健康檢查（所有 Ticket 完成？CHANGELOG 更新？）, (3) 更新版本文件（worklog 狀態、CHANGELOG）。Use when: 準備發布版本、執行 /version-release check 確認發布前狀態、完成所有 Ticket 後要收尾時。"
---

# Version Release Skill

版本發布整合工具。結合工作日誌檢查、CHANGELOG 更新、Git 操作（合併、Tag、推送、清理）。

## 三步驟發布流程

1. **Pre-flight 檢查** - 驗證 Ticket 完成度、技術債務、版本同步
2. **文件更新** - 清理 todolist、更新 CHANGELOG、確認版本號
3. **Git 操作** - 合併、建立 Tag、推送、清理分支

> 各步驟的完整偽程式碼和檢查邏輯：`references/release-workflow-details.md`

## CLI 使用

```bash
# 啟動新版本
/version-release start --version 0.18.0 --description "測試重寫"

# 啟動新版本（預覽模式）
/version-release start --version 0.18.0 --from 0.17.2 --dry-run

# 完整發布（自動偵測版本）
/version-release release

# 指定版本 + 預覽模式
/version-release release --version 0.19 --dry-run

# 只執行檢查
/version-release check

# 只更新文件
/version-release update-docs
```

| 子命令 | 說明 |
|--------|------|
| `start` | 啟動新版本（Options: `--version`(必填)、`--from`、`--description`、`--dry-run`） |
| `release` | 完整發布流程（Options: `--version`、`--dry-run`、`--force`、`--defer-td`） |
| `check` | 只執行 Pre-flight 檢查 |
| `update-docs` | 只更新文件 |

### start 子命令

程式化版本啟動流程，完整生命週期：`start` -> `check` -> `release`。

**執行步驟**：
1. 前版本驗證（檢查 completed 狀態和 git tag）
2. 專案類型偵測（自動或讀取 `.version-release.yaml` 配置）
3. 重複檢查（確認新版本不存在）
4. 更新 todolist.yaml（插入新版本條目，字串操作保留格式）
5. 建立 worklog 目錄結構和主檔案（從模板生成，路徑依專案類型決定）
6. Bump 版本檔案（依專案類型選擇對應的版本源 + sync targets）
7. 輸出摘要報告和下一步建議

## 多專案類型支援

工具自動偵測專案類型並調整版本偵測、bump 策略與 worklog 路徑。支援以下專案類型：

> **monorepo 設定前先決定版本模型**：單一版本號（整個 repo 一個 tag）vs 子專案獨立版本，取捨判準（耦合 / 獨立消費者 / 相容性 / 發布節奏）與兩種配置 recipe 見 `references/monorepo-versioning-strategy.md`。註：現行 `monorepo` 類型預設「子專案各自獨立版本」，統一版本 monorepo 需以主版本源子專案的語言類型 + `version_source.primary` 表達。

| 專案類型 | 識別方式 | 主版本源 | bump 格式 |
|---------|---------|---------|----------|
| `flutter` | `pubspec.yaml` 存在 | `pubspec.yaml` | YAML（支援 `X.Y.Z+build` 自動遞增 build number） |
| `go` | `go.mod` 存在 | git tag | 無檔案 bump（版本由 git tag 管理） |
| `chrome-ext` | `package.json` + `manifest.json` 同時存在 | `package.json` | JSON（自動同步 `manifest.json`） |
| `php` | `composer.json` 存在 | `composer.json` | JSON |
| `npm` | 僅 `package.json` 存在（無 `manifest.json`） | `package.json` | JSON |
| `python` | `pyproject.toml` 存在 | `pyproject.toml` | TOML（支援單引號和雙引號） |
| `monorepo` | 根目錄無版本檔但子目錄（depth=1）含版本檔 | 依子專案 | 依子專案類型 |
| `unknown` | 無任何已知標記檔 | git tag | 無檔案 bump |

### 自動偵測優先序

偵測按以下順序進行，**第一個命中即停止**：

1. `pubspec.yaml` → `flutter`
2. `go.mod` → `go`
3. `package.json` + `manifest.json` → `chrome-ext`
4. `composer.json` → `php`
5. 僅 `package.json` → `npm`
6. `pyproject.toml` → `python`
7. 子目錄含版本檔 → `monorepo`
8. 全無 → `unknown`

若自動偵測不正確，在 `.version-release.yaml` 中明確指定 `project_type` 覆蓋。

### 版本源解析優先序

`resolve_version_source` 依以下優先序決定版本源：

1. `.version-release.yaml` 指定 `version_source.primary` → 使用指定檔案
2. 無配置 → 依 `VERSION_FILE_CANDIDATES` 順序掃描（`pubspec.yaml` > `package.json` > `manifest.json` > `composer.json` > `pyproject.toml`）
3. 全無版本檔但有 `go.mod` → fallback 到 `git-tag`（不 bump 檔案，版本由 tag 管理）

## 版本偵測

偵測優先順序：`--version 參數` -> `git branch (feature/vX.Y)` -> 版本檔案（依語言） -> `git tag`

## 版本策略

### Chrome Extension 雙版本來源

| 來源 | 檔案 | 說明 |
|------|------|------|
| NPM 版本 | `package.json` | 專案主版本，Ticket/Wave 以此為準 |
| Chrome 版本 | `manifest.json` | Chrome Web Store 發布版本 |

`check` 子命令驗證兩者一致，不一致視為錯誤。

### 其他專案類型

| 專案類型 | 版本策略 |
|---------|---------|
| `flutter` | `pubspec.yaml` 為唯一版本源；含 `+build` 後綴時 bump 自動遞增 build number |
| `go` | 無版本檔，版本完全由 git tag 管理；`start` 階段不 bump 檔案 |
| `php` / `npm` / `python` | 單一版本源（`composer.json` / `package.json` / `pyproject.toml`） |
| `monorepo` | 依 `subprojects` 配置各別管理（見 `.version-release.yaml` schema） |

## 前置條件

- Python 3.10+、Git 2.0+、`pyyaml`
- 完成 Phase 4 重構評估，技術債務已分類
- 版本檔案已存在（或使用 git-tag 策略）

## 使用流程檢查清單

- [ ] 所有 Ticket 已完成（無 pending/in_progress）
- [ ] 技術債務已分類到 todolist.yaml
- [ ] 權限需求變更檢查已完成（依專案類型，見「權限需求變更檢查」章節）
- [ ] 運行 `check` 確認所有檢查通過
- [ ] 運行 `release --dry-run` 預覽
- [ ] 運行 `release` 完成發布
- [ ] 驗證 main 分支已更新、Tag 已建立、feature 分支已清理

## `.version-release.yaml` 配置檔

配置檔為可選，放置於專案根目錄（`<root>/.version-release.yaml`）或 `.claude/` 目錄下（`<root>/.claude/.version-release.yaml`，後者在 branch-verify hook 豁免路徑內，適用 all-on-main 工作流）。不存在時使用內建預設值。

### Schema

| 欄位 | 型別 | 預設值 | 說明 |
|------|------|--------|------|
| `project_type` | `string \| null` | `null` | 專案類型，`null` 時自動偵測。可選值：`chrome-ext` / `flutter` / `go` / `php` / `python` / `npm` / `monorepo` |
| `version_source` | `object \| null` | `null` | 版本源配置（見下方子欄位）。`null` 時依 `VERSION_FILE_CANDIDATES` 自動偵測 |
| `version_source.primary` | `string` | — | 主版本源檔案相對路徑（如 `package.json`、`pubspec.yaml`） |
| `version_source.parser` | `string \| null` | 依副檔名推斷 | 版本源 parser 類型：`json` / `yaml` / `toml` / `git-tag` |
| `version_source.key` | `string` | `"version"` | 版本 key（json/yaml/toml 用） |
| `version_source.sync_targets` | `list[object]` | `[]` | 版本 bump 時一併更新的檔案清單，每項含 `path` 和 `parser` |
| `subprojects` | `list[object] \| null` | `null` | monorepo 子專案配置，每項含 `path` 和 `version_source` 子配置 |
| `release_workflow` | `string` | `"trunk"` | 發布工作流模式：`trunk`（all-on-main）或 `feature-branch`（merge + 分支清理） |
| `tag_format` | `string` | `"v{version}"` | Tag 命名範本，支援 `{version}` 和 `{major_minor}` 佔位符 |
| `worklog_path_pattern` | `string` | 依專案類型 | Worklog 目錄路徑範本，支援 `{version}` / `{major_minor}` / `{major}` 佔位符 |
| `versions` | `object` | 內建 Chrome Extension 配置 | 版本源定義（`package` / `manifest` 子配置） |
| `sync_rules` | `object` | 內建同步規則 | 版本同步規則（`on_release` / `on_development` / `conflict_detection`） |
| `preflight_checks` | `object` | 內建檢查配置 | Pre-flight 檢查配置 |

### Worklog 路徑預設值

未明確設定 `worklog_path_pattern` 時，依專案類型決定預設值：

| 專案類型 | 預設路徑範本 | 範例（v0.19.0） |
|---------|------------|----------------|
| `flutter` | `docs/work-logs/v{major}/v{major_minor}/v{version}` | `docs/work-logs/v0/v0.19/v0.19.0` |
| 其餘所有類型 | `docs/work-logs/v{version}` | `docs/work-logs/v0.19.0` |

### 各專案類型範例

#### Chrome Extension

```yaml
# .version-release.yaml
project_type: chrome-ext
release_workflow: trunk
tag_format: "v{version}"
version_source:
  primary: package.json
  parser: json
  sync_targets:
    - path: manifest.json
      parser: json
```

#### Flutter

```yaml
# .version-release.yaml
project_type: flutter
release_workflow: feature-branch
tag_format: "v{version}"
worklog_path_pattern: "docs/work-logs/v{major}/v{major_minor}/v{version}"
version_source:
  primary: pubspec.yaml
  parser: yaml
```

#### Go

```yaml
# .version-release.yaml
project_type: go
release_workflow: feature-branch
tag_format: "v{version}"
version_source:
  parser: git-tag
```

#### PHP

```yaml
# .version-release.yaml
project_type: php
release_workflow: trunk
version_source:
  primary: composer.json
  parser: json
```

#### Monorepo

```yaml
# .version-release.yaml
project_type: monorepo
release_workflow: feature-branch
subprojects:
  - path: packages/frontend
    version_source:
      primary: package.json
      parser: json
  - path: packages/backend
    version_source:
      primary: pyproject.toml
      parser: toml
```

## 參考資料

| 資料 | 說明 |
|------|------|
| `references/release-workflow-details.md` | 三步驟完整偽程式碼和檢查邏輯 |
| `references/cli-output-examples.md` | CLI 輸出範例和版本偵測說明 |
| `references/troubleshooting.md` | 常見問題和恢復指引 |
| `references/monorepo-versioning-strategy.md` | monorepo 單一版本 vs 子專案獨立版本的取捨判準與配置 recipe |

## 權限需求變更檢查

版本發布或推進時，若專案有面向使用者的權限宣告，須檢查權限是否較上一發布版本變更；有變更則同步更新權限說明文件與上架頁的權限聲明。**Why**：應用程式商店（Chrome Web Store、Google Play、App Store）審核會比對上架頁的權限聲明與專案實際的權限宣告檔，兩者不符是審核卡關的常見原因。**Consequence**：權限說明 drift 後，審核退件需重新提交，延誤發布。**Action**：發布前依下方專案類型對照表，檢查權限宣告檔差異並同步更新。

### 各專案類型處理方式

不同專案類型的權限宣告位置與更新對象不同，後端服務則無此需求：

| 專案類型 | 是否需檢查 | 權限宣告位置 | 同步更新對象 |
|---------|-----------|-------------|-------------|
| Chrome Extension | 是 | `manifest.json` 的 `permissions` / `host_permissions` | README 權限說明、隱私權政策文件、Chrome Web Store 開發者後台 |
| 行動 APP（Android / iOS） | 是 | Android `AndroidManifest.xml`；iOS `Info.plist` 的 usage description | 權限說明文件、Google Play / App Store 上架頁的權限與隱私聲明 |
| 後端服務 | 否 | 無使用者端權限宣告 | N/A |

### 檢查步驟（適用「需檢查」的專案類型）

1. 比對權限宣告位置的內容與上一發布版本（git tag 或上一 release commit）的差異。
2. 若有新增或移除權限，同步更新上表「同步更新對象」欄列出的所有文件與上架頁。
3. 若無變更，於該版本 worklog 的技術筆記章節標註「權限無變更」。

**相關 Skill**: `tech-debt-capture`（Phase 4 技術債務提取）

---

**Last Updated**: 2026-06-17
**Version**: 2.0.0 - 新增多專案類型支援文件（chrome-ext/flutter/go/php/python/npm/monorepo）、.version-release.yaml schema 文件化、自動偵測 fallback 說明（1.0.0-W1-104）

---

## 修改 source 後必須重新安裝

> **重要**：本 skill 透過 `uv tool install` 安裝為獨立 CLI，source（本目錄）與 installed（`~/.local/share/uv/tools/<package>/`）是兩份獨立 Python package。修改 source 後若未 reinstall，CLI 仍使用 stale installed 版本，新增的函式會 AttributeError 或被 hasattr 包裝靜默吞掉（W11-037 根因）。

**修復指令**：

```bash
cd .claude/skills/<本 skill 目錄> && uv tool install . --force --reinstall
```

**自動偵測**：每次 SessionStart 由 `uv-tool-staleness-check-hook` 比對 source vs installed SHA256，偵測 stale 時提示修復指令。對應 ticket-skill 本身另有 `ticket-reinstall-hook` 自動 reinstall。
