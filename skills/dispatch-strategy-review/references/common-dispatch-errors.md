# 常見派發錯誤和修正

派發策略檢討工具識別和修正的常見派發錯誤參考。

## 錯誤 1: 代理人選擇錯誤

代理人無法勝任派發的工作，導致任務失敗或效率低下。

| 錯誤派發 | 正確派發 | 識別特徵 |
|---------|---------|---------|
| parsley → Hook 開發 | basil-hook-architect | 任務涉及 Hook 腳本 |
| parsley → 文件整合 | thyme-documentation-integrator | 任務涉及方法論整合 |
| parsley → 格式化 | mint-format-specialist | 任務涉及程式碼格式化 |
| parsley → 環境問題 | sumac-system-engineer | 錯誤為依賴/環境問題 |

**預防措施**:
1. 根據任務特性確認代理人能力是否覆蓋
2. 使用決策樹的代理人派發規則
3. 查閱 `.claude/agents/` 中的代理人定義

## 錯誤 2: 任務定義不清

任務描述過於模糊，代理人無法理解確切需求。

**問題特徵**:
- 任務無明確動詞和目標（如「改進系統」而非「修復 Hook 啟動延遲」）
- 缺少必要的背景資訊
- 驗收條件模糊或不可量化
- 未標記依賴關係

**修正方式**:
- 使用 Atomic Ticket 原則：「一個 Action + 一個 Target」
- 確保任務標題包含清晰的動詞（create, fix, refactor, analyze）
- 補充背景和上下文
- 定義具體的驗收條件

## 錯誤 3: 前置條件缺失

派發時未檢查必要的前置工作或依賴條件。

**問題特徵**:
- 派發任務所依賴的 Ticket 仍在進行中
- 需要的資料或 SA 前置審查未完成
- 環境或工具準備不足

**修正方式**:
- 增加 SA 前置審查，確保系統一致性
- 使用 Ticket 的 `blockedBy` 欄位明確標記依賴
- 派發前驗證 Level 2 前置條件（參見 verification-framework.md）
- 建立派發檢查清單

---

**Last Updated**: 2026-03-02
**Source**: dispatch-strategy-review SKILL 精簡提取
