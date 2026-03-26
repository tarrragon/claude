# 五重文件系統 - 職責詳解

本文件提供五重文件系統各文件的詳細說明。

---

## 1. CHANGELOG.md

**核心問題**：這個版本做了什麼改變？

**內容範圍**：
- 新增功能
- 架構變更
- Bug 修復
- 重大決策

**寫作風格**：
- 給其他工程師閱讀
- 簡潔、技術導向
- 按版本倒序排列

**更新時機**：版本發布時（由 `/version-release` 觸發）

**禁止內容**：
- 過度詳細的實作細節
- 開發過程中的嘗試錯誤
- 用戶不關心的內部變更

---

## 2. todolist.yaml（結構化版本索引）

**核心問題**：還有哪些問題需要處理？版本狀態是什麼？

**檔案格式**：YAML（取代舊版 todolist.yaml）

**內容範圍**：
- 版本對應表（status: active/planned/completed/paused）
- UC-Oriented 開發計畫
- 技術債務追蹤
- 品質標準和參考文件

**寫作風格**：
- YAML 結構化格式，機器可解析
- 版本索引（什麼版本、什麼狀態、在哪裡）
- 版本細節下沉到 worklog

**關鍵規則**：
- `status: active` 決定當前活躍版本（`get_current_version()` 的 Source of Truth）
- 已解決的版本標記為 `status: completed`
- 版本細節（Wave 進度、品質指標等）在 worklog 中追蹤
- 格式為 `docs/todolist.yaml`

**範本**：`.claude/skills/doc-flow/templates/todolist.yaml.template`

---

## 3. worklog（版本企劃）

**核心問題**：這個版本要達成什麼目標？怎麼規劃？

**內容範圍**：
- 版本目標（一句話描述）
- 前情提要（為什麼需要這個版本）
- 執行策略（Step-by-Step）
- Ticket 總覽（連結到細節）
- Context 還原指引

**寫作風格**：
- 大方向、高層次
- 任何工程師不需其他 context 就能理解
- 執行細節下沉到 ticket

**更新時機**：
- 版本開始時建立
- 版本完成時更新狀態

**禁止內容**：
- 具體的程式碼變更
- 詳細的執行日誌
- 問題的完整分析過程（這些屬於 ticket）

---

## 4. ticket（任務執行細節）

**核心問題**：這個任務的完整執行歷程是什麼？

**內容範圍**：
- 任務來源和目標
- 5W1H 設計
- 問題分析
- 解決方案
- 測試結果
- 執行進度

**寫作風格**：
- 詳細、完整
- 記錄所有決策和變更
- 直到任務完成

**更新時機**：
- 任務建立時（/ticket create）
- 執行過程中持續更新
- 完成時標記狀態

**格式**：Markdown + YAML Frontmatter

---

## 5. error-patterns（經驗學習）

**核心問題**：之前遇過類似問題嗎？

**內容範圍**：
- 錯誤症狀
- 根因分析
- 解決方案
- 預防措施
- 相關 Ticket

**寫作風格**：
- 模式化、可查詢
- 按類型分類
- 提供具體範例

**更新時機**：
- 執行 ticket 前查詢
- 發現新模式時新增
- 修復後補充預防措施

---

## 相關文件

- `.claude/methodologies/five-document-system-methodology.md` - 完整方法論
- `.claude/references/document-system.md` - 文件系統規則
