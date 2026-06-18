# 認知接地雙層 + 軸登錄協議（詳細 SOP）

本檔為 `pm-rules/decision-tree.md`「認知接地雙層」結構的按需讀取詳細版。涵蓋 L_ground-before（F 軸判斷協議）與 L_ground-truth（D 軸機械閘門）的完整職責、順序、手段差異、軸登錄協議，以及與既有機制的相容對照。

> **來源**：1.2.0-W1-033 ANA（F+D 認知接地雙層架構設計），背書於 1.2.0-W1-032 軸分佈實證（N=326）+ F-drill 子分析。耐久資產是「實證決策軸發現法」（`.claude/methodologies/empirical-decision-axis-discovery-methodology.md`），本檔 F+D 結論為語料快照 2026-06-18 的當前快照，非永久前提。

---

## 為何決策第一級軸是「信念接地」（Why）

跨專案累積錯誤語料（N=326，2026-06-18 快照）指出：決策失敗的最大兩軸不是功能/分類，而是「信念是否對齊世界」——

- **F（知識/規格缺口）= 29.8%**：未驗假設就行動、沒查既有就斷言不存在、規格漏、重複造輪。
- **D（狀態完整性）= 23.9%**：confabulation、幻覺工具結果、stale 狀態、未提交、假完成、記錄≠世界。

F 與 D 不是兩個獨立問題，而是同一「信念 vs 世界」斷層的**事前面與事後面**：

| 面 | 軸 | 斷層形態 |
|----|----|---------|
| 事前 | F（尤其 F4 未驗假設就行動 39.2% + F2 沒查既有 21.6%，合計約 60% of F） | 行動前未查證，憑預期分布填補事實 |
| 事後 | D | 行動後採信記錄平面（transcript / 記憶），未與世界平面（filesystem / git / ticket）對帳 |

**Consequence（不接地的後果）**：圍繞功能軸（A，19%，從沒卡過）設計第一級防護會把資源投在沒漏血的軸，而真實最大漏口（F/D 合計 53.7%）持續失血，產生「防護完整卻持續同類失敗」的假象。

**Action**：決策路由的第一級護欄按「信念接地」分流（F→事前協議、D→事後閘門），而非按功能/分類切層。

---

## L_ground-before（F 軸，判斷協議層）

**職責**：在行動者**斷言當下事實 / 採信工具行為 / 宣稱「做不到」 / 假設「沒人做過」**之前，強制最小實證，再行動。

**核心機制**：把「未驗假設」設為**第一級具名狀態**，行動前必須 discharge（消解），不得帶著未驗假設往下走。

**最小實證形態（依斷言類型選一）**：

| 斷言類型 | 最小實證動作 |
|---------|------------|
| 斷言某工具/命令行為 | 跑一次 `--help` 或實機執行一次觀察真實輸出 |
| 採信工具回傳的結果 | 只信 raw stdout；帶旁白者視為自己生成雜訊（tool-output-trust 規則 2） |
| 宣稱「做不到 / 不支援」 | 先過 tool-discovery 五問（含 ToolSearch 搜尋 deferred tool） |
| 假設「沒人做過 / 不存在」 | 掃既有（grep / ls / saffron 防重複），命中即不重複造輪 |

**手段性質**：**判斷協議（勸告型）**。F 軸難機械化——要求行動者察覺「我正在斷言一件我沒查過的事」，這是內省動作，hook 無法逐句攔截。框架在 F 軸裝最多協議（WRAP Step0、tool-output-trust 規則 3、saffron 防重複）卻仍是最大軸，正因協議是勸告型非強制型。**不可誤以為「裝了協議＝堵住了」。**

**承載既有機制**：WRAP Step0（資料充足度閘門 + Consider-the-Opposite）、saffron 防重複（F2）、tool-output-trust 規則 3（關鍵事實用固定值交叉驗證）、tool-discovery 五問。

---

## L_ground-truth（D 軸，機械閘門層）

**職責**：在行動**之後**，驗證 believed-state（行動者相信的狀態）== world（世界真實狀態），用**無法腦補的固定值**比對。

**核心機制**：重大狀態轉換（claim / complete / commit / spawn）後，以世界平面查證為準，不以對話記憶為準。

**固定值查證形態**：

| 待確認 | 固定值命令 | 判據 |
|-------|----------|------|
| commit 真實性 | `git rev-parse HEAD` / `git cat-file -t <hash>` | 40 字 hash / 二元 type |
| ticket 已 complete | `ticket track query <id>` 讀真實 status | 枚舉狀態 |
| 檔案是否存在 | `ls <path>` / `test -f <path>` | 二元有/無 |
| working tree 狀態 | `git status --porcelain` | 有/無輸出 |

**手段性質**：**機械閘門（強制型）**。D 軸可機械化——believed-state vs world 可用固定值比對，能由 hook 在 PostToolUse / commit-level 強制執行。

**承載既有機制**：028/030 worktree 交付物驗證 + 分支漂移守護 hook、tool-output-trust 規則 5（記錄平面非 ground truth，重大狀態以世界平面為準）。

---

## 手段不對稱（核心設計約束）

**體系化 ≠ 對兩軸用同一手段。** F 層與 D 層的強制手段本質不同：

| 層 | 軸性質 | 手段 | 強制力 | 漏口 |
|----|--------|------|--------|------|
| L_ground-before | F（難機械化，需內省察覺） | 判斷協議 | 勸告型 | 最大漏口（協議可被忽略） |
| L_ground-truth | D（可驗證，固定值可比對） | 機械閘門 hook | 強制型 | 小（hook 攔截） |

誤把 F 軸當可機械化、或對 D 軸只放協議不放 hook，都會錯置防護手段。

---

## 功能路由保留現狀

功能/分類軸（A，19%）從沒卡過（路由順暢），保留現狀 prose，不升為第一級護欄。資源投在「信念接地」而非「分類/路由」是資料指向的結論。

---

## 軸登錄協議（bottom-up，反 anchor）

新防護閘門誕生時，**宣告其所屬軸並登錄組織**，而非 top-down 預先切層。

**組織方式**：`子系統壓力 → 露出某軸 → 守該軸 → 登錄`。新軸由真實摩擦露出，不由設計者憑空指定層級。

**實例**：1.2.0 並行壓力 → 露出 E（並行/worktree）與 D（狀態完整性）軸 → 028/030 hook 守該軸 → 登錄至 L_ground-truth（D）。E 軸全語料僅 2.8%，證實其為真實但小眾的軸，守它但不升為第一級。

**反 anchor**：F+D 是「用實證決策軸發現法跑一次」得到的當前快照（2026-06-18，N=326）。model 演進 + 語料增長會改變軸分佈（F4 今日 39.2%，未來未必）。任何「主導軸是 X」的結論都帶快照日期與樣本量，文件不得將某軸固化為永久前提。校準 trigger 綁定見 `.claude/methodologies/empirical-decision-axis-discovery-methodology.md`「重新校準 trigger」。

---

## 與既有機制相容對照

F+D 雙層**全是既有零件重組，非新發明**。既有機制各歸層如下：

| 既有機制 | 歸層 | 對應軸 |
|---------|------|--------|
| WRAP Step0（資料充足度閘門） | L_ground-before | F |
| Consider-the-Opposite | L_ground-before | F |
| saffron 防重複 | L_ground-before | F2 |
| tool-output-trust 規則 3（固定值交叉驗證關鍵事實） | L_ground-before | F |
| tool-discovery 五問（宣稱做不到前） | L_ground-before | F |
| tool-output-trust 規則 5（記錄平面非 ground truth） | L_ground-truth | D |
| 028/030 worktree 交付物驗證 + 分支漂移 hook | L_ground-truth | D |
| 016 集中化（書面文字品質） | 品質層（非接地軸） | G |
| 功能路由 prose（問題 vs 命令 / Skill 匹配 / 派發閘門） | 功能路由（保留現狀） | A |

---

## 與其他規則的邊界

| 規則 / 文件 | 分工 |
|------------|------|
| `decision-gate-budget-details.md` | 治理 routing 檔防禦增生的「預算與退場」；本檔治理「第一級護欄按哪個軸分流」。兩者正交：前者管 prose 體量，後者管軸結構 |
| `empirical-decision-axis-discovery-methodology.md` | 提供「如何發現主導軸」的可重跑方法；本檔是「用該方法跑出 F+D 後的落地結構」。方法是耐久資產，本檔結論是快照 |
| `tool-output-trust-rules.md` | 提供 F/D 兩軸的具體查證手段（規則 3 事前、規則 5 事後）；本檔把這些手段組織進兩層 |
| `decision-trigger-binding.md` | 校準延後須綁 ticket trigger；本檔軸快照的重新校準走該規則 |
| `decision-tree-parallel-session-details.md` | 並行壓力露出的 E 軸狀態漂移**具體處置 SOP**（停手問用戶 / 靜態 vs 動態判別）由該檔負責；本檔負責把 028/030 hook 登錄至 L_ground-truth(D) 並給**軸歸屬**。讀者遇「狀態被改」對帳：該檔查 SOP、本檔查軸結構（職責互補不重複）|

---

**Last Updated**: 2026-06-18 | **Version**: 1.0.0 — 從 1.2.0-W1-033 ANA 落地（F+D 認知接地雙層 + 軸登錄協議 + 相容對照）。**Source**: 1.2.0-W1-032 軸分佈實證（N=326）+ F-drill。
