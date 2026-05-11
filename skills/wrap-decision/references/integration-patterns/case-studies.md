# WRAP Case Study Pattern

案例庫模式的責任是把實戰事件轉成可重用的決策教訓。案例不依賴原專案背景也要能被理解，重點是抽出觸發訊號、錯誤判斷、WRAP 介入點與後續防護。

---

## 收錄欄位

| 欄位                     | 責任                            |
| ------------------------ | ------------------------------- |
| 案例標題（Case title）   | 一句話說明事件                  |
| Situation                | 當時要完成的目標                |
| Trigger                  | 為什麼需要 WRAP                 |
| 錯誤路徑（Faulty path）  | 原本自動駕駛的路徑              |
| WRAP observation         | WRAP 揭露了什麼選項、證據或成本 |
| 改善路徑（Better path）  | 調整後的做法                    |
| 防護欄（Guardrail）      | 後續新增的檢查、規則或提醒      |
| 重用訊號（Reuse signal） | 未來遇到什麼情境要重讀本案例    |

---

## 抽象化規則

1. 移除專案私有路徑、內部編號與人名。
2. 保留決策結構：目標、選項、證據、成本、回退。
3. 把工具名稱改成中性角色，例如 task runner、rule store、automation hook。
4. 若案例依賴特定工具，改寫成「某 CLI」「某任務系統」「某文件產生流程」。
5. 每個案例最後要有可 grep 的 reuse signal。

---

## 案例模板

```markdown
## {case-title}

**Situation**：...
**Trigger**：...
**錯誤路徑（Faulty path）**：...
**WRAP observation**：...
**改善路徑（Better path）**：...
**防護欄（Guardrail）**：...
**重用訊號（Reuse signal）**：...
```

---

## 常見案例類型

| 類型                                | 典型教訓                     |
| ----------------------------------- | ---------------------------- |
| 過早收斂（Premature convergence）   | 過早相信第一個根因           |
| 偽擴增選項（Pseudo widen）          | 多個選項仍指向同一假設       |
| 來源幻覺（Source hallucination）    | 清單項目未逐項核對來源       |
| 工具化偏誤（Toolification）         | 把新增工具當成預設答案       |
| 家長主義悖論（Paternalism paradox） | 為保護使用者而過度限制使用者 |
| 絆腳索疲乏（Tripwire fatigue）      | 提醒太頻繁導致被忽略         |

---

**Last Updated**: 2026-04-30
**Version**: 2.0.0 — 可攜案例庫模板。
