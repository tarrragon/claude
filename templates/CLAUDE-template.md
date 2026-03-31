# CLAUDE.md

本文件為 Claude Code 在此專案中的開發指導規範。

---

## 1. 專案身份

<!-- 填入專案特定資訊 -->

**專案名稱**: <!-- 例如：Book Overview App -->

**專案目標**: <!-- 簡述專案目的和願景 -->

**專案類型**: <!-- Flutter / Python / Node.js 等 -->

| 項目 | 值 |
|------|------|
| **語言** | <!-- Flutter/Dart, Python, Node.js 等 --> |
| **實作代理人** | <!-- parsley-flutter-developer 等 --> |
| **識別特徵** | <!-- pubspec.yaml, package.json 等 --> |

**啟用的 MCP/Plugin**:

<!-- 列出專案使用的 MCP 伺服器 -->

- dart - Dart/Flutter 開發工具
- serena - 語意程式碼操作
- context7 - 文檔查詢

---

## 2. 核心價值

@.claude/rules/core/quality-baseline.md

---

## 3. 規則系統

@.claude/rules/README.md

---

## 4. Skill 指令

@.claude/rules/guides/skill-index.md

---

## 5. 方法論參考

@.claude/rules/guides/methodology-index.md

---

## 6. 技術選型與架構決策

<!-- 在此記錄專案的技術選型（架構模式、狀態管理、目錄結構等） -->
<!-- 技術知識（怎麼寫好某個框架）放在代理人定義中 -->
<!-- 專案設定（我們選了什麼、為什麼）放在這裡 -->

---

## 7. 專案文件

### 任務追蹤

| 文件 | 用途 |
|------|------|
| `docs/todolist.yaml` | 結構化版本索引（Source of Truth） |
| `docs/work-logs/` | 版本工作日誌 |
| `CHANGELOG.md` | 版本變更記錄 |
| `docs/work-logs/v{version}/tickets/` | Ticket 文件 |

### 專案文件

<!-- 根據專案需要填入 -->

| 文件 | 用途 |
|------|------|
| `docs/app-requirements-spec.md` | 需求規格 |
| `docs/app-use-cases.md` | 用例說明 |
| `docs/test-pyramid-design.md` | 測試設計 |

---

## 8. 里程碑

<!-- 根據專案規劃填入 -->

- v0.0.x: 基礎架構與測試框架
- v0.x.x: 開發階段，逐步實現功能
- v1.0.0: 完整功能，準備上架

---

*專案入口文件 - 詳細規則請參考 .claude/rules/ 目錄*

<!--
使用說明：
1. 將此範本複製到專案根目錄
2. 重命名為 CLAUDE.md
3. 填入專案特定資訊（標記 <!-- --> 的區塊）
4. Section 2-5 使用 @ 引用自動載入通用規則
5. 只需客製化 Section 1/6/7/8
6. 驗證所有連結有效
-->
