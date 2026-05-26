---
id: PC-162
title: Ticket 描述含過時環境狀態 + schema 註解 PC 引用語意錯誤
category: process-compliance
severity: medium
status: active
created: 2026-05-26
related:
- PC-007
- PC-100
- PC-111
---

# PC-162: Ticket 描述含過時環境狀態 + schema 註解 PC 引用語意錯誤

本 PC 涵蓋兩個獨立但同源的問題：(A) Ticket 撰寫時間晚於環境變動，描述未同步更新；(B) ticket schema 模板的「接手者驗證」註解掛到 PC-007 編號，但 PC-007 實際標題與接手者驗證無關。

## 問題描述

### 問題 A：Ticket 描述含過時環境狀態

PM 建 Ticket 時，描述基於過去的環境記憶或舊文件，未驗證當下環境是否仍與描述一致。當環境經歷重構（如 hook 合併、檔案重命名、邏輯搬移）後，Ticket 的 where.files / Problem Analysis / strategy 可能引用已不存在的檔案或路徑。

### 問題 B：Ticket schema 模板的 PC 引用語意錯誤

`docs/work-logs/v*/v*/tickets/*.md` 模板中的 Problem Analysis 章節含註解：

```html
<!-- 注意：接手者應獨立重新驗證數量/範圍（PC-007）-->
```

但 PC-007 實際標題是「Command 引導與腳本實作行為不符」，與「接手者獨立驗證」語意完全不對應。引用的 PC 編號是錯的——schema 模板把一個提醒（接手者驗證）掛到了一個內容無關的 PC 編號上。

## 觸發案例

### W3-041 案例（2026-05-26）

**完整時序**：
- 2026-04-07 commit `7a22f9f0`（W10-001）刪除 `.claude/hooks/pre-fix-evaluation-hook.py`（432 行），邏輯合併到 `.claude/hooks/post-test-hook.py` L191-296（W9 審查清理「已合併的原始 Hook 檔案」）
- 2026-05-21 PM 建 W3-041 ticket，描述「pre-fix-eval hook 對 ticket body 寫入內容誤判」，where.files 寫 `.claude/hooks`（目錄級，未指定具體檔案）
- 2026-05-26 PM 接手 W3-041 → 觸發 schema 註解的「接手者驗證」提示 → grep 發現 `pre-fix-evaluation-hook.py` 已不存在 → 進一步 git log 考古發現實際邏輯在 `post-test-hook.py`

**雙重觸發**：
- 問題 A 觸發：ticket 描述 1.5 個月內已過時（hook 已合併）
- 問題 B 觸發：接手 PM 引用 schema 註解的 PC-007 提醒，但實際 PC-007 標題與接手者驗證無關（PM 在 memory 中曾誤記為「接手者驗證 = PC-007」，本次因建立此 PC-162 才釐清）

## 根本原因

### 表層原因

| 問題 | 原因 |
|------|------|
| A | PM 建 ticket 時依過去經驗描述環境，未當下 ls/grep 驗證 |
| B | Schema 模板的 PC 引用是初版填寫後未維護，PC-007 內容變更或重編號時模板不同步 |

### 深層原因

| 維度 | 說明 |
|------|------|
| 環境變動沒有追蹤機制 | hook 移除/合併沒有觸發相關 ticket 描述審查；W10-001 commit 沒有附 follow-up 任務檢查「是否有 ticket 引用被移除的 hook」 |
| Schema 模板引用穩定性弱 | Schema 註解 + PC 編號的綁定是純文字，沒有自動驗證 |
| 接手者驗證是事後安全網非事前防護 | 防護機制依賴接手者個人警覺 + schema 註解提醒，沒有 hook 層自動偵測 ticket 描述過時 |

## 正確做法

### 預防 A：Ticket 建立時驗證

| 動作 | 何時 |
|------|------|
| where.files 必填具體檔案路徑（非目錄） | Ticket create 時 |
| Ticket 描述提到的「hook / 模組 / 檔案」必須當下 ls 確認存在 | Ticket create 時 |
| 跨月份 reference 既有現況時 grep / find 重新驗證 | 一切引用既有檔案時 |

### 預防 B：Schema 模板 PC 引用驗證

| 動作 | 何時 |
|------|------|
| 修改 schema 模板的 PC 引用前，grep PC 實際標題確認語意對應 | Schema 模板維護時 |
| 定期掃描 schema 模板的 PC 引用 vs PC 實際內容（自動化建議） | 季度審查 |

### 接手者驗證（事後安全網）

| 動作 | 何時 |
|------|------|
| `ls` / `find` / `grep` 驗證 ticket 描述提到的檔案實際存在 | claim 前 |
| 若描述含 hook 名稱，`grep -l "<hook-name>" .claude/settings.json` 確認註冊狀態 | claim 前 |
| 若發現過時，先寫 Problem Analysis 「前提驗證考古結果」段落（含時序 + git commit + 邏輯實際位置），再 claim | claim 前 |

## 補救措施（觸發案例）

W3-041 處理：
- 接手 PM 修正 where.files：`.claude/hooks` → `.claude/hooks/post-test-hook.py`
- ticket Problem Analysis 補完整考古表格（hook 原檔位置 / 移除時間 / 移除原因 / 邏輯實際位置 / 註解標記）
- 修復方向重寫對齊實際 hook（post-test-hook.py 加 ticket body 豁免）

PC-007 引用釐清：
- 本 PC 文件 footer 註明「PC-007 實際標題與接手者驗證無關」
- Schema 模板的「接手者驗證」註解中的 `PC-007` 應改為引用本 PC-162（後續 schema 模板維護 ticket 處理）

## 預防措施

### 一線防護（PM 建 Ticket 時）

| 檢查項 | 動作 |
|------|------|
| where.files 是否為具體檔案（非目錄）？ | `find .claude -name <檔名>` 驗證存在 |
| 描述含 hook 名稱？ | `grep <hook-name> .claude/settings.json` 確認註冊 |
| 跨月份引用既有檔案？ | `git log -1 --diff-filter=DM -- <路徑>` 確認近期未刪除/重命名 |

### 二線防護（接手者）

接手 ticket 後、claim 前執行：
```bash
# 步驟 1：驗證 where.files 存在
ls -la <ticket where.files 列出的每個路徑>

# 步驟 2：若含 hook，驗證註冊狀態
grep -l "<hook-name>" .claude/settings.json

# 步驟 3：若不存在，git log 考古
git log --all --diff-filter=D --name-only --pretty=format:"%h %ad %s" --date=short -- <檔名>
```

### 三線防護（Schema 模板維護）

修改 schema 模板的 PC 引用前：
```bash
# 確認 PC 實際標題與註解語意對應
grep "title:" .claude/error-patterns/<category>/PC-<NNN>*.md
```

### Hook 自動偵測建議

未來可加入 hook 在 ticket create 時掃描 where.files 路徑存在性 + PC 引用語意對應，但成本中等需獨立 ticket 評估。

## 相關規則 / 經驗

- PC-007（Command 引導與腳本實作行為不符，**本 PC schema 模板誤引用 PC-007**）
- PC-100（spawned ticket 未繼承 PCB）— 同類 ticket 描述完整性問題
- PC-111（PM narrative fabrication）— 接手者禁止依未驗證的描述直接行動
- quality-baseline 規則 5（所有發現必須追蹤）— W3-041 處理 + spawned IMP 追蹤 substring 缺陷 + cache 殘留

---

**Last Updated**: 2026-05-26
**Source**: 0.19.0-W3-041（PM 接手 W3-041 觸發 PC-007 schema 註解引用 + git log 考古發現 W10-001 hook 合併歷史）
