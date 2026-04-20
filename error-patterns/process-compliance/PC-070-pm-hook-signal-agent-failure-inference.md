# PC-070: PM 用 Hook 廣播訊號推論代理人失敗（跳過 TaskOutput status 查詢）

> **[已併入 PC-050 模式 E]**（2026-04-15）
>
> 本 Pattern 與 PC-050 同屬「代理人狀態誤判」家族，已整合為 PC-050 **模式 E**：
> - **主索引**（含完整防護規則、假設生成要求、訊號可靠度表）：`.claude/error-patterns/process-compliance/PC-050-premature-agent-completion-judgment.md`
> - **本檔案**：保留為模式 E 的獨立歷史紀錄（觸發案例、原始根因分析維度）
>
> 新讀者請先讀 PC-050 模式 E，本檔作為補充背景閱讀。

## 錯誤症狀

PM 派發背景代理人後，收到以下**組合訊號**即判定「代理人完成但失敗」：

1. `PostToolUse:Agent hook additional context: 已清理派發記錄 | 所有代理人已完成`
2. `dispatch-active.json` 為空
3. `git status` 顯示目標檔案無變更
4. `ticket track query` 顯示 Solution 區段仍為模板預設文字

PM 據此推論「代理人未做預期工作」，進入代理人失敗 SOP（分析根因、重試策略、拆分 scope）。

**實際情況**：代理人仍在 running，Hook 廣播訊號與 CC runtime agent 真實完成狀態不同步。

## 根因分析

### 核心矛盾

| 訊號類型 | 性質 | 可靠度 |
|---------|------|--------|
| `PostToolUse:Agent` 廣播 | Hook 自行維護，邏輯可能誤觸 | 中 |
| `dispatch-active.json` 空 | Hook 清除邏輯早於 agent 真實完成 | 中 |
| `git status` 無變更 | 代理人工作中段本來就可能無落盤 | **低**（無鑑別力） |
| `ticket Solution` 空 | 代理人填 Solution 通常在尾段 | **低**（無鑑別力） |
| **`TaskOutput <status>` 標籤** | CC runtime 直接查詢 | **高**（唯一直接證據） |

### 五項具體誤判機制

1. **過度信任 Hook 廣播訊息**：把 Hook 維護的計數檔當 runtime 真相
2. **跳過 agent-failure-sop.md Step 0.5**：失敗判斷前置步驟明寫「對懷疑失敗的 agentId 呼叫 TaskOutput(task_id, block=false, timeout=3000)，只讀 `<status>` 標籤」，但 PM 直接跳到結論
3. **PC-050 防護焦點偏移**：PC-050 模式 D 強調「禁止讀 transcript body 推論」，PM 把「不讀 body」誤解為「不要用 TaskOutput」
4. **單一假設錨定**：看到「completion 通知 + Solution 空 + 無 commit」立即定錨「失敗」，無替代假設生成
5. **把間接訊號當直接證據**：`dispatch-active.json` 清空是**結果**訊號，非**狀態**查詢

## 與 PC-050 的關係

| 維度 | PC-050 模式 D | 本 Pattern (PC-070) |
|------|-------------|-------------------|
| 誤判類型 | 信任**錯誤**的資訊源（transcript body） | 跳過**正確**的資訊源（TaskOutput status） |
| 工具焦點 | transcript JSONL 檔案 | Hook 廣播訊息 + dispatch-active.json |
| 症狀 | 讀到「我即將做 X」就判失敗 | 看到「完成訊號組合」就判失敗 |
| 防護方向 | 禁止讀 body | 強制用 status 查詢 |

兩者為同一家族（代理人狀態誤判），互補防護。

## 防護措施

### 1. 強制執行 agent-failure-sop.md Step 0.5

**任何**懷疑代理人失敗的情境，**必須先**呼叫：

```
ToolSearch(query="select:TaskOutput")
TaskOutput(task_id=<agentId>, block=false, timeout=3000)
```

只讀 `<status>` 標籤值：

| status | 意義 | PM 行動 |
|--------|------|--------|
| `running` | 代理人仍在工作 | **停止**推論、等待完成通知 |
| `completed` | 代理人已完成 | 開始驗收流程 |
| `error` | 代理人錯誤中止 | 走失敗 SOP |

### 2. Hook 廣播訊號視為「輔助提示」而非「真相」

`PostToolUse:Agent hook additional context` 的內容（如「所有代理人已完成」）只是建議性提示，不構成代理人狀態的最終判定。PM 在收到此訊號時**仍需**執行 Step 0.5。

### 3. TaskOutput body 污染的實務處理

PC-050 安全範本要求「只讀 status 標籤」，但 TaskOutput 工具實際輸出包含 transcript body。實務解法：

- 接受 body 污染一次（把 status 查出來即止）
- 禁止因 body 內容做任何推論（PC-050 模式 D）
- 未來可建 CLI 包裝腳本（`grep -o "<status>[^<]*</status>"`）降低污染（建議由 W10-059 ANA ticket 追蹤）

### 4. 生成 2+ 替代假設

收到「完成訊號組合」時，**禁止**立即定錨「失敗」。至少列出：

- 假設 A：代理人完成但失敗（最常見誤判）
- 假設 B：**代理人仍在工作**（Hook 訊號不可靠）
- 假設 C：代理人在「長單步」中（例如連續 Edit）
- 假設 D：代理人已完成但產出不在預期位置（例如寫到子目錄）

四假設之一被 TaskOutput status 排除之前，不做重試/重派決策。

## 實際案例

### 案例 1（觸發案例）

**背景**: Phase 4b 重構 ticket 派發代理人執行 4 項 CE 重構

**經過**:
1. PM 派發代理人（background）
2. 短時間內收到 `PostToolUse:Agent` 廣播「所有代理人已完成」+ dispatch-active.json 空
3. PM 查 ticket：Solution 空、hook 檔無變更、無新 commit
4. PM 推論「代理人完成但沒做事」，準備走失敗 SOP（分析根因、縮小 scope、重派）
5. 用戶打斷並指正「代理人還在工作」
6. PM 執行 TaskOutput（block=false），`<status>` 回傳 `running`
7. 確認代理人實際正在 Edit DetectResult dataclass、Protocol 定義、Strategy apply 邏輯

**成本**: 差點重派導致同檔衝突；PM context 浪費在錯誤根因分析；用戶需主動打斷

**教訓**:
- Hook 訊號時機與 CC runtime 不同步
- `git status` / `ticket Solution` 不具狀態判定鑑別力
- Step 0.5 是**必經**步驟，非可選

## 相關

- PC-050（模式 A-D）：代理人完成誤判家族
- pm-rules/agent-failure-sop.md 失敗判斷前置步驟 Step 0.5
- `.claude/references/pm-agent-observability.md`：四工具分工
- W10-059（ANA）：Hook 完成訊號誤觸與 PM 間接訊號推論根因分析

---

**建立日期**: 2026-04-15
**Last Updated**: 2026-04-15（併入 PC-050 模式 E）
**嚴重程度**: High（同 PC-050 模式 E）
**類別**: process-compliance
**狀態**: 已併入 PC-050 模式 E，保留為歷史紀錄
