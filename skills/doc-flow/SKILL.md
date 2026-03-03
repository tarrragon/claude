---
name: doc-flow
description: "Manages project documentation system including CHANGELOG, worklog, tickets, error-patterns, and todolist. Use for: (1) worklog initialization and updates, (2) todolist management, (3) version collaboration workflows, (4) documentation consistency checks"
---

# Doc-Flow SKILL

五重文件管理系統 - 專案文件運作的核心控制中心

---

## 核心理念

每個文件有單一職責，工程師只需讀對應文件就能理解全部。

---

## 重要規範：禁用 Emoji

所有五重文件系統中的文件禁止使用 emoji。

原因：
1. 交接文件需要專業、正式
2. emoji 在某些環境可能顯示不正確
3. Claude Code CLI 處理 markdown 表格中的 emoji 可能導致 Rust panic

適用範圍：CHANGELOG.md、todolist.yaml、worklog、ticket、error-patterns

---

## 五重文件系統

### 職責定義

| 文件               | 核心問題                     | 職責定位                          | 更新時機      |
| ------------------ | ---------------------------- | --------------------------------- | ------------- |
| **CHANGELOG**      | 這個版本做了什麼改變？       | 版本推進變化（給工程師看）        | 版本發布時    |
| **todolist.yaml**  | 還有哪些問題需要處理？       | 結構化版本索引（Source of Truth） | 持續更新      |
| **worklog**        | 這個版本要達成什麼目標？     | 版本企劃（大方向 + 策略）         | 版本開始/結束 |
| **ticket**         | 這個任務的執行細節是什麼？   | 任務執行歷程（細節記錄）          | 執行過程中    |
| **error-patterns** | 之前遇過類似問題嗎？         | 經驗學習（查詢/更新）             | 執行前後      |

### 關係圖

```
                    ┌─────────────────┐
                    │   CHANGELOG     │
                    │  (版本間差異)    │
                    └────────┬────────┘
                             │
                    ┌────────┴────────┐
                    │    worklog      │
                    │   (大方向)       │
                    └────────┬────────┘
                             │
            ┌────────────────┼────────────────┐
            │                │                │
     ┌──────┴──────┐  ┌──────┴──────┐  ┌──────┴──────┐
     │   ticket    │  │todolist.yaml│  │error-patterns│
     │ (執行細節)   │  │ (版本索引)   │  │ (經驗學習)   │
     └─────────────┘  └─────────────┘  └─────────────┘
```

---

## 可用指令

### 狀態查詢

```bash
/doc-flow status                    # 查看五重文件系統整體狀態
/doc-flow check                     # 檢查文件一致性
```

### Worklog 管理

```bash
/doc-flow worklog init [version]    # 初始化新版本 worklog
/doc-flow worklog read [version]    # 讀取指定版本 worklog 摘要
/doc-flow worklog update            # 更新當前版本 worklog 狀態
```

### Todo 管理

```bash
/doc-flow todo list                 # 列出所有待處理問題
/doc-flow todo add [description]    # 新增待處理問題
/doc-flow todo resolve [id]         # 標記問題已解決（移除）
/doc-flow todo defer [id] [version] # 延遲到指定版本
```

### Changelog 管理

```bash
/doc-flow changelog preview         # 預覽即將發布的變更
/doc-flow changelog update          # 版本發布時更新
```

### Error Pattern 整合

```bash
/doc-flow learn                     # 觸發錯誤模式學習流程
```

---

## 檔案位置

```
docs/
├── CHANGELOG.md                     # 版本變更記錄
├── todolist.yaml                    # 結構化版本索引（Source of Truth）
├── error-patterns/                  # 錯誤模式知識庫
│   ├── README.md
│   └── categories/
└── work-logs/
    └── v{VERSION}/
        ├── v{VERSION}-main.md       # 版本企劃（大方向）
        └── tickets/                 # 執行細節
            ├── {version}-W1-001.md
            └── ...
```

---

## 設計原則

### 1. 職責單一化

每個文件回答一個核心問題，不重疊、不混淆。

### 2. 自給自足原則

讀 worklog 就能理解版本全貌，不需要額外 context。

### 3. 細節下沉原則

執行細節 - Ticket，大方向 - Worklog

### 4. 經驗累積原則

每次修復都查詢/更新 error-patterns，持續改善工作模式。

---

## 相關文件

- 職責詳解：`references/document-responsibilities.md`
- 工作流程整合：`references/workflow-integration.md`
- 方法論：`.claude/methodologies/five-document-system-methodology.md`
- 規則：`.claude/rules/core/document-system.md`
- Worklog 模板：`.claude/skills/doc-flow/templates/worklog.md.template`
- Todolist 模板：`.claude/skills/doc-flow/templates/todolist.yaml.template`
