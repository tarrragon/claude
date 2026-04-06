# PC-044: 拆分後檔案命名結構化而非語義化

## 錯誤症狀

檔案拆分/重構後，新檔案命名為「原檔名-部分名」（如 `decision-tree-completion.md`），而非以內容語義命名。讀者無法從檔名直覺判斷裡面有什麼，必須打開才知道。

## 根因分析

**直接原因**：拆分時的思維是「從哪裡拆出來的」（結構化），而非「讀者要找什麼」（語義化）。

**深層原因**：
1. 拆分是機械操作，容易用原檔名加後綴的方式命名
2. 缺乏「站在讀者角度」的命名檢查——讀者不關心檔案從哪裡來，只關心裡面有什麼
3. DDD 拆分的目標是降低認知負擔和方便定位，但結構化命名反而增加了定位成本

## 影響

| 影響 | 說明 |
|------|------|
| 增加認知負擔 | 讀者需要記住「completion 在 decision-tree-completion.md 裡」的映射 |
| 違反拆分目的 | 拆分是為了更方便找到，結構化命名反而更難找 |
| 路由指向不直觀 | `> 詳見：decision-tree-completion.md` 不如 `> 詳見：completion-checkpoint-rules.md` 清楚 |

## 正確做法

命名以「讀者要找什麼」為導向：

| 結構化命名（錯誤） | 語義化命名（正確） | 讀者搜尋意圖 |
|------------------|-----------------|------------|
| `decision-tree-execution.md` | `execution-discovery-rules.md` | 「執行中發現額外問題怎麼辦」 |
| `decision-tree-completion.md` | `completion-checkpoint-rules.md` | 「完成後的 Checkpoint 流程」 |
| `decision-tree-agents.md` | `agent-dispatch-enforcement.md` | 「代理人派發優先級」 |

## 預防措施

| 措施 | 類型 | 說明 |
|------|------|------|
| 拆分後命名自檢 | 檢查清單 | 問自己：「讀者找 X 會直覺看這個檔名嗎？」 |
| 記錄到 memory | 反饋記憶 | 已記錄 feedback_file_naming_semantic.md |

## 發現來源

- Ticket: W3-007.1 decision-tree 拆分
- 場景：拆分後命名為 decision-tree-{part}.md，用戶質疑檔名不符合內容語義
- 日期：2026-04-06

---

**Created**: 2026-04-06
**Version**: 1.0.0
