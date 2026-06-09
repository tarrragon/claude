---
name: error-pattern
description: "錯誤模式知識庫管理工具。Use for: (1) 查詢既有錯誤經驗和防護措施 (query), (2) 記錄新發現的錯誤模式和教訓 (add), (3) Ticket 開始前查詢歷史問題避免再犯, (4) 系統化管理錯誤學習經驗。Use when: user mentions error pattern, 錯誤模式, 教訓, 經驗記錄, 學習經驗, 防護措施, 錯誤紀錄, or needs to avoid recurring issues."
---

# error-pattern SKILL

錯誤模式知識庫管理工具。查詢既有錯誤經驗，記錄新發現的錯誤模式。

## 指令

### `/error-pattern query <關鍵字>`

查詢既有錯誤模式經驗。

**使用時機**：每個 Ticket 開始前

**執行流程**：
1. 搜尋 `.claude/error-patterns/` 目錄下所有 `.md` 檔案
2. 使用關鍵字匹配錯誤症狀、根因、解決方案
3. 返回匹配的錯誤模式清單

**輸出格式**：
```
找到 N 個相關錯誤模式：

1. [編號] 錯誤名稱
   - 症狀：簡短描述
   - 解決方案：簡短描述
   - 相關 Ticket：TICKET-XXX

（無匹配時）
未找到相關錯誤模式。這可能是新發現的問題，請使用 /error-pattern add 記錄。
```

### `/error-pattern add`

互動式記錄新發現的錯誤模式。

**使用時機**：發現新問題時

**執行流程**：

1. **選擇錯誤類別**
   - di-registration: DI 註冊相關
   - widget-finder: Widget Finder 相關
   - async-resource: 異步資源相關
   - type-mismatch: 類型不匹配
   - hook-schema: Hook Schema 相關
   - code-quality: 程式碼品質相關
   - process-compliance: 流程合規相關
   - other: 其他（需要新建分類）

2. **輸入症狀描述**
   - 錯誤訊息特徵
   - 發生位置類型

3. **分析根因**
   - 為什麼會發生
   - 行為模式分析

4. **記錄解決方案**
   - 具體修復步驟
   - 程式碼範例（如適用）

5. **提出預防措施**
   - 如何避免再次發生
   - 相關 Hook 或檢查機制建議

6. **關聯 Ticket**
   - 輸入相關 Ticket 編號

7. **自動分配來源前綴 ID**（跨專案共享框架必用）
   - 呼叫 allocator 取得下一個 `<CATEGORY>-<PROJ>-NNN`：
     ```python
     import sys; sys.path.insert(0, ".claude/skills/error-pattern/lib")
     from allocator import identify_project_code, allocate_pattern_id
     proj = identify_project_code(
         ".claude/error-patterns/_project-registry.yaml",
         "<git toplevel>",  # git rev-parse --show-toplevel
     )
     pattern_id = allocate_pattern_id("<CATEGORY>", ".claude", proj)
     ```
   - allocator 自動：以 git toplevel basename 自我識別專案代號 → 掃該專案前綴空間
     取最大號 +1（flat 凍結 base 不參與遞增）。
   - **禁止**手動指定 flat `<CATEGORY>-NNN`（凍結 base 不再新增，見編號章節）。

**輸出**：
- 在對應的分類檔案中以 `<CATEGORY>-<PROJ>-NNN-<slug>.md` 命名新增錯誤記錄
- 更新 README.md 統計資訊

### `/error-pattern list`

列出所有已記錄的錯誤模式。

**輸出格式**：
```
錯誤模式知識庫統計：

DI 註冊 (3)
├─ [DI-001] 服務未註冊到 ServiceLocator
├─ [DI-002] 依賴服務尚未初始化
└─ [DI-003] 循環依賴

Widget Finder (2)
├─ [WF-001] 多重匹配
└─ [WF-002] 找不到元素

...
```

---

## 錯誤編號規則

### Category 前綴（依目錄）

| 類別目錄 | 前綴 | 凍結 base 範例 |
|---------|------|---------------|
| architecture | ARCH | ARCH-001 |
| code-quality | CQ | CQ-001 |
| documentation | DOC | DOC-001 |
| implementation | IMP | IMP-001 |
| process | PROC | PROC-001 |
| process-compliance | PC | PC-001 |
| test | TEST | TEST-001 |

### 來源前綴（跨專案共享框架必用）

本框架透過共享 repo 同步至多個專案。為防多專案併發分配同號碰撞，**新增任何
category 的 error-pattern 一律使用來源前綴格式**：

```
<CATEGORY>-<PROJ>-NNN     例：PC-V1-001、IMP-APP-003、ARCH-SCLK-002
```

- 既有 flat `<CATEGORY>-NNN` 為**凍結 canonical base**，原樣保留、不再新增 flat 號。
- `<PROJ>` 取自 `.claude/error-patterns/_project-registry.yaml`（tooling 以 git
  toplevel basename 對應 `dir` 欄自動取得）。
- 完整規則（凍結語意、協議字串豁免、canonical 升格、dedup、rejected options）見
  `.claude/methodologies/error-pattern-numbering-methodology.md`。

> **單一專案使用本框架時**：無碰撞風險，可沿用 flat `<CATEGORY>-NNN`。來源前綴僅在
> 多專案共享同步情境強制。

---

## 整合到工作流程

### Ticket 模板整合

在 Ticket 中加入：
```markdown
## 參考既有錯誤模式
<!-- 執行 /error-pattern query 後填寫 -->
- [ ] 已查詢既有模式
- 匹配模式：[編號] 或「無匹配 - 新發現模式」
```

### Worklog 整合

在工作日誌中記錄：
```markdown
## 錯誤模式學習
- 發現新模式：[編號] 錯誤名稱
- 參考既有模式：[編號] 錯誤名稱
```

---

## 檔案位置

| 檔案 | 用途 |
|------|------|
| `.claude/error-patterns/README.md` | 知識庫索引 |
| `.claude/error-patterns/{category}/*.md` | 各分類錯誤模式檔案 |

---

**Last Updated**: 2026-03-02
**Version**: 1.0.0
