# 敏捷重構方法論

## 核心概念

主線程統籌分派、子代理人專責執行的協作模式。

**三大原則**：
1. 主線程只負責分派，不執行程式碼
2. 任務符合 Atomic Ticket 原則（一個 Action + 一個 Target）
3. 100% 測試通過率是最低要求

## 執行步驟

### 主線程流程

1. 檢查主版本工作日誌 (`vX.Y.0-main.md`)
2. 分派任務給子代理人
3. 等待回報，不親自執行
4. 處理升級請求（呼叫 PM 代理人）
5. 重構代理人驗證通過後，文件代理人更新日誌

### 子代理人流程

1. 確認任務目標和完成標準
2. 評估規模（過大則向上回報）
3. 執行任務
4. 回報結果
5. 配合重構代理人檢查

## Agent 角色

| 角色 | 代理人 | 職責 |
|------|--------|------|
| 主線程 | rosemary-project-manager | 分派任務、監控進度 |
| Phase 1 | lavender-interface-designer | 功能設計 |
| Phase 2 | sage-test-architect | 測試設計 |
| Phase 3a | pepper-test-implementer | 語言無關策略 |
| Phase 3b | parsley-flutter-developer | Flutter 實作 |
| Phase 4 | cinnamon-refactor-owl | 重構執行 |
| 文件 | memory-network-builder | 工作日誌維護 |
| 格式化 | mint-format-specialist | 程式碼格式化 |

## 五重文件原則

| 文件 | 核心問題 | 更新時機 |
|------|---------|----------|
| CHANGELOG.md | "這個版本做了什麼改變？" | 版本發布時 |
| todolist.yaml | "還有哪些問題需要處理？" | 問題發現/解決時 |
| worklog | "這個版本要達成什麼目標？" | 版本開始/結束時 |
| ticket | "這個任務的執行細節是什麼？" | 任務執行中 |
| error-patterns | "之前遇過類似問題嗎？" | 執行前後 |

**核心原則**：
- 職責單一化：每個文件只回答一個核心問題
- 細節下沉：執行細節 → ticket，大方向 → worklog
- 禁用 emoji：所有五重文件禁止使用 emoji

**完整規範**：[五重文件系統方法論](./five-document-system-methodology.md)

## 檢查清單

### 任務分派前（主線程）

- [ ] 任務目標明確
- [ ] 完成標準可測量
- [ ] 參考文件完整（UseCase、流程圖、依賴類別）
- [ ] 影響範圍已評估

### 任務完成後

- [ ] 測試 100% 通過
- [ ] 重構代理人驗證通過
- [ ] work-log 已更新
- [ ] todolist 狀態同步

### 階段驗證（強制）

- [ ] `flutter analyze` 無 error
- [ ] `dart test` 100% 通過
- [ ] 無相對路徑 import
- [ ] 檔案位置符合 Clean Architecture

## 技術債務處理責任分工

### Phase 4 技術債務處理流程

| 步驟 | 責任代理人 | 產出 |
|------|-----------|------|
| 識別技術債務 | cinnamon-refactor-owl | 技術債務清單（工作日誌） |
| 記錄標準表格 | cinnamon-refactor-owl | 標準格式表格 |
| 執行 `/tech-debt-capture` | cinnamon-refactor-owl | Ticket 檔案 |
| 驗證 Ticket 建立 | rosemary-project-manager | 確認 todolist 更新 |
| 排程處理 | rosemary-project-manager | 目標版本分配 |

### cinnamon-refactor-owl 的技術債務責任

1. **識別責任**：在重構評估過程中識別所有技術債務
2. **記錄責任**：使用標準表格格式記錄到工作日誌
3. **開票責任**：執行 `/tech-debt-capture` 建立 Ticket
4. **確認責任**：確認 Ticket 成功建立後才能完成 Phase 4

### 技術債務遺漏的補救流程

如果在版本提交後發現遺漏的技術債務：

1. 立即建立 Ticket（使用 `/ticket create`）
2. 在 Ticket 中標註「補救」來源
3. 通知 PM 代理人進行排程

## Reference

### 相關方法論

- [Atomic Ticket 方法論](./atomic-ticket-methodology.md) - 單一職責設計
- [Ticket 生命週期管理](./ticket-lifecycle-management-methodology.md) - 狀態流轉
- [TDD 協作流程](../tdd-collaboration-flow.md) - 四階段詳細說明