# PC-MON-001: 工具防護落地於可繞過的執行點導致復發

**類別**: process-compliance
**發現日期**: 2026-07-02
**相關 Ticket**: 0.3.3-W1-002（根因 ANA）、0.3.5 追蹤校準稽核
**嚴重度**: 中（追蹤資料漂移，不損壞產品程式碼，但使進度判斷失準）

---

## 症狀

版本追蹤五載體（git tag / todolist.yaml / ticket frontmatter / CHANGELOG / worklog 目錄）漂移，且在防護落地後仍復發：

- todolist.yaml 三版本同時 `active`（0.3.4 / 0.4.0 / 0.5.0）
- 0.3.5 為幽靈版本：ticket 與 worklog 存在、todolist 無條目、無 git tag
- CHANGELOG 停在 0.3.3 且 0.3.0–0.3.3 為未填寫模板、0.2.x 條目整段缺漏
- 0.2.0 / 0.2.1 / 0.2.2 從未打 tag（tag 序列 v0.1.0 直接跳 v0.3.0）
- `ticket track summary` 版本排序倒置（0.3.5 的「下一個 active 版本」回報 0.3.4）

## 根因

**防護放在可選流程內，等於防護不存在。**

0.3.3-W1-002（2026-06-25）已診斷此問題並落地防護：version-release pre-flight 加入 stale active 版本掃描。但防護的執行點是 `version-release check`——一個「建議執行」的可選 CLI 流程。0.3.4 / 0.3.5 收尾時走手動路徑（手動打 tag、手動改文件），pre-flight 從未被觸發，防護零次執行，漂移復發。

行為模式：發布收尾是低頻操作，操作者（PM / AI agent）傾向就地手動完成而非回想「應該走哪個 CLI」；`ticket track summary` 的「建議執行 version-release」屬文字提醒層，無強制力（對照 opinionated-default-design：每個「寫文件提醒遵守」都是工具預設行為的改善信號）。

## 解決方案

（本次修復：commit b51463e + tag v0.3.5）

1. todolist.yaml 校準：0.3.4 / 0.3.5 → `completed`、0.5.0 → `pending`，僅留一個 `active`
2. CHANGELOG 回補 0.2.0–0.3.5 全部條目
3. 補打 v0.3.5 annotated tag
4. 結案 stale in_progress 的根因 ANA（0.3.3-W1-002）

## 預防措施

**防護必須放在不可繞過的執行點**，判別基準：

| 執行點 | 可繞過？ | 適合放防護？ |
|--------|---------|-------------|
| 可選 CLI 子命令（version-release check） | 是——手動流程直接跳過 | 否（只保護走對流程的人） |
| session-start hook | 否——每個 session 必經 | 是 |
| 每回合必經 CLI 路徑（ticket track summary / complete） | 低——日常操作必經 | 是 |

落地方向（追蹤 ticket 見下）：session-start hook 做版本追蹤一致性掃描——偵測多重 active、幽靈版本（ticket/worklog 存在但 todolist 缺）、全完成未收版、tag 與 todolist drift，異常時 stderr 警告。

## 關聯

- `.claude/rules/core/opinionated-default-design.md` — 主張 1「預設行為 > 文件規範」的復發實證
- 0.3.3-W1-002 — 首次根因分析（防護落地但執行點錯誤）
