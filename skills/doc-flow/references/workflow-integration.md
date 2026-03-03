# 工作流程整合指南

本文件說明如何在開發流程中整合五重文件系統的各項指令。

---

## 開始新版本

```
1. /doc-flow worklog init v0.26.0
   - 建立版本企劃
   - 定義目標和策略

2. /ticket create
   - 建立具體任務 tickets
   - worklog 自動索引 tickets

3. 執行開發
   - 更新 ticket 進度
   - 查詢/新增 error-patterns
```

---

## 執行任務前

```
1. /doc-flow check
   - 確認文件同步狀態

2. /error-pattern query <關鍵字>
   - 查詢既有經驗

3. /ticket track claim <ticket-id>
   - 開始執行任務
```

---

## 完成版本

```
1. /doc-flow worklog update
   - 更新版本狀態為完成

2. /doc-flow changelog preview
   - 預覽 CHANGELOG 更新

3. /version-release
   - 發布版本
   - 自動更新 CHANGELOG
```

---

## 與現有 SKILL 整合

| 現有 SKILL           | 整合方式                        |
| -------------------- | ------------------------------- |
| `/ticket create`     | worklog 自動索引新建的 tickets  |
| `/ticket track`      | 追蹤 ticket 狀態同步到 worklog  |
| `/tech-debt-capture` | 捕獲的 TD 同步到 todolist.yaml  |
| `/version-release`   | 發布時更新 CHANGELOG 和 worklog |
| `/error-pattern`     | 經驗學習系統整合                |

---

## 相關文件

- `.claude/skills/ticket/SKILL.md` - Ticket 系統
- `.claude/skills/error-pattern/SKILL.md` - 錯誤模式系統
- `.claude/skills/version-release/SKILL.md` - 版本發布
