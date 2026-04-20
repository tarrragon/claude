---
id: PC-087
title: PM 寫 /tmp 中介檔作為 ticket 內容寫入繞路
category: process-compliance
severity: medium
created: 2026-04-18
---

# PC-087: PM 寫 /tmp 中介檔作為 ticket 內容寫入繞路

## 症狀

PM 主線程準備寫長篇 Solution/分析內容到 ticket 時，先 Write 到 `/tmp/xxx.md` 作為中介檔，打算後續用 `cat /tmp/xxx.md | ticket track append-log` 的方式注入 ticket。

實際觸發：main-thread-edit-restriction-hook 攔截 `/tmp` 路徑不在白名單，工作流中斷。

## 根因（3 層深度）

> **方法論提醒**：若「根因」只能用 1 句話寫完，80% 是表層。真因應能解釋「為何不是 B/C/D」而不只「為何是 A」。本章節依此 checklist 寫到真實根因。

### 表層（shell 習慣）

PM 習慣「先寫檔案再引用」的傳統 sysadmin 模式。

**局限**：解釋不了「為何不用 heredoc」——heredoc 也是訓練資料中同樣常見的模式。表層歸因無法分辨兩者。

### 第一層深因：長文字 payload 的「檔案感」物化

當內容滿足以下條件，PM 思考會切換到「檔案模式」：
- 超過 20 行
- 包含表格 / 多段 markdown / 程式碼區塊
- 結構化（多個章節）

此時 PM 把它視為**文件系統物件**而非**命令字串參數**。檔案感觸發反射動作「Write → 後續處理」，跳過「這能當參數直接傳嗎？」的判斷。

### 第二層深因：認知負擔規避

Write `/tmp` 是**最低單步複雜度**的表面路徑：

| 路徑 | 單步複雜度 | 總步驟數 |
|------|-----------|---------|
| Write /tmp → cat → append-log | 每步簡單 | 3 步 |
| heredoc 內嵌 append-log | 單步含長引號塊 | 1 步 |
| Edit ticket md | 需 Read 定位 + old_string 精確匹配 | 2 步（對大檔有摩擦） |

PM 無意識地**增加步驟換取每步心智簡潔**，違反 Occam's Razor 但個別步驟感覺更舒服。

### 真實根因（最深）

**PM 的 tool selection heuristic 在內容規模觸發「檔案感」時會選擇增加步驟，換取每步認知負擔的降低。這是主動認知策略，不是被動習慣。**

差別決定防護方向：
- 若只是被動習慣 → 加規則提醒即可
- 若是主動認知策略 → **需要 check heuristic「是否把參數當檔案了？」**，在 tool selection 時介入

### 白名單事實（技術層）

- 主線程編輯白名單（W10-033）：`.claude/`、`docs/**`、`CLAUDE.md`、`CHANGELOG.md`、`.gitignore`
- `/tmp/` 不在白名單 → main-thread-edit-restriction-hook 攔截

### Meta 問題（自我參照）

寫 error-pattern 時，PM 也會走認知負擔規避路線：
- 「shell 習慣」是 1 分鐘可產出的表層答案
- 真因分析需自我觀察 5 層，慢且痛
- 原 PC-087 只寫到表層，用戶質疑後才重寫 → **error-pattern 本身需要深度檢查**

## 防護

### 規則（即時）

PM 寫 ticket 內容時禁止使用 `/tmp/` 或任何白名單外路徑作為中介檔。直接用 heredoc 或 Edit ticket md。

### Tool Selection Heuristic（真因對應）

選 Write 前必過以下 check：

| 檢查 | 問題 | 觸發重選 |
|------|------|---------|
| 物化檢查 | 我把長文字當「檔案」而非「字串參數」了嗎？ | 是 → 考慮 heredoc 或 Edit |
| 步驟數檢查 | 這個選擇是否為了降低單步複雜度而增加了總步驟？ | 是 → 選步驟少的路徑 |
| 目的地檢查 | 內容的最終目的地是什麼？ | 若為 ticket section → append-log heredoc；若為 ticket 整體 → Edit |
| 白名單檢查 | 目標路徑在主線程白名單內嗎？ | 否 → 必改道 |

### 識別信號

| 信號 | 含義 |
|------|------|
| 準備 Write 到 `/tmp/*.md` | 99% 是繞路，停下來問：目的是什麼？ |
| 內容 > 20 行含表格/章節 | 高機率觸發「檔案感」，強制過 heuristic |
| 目的是「準備 append-log 內容」 | 改用 heredoc 內嵌 |
| 目的是「準備 Edit ticket 區段」 | 直接 Edit ticket 檔 |
| 目的是「分享給其他代理人」 | 寫入 ticket body 或 `.claude/plans/` |

### Bash 規則四擴充適用

PC-079（Bash 規則四）禁止 backtick 被 command substitution。本 PC-087 與其同源——都是「透過 shell 中介傳遞長文字」引發的工作流阻塞。

統一解法：**heredoc with quoted delimiter 是 PM 傳遞長文字的預設選擇**。

## 案例

- 2026-04-18 (W15-001 session)：PM 準備 WRAP 分析結論寫入 W15-001 ticket，先 Write `/tmp/w15_001_solution.md` → hook 攔截 → 改用 heredoc 內嵌 append-log 成功。用戶質疑「為什麼寫 /tmp 而不寫 ticket？」暴露此繞路習慣。
- 2026-04-18 (W15-005 session)：用戶再質疑 PC-087 原版根因「shell 習慣」流於表層，要求 PM 深度反思。PM 建 W15-005 ANA ticket 回顧，識別出 3 層根因（檔案感物化 → 認知負擔規避 → 主動認知策略）。本 PC-087 依 W15-005 結論重寫。

## 相關

- `.claude/rules/core/bash-tool-usage-rules.md` 規則四（backtick）
- `.claude/error-patterns/process-compliance/PC-079-bash-backtick-command-substitution-in-cli-args.md`
- W10-033：`.gitignore` 加入白名單的前例（白名單擴充需走 Ticket 流程）
- 0.18.0-W15-005：PM 深度反思 ANA，真實根因 3 層分析來源

## 方法論教訓

寫 error-pattern 時適用「根因深度 checklist」：

1. 若根因 1 句話寫完 → 80% 是表層，強制挖 2 層以上
2. 真因應解釋「為何不是 B/C/D」（表層只能解釋「為何是 A」）
3. 真因應對應到具體**思考流程步驟**，而非抽象「習慣/偏好/文化」
4. 真因決定防護方向：被動因素加規則；主動策略加 heuristic check
5. 寫完回讀：若自己能被說服「這就是真因」→ 深度足夠；若有「可是為什麼...」→ 繼續挖
