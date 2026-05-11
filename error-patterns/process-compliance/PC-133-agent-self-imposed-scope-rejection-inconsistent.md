---
id: PC-133
title: 代理人對同性質任務的接受/拒絕行為不一致（self-imposed scope rejection）
category: process-compliance
severity: medium
created: 2026-05-07
source_ticket: 0.18.0-W17-083
related_pc:
  - PC-104
  - PC-088
related_arch: []
---

## 症狀

PM 在同 session（或跨 session）派發**性質相同**的任務給**同一代理人**，代理人行為不一致：

- 第一次：接受並完成（含完整 commit / acceptance / complete 流程）
- 第二次（同性質任務）：以「不在我職責範圍」拒絕，建議改派其他代理人

具體案例（W17-083 系列）：

| 派發 | 代理人 | 任務性質 | 行為 |
|------|--------|---------|------|
| W17-083.1 | thyme-extension-engineer | Python lib 實作（`.claude/skills/ticket/ticket_system/lib/worklog_parser.py` + pytest） | 接受，4 commit 完整自律 complete |
| W17-083.2 | thyme-extension-engineer | Python CLI + Hook 實作（`commands/handoff.py` + `.claude/hooks/*.py` + pytest） | 拒絕，建議改派 thyme-python-developer |

兩次任務本質皆為 .claude/ 框架層 Python 實作，與 Chrome Extension 無關，但代理人前後判斷不同。

## 根因（待調查）

可能假設：

| 假設 | 描述 |
|------|------|
| H1 | 代理人 system prompt 對「職責範圍」的判斷依賴具體檔案路徑提示詞，路徑提示詞細節改變導致判斷漂移 |
| H2 | 代理人對「Python 開發」與「Chrome Extension 規劃」的邊界判斷依靠隨機性 LLM token 抽樣，同樣 prompt 兩次可得不同結論 |
| H3 | PM 派發 prompt 文字差異（W17-083.1 強調 lib/test 實作，W17-083.2 強調 CLI+Hook+PEP 723）觸發代理人不同職責邊界 trigger |

當前無實證可區辨。

## 影響範圍

| 面向 | 影響 |
|------|------|
| 開發效率 | PM 重派耗 1-2 min（reset who 欄位 + 重新派發） |
| 派發信心 | PM 對「該派誰」失去穩定預期，每次都需準備 fallback 派發路徑 |
| 系統信任 | 代理人定義（agent definition）與實際 runtime 行為不一致，文件意義被弱化 |
| Context 浪費 | 拒絕派發的 token 消耗（19663 ms / 78144 tokens 在 W17-083.2 第一次派發）為純損失 |

## 鑑別診斷

| 訊號 | 對應 PC |
|------|---------|
| 代理人接受任務後執行偏離職責（actually 越界） | PC-104（agent execution boundary misjudgment） |
| 代理人拒絕後 PM 抽查發現 tool 集合可用 | PC-104 |
| 代理人對同性質任務行為不一致（本 PC） | **PC-133** |
| 代理人選擇工具不當（如 MCP write 對純文字檔） | PC-088 |

## 防護

| 層級 | 機制 |
|------|------|
| PM 預防 | 派發 Python 任務優先選 thyme-python-developer 而非 thyme-extension-engineer，避免邊界判斷觸發拒絕 |
| Ticket 設計 | 子 ticket 建立時 `who` 欄位明示語言代理人（thyme-python-developer / fennel-go-developer / parsley-flutter-developer）而非任務類別代理人（thyme-extension-engineer） |
| Agent definition | thyme-extension-engineer 主文「禁止行為」可加註「.claude/ 框架層 Python 修改改派 thyme-python-developer」明示性條款 |
| 監測 | 累積 ≥ 3 次同類拒絕案例後，啟動 PC-133 根因調查（H1-H3 區辨設計） |

## 觸發案例

W17-083.2（2026-05-07）：W17-083.1 thyme-extension-engineer 接受 Python lib 實作 4 commit 完成；同 session W17-083.2（性質相同）thyme-extension-engineer 拒絕。PM 改派 thyme-python-developer 後接受並完成（commit b239d660，19 RED 測試全綠）。

## 後續觀察

- 累積案例數：1（待累積至 3+ 才啟動根因調查）
- 監測週期：30 天內若再出現 ≥ 2 次，啟動 ANA ticket 區辨 H1/H2/H3
- 替代防護：PM 在 W17-083.3 commit 已採用「Ticket 設計層」防護，後續類似 ticket 直接指定 thyme-python-developer

## 與既有 PC 的邊界

| PC | 差異 |
|------|------|
| PC-104（agent execution boundary misjudgment） | PC-104 處理「代理人接受後執行偏離 / 拒絕後實際可做」；PC-133 處理「同代理人對同性質任務接受/拒絕不一致」（行為前後不一致而非判斷錯誤） |
| PC-088（LLM tool selection bias） | PC-088 處理「工具選擇偏誤」；PC-133 處理「任務接受邊界判斷漂移」 |
