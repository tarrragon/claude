# Monorepo 版本管理策略

本文件定義 monorepo 中多個版本層級的定義、同步規則和工具適配策略。

> **與 version-progression.md 的關係**：version-progression.md 定義「何時推進版本號」（Wave/Patch/Minor/Major 語義判斷），本文件定義「monorepo 中多個版本如何定義和協調」（L1/L2/L3 技術層級同步）。兩者互補，不重複定義相同概念。
>
> **來源**：0.1.1-W5-001 Monorepo 版本管理策略分析報告

---

## 三層版本定義

Monorepo 包含三個獨立的版本層級，各自有不同的來源、語義和更新規則。

### L1：Monorepo 版本（專案管理層）

| 項目 | 說明 |
|------|------|
| **來源** | `docs/todolist.yaml` → `current_version` |
| **當前值** | 由 todolist.yaml 的 `status: active` 版本決定 |
| **語義** | 整個專案（Go + Flutter + 文件系統）的發布版本 |
| **用途** | Ticket 版本號、Wave 管理、技術債務追蹤、發布計劃 |
| **更新時機** | 功能里程碑、主要架構變更、整體發布 |
| **決定者** | PM（透過 version-progression.md 的 Q1-Q4 判斷） |

**核心地位**：L1 是唯一的「專案版本」權威來源。所有 Ticket ID（如 `0.1.0-W1-001`）、工作日誌路徑（`docs/work-logs/v0.1.0/`）都基於 L1 版本。

### L2：Flutter UI 版本（應用層）

| 項目 | 說明 |
|------|------|
| **來源** | `ui/pubspec.yaml` → `version` |
| **當前值** | `1.0.0+1` |
| **語義** | Flutter 應用程式的發布版本 |
| **用途** | App Store / Google Play 版本管理、build number 迭代 |
| **更新時機** | UI 功能新增、大版本重構、App 商店發布 |
| **獨立性** | **獨立於 L1**（可在 L1 v0.1.0 期間升級到 L2 v1.1.0） |

**版本語義**：
- 主版本號：首次 App 商店發布
- build number（`+` 後數字）：每次構建遞增

### L3：Go Server 版本（後端層）

| 項目 | 說明 |
|------|------|
| **來源** | `server/go.mod`（無版本欄位） |
| **當前值** | 無自身版本定義 |
| **語義** | Go module 不具有自身版本（module path 為識別符） |
| **用途** | Go module 依賴版本管理 |
| **更新時機** | 與 L1 monorepo 版本同步 |
| **獨立性** | **隱含同步 L1**（Server 發布版本由 monorepo 版本決定） |

**未來規劃**：可在 `server/version.go` 添加版本常數，實現 Server 版本的顯式管理。

---

## 三層版本關係矩陣

| 版本層 | 來源檔案 | 獨立性 | 同步規則 | 更新時機 |
|--------|---------|--------|---------|---------|
| **L1 Monorepo** | todolist.yaml | 完全獨立 | N/A（權威來源） | Wave 完成、功能里程碑 |
| **L2 UI** | ui/pubspec.yaml | 獨立 | 建議同步（非強制） | App 發布、功能新增 |
| **L3 Server** | server/go.mod | 隱含同步 L1 | 同 monorepo | 整體系統發布 |

**核心規則**：

| # | 規則 | 說明 |
|---|------|------|
| 1 | L1 是唯一的「發布版本」定義 | Ticket、工作日誌、CHANGELOG 都基於 L1 |
| 2 | L2 可獨立於 L1 升級 | UI 小版本更新不需要同步 L1 |
| 3 | L3 由 L1 隱含決定 | Server 無自身版本欄位，跟隨 monorepo |
| 4 | Ticket 版本號永遠基於 L1 | 即使 L2 版本不同，Ticket 仍用 L1 版本 |

---

## 版本同步規則

### 發布時同步

| 版本層 | 必須更新 | 建議 |
|--------|---------|------|
| L1 Monorepo | 是 | 更新 todolist.yaml + CHANGELOG |
| L2 UI | 否 | 建議更新 build number（如 `1.0.0+5` → `1.0.0+6`） |
| L3 Server | 否 | 無需更新（由 L1 決定） |

### 開發中的版本邊界

| 規則 | 說明 |
|------|------|
| 允許版本不匹配 | 開發中 L2 和 L3 可獨立迭代 |
| 不自動同步 | 版本同步是顯式動作，非自動行為 |
| 不阻塞開發 | 版本不匹配不阻塞任何開發流程 |

### 版本衝突偵測

| 情境 | 嚴重程度 | 處理 |
|------|---------|------|
| L2 大於 L1 | warning | 確認是否故意（L2 可獨立升級） |
| L2 小於 L1 | info | 正常（L2 未同步升級） |
| L1 不匹配 git tag | error | 必須修正後才能發布 |
| L3 有版本欄位但與 L1 不同 | warning | 建議同步 |

---

## Version-Release Check 適配

### 現有檢查流程

```
version-release check
    |
    v
1. detect_version_files()
   → 找到 ["ui/pubspec.yaml"]
    |
    v
2. extract_version_from_file()
   → 提取 UI 版本 "1.0.0+1"
    |
    v
3. 版本對比
   → 比較 "1.0.0+1" vs "0.1.0"（L1 monorepo 版本）
    |
    v
4. 輸出警告（非致命）
   → WARNING: 版本不匹配（monorepo 場景下此為預期行為）
    |
    v
5. 繼續執行（檢查通過）
```

### 現有問題

| 問題 | 根本原因 |
|------|---------|
| 不清楚哪些版本差異是預期的 | 版本策略未正式定義（本文件解決） |
| 無法驗證 Server 版本 | go.mod 無版本欄位 |
| 不知何時應強制同步 | 缺乏同步規則定義（本文件解決） |
| 使用者看到警告無法判斷是否應修復 | 缺乏決策標準 |

### 改進方案：顯式版本同步規則

**同步政策定義**：

```python
VERSION_SYNC_POLICY = {
    "monorepo": {
        "source": "todolist.yaml",
        "mandatory": True,         # 必須更新
        "description": "整體專案版本"
    },
    "ui": {
        "source": "ui/pubspec.yaml",
        "mandatory": False,        # 可選同步（獨立版本）
        "recommendation": "建議與 monorepo 版本保持主版本號一致",
        "description": "Flutter 應用版本，獨立於 monorepo"
    },
    "server": {
        "source": "server/go.mod",
        "mandatory": None,         # 尚無版本欄位
        "note": "Go module 無自身版本欄位，版本由 monorepo 決定"
    }
}
```

**改進後的 CLI 輸出範例**：

```
版本同步檢查

monorepo 版本: 0.1.0 (todolist.yaml)
|-- ui/pubspec.yaml: 1.0.0+1
|   +-- 不匹配警告（此為預期行為）
|       理由：UI 應用版本獨立於 monorepo 版本
|       建議：若需同步，請修改 ui/pubspec.yaml -> version: 0.1.0
|
+-- server/go.mod: 無版本欄位（正常）
    理由：Go module 無自身版本，由 monorepo 決定
    +-- 版本由 monorepo 0.1.0 決定

結論：通過（版本策略符合 monorepo）
```

---

## .version-release.yaml 配置檔

### 用途

明確定義 monorepo 的版本管理策略，使工具和使用者有一致的理解。

### 位置

`.version-release.yaml`（根目錄）

### 建議內容

```yaml
# .version-release.yaml - Monorepo 版本管理配置

# 版本定義
versions:
  monorepo:
    source: docs/todolist.yaml       # 唯一的權威來源
    key: current_version
    semantic_version: true
    description: "整個專案的發布版本（用於 Ticket、Wave、發布計劃）"

  ui:
    source: ui/pubspec.yaml
    key: version
    semantic_version: true
    independent: true                 # UI 可獨立於 monorepo 升級
    description: "Flutter 應用版本（用於 App Store）"
    sync_policy: "optional"           # 建議同步，非強制
    sync_recommendation: "保持主版本號一致（如都是 v0.x.0）"

  server:
    source: null                      # go.mod 無版本欄位
    semantic_version: false
    independent: false
    description: "Go Server 版本由 monorepo 版本決定"
    sync_policy: "implicit"           # 隱含同步

# 版本同步規則
sync_rules:
  on_release:
    monorepo:
      required: true                  # 必須更新
    ui:
      required: false                 # 可選
      recommendation: |
        建議更新 UI 版本的 build number（例如 1.0.0+5 -> 1.0.0+6）
        或更新主版本號以匹配 monorepo（例如 1.0.0 -> 0.1.0）
    server:
      required: false                 # 無需更新（由 go.mod 決定）

  on_development:
    allow_version_mismatch: true
    reason: "開發中 UI 和 Server 可獨立迭代"

  conflict_detection:
    ui_ahead_of_monorepo:
      severity: "warning"
      message: "UI 版本大於 monorepo，確認是否故意？"
    ui_behind_monorepo:
      severity: "info"
      message: "UI 版本低於 monorepo（正常）"

# 版本偵測策略
detection:
  version_files:
    - path: ui/pubspec.yaml
      type: yaml
      key: version
      context: "Flutter 應用版本"

    - path: server/go.mod
      type: toml
      key: null
      context: "Go module（無版本欄位）"

    - path: docs/todolist.yaml
      type: yaml
      key: current_version
      context: "權威的 monorepo 版本來源"

  auto_detect_order:
    - git_branch                      # feature/v0.1
    - monorepo_version_file           # todolist.yaml
    - ui_version_file                 # ui/pubspec.yaml
    - git_tag                         # v0.1-final

# 發布前檢查項
preflight_checks:
  version_sync:
    enabled: true
    fail_on_error: false              # monorepo 版本不匹配不阻塞
    warn_on_mismatch: true
```

### 優點

| 優點 | 說明 |
|------|------|
| 中央化配置 | 所有版本策略集中定義 |
| 文件化 | 團隊成員清楚瞭解版本規則 |
| 工具友善 | version-release 可讀取此配置 |
| 靈活性 | 可根據專案需求調整策略 |
| 可追蹤性 | 版本策略變更有 git 歷史 |

---

## 版本策略決策樹

```
新版本發布
    |
    v
[Q1] Monorepo 功能里程碑改變？
    |
    +-- 是 --> 更新 L1 monorepo 版本（0.1.0 -> 0.2.0）
    |
    +-- 否 --> 進行 patch 更新（0.1.0 -> 0.1.1）
    |
    v
[Q2] UI 應用有重大功能更新？
    |
    +-- 是 --> L2 UI 版本主版本遞增（1.0.0 -> 2.0.0）
    |          或 build 號遞增（1.0.0+1 -> 1.0.0+2）
    |
    +-- 否 --> L2 UI 版本保持不變
    |
    v
[Q3] Server 有 API 版本變更？
    |
    +-- 是 --> 在下次 monorepo 發布時同步
    |
    +-- 否 --> L3 Server 版本由 monorepo 決定
```

### 日常開發版本判斷

```
修改了程式碼
    |
    v
修改了哪個子專案？
    |
    +-- ui/ --> L2 版本是否需要更新？
    |           |
    |           +-- 新功能/重大修改 --> 更新 L2 版本
    |           +-- Bug 修復/小調整 --> 不更新 L2
    |
    +-- server/ --> L3 無版本欄位，無需更新
    |
    +-- docs/.claude/ --> 不涉及版本更新
    |
    v
L1 monorepo 版本是否需要更新？
    --> 遵循 version-progression.md 的 Q1-Q4 判斷
```

---

## 與 Handoff 機制的相容性

### 同版本 Handoff

| 檢查項 | 相容性 | 說明 |
|--------|--------|------|
| 同版本 handoff | 完全相容 | 0.1.0-W1 -> 0.1.0-W2 正常 |
| Ticket 版本號格式 | 相容 | `{version}-W{wave}-{seq}` 標準格式 |
| Direction 判斷 | 相容 | 字符串匹配，不涉及版本號解析 |

### 跨版本 Handoff

| 檢查項 | 相容性 | 說明 |
|--------|--------|------|
| 跨版本 handoff | 需驗證 | 0.1.0 -> 0.2.0 時的版本過濾邏輯 |
| stale 判斷 | 風險 | 不應將版本差異視為 stale 判斷因素 |

**設計原則**：
- Ticket 版本號永遠基於 L1 monorepo 版本
- L2 UI 版本的獨立性不影響 Ticket 版本策略
- 跨版本 handoff 實現時，不應基於版本號差異自動過濾

---

## 強制規則

| 規則 | 說明 |
|------|------|
| L1 為唯一權威 | Ticket、工作日誌、CHANGELOG 都基於 L1 版本 |
| L2 可獨立升級 | UI 版本不匹配 L1 是預期行為，非錯誤 |
| L3 隱含同步 | Server 無自身版本，由 L1 決定 |
| 版本同步是顯式動作 | 不自動同步版本，需手動或工具輔助 |
| 版本不匹配不阻塞開發 | 開發中允許各層版本獨立迭代 |
| 版本推進遵循 Q1-Q4 | L1 版本推進規則定義在 version-progression.md |

---

## 相關文件

- .claude/pm-rules/version-progression.md - 版本推進決策規則（何時升版）
- .claude/skills/version-release/SKILL.md - 版本發布工具
- docs/work-logs/v0.1.1/tickets/0.1.1-W5-001-monorepo-version-strategy-report.md - 分析報告（來源）

---

**Last Updated**: 2026-03-13
**Version**: 1.0.0 - 初始版本，基於 0.1.1-W5-001 分析報告建立
**Source**: 0.1.1-W5-001 Monorepo 版本管理策略分析
