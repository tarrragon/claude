# 查詢 vs 研究判斷情境範例

本檔案包含詳細的情境分析範例，供深入理解查詢 vs 研究的判斷邏輯。

> 快速決策指南：@.claude/rules/guides/query-vs-research.md

---

## 情境 1：查詢 Ticket 進度

**用戶詢問**：「進度如何？」或「0.31.0-W4-010 完成了嗎？」

**判斷**：內部查詢

**原因**：
- 資料來源：Ticket 系統（專案內部）
- 工作量：< 1 分鐘
- 工具：/ticket track

**執行**：
```bash
/ticket track summary        # 全部進度
/ticket track query 0.31.0-W4-010  # 特定 Ticket
```

---

## 情境 2：查詢待辦項目

**用戶詢問**：「還有哪些問題需要處理？」

**判斷**：內部查詢

**原因**：
- 資料來源：docs/todolist.yaml（專案內部）
- 工作量：< 2 分鐘
- 工具：Read

**執行**：`Read file_path="docs/todolist.yaml"`

---

## 情境 3：查詢版本進度

**用戶詢問**：「v0.31.0 的進度如何？」

**判斷**：內部查詢

**原因**：
- 資料來源：工作日誌（專案內部）
- 工作量：< 3 分鐘
- 工具：Read

**執行**：`Read file_path="docs/work-logs/v0.31.0/README.md"`

---

## 情境 4：評估外部工具或套件

**用戶詢問**：「應該用哪個 Flutter 套件做 X？」或「對比 A 和 B 工具哪個更好？」

**判斷**：外部資源研究

**原因**：
- 資料來源：GitHub、官方文檔、npm registry 等外部資源
- 工作量：>= 5 分鐘（需要研究多個選項）
- 分析深度：需要比較評估

**執行**：
派發 oregano-data-miner 建立 Ticket：
- 題目：研究 Flutter X 功能的最佳套件方案
- 需求：比較 A、B、C 三個套件的優缺點
- 交付物：評估報告 + 建議

---

## 情境 5：查詢 GitHub 原始碼實作細節

**用戶詢問**：「Dart package X 如何實作的？」或「我想了解 Y 套件的原始碼」

**判斷**：外部資源研究

**原因**：
- 資料來源：GitHub 外部倉庫
- 工作量：>= 5 分鐘（需要深入分析原始碼）
- 分析深度：需要讀程式碼、理解設計

**執行**：
派發 oregano-data-miner 建立 Ticket：
- 題目：研究 package X 的實作原理
- 需求：分析關鍵函式和設計模式
- 交付物：分析報告 + 參考連結

---

## 情境 6：查詢官方文檔或 API 規格

**用戶詢問**：「Flutter X API 的詳細用法」或「Dart Y 的官方規格」

**判斷**：工作量決定
- 快速查閱（< 5 分鐘）→ 內部查詢
- 深度研究（>= 5 分鐘）→ 派發代理人

**快速查閱**：`Read file_path="docs/app-requirements-spec.md"`

**深度研究**：派發 oregano-data-miner 建立 Ticket

---

## 情境 7：查詢規則或文件系統

**用戶詢問**：「Skip-gate 規則是什麼？」或「五重文件系統怎麼用？」

**判斷**：內部查詢

**原因**：
- 資料來源：專案規則文件（專案內部）
- 工作量：< 3 分鐘
- 工具：Read/Grep

**執行**：
```bash
Read file_path=".claude/rules/forbidden/skip-gate.md"
Grep pattern="五重文件系統" path=".claude/rules"
```

---

## 情境 8：技術方案選型

**用戶詢問**：「應該用 X 架構方案還是 Y 架構方案？」

**判斷**：
- 內部已有相似案例 → 內部查詢：`Grep pattern="架構方案|選型決策" path=".claude"`
- 需要研究外部最佳實踐 → 派發 oregano-data-miner

---

**Last Updated**: 2026-02-06
**Version**: 1.0.0
**Source**: Extracted from query-vs-research.md (0.31.0-W9-007)
