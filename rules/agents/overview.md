# 代理人系統總覽

本文件定義所有代理人的職責矩陣、優先級順序和升級規則。

> **核心原則**：每個代理人有明確的職責邊界，超出範圍必須升級或轉派。

---

## 職責矩陣

| 代理人 | 核心職責 | 觸發條件 | 不負責 |
|--------|----------|----------|--------|
| rosemary-project-manager | 任務分派、驗收、決策 | 所有任務入口 | 程式實作 |
| [incident-responder](incident-responder.md) | 問題分析、Ticket 開設 | 錯誤/失敗發生 | 問題修復 |
| [security-reviewer](security-reviewer.md) | 安全漏洞偵測、修復建議 | 認證/輸入/API/敏感資料 | 漏洞修復實作 |
| [system-analyst](system-analyst.md) | TDD 前置審查、系統一致性 | 新功能、架構變更 | 單一功能設計 |
| [system-designer](system-designer.md) | UI 系統規範、頁面結構 | UI 規範需求 | 具體 Widget 實作 |
| [system-engineer](system-engineer.md) | 環境建置、編譯問題 | 環境/編譯錯誤 | 業務邏輯 |
| [data-administrator](data-administrator.md) | 資料模型、儲存策略 | 資料相關需求 | CRUD 實作 |
| [memory-network-builder](memory-network-builder.md) | 知識記憶、經驗沉澱 | 決策/學習/經驗記錄 | 程式實作 |
| [lavender-interface-designer](lavender-interface-designer.md) | Phase 1 功能設計 | TDD Phase 1 | 系統審查 |
| [sage-test-architect](sage-test-architect.md) | Phase 2 測試設計 | TDD Phase 2 | 程式實作 |
| [pepper-test-implementer](pepper-test-implementer.md) | Phase 3a 策略規劃 | TDD Phase 3a | 程式實作 |
| [parsley-flutter-developer](parsley-flutter-developer.md) | Phase 3b Flutter 實作 | TDD Phase 3b | 環境問題 |
| [cinnamon-refactor-owl](cinnamon-refactor-owl.md) | Phase 4 重構優化 | TDD Phase 4 | 新功能開發 |

---

## 觸發優先級

### 優先級順序

```
Level 1: incident-responder（錯誤/失敗最高優先）
Level 2: system-analyst（架構審查）
Level 3: security-reviewer（安全審查）
Level 4: 其他專業代理人（DBA, SE, SD, ginger, MNB 等）
Level 5: TDD 階段代理人（lavender, sage, pepper, parsley, cinnamon）
```

### 多條件觸發處理規則

| 觸發組合 | 處理方式 | 理由 |
|---------|---------|------|
| 錯誤 + 任何 | incident-responder 先處理 | 錯誤必須優先排除 |
| SA + security | SA 先審查架構 | 安全審查依賴架構設計 |
| SA + 專業代理人 | SA 先分解需求 | 需先確定範圍 |
| 多個專業代理人 | SA 協調或按需求分解為多 Ticket | 避免職責混亂 |
| security + 專業代理人 | security 先審查安全性 | 安全問題不可延後 |

### 並行 vs 序列判斷

| 情況 | 處理方式 | 範例 |
|------|---------|------|
| 同層級且無依賴 | 可並行 | DBA 設計 + SE 環境配置 |
| 有輸出依賴 | 必須序列 | SA 審查 → Phase 1 設計 |
| 有輸入依賴 | 必須序列 | security 審查 → 修復實作 |
| 同一檔案修改 | 必須序列 | 避免衝突 |

---

## 派發決策樹

```
任務進入
    |
    +-- 錯誤/失敗? --> incident-responder (強制)
    |                     |
    |                     +-- 安全相關? --> security-reviewer
    |
    +-- 涉及認證/授權/API/敏感資料? --> security-reviewer (強制)
    |
    +-- 新功能/架構變更? --> system-analyst
    |
    +-- UI 規範需求? --> system-designer
    |
    +-- 環境/編譯問題? --> system-engineer
    |
    +-- 資料設計需求? --> data-administrator
    |
    +-- 需記錄決策/經驗? --> memory-network-builder
    |
    +-- TDD 階段任務?
        +-- Phase 1 --> lavender-interface-designer
        +-- Phase 2 --> sage-test-architect
        +-- Phase 3a --> pepper-test-implementer
        +-- Phase 3b --> parsley-flutter-developer
        +-- Phase 3b 完成後 --> security-reviewer (建議)
        +-- Phase 4 --> cinnamon-refactor-owl
```

---

## 派發驗證機制

### Task 派發驗證

所有使用 Task 工具的派發必須通過 Hook 系統驗證：

| 驗證項目 | 驗證內容 | 失敗處理 |
|---------|---------|---------|
| Ticket 引用 | prompt 中必須包含有效的 Ticket ID | 阻止派發 |
| Ticket 存在 | 引用的 Ticket 必須存在於系統中 | 阻止派發 |
| 決策樹欄位 | Ticket 必須包含 decision_tree_path 欄位 | 阻止派發 |

### Ticket ID 引用格式

派發時，prompt 中必須包含以下任一格式的 Ticket 引用：

```
Ticket: {id}
#Ticket-{id}
[Ticket {id}]
```

**範例**：
```
Ticket: 0.30.1-W1-001

## 任務指派
...
```

### 驗證失敗處理

當驗證失敗時，Hook 系統會：
1. 輸出 exit code 2（阻止執行）
2. 輸出錯誤訊息說明問題
3. 提供建議的修正操作

**常見錯誤訊息**：
- 「派發任務必須引用有效的 Ticket ID」
- 「找不到 Ticket: {id}」
- 「Ticket {id} 缺少決策樹欄位，為無效 Ticket」

---

## 升級規則

### 強制升級條件

代理人遇到以下情況**必須升級到 PM**：

#### 認知負擔過重

| 指標 | 閾值 | 行動 |
|------|------|------|
| 需追蹤概念數 | > 7 個 | 升級：任務需要拆分 |
| 需理解檔案數 | > 5 個 | 升級：可能跨越職責邊界 |
| 需追蹤呼叫層級 | > 3 層 | 升級：架構複雜度過高 |
| 無法 5 分鐘理解 | 是 | 升級：需要進一步分析 |

#### 職責邊界問題

| 情況 | 行動 |
|------|------|
| 跨架構層（UI + Controller + Domain） | 升級：需要多代理人協作 |
| 跨模組（3+ 個獨立模組） | 升級：影響範圍過大 |
| 不確定性（無法清晰描述目標） | 升級：需要進一步分析 |
| 超出專業 | 升級：需要派發正確代理人 |

#### 技術決策問題

| 情況 | 行動 |
|------|------|
| 多方案選擇（2+ 可行方案） | 升級：需要 PM 或 SA 決策 |
| 架構影響 | 升級：需要 SA 審查 |
| 規範不明 | 升級：需要補充規範 |

### 自我檢查問題

代理人在開始任務前**必須**問自己：

1. **我需要同時記住多少個概念？** (< 5: 繼續, 5-7: 謹慎, > 7: 升級)
2. **我需要閱讀多少個檔案？** (< 3: 繼續, 3-5: 謹慎, > 5: 升級)
3. **我能用一句話說明這個任務嗎？** (可以: 繼續, 不行: 升級)
4. **這個任務屬於我的職責範圍嗎？** (是: 繼續, 不是: 升級)
5. **我需要修改幾個架構層？** (1: 繼續, 2: 謹慎, 3+: 升級)

---

## 跨代理人協作規則

### 規則 1：單一責任原則

每個代理人只處理其職責範圍內的任務，超出範圍的任務必須升級或轉派。

### 規則 2：禁止越權

| 代理人類型 | 禁止行為 |
|-----------|---------|
| 管理層 | 直接修改程式碼 |
| 分析層 | 直接修復問題 |
| 執行層 | 自行決定派發 |

### 規則 3：升級機制

當代理人遇到超出職責、無法完成、需要決策時，必須升級到 rosemary-project-manager。

### 規則 4：文件傳遞

代理人之間的任務交接必須透過：
- Ticket（正式任務）
- 工作日誌（進度記錄）
- Incident Report（問題報告）

---

## 常見誤派情況

| 誤派情況 | 正確派發 | 識別方法 |
|---------|---------|---------|
| parsley 處理環境問題 | system-engineer | 錯誤訊息包含 "SDK", "dependency" |
| parsley 處理資料設計 | data-administrator | 任務涉及資料模型規劃 |
| lavender 處理系統審查 | system-analyst | 影響 3+ 模組 |
| sage 處理程式實作 | parsley-flutter-developer | 任務需要撰寫程式碼 |

---

## 升級報告格式

```markdown
## 升級請求報告

### 任務資訊
- **Ticket ID**: {ID}
- **任務描述**: {描述}
- **代理人**: {代理人名稱}

### 升級原因
| 檢查項目 | 結果 | 說明 |
|---------|------|------|
| 概念數量 | {數量} | {超過/未超過} 閾值 |
| 檔案數量 | {數量} | {超過/未超過} 閾值 |
| 職責匹配 | {是/否} | {說明} |

### 建議行動
- [ ] 任務需要拆分
- [ ] 需要其他代理人協作
- [ ] 需要更多資訊
- [ ] 需要架構決策
```

---

## 相關文件

- [decision-tree](../core/decision-tree.md) - 主線程決策樹
- [cognitive-load](../core/cognitive-load.md) - 認知負擔設計原則

---

**Last Updated**: 2026-01-27
**Version**: 1.1.0

**Change Log**:
- v1.1.0 (2026-01-27): 新增派發驗證機制章節
  - 加入 Task 派發驗證規則
  - 定義 Ticket ID 引用格式
  - 說明驗證失敗處理流程
- v1.0.0 (2026-01-23): 初始版本
