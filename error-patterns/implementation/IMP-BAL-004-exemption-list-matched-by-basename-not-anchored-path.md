---
id: IMP-BAL-004
title: 豁免清單以檔名比對而非路徑錨定，使樹中任意深度的同名檔全數豁免
severity: high
category: implementation
created: "2026-07-29"
source_tickets: [0.2.1-W3-133]
related_patterns: [IMP-MON-003, IMP-004, IMP-011]
---

# IMP-BAL-004: 豁免清單的比對維度錯置（basename vs anchored path）

## 症狀

一份「不要動這些檔」的豁免清單，成員實際是**根目錄專屬的 repo metadata**
（`README.md` / `CHANGELOG.md` / `LICENSE` / `VERSION` / `.gitignore`），
但比對實作寫成 `path.name in EXEMPT_SET`。結果豁免範圍從「根目錄那一個檔」
擴張為「樹中每一層的同名檔」。

刪除傳播、清理、掃描、覆寫這類遍歷全樹的操作因此對同名檔全面失效，且
**失效方式是靜默的**——操作照常回報成功，只是少做了一部分。

**識別特徵**：

- 豁免集合同時混入目錄名（`.git`）與檔名（`README.md`），共用同一次比對。
- 比對用 `rel.name in EXEMPT` 或 `any(part in EXEMPT for part in rel.parts)`，
  沒有任何 `len(rel.parts) == 1` 之類的根目錄錨定條件。
- 操作回報的處理數量與預期數量差一個小數目，且差額恰好等於受影響目錄數。

## 實證案例（flutter_balance 0.2.1-W3-133，2026-07-29）

刪除 `.claude/skills/wrap-decision/references/integration-patterns/`（8 檔）後執行
`sync-push --clean` 傳播刪除至 canonical repo。腳本回報「已清理 7 個遠端過時檔案」，
逐檔列出的 7 個檔中缺 `README.md`。`gh api` 查證確認 canonical 該目錄仍存在，
內容只剩一個 `README.md`——一個沒有任何內容的孤兒目錄。

根因在 `sync-claude-push.py`：

```python
_CLEAN_EXCLUDE = {".git", "CHANGELOG.md", "VERSION", "README.md", "LICENSE", ".gitignore"}

def _should_skip_clean_file(rel, ...):
    if any(part in _CLEAN_EXCLUDE for part in rel.parts):   # 意圖是目錄語意（為了 .git）
        return True
    if rel.name in _CLEAN_EXCLUDE:                          # 檔名語意
        return True
```

集合的設計意圖是保護 canonical repo 根目錄的 metadata（該 repo 自己的 README、
版本檔、授權檔不該被 consumer 專案的 overlay 覆寫或刪除）。實證支持此意圖：
`LICENSE` 與 `.gitignore` 在本地 `.claude/` 根本不存在，是 canonical 專屬檔案。

**兩行都有份，不是只有第二行**。`rel.parts` 對檔案路徑而言最後一個成分就是檔名，
因此第一行的 `any(part in _CLEAN_EXCLUDE for part in rel.parts)` 單獨就已經對
任意深度的 `README.md` 命中，第二行對檔案是冗餘的。只刪掉看起來明顯錯誤的第二行
並不會修好——這是「表面歸因」的陷阱：錯誤最顯眼的那一行未必是唯一成因。

**影響範圍不限單一事件**：此框架幾乎每個目錄都放 `README.md` 作為入口說明，
因此 `--clean` 結構性地無法完整刪除任何目錄——每次都留下一個孤兒 README。
這是「遠端孤兒持續累積」這個既知問題的一條未被發現的分支：先前的調查歸因於
`--clean` 是 opt-in（使用者忘記加旗標），未察覺即使加了旗標也刪不乾淨。

## 根因

1. **一個集合承載兩種比對語意**。`.git` 需要的是「路徑中任一層是這個名字」，
   `README.md` 需要的是「這個路徑就是根目錄的這個檔」。兩者共用一個集合，
   實作者只能挑一種比對，於是其中一組必然錯配。
2. **豁免清單的成員語意未被寫下來**。集合只有名字沒有註解，讀者無從判斷
   `README.md` 指的是「根目錄那一個」還是「所有的」，程式碼審查時不會停下來。
3. **漏刪不產生錯誤**。清理少刪一個檔的觀察後果是「遠端多一個檔」，不觸發任何
   斷言、測試或執行期錯誤。缺陷只有在有人主動查證遠端狀態時才會浮現。

## 防護

| 層級 | 措施 |
|------|------|
| 設計層 | 豁免清單依比對維度拆為獨立集合：目錄名集合（任意深度生效）、根目錄檔名集合（僅 `len(rel.parts) == 1` 生效）、glob 樣式集合。禁止單一集合混裝多種語意 |
| 實作層 | 每個豁免集合的定義處註明比對維度與意圖（「保護目標 repo 根目錄的 metadata，不涵蓋巢狀同名檔」） |
| 測試層 | 對每個豁免集合建立成對測試：根目錄同名檔應被豁免、巢狀同名檔應**不**被豁免。單向測試（只測「有豁免到」）無法捕捉過度匹配 |
| 驗證層 | 刪除傳播 / 清理類操作，回報的處理數量須與預期數量對帳；不一致時輸出差集而非只報總數 |

**判定準則**：看到豁免清單時，逐一問每個成員「這是目錄名還是檔名？是任意深度還是
根目錄專屬？」。答案不一致的成員不能共用同一次比對。

## 相關

- `IMP-MON-003`（貪婪字串替換命中 URL 子字串）——同屬「比對維度比意圖寬」的家族，
  該案例是字串子集過度匹配，本案例是路徑層級過度匹配。
- `IMP-004`（Hook 白名單不完整）——豁免清單的對偶面：該案例是漏列導致誤擋，
  本案例是比對過寬導致漏做。
- `IMP-011`（不完整的格式比對）——比對規則未涵蓋實際輸入樣態的家族。
- `.claude/commands/sync-push.md`「skill / hook 遷移後須跑 --clean 傳播刪除」章節
  ——該章節記載的孤兒累積問題，本 pattern 補上「加了 --clean 仍刪不乾淨」這一支。
