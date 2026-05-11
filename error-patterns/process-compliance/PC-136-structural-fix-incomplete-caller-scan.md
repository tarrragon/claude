# PC-136: 結構性修復未掃 lib callers 反模式

**類別**: process-compliance
**嚴重度**: High
**首次發現**: 2026-05-10（W17-182 retrospective ANA）
**相關**: ARCH-020、PC-135、W17-179（false negative 案例）、W17-181（重啟調查觸發）

---

## 症狀

修復共用邏輯（predicate / utility function / shared module）的 bug 時，只修「最近一次發現的 caller」，未掃描所有 callers 是否有同一 bug 或同名獨立實作。表現：

1. 第 N 次發現某 bug 後修復「觸發本次 bug 的檔案」
2. 數週至數月後，同一 bug 在另一個 caller 重爆
3. 此循環反覆 3+ 次，每次修復都「以為解決」
4. 期間可能發生 ANA false negative（將「修了一處」誤判為「整個問題已解決」）

---

## 根因

### 心智模型缺陷

修復者的心智模型：「我修了觸發 bug 的那個檔案」

正確心智模型：「我修了所有使用這個 predicate / 共用邏輯的檔案」

兩者差異：前者範圍 = bug 重現路徑；後者範圍 = 結構搜尋（grep all callers）。前者是被動修復，後者是主動防禦。

### 結構性因素

| 因素 | 說明 |
|------|------|
| 同名函式無交叉引用註解 | 修復者看不到「另外兩處有同名函式」 |
| Lib + Hook 雙層架構 | Hook 為了避免 import 開銷常自定義同邏輯，產生 SSOT 漂移 |
| pytest 環境不對稱 | 修一處測試綠燈即可通過 CI，無壓力主動掃 callers |
| ANA 驗證範圍只到「直接被問的函式」 | 未追蹤 callees 呼叫鏈，產生 false negative |

### ANA 方法論缺口

ANA 驗證「函式 A 是否正確」時，只檢查 A 本體，未檢查：
- A 呼叫的 callees（是否也已正確修正）
- 呼叫 A 的 callers（是否也以同樣假設使用）
- 與 A 同名 / 同職責的其他實作（lib 與 hook 雙副本）

---

## 案例

### 案例 1：ARCH-020 三次重爆軌跡（W17-165 → W17-176.2.1 → W17-181）

| 重爆 | 修了什麼 | 漏了什麼 | 後果 |
|------|---------|---------|------|
| W17-165 | stop hook 自身 `is_ticket_completed` 改用 `find_ticket_file` | prompt-reminder hook 同名函式、lib 層 `handoff_utils.is_ticket_completed` | 數月後 prompt-reminder 重爆 |
| W17-176.2.1 | prompt-reminder hook 改用 `find_ticket_file` | lib 層 `handoff_utils.is_ticket_completed` / `is_ticket_in_progress_or_completed` | 同月內 stale handoff 持續未 GC |
| W17-181 | 識別完整消費者清單（8 處）+ lib SSOT delegate | （後續 W17-181.1/.2 執行） | （目前修復鏈閉合） |

每次修復者都覺得「這次徹底了」，但下次重爆暴露範圍未足。

### 案例 2：W17-179 ANA false negative

W17-179 ANA 結論「stop hook 行為正確」是 false negative。

| ANA 步驟 | 做了什麼 | 應做但沒做 |
|---------|---------|-----------|
| 驗證 stop hook L361 自身函式 | 是（已由 W17-165 修） | — |
| 驗證 lib `handoff_utils.is_ticket_completed`（L49） | **否** | grep 所有 `def is_ticket_completed` |
| 驗證 `is_handoff_stale` 呼叫的是 lib 版 | **否** | trace import chain |

ANA 驗證範圍只到「直接被問的函式」，未追蹤 callees。

---

## 防護

### 規則層（建議升級為 quality-common.md 1.2 條款）

修復共用邏輯時，必須執行：

```
1. grep -rn "<函式名>" .claude/ src/ lib/   # 找所有實作 + caller
2. 對每處實作：確認是否同病灶
3. 對每處 caller：確認是否依賴本次修復
4. 同步修正所有同名實作（或改 delegate 至 SSOT）
```

不只 ANA 適用，IMP 修共用 bug 時同樣必須執行。

### ANA 方法論層

ANA 驗證函式正確性時，**必須追蹤 callees 呼叫鏈至少一層**：

| 驗證對象 | 必查 |
|---------|------|
| 函式 A 本體 | 是 |
| A 的 callees（A 呼叫的函式）| 至少一層 |
| A 的同名實作（grep `def A`）| 全部 |
| A 的 callers | 抽樣（看是否假設一致） |

### Hook 層（不建議）

grep callers 自動化在 commit hook 難以可靠實作（需語意理解函式邊界）。建議走規則層自律 + ANA 方法論升級。

### 派發 prompt 層

PM 派發共用 lib 修復 IMP 時，prompt 加註：

> 修復前必須執行 `grep -rn "<函式名>"` 列出所有實作位置與 callers，並在 ticket Problem Analysis 章節記錄完整清單。修復後對每處逐一確認已同步。

---

## 與其他 pattern 的關係

| Pattern | 關係 |
|---------|------|
| ARCH-020 | 描述「為何會有重複邏輯」的結構問題；本 PC 描述「修復重複邏輯時未掃所有實作」的流程問題。互補不重複 |
| PC-135 | 環境異質（pytest vs hook subprocess）；本 PC 是 caller 範圍盲點。兩者並列為 W17-181.1 regression 的雙重根因 |
| W17-182 | 本 PC 為 W17-182 retrospective ANA 的核心產出 |
| W17-179 | 本 PC 解釋 W17-179 false negative 的方法論成因 |

---

## 後續觀測

- 觀測 ARCH-020 變體是否在其他 lib/hook 場景重現
- 若觀測到第 4 次同類重爆（含 W17-181 之後），需考慮升級為強制 hook 檢查（commit msg parse 偵測「fix」+「共用函式名」+ 強制要求附 grep 結果）
- 重啟調查鏈累積閾值（W17-154 機制）：W17-165 → W17-176.2.1 → W17-181 + W17-181.1 → 共 4 次相關修復；下次同類事件必須觸發 PC-115 強制重啟調查

---

**Last Updated**: 2026-05-10
**Version**: 1.0.0 — 從 W17-182 retrospective ANA 收斂（saffron 分析 + PM 整理）
