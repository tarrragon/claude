# PC-109: .claude/ Runtime State 類型未評估 Sync 排除

**Category**: process-compliance
**Severity**: High
**Status**: Active
**Created**: 2026-04-22
**Source**: W17-045 事件 — book_overview_v1 sync-push 將 `dispatch-active.json` 和 `hook-state/wrap-tripwire-state.json` 推送到共享 repo，ccsession 專案 sync-pull 後本地 session runtime state 被覆蓋汙染。

---

## 症狀

跨專案 sync-pull 執行後，本專案的 runtime state 檔案被其他專案的狀態覆蓋，造成以下異常：

- `dispatch-active.json` 顯示的「正在執行代理人」並非本專案實際派發狀態，PM 以為有人在背景跑，實際是其他專案殘留
- `hook-state/wrap-tripwire-state.json` 的 tripwire 計數器被重置或灌入陌生數值，WRAP 觸發邏輯失準
- 並行多 session 排程工具（scheduler / runqueue）因共用檔被覆蓋而誤判 Ticket 狀態
- 修復方式：手動還原當前 session state → 把受害檔加入 sync 兩端排除清單 → 重新 sync-push

典型訊號：

| 訊號 | 說明 |
|------|------|
| sync-pull 後 `dispatch-active.json` 指向不存在的 ticket | state 來自其他專案 |
| Hook 行為突然改變（WRAP 頻繁觸發或長時間沉默） | hook-state 被覆蓋 |
| 排程工具回報「有代理人在跑」但實際沒有 | dispatch registry 污染 |

## 根因

框架新增 `.claude/` 底下的運行期機制時，沒有強制流程評估該檔案是否應該被 sync 到其他專案。排除清單長期以內容類別（rules/ skills/ agents/）為主，runtime state 類別缺席。

| 層級 | 缺口 |
|------|------|
| 新增機制流程 | 沒有 checklist 要求設計者回答「這個檔案是否專案本地 state？需不需要排除？」 |
| 排除清單設計 | 清單內條目無分類說明，維護者難以判斷新檔屬於哪一類或是否遺漏 |
| Sync 工具防線 | sync-push 前沒有自動偵測「新出現的 runtime 檔案未被排除」 |
| 文件規範 | 無 `sync-exclusion-guide.md` 類文件定義三類必排除型別與判別準則 |

本質上，sync 機制假設 `.claude/` 都是框架共享內容，但實際上存在三類必排除的 runtime state，過去靠維護者個別記憶，而非流程強制。

## 三類必排除型別

設計新增 `.claude/` 檔案時，若屬於以下任一類，必須加入兩端排除清單：

| 類型 | 特徵 | 範例 |
|------|------|------|
| Session / Dispatch State | 記錄當前 session 或 dispatch 活動的即時狀態 | `dispatch-active.json`、`dispatch-active.lock` |
| Hook Runtime State | Hook 執行過程累積的計數器、tripwire、快取 | `hook-state/*.json`、`hook-state/*.lock` |
| Log / 時序產物 | 時序記錄、執行歷史、暫存輸出 | `hook-logs/`、`logs/`、`analyses/*/runtime-*.json` |

共同特徵：

- **本地特異性**：內容只對產生它的專案有意義，對其他專案而言是雜訊或錯誤狀態
- **頻繁變動**：每次派發、每次 Hook 執行都會寫入，sync 版本永遠落後
- **覆蓋危害性**：被其他專案的版本覆蓋會導致本專案誤判、流程卡住或防線失效

## 觸發案例

### W17-045（2026-04-22）

book_overview_v1 執行 sync-push 時，將以下檔案推送到共享 repo：

- `.claude/dispatch-active.json`（當時記錄某個 thyme agent 正在跑）
- `.claude/hook-state/wrap-tripwire-state.json`（當時 WRAP tripwire 計數為某個中間值）

ccsession 專案 sync-pull 後，本地 `dispatch-active.json` 被覆蓋為 book_overview_v1 的版本，導致 ccsession 的 PM 以為有 thyme agent 在跑，實際上 thyme 只存在於 book_overview_v1 的派發歷史。WRAP tripwire 計數同樣被灌入 book_overview_v1 的數值，ccsession 的 WRAP 行為失準。

暴露的結構性問題：

- `dispatch-active.json` 於 W17 系列新增時，沒有流程強制評估 sync 排除
- `hook-state/` 於 Hook 系統重構時，沒有文件規定該目錄屬於「專案本地 state」
- 兩端排除清單（book_overview_v1 和 ccsession）皆未涵蓋這兩項

## 影響

- 跨專案 sync 變成隨機事件：誰最後 push 就決定其他專案的 runtime state
- PM 在接手 session 時誤判派發狀態，浪費時間追查不存在的背景代理人
- Hook 防線（WRAP tripwire、dispatch guard）在被覆蓋後失效，decision quality 無 safety net
- 長期弱化 sync 機制可信度，維護者傾向手動拷貝取代自動同步，喪失框架統一優勢

## 防護措施

### 1. 建立 Sync 排除分類規範（W17-045.1）

於 `.claude/references/sync-exclusion-guide.md` 建立以下規範：

- 明列三類必排除型別（Session/Dispatch State、Hook Runtime State、Log/時序產物）及其判別準則
- 為排除清單每條目加上分類標籤與註解，維護者可快速判斷新檔應歸入哪類
- 提供新增 `.claude/` 機制時的 sync 評估 checklist（5 問：專案本地？頻繁變動？覆蓋有害？需跨專案共享？加入哪類排除？）

### 2. SessionStart Hook 自動偵測未排除檔案（W17-045.3）

新增 Hook 於 SessionStart 時掃描 `.claude/` 底下：

- 比對現有排除清單
- 偵測新出現的「看起來像 runtime state」檔案（副檔名 `.json`、`.lock`；路徑含 `state`、`logs`、`runtime`）
- 若偵測到未排除的疑似 runtime state，輸出 stderr 警告並建議設計者補排除或將檔案標記為共享

### 3. 本 Error Pattern 作為記憶體

本 pattern 記錄 W17-045 事件與三類型定義，作為未來 PM / 設計者審查新增 `.claude/` 機制時的對照表。遇到類似症狀（sync 後 runtime 異常、派發狀態詭異）先查本 pattern，確認是否屬同一根因。

### 4. 新增機制時的 Ticket Checklist

任何建立新 `.claude/` 檔案的 Ticket，在 acceptance 中納入：

```
[ ] 已評估 sync 排除需求：若屬三類必排除型別，已更新 sync 兩端排除清單
```

Hook 或 PM 審查 acceptance 時可強制此項勾選。

### 5. 修復流程（事件發生時）

一旦偵測到 runtime state 被 sync 覆蓋：

1. 立即停止後續 sync 操作，避免擴大汙染範圍
2. 從 git 歷史或 session 備份還原本地受害檔案
3. 將受害檔案路徑加入兩端（本專案 + 共享 repo）的 sync 排除清單
4. 重新執行 sync-push，確認該檔不再被推送
5. 記錄事件至本 error-pattern 觸發案例段

## 與其他 Pattern 關係

| Pattern | 關係 |
|---------|------|
| PC-015（Framework Footer Wave Contamination 類結構性缺口） | 同屬「框架新增機制時缺乏強制檢查點」的系統性缺口 |
| ARCH-015 | `.claude/` subagent 編輯邊界；本 pattern 聚焦 sync 面，ARCH-015 聚焦 edit 面 |
| framework-asset-separation | 框架資產 vs 專案產物分離原則；本 pattern 是該原則在 sync 面的缺口補強 |

## 關鍵教訓

> `.claude/` 不是單一類別；它同時容納「框架共享內容」和「專案本地 runtime state」。sync 機制若假設兩者同質，結構性缺口會隨新機制持續擴大。防線不能只靠維護者記憶，必須有文件規範 + Hook 自動偵測 + Ticket checklist 三層強制點。

設計新機制時，第一個問題不應是「要放 `.claude/` 哪裡？」而是「這個檔案是專案本地 state 還是框架共享內容？」。前者必須進入排除清單；後者才進入 sync 流程。
