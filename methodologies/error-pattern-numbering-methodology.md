# Error-pattern 來源前綴編號方法論

本方法論規範跨專案共用框架下，error-pattern（PC / IMP / ARCH / DOC / TEST / CQ / PROC 等全 category）的編號分配方式，防止多專案併發分配同號造成知識庫指涉碰撞。

> **適用前提**：一套 `.claude/` 框架透過共享 repo 同步至多個專案（full-overlay sync）。若框架僅單一專案使用，本方法論不適用，沿用 flat 編號即可。

---

## 核心原則：凍結 flat base，新編號用來源前綴

| 編號層 | 格式 | 語意 |
|--------|------|------|
| 凍結核心（canonical base） | `<CATEGORY>-NNN`（如 `PC-093`） | 既有 flat 編號，視為共享 canonical 知識，**凍結不再新增 flat 號** |
| 來源前綴（staging） | `<CATEGORY>-<PROJ>-NNN`（如 `PC-V1-001`） | 各專案新發現的 error-pattern，前綴取自來源專案代號 |

**Why**：flat 序列把「發現時機」當主鍵。多專案從相同 base 各自累加，併發分配必然撞號（同號指向不同教訓）；full-overlay sync 後同號異義檔因 slug 不同而並存，知識庫失去「一個編號 = 一個教訓」的唯一指涉。來源前綴讓每個專案在自己的命名空間單調遞增，碰撞在資料結構層消失，不靠事後協調。

**Consequence**：未採來源前綴時，每次跨專案 sync 都可能引入同號異義；解法退化為「碰撞後重編號」，而重編號會 churn 所有引用（規則 / 方法論 / 各 pattern 的 `related:` 欄 / 工作日誌），成本隨專案數與引用密度上升。

**Action**：新增任何 category 的 error-pattern 時，一律使用 `<CATEGORY>-<PROJ>-NNN`，`<PROJ>` 取自來源專案代號（見「專案代號註冊表」）；**禁止**新增無前綴的 flat 號。

---

## 凍結 flat base 的語意

凍結指「不再新增 flat 號」，**不是**「改寫既有 flat 號」。既有 `<CATEGORY>-NNN` 全部原樣保留——這是維持向後相容（既有引用不破）的前提。

### 協議字串豁免（永不重編）

部分 flat 編號已成為**協議字串**（protocol marker），被 hook / 規則 / 測試以字面 hardcode 解析。這類 ID 屬凍結 base，**永不重編**，避免任何 remediation 誤觸破壞協議。

| 協議字串範例 | 使用處 |
|-------------|--------|
| `PC-093-exempt: <category>:<reason>` | 延後決策豁免 marker（hook 字面解析） |

**Action**：remediation（去重 / 整理）若涉及重編號，須先確認目標 ID 非協議字串；協議字串一律跳過。

### 已知 legacy intra-dir 重號（凍結保留，不重編）

凍結 base 內存在數組「同號異義」的 legacy 碰撞——同一 flat 號對應兩個不同教訓的檔案。這些碰撞繼承自多專案分叉前的共同 base，**在所有同步專案中完全一致**（非 sync 新引入），故視為 legacy 凍結保留，**刻意不重編**。

**Why**：這些碰撞跨專案一致、無 sync 惡化風險；重編會 churn 大量既有引用（規則 / 方法論 / 各 pattern `related:` 欄 / 工作日誌），成本遠高於碰撞本身的低危害。標註使碰撞「已知且文件化」優於靜默重編。

**Consequence**：若對 legacy 碰撞執行重編，會觸發跨檔引用 churn 且各專案需同步重編才能保持一致，違反「凍結不改寫既有 flat 號」的向後相容前提。

**Action**：以下 6 組（`process-compliance` category）已知重號，引用時須以 slug 區辨語意，**禁止重編**：

| Flat 號 | 教訓 A（slug） | 教訓 B（slug） |
|---------|---------------|---------------|
| PC-010 | pm-skipped-checkpoint-after-ticket-complete | task-tracking-in-memory |
| PC-018 | parallel-agents-overlapping-followup-tickets | pm-resume-incomplete-5w1h-dispatch |
| PC-019 | design-decision-memory-only | worktree-merge-state-loss |
| PC-020 | fix-at-consumer-instead-of-producer | plan-execution-dispatch-mismatch |
| PC-030 | agent-slash-command-unreachable | phase4-unused-code-incomplete-grep |
| PC-105 | feature-implemented-without-doc-integration | pm-cli-syntax-autopilot |

> **PC-165 例外（已由去重解決，非凍結）**：PC-165 原亦為重號（auq-dispatch + false-positive-fix-chain），但 auq-dispatch 已本地重編為 `PC-171`（含編號溯源註記），上游遺留的 `PC-165-auq-dispatch-*` 孤兒檔已刪除。現 `PC-165` 唯一指涉 false-positive-fix-chain。

---

## canonical 升格機制（凍結 base = canonical 層 / 前綴 = staging 層）

凍結 base 不是終局封死，而是**分層**：

| 層 | 角色 |
|----|------|
| 凍結 base（`<CAT>-NNN`） | canonical 層：已被識別為通用、單一指涉的教訓 |
| 來源前綴（`<CAT>-<PROJ>-NNN`） | staging 層：各專案新發現，尚未整合 |

**Why**：多數 error-pattern 是框架通用知識（適用任何專案）。前綴記錄「發現位置」，但通用教訓的價值不依賴發現位置。

**Consequence**：若無回流通道，同一通用教訓會以多個前綴版本永久碎片化於各專案命名空間，dedup 候選清單隨專案數無限增長，知識庫退化為「N 份重複教訓」而非「一份 canonical 集」。

**Action**：當某 staging 教訓被識別為通用且穩定，可**升格**——於凍結 base 賦予一個 canonical alias（或在共享 repo 將其視為 canonical），前綴版標註指向 canonical。升格屬低頻、刻意動作，不是每筆 staging 都需升格。

---

## dedup：偵測「異號同義」

來源前綴消除「同號異義」碰撞，但引入新類別：同一通用教訓在多專案各自發現 → 不同前綴號、內容雷同（異號同義）。

**Why**（偵測而非阻擋）：新增時阻擋「疑似重複」會在合法情境誤殺——多專案各自真實踩到同一坑、獨立寫下教訓是正當行為，且新增當下無法可靠判定「雷同」與「真重複」。故以事後偵測 + 人工裁決取代前置阻擋。

**Action**：定期（如 sync-pull 後）跑 detect，以內容雜湊（content-hash）找跨前綴的雷同 pattern，列為候選 dedup / 升格清單，人工裁決保留哪個為 canonical。detect 偵測重複，升格機制決定歸併方向。

---

## 專案代號註冊表

| 項目 | 規範 |
|------|------|
| SSOT 位置 | `.claude/error-patterns/_project-registry.yaml`（隨 `.claude/` sync 至所有專案，全域一致） |
| 自我識別 | tooling 取 `git rev-parse --show-toplevel` 的 basename，對應註冊表 `dir` 欄 → 得 `code`；不需 project-local 設定檔 |
| 代號規則 | 短大寫英數（2-5 字元）、全域唯一（含退役保留）、新專案首次新增 pattern 前先登錄 |
| 唯一性 | 新專案 code 不得與既有或退役 code 重複，否則前綴空間內重演同號碰撞 |

---

## Rejected options（決策完整性記錄）

| 方案 | 淘汰理由 |
|------|---------|
| slug-as-identity（slug 當主鍵，編號降排序號） | 理論上 root-fix 碰撞與 dedup（sync 同 slug 自動互蓋），但既有大量 `<CAT>-NNN` 字面引用需全改 slug、放棄簡短編號慣例，遷移成本過高 |
| 弱協調 append-only 分配日誌 | git 式分散 append + merge 偵測；可行但仍需各專案 pull 後跑 detect，未優於前綴的零協調 |
| 按 domain（適用範圍）分前綴 | 語意較佳，但 domain 內多專案併發分配仍會撞號，未解碰撞核心 |
| content-hash / UUID 主鍵 | 無人類可讀性、斷裂既有慣例；hash 改用於 dedup 偵測鍵 |
| 日期序 / commit 衍生號 | 同日同序仍可能撞 / commit hash 不穩定且分配時尚未產生 |

---

## 跨專案 remediation checklist 與部署序列

flat base 碰撞已存在於所有同步專案（發散狀態，63~309 檔）。sync 是檔案 overlay，不會替各專案刪除其本地舊號檔，故各專案需**自行 pass** remediation。本節為 synced 跨專案 handoff——各專案 pull 後於自身 session 依此執行。

**Why**：中央一次性重編在 N 發散專案下不可行（各專案碰撞集合不同、同步頻率不一）。各專案本地跑 detect + 套用既定 canonical 重編，是唯一零協調且可驗證的路徑。

**Action（各專案 pull 框架更新後依序執行）**：

1. 跑 `.claude/scripts/detect_pc_collision.py` 取得本專案碰撞清單
2. **共同 base 碰撞（8 組 + ARCH-021）**：凍結保留，不重編（見上「已知 legacy intra-dir 重號」），引用以 slug 區辨
3. **本專案獨有未處理碰撞**：套用既定 canonical 重編（重編 ID 對齊上游 canonical：auq-dispatch→PC-171、defensive-rule→PC-181、ui-test-green→PC-182；刪上游遺留孤兒檔），grep 更新引用
4. 重編後再跑 detect 確認獨有碰撞歸零（共同 base 仍在屬正常）

**部署序列 gate**：

| 順序 | 動作 | gate |
|------|------|------|
| 1 | 各專案 pull 到含前綴支援的 hook（PC-ID regex 拓寬 + allocator） | — |
| 2 | 跑 detect + remediation | 須先完成順序 1 |
| 3 | 新增 error-pattern 改用 `<CAT>-<PROJ>-NNN` 前綴 | **禁止**在順序 1 完成前 add 前綴 PC（hook 不認新格式會拒絕） |

## 與既有規則的邊界

| 規則 | 聚焦 | 與本方法論關係 |
|------|------|--------------|
| PC-122（error-pattern-conflict-not-synced） | 新 pattern 推翻舊 pattern 須同步 deprecated | 本方法論處理「併發分配同號」，PC-122 處理「同步時的版本衝突」，互補 |
| PC-180（dual-project-sync-scope-conflation） | 「本地保留」vs「共享納入」兩決策軸分離 | PC-180 的 preserve 機制只防覆蓋 / 刪除，**無法**防同號異義新增；編號碰撞需本方法論的前綴分配獨立處理 |

---

## 檢查清單

新增 error-pattern 前：

- [ ] 使用 `<CATEGORY>-<PROJ>-NNN` 格式（非 flat `<CATEGORY>-NNN`）？
- [ ] `<PROJ>` 取自註冊表（git toplevel basename 對應 `dir`）？
- [ ] 新專案已先於 `_project-registry.yaml` 登錄 code？
- [ ] remediation 重編號前已排除協議字串（如 `PC-093-exempt`）？

---

**Last Updated**: 2026-06-09
**Version**: 1.0.0
