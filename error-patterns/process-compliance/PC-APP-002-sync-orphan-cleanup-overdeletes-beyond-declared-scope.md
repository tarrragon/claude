# PC-APP-002: sync-pull 孤兒清理超出宣稱範圍刪除，preserve 機制未生效致專案特化檔遺失

> **框架級（canonical-bound）**：本教訓的根因與防護皆屬框架共享工具（`sync-claude-pull.py`）行為，非單一專案特化——每個同步此 sync 機制的專案都會中招。APP 前綴僅記錄發現地。防護應內建進 sync 腳本本體（preserve-aware 孤兒清理 + 宣稱/實際刪除對帳，見 0.32.0-W1-006 spawn 的 IMP 票），並於 sync-push 時由框架賦予 canonical 編號。

## 摘要

sync-pull「框架追平」會以「上游 HEAD 沒有此檔」作為孤兒判定刪除本地檔，此判定不檢查檔案是否為本專案刻意建立的特化內容。當本地 base 落後上游較多時，一次追平會刪除大量檔案；若 commit 訊息只描述部分刪除（如「清 16 孤兒」）而實際刪除數遠超此數，超出部分會把專案特化檔（專案專屬 PC error-pattern、專案保留的 hook 版、skill 的專案落地層）當孤兒一併刪除。本該保護這些檔的 `sync-preserve.yaml` 因 gitignored 且未進版控、或同步當下未被孤兒清理流程套用，使保護失效。修正方向：刪除前以 preserve 清單過濾孤兒候選；sync commit 訊息的宣稱刪除數須與實際 `diff-filter=D` 數對帳；誤刪可從刪除 commit 的父版 `<delete-commit>^` 完整復原。

## 症狀

- sync-pull 後續輪次出現警告：`preserve 清單中的檔案不存在: <path>`（多筆），但這些路徑曾是專案特化檔。
- 某 sync commit 訊息宣稱「清 N 孤兒」，但 `git show --diff-filter=D --name-only <commit>` 實際刪除數約為 2N。
- 超出宣稱範圍被刪的多為非 root 路徑（`error-patterns/`、`hooks/`、`skills/*/references/`），即專案特化而非框架 root 層舊檔。
- 復原的 hook 隨刪除一併失去 settings.json 登記，復原檔案後不會自動執行。

## 根因（孤兒判定缺專案特化維度 + preserve 未生效 + 宣稱與實際刪除脫節）

孤兒清理的判定軸是單一的「上游 HEAD 是否存在」，缺少「此檔是否為本專案刻意特化」這條正交維度。`sync-preserve.yaml` 正是用來補上這條維度，但它的保護在該次同步未生效（檔案 gitignored、未進版控，且刪除 commit 未觸及它）。三者共振：

| 因素 | 對誤刪的貢獻 |
|------|------------|
| 孤兒判定只問「上游有沒有」 | 把專案特化檔（上游本就不該有）誤判為孤兒 |
| preserve 機制未套用 | 本該攔下的專案特化檔未被保護 |
| commit 訊息宣稱 < 實際刪除 | 宣稱「清 16 孤兒」遮蔽了實際刪 30 的事實，審查者核對訊息即放行 |

三因素須同時成立才使誤刪靜默：僅有孤兒誤判但 preserve 生效，特化檔會被攔下；僅 preserve 失效但 commit 訊息誠實列出全部刪除，審查者能於 commit 階段察覺；唯有「孤兒誤判 + preserve 失效 + 宣稱遮蔽實際」三者疊加，誤刪才會穿過每一道關卡而無人察覺。

結果：宣稱範圍內的 root 層舊檔刪得正確，但超出宣稱的專案特化檔靜默遺失，直到後續 pull 的 preserve 警告才暴露。

## 案例：c014eccf 宣稱清 16 實刪 30（2026-06-15 → 2026-06-16 揭露）

c014eccf「.claude 框架追平至 ce0dcd7（清 16 孤兒 + 框架演進）」commit 訊息描述「16 W10-049 孤兒（14 root D + 2 R100 遷移）」，實際 `diff-filter=D` 刪除 30 檔。超出的 16 個非 root 刪除含 preserve 清單標記的專案特化檔：

- `error-patterns/process-compliance/PC-177`（防護規則機械套用反噬）、`PC-178`（UI 測試綠但 runtime 不可達）——APP 專案版，與上游同編號不同教訓。
- `hooks/pre-fix-evaluation-hook.py`（APP 保留的 hook 版修復前評估，432 行）。
- `skills/wrap-decision/references/project-integration/` 下 7 個 `.md`（專案 WRAP 落地層）。

揭露路徑：下一輪 sync-pull（2026-06-16）噴出 10 筆「preserve 清單中的檔案不存在」警告 → `git log --all --full-history --diff-filter=D` 定位全部刪於 c014eccf → 從 `c014eccf^` 完整復原 10 檔（commit 04553fd6）。`triggers-alignment.md`（163 行專案文件）與現存的 `triggers-alignment.yaml`（59 行 hook 映射表）為不同檔，preserve 條目本身無誤。

## 防護（sync 孤兒清理對帳順序）

| 步驟 | 動作 | 目的 |
|------|------|------|
| 1 | 孤兒清理刪除前，以 `sync-preserve.yaml` 過濾候選；列入 preserve 者不刪 | 補上「專案特化」正交維度，攔下誤刪 |
| 2 | sync commit 前，對帳「宣稱刪除數」與 `git show --diff-filter=D --name-only` 實際數；不符則於訊息逐類列出超出部分 | 消除宣稱遮蔽實際的盲區 |
| 3 | pull 後若見「preserve 清單中的檔案不存在」警告，視為「曾被刪除」訊號，用 `git log --all --full-history --diff-filter=D -- <path>` 追溯刪除 commit | 區分「從未建立」與「曾存在被誤刪」 |
| 4 | 確認誤刪後從 `<delete-commit>^` 復原；hook 類檔復原後檢查 settings.json 登記與執行權限（`git show` 不保留 mode） | 完整復原（檔案 + 登記 + 755 權限） |

**Why**：孤兒判定的單一軸（上游有無）無法表達「專案刻意特化」，preserve 清單是唯一補正維度；commit 訊息宣稱數與實際刪除數脫節會讓審查者核對訊息即誤放行。

**Consequence**：跳過對帳會讓專案特化檔靜默遺失——專案專屬知識（PC error-pattern）、專案保留的 hook 行為、skill 落地層消失且當下無人察覺，可能延續多次 sync 後才由 preserve 警告暴露，且復原需逐檔考古；hook 類遺失更會連帶失去 settings.json 登記，runtime 行為靜默改變。

**Action**：sync 孤兒清理刪除前以 preserve 清單過濾候選；commit 前對帳宣稱與實際刪除數；見 preserve「檔案不存在」警告時用 git 全歷史追溯刪除點，確認誤刪後從刪除 commit 父版復原並還原 hook 登記與執行權限。

## 相關

- `.claude/rules/core/tool-output-trust-rules.md` 規則 5「記錄平面不是 ground truth」——commit 訊息（宣稱）vs git 實際刪除（世界平面）的對帳即此規則的應用。
- `.claude/error-patterns/process-compliance/PC-177-defensive-rule-mechanical-overapplication.md` — 防護手段機械套用反噬上位模式（孤兒清理機械套用即其變體）。
- 案例 commit：誤刪 `c014eccf`、復原 `04553fd6`、hook 登記 `69e236a1`。
- `.claude/sync-preserve.yaml`、`.claude/scripts/sync-claude-pull.py`（`--audit` 孤兒稽核）。

---

**Last Updated**: 2026-06-16 | **Version**: 1.1.0 — 標記框架級（canonical-bound）+ 防護內建 sync 腳本路由（0.32.0-W1-006）；補根因三因素疊加機制句（basil-writing-critic 審查建議）。**Version**: 1.0.0 — 初始建立（c014eccf 宣稱清 16 實刪 30，誤刪 10 個 preserve 標記專案特化檔，2026-06-16 sync-pull 警告揭露 + c014eccf^ 復原）。**Source**: sync-pull 第二輪 preserve 警告 git 考古。
