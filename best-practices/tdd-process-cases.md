# TDD 流程最佳實踐案例庫

## 案例庫目的

**建立可複製的學習機制**：
- 記錄真實開發中的正確和錯誤決策
- 提供具體的決策模板和禁用語言清單
- 累積實戰經驗形成知識資產
- 支援新 PM/Agent 快速學習正確流程

**維護原則**：
- **實戰導向**：所有案例來自真實開發經驗
- **對比學習**：同一情境的錯誤 vs 正確決策對比
- **持續累積**：每次發現新案例都加入
- **定期回顧**：SessionStart Hook 可隨機顯示案例提醒

---

## 正確決策案例

### 案例 1: v0.12.1 Phase 4 完整執行（2025-10-07）

**情境描述**：
- Phase 1-3 已完成，Domain 介面設計全部實作完成
- 測試通過率 100% (31/31 tests)
- 程式碼品質評估 A+（pepper-test-implementer 評估）

**PM 初始決策（錯誤）**：
```text
選項 A：跳過 Phase 4，直接進入 v0.12.2
  理由：測試全通過，程式碼品質已達 A+

選項 B：執行輕量級 Phase 4 檢查
  理由：快速確認無重構需求即可
```

**用戶糾正**：
> "如果要做檢查，為什麼是輕量化檢查？我們有專門的重構代理人，我們是否有安排重構代理人進場的時機？"

**正確決策（修正後）**：
```text
執行 Phase 4 三步驟流程：
  Phase 4a：派發 /parallel-evaluation B 多視角重構分析（Redundancy/Coupling/Complexity）
  Phase 4b：依 4a 報告派發 cinnamon-refactor-owl 執行重構
  Phase 4c：派發 /parallel-evaluation A 多視角再審核（Reuse/Quality/Efficiency）

理由：
1. TDD Phase 4 是強制性的，不可基於任何理由跳過
2. Phase 4 的目的不是驗證品質，而是探索改進機會
3. 即使程式碼品質 A+，也要執行完整三步驟評估
4. Phase 4a 多視角分析提供客觀依據，讓 4b 重構更精準
5. Phase 4c 再審核確保重構達到預期品質目標
```

**執行結果**：
- Phase 4a 多視角分析發現檔案命名不一致問題
- cinnamon-refactor-owl 依報告修正：`import_validation_result.dart` 檔案名與類別名對齊
- Phase 4c 再審核確認重構達標
- 最終品質：A- (87/100)
- **證明**：即使初步評估 A+，Phase 4 仍發現改進空間

**學習要點**：
1. **Phase 4 是強制性的**：與程式碼品質、測試通過率無關
2. **Phase 4 三步驟設計**：4a 分析提供依據 → 4b 執行重構 → 4c 驗證成果
3. **PM 角色定位**：派發代理人，不評估「是否需要」
4. **禁用逃避語言**：「跳過」「輕量級」「簡化」都是違規詞彙
5. **信任流程設計**：三步驟確保多視角評估，比 PM 單一判斷更準確

---

## 錯誤決策案例

### 案例 1: v0.12.1 Phase 4 跳過建議（2025-10-07）

**錯誤行為**：
PM 在 Phase 3 完成後建議「跳過 Phase 4」或「輕量級 Phase 4 檢查」

**違反原則**：
- TDD Phase 4 三步驟完整執行鐵律
- PM 決策檢查清單

**根因分析**：

**文件層面**：
- CLAUDE.md 缺少 TDD Phase 4 三步驟的強制性聲明
- 三大鐵律存在，但未包含 Phase 4 強制執行

**流程層面**：
- agent-collaboration.md 無 PM 決策檢查清單
- Phase 3 → Phase 4 轉換點無明確指引

**技術層面**：
- 無自動化檢測機制偵測 Phase 4 跳過行為
- Hook 系統未整合 TDD 流程檢查

**修復行動**：

**立即修復**：
1. [x] 執行 Phase 4 三步驟：4a 多視角分析 → 4b 重構執行 → 4c 多視角再審核
2. [x] 完成 v0.12.1 所有 TDD 階段

**流程改進**（已完成）：
1. [x] CLAUDE.md 加入第四大鐵律「TDD Phase 4 三步驟完整執行鐵律」
2. [x] agent-collaboration.md 加入 PM 決策強制檢查清單
3. [x] 建立 `tdd-phase-check-hook.sh` 自動檢測機制
4. [x] prompt-submit-hook.sh 整合 TDD Phase 檢查
5. [x] 建立本案例庫記錄經驗

**預防機制**：
- **文件層**：明確的鐵律和禁用語言
- **決策層**：PM 檢查清單強制驗證
- **技術層**：Hook 系統即時檢測和警告

**經驗總結**：
- 文件存在不等於流程合規
- 需要多層防護：文件 + 檢查清單 + 自動化
- 即時反饋優於事後檢討

---

## PM 決策訓練

### Phase 3 完成後的標準流程

**情境**：pepper-test-implementer 報告 Phase 3 實作完成

**PM 強制檢查清單**（必須全部回答「是」）：

- [ ] **Phase 1-3 是否已完成？**
  - 確認 TDD 流程進度

- [ ] **是否要立即進入 Phase 4 三步驟？**
  - 強制進入 Phase 4，無需評估
  - Phase 4a → Phase 4b → Phase 4c

- [ ] **Phase 4a 豁免條件是否適用？**
  - 修改 <= 2 個檔案：可直接進入 Phase 4b
  - DOC 類型任務：可直接進入 Phase 4b
  - 任務範圍單純（單一模組、修改目的明確）：可直接進入 Phase 4b
  - 不符合任何豁免條件：必須執行完整三步驟

- [ ] **是否禁止建議「跳過」或「輕量級檢查」？**
  - 避免逃避行為

- [ ] **是否理解 Phase 4 是強制性的，與程式碼品質無關？**
  - 原則確認

**Phase 4 三步驟說明**：

| 步驟 | 代理人 | 視角 | 產出 |
|------|--------|------|------|
| Phase 4a | /parallel-evaluation B | Redundancy/Coupling/Complexity | 重構分析報告（什麼應該/不該重構） |
| Phase 4b | cinnamon-refactor-owl | 依 4a 報告執行 | 重構後程式碼、品質改善說明 |
| Phase 4c | /parallel-evaluation A | Reuse/Quality/Efficiency | 審核報告（重構是否達到品質目標） |

**豁免條件（可跳過 4a/4c，直接進入 4b）**：
- 小型修改（修改 <= 2 個檔案）
- DOC 類型任務（純文件更新）
- 任務範圍單純（單一模組、修改目的明確）

**正確決策模板**：

```markdown
[x] Phase 1-3 已完成確認

**Phase 4 三步驟派發**：

[豁免條件不符合時]
1. Phase 4a：派發 /parallel-evaluation B（Redundancy/Coupling/Complexity 視角）
2. Phase 4b：待 4a 報告完成後，派發 cinnamon-refactor-owl 依報告執行重構
3. Phase 4c：待 4b 完成後，派發 /parallel-evaluation A（Reuse/Quality/Efficiency 視角）

[豁免條件符合時]
直接進入 Phase 4b：派發 cinnamon-refactor-owl 執行重構評估

理由：TDD Phase 4 強制執行，無需評估是否需要

**預期產出**：
- 多視角重構分析報告（4a）
- 重構後程式碼和品質改善說明（4b）
- 多視角再審核報告（4c）
- Phase 4 技術債務記錄
```

**錯誤決策識別**：

錯誤（禁止）的思考模式：
- "程式碼看起來已經很好，可以跳過 Phase 4"
- "只需要輕量級檢查就好，不用完整重構評估"
- "Phase 4 可以簡化執行，快速檢查一下"
- "讓我先評估是否真的需要 Phase 4"
- "測試都通過了，程式碼品質 A+，應該不需要重構"
- "直接派 cinnamon-refactor-owl 就好，不需要先做多視角分析"

正確的思考模式：
- "Phase 1-3 完成，現在進入 Phase 4 三步驟"
- "根據 TDD 流程，Phase 4 是強制性的"
- "先執行 Phase 4a 多視角分析，再讓 cinnamon-refactor-owl 依報告執行"
- "Phase 4c 再審核確認重構成果，再進入 /tech-debt-capture"

---

## 禁用語言識別訓練

### Phase 4 逃避語言模式

**跳過類**：
- 錯誤："跳過 Phase 4"
- 錯誤："Phase 4 可以不做"
- 錯誤："直接進入下一個版本"
- 錯誤："Phase 4 可選"

**簡化類**：
- 錯誤："輕量級檢查"
- 錯誤："簡化重構"
- 錯誤："快速檢查一下"
- 錯誤："簡化 Phase 4 流程"

**條件化類**：
- 錯誤："看起來不用重構"
- 錯誤："如果品質好就跳過"
- 錯誤："評估是否需要 Phase 4"
- 錯誤："根據程式碼品質決定"

**品質藉口類**：
- 錯誤："測試都通過了，不用 Phase 4"
- 錯誤："程式碼品質 A+，應該不需要重構"
- 錯誤："沒發現問題，可以跳過"
- 錯誤："已經很好了，不用再優化"

**繞過三步驟類**（新增）：
- 錯誤："直接派 cinnamon-refactor-owl 就好"
- 錯誤："不需要 parallel-evaluation，直接重構"
- 錯誤："Phase 4a 可以跳過，直接進入 4b"
- 錯誤："Phase 4c 再審核不必要，重構就算完成"

### 正確語言模板

**三步驟派發語言**：
- 正確："執行 Phase 4 三步驟：4a → 4b → 4c"
- 正確："派發 /parallel-evaluation B 執行 Phase 4a 多視角分析"
- 正確："待 4a 報告完成，派發 cinnamon-refactor-owl 執行 Phase 4b 重構"
- 正確："待 4b 完成，派發 /parallel-evaluation A 執行 Phase 4c 再審核"

**豁免時的正確語言**：
- 正確："符合豁免條件（修改 <= 2 檔案），直接進入 Phase 4b"
- 正確："DOC 類型任務，豁免 4a/4c，直接進入 Phase 4b"

**原則聲明**：
- 正確："Phase 4 是強制性的"
- 正確："TDD Phase 4 三步驟必須完整執行"
- 正確："Phase 4 不可跳過"

**角色定位**：
- 正確："讓多視角分析提供客觀依據，再派重構代理人執行"
- 正確："PM 負責派發，不評估是否需要"
- 正確："信任多視角設計，三步驟確保品質"

---

## Hook 系統檢測機制

### TDD Phase Check Hook 檢測項目

**工作日誌檢查**：
```bash
# 檢查是否有 Phase 1-4 的標記
phase1=$(grep -c "Phase 1|Phase 1.*功能設計" "$work_log")
phase2=$(grep -c "Phase 2|Phase 2.*測試" "$work_log")
phase3=$(grep -c "Phase 3|Phase 3.*實作" "$work_log")
phase4a=$(grep -c "Phase 4a|4a.*多視角|parallel-evaluation.*B" "$work_log")
phase4b=$(grep -c "Phase 4b|cinnamon-refactor-owl" "$work_log")
phase4c=$(grep -c "Phase 4c|4c.*再審核|parallel-evaluation.*A" "$work_log")

# Phase 1-3 存在但 Phase 4 缺失 → 警告
if [[ $phase1 -gt 0 ]] && [[ $phase2 -gt 0 ]] && [[ $phase3 -gt 0 ]]; then
    if [[ $phase4b -eq 0 ]]; then
        log "[WARNING] 發現 Phase 1-3 已執行，但缺少 Phase 4b（重構執行）"
        log "[ERROR] 違反 TDD Phase 4 三步驟完整執行鐵律"
    fi
fi
```

**逃避語言檢測**：
```bash
avoidance_patterns=(
    "跳過.*Phase 4"
    "Phase 4.*跳過"
    "輕量.*檢查"
    "簡化.*重構"
    "Phase 4.*可選"
    "看起來.*不用.*重構"
    "品質.*好.*跳過"
    "不需要.*Phase 4"
    "直接派.*cinnamon.*不需要.*parallel"
    "Phase 4a.*跳過"
    "Phase 4c.*不必要"
)

for pattern in "${avoidance_patterns[@]}"; do
    if grep -qE "$pattern" "$work_log"; then
        log "[ERROR] 檢測到逃避語言: 符合模式 \"$pattern\""
    fi
done
```

**Phase 3 → Phase 4 轉換檢查**：
```bash
# 檢測 Phase 3 完成後是否建議跳過 Phase 4
if grep -qE "Phase 3.*完成|Phase 3 完成" "$work_log"; then
    if grep -qE "建議.*跳過|選項.*跳過.*Phase 4" "$work_log"; then
        log "[ERROR] 發現 Phase 3 完成後建議跳過 Phase 4"
        log "[ERROR] 這違反了 TDD Phase 4 強制執行鐵律"
    fi
fi
```

### Hook 執行時機

- **UserPromptSubmit Hook**：每次用戶輸入時觸發
- **背景執行**：不阻止主流程，即時反饋
- **日誌記錄**：所有檢測結果記錄到 `.claude/hook-logs/tdd-phase-check-*.log`

---

## 案例庫維護指引

### 新增案例時機

**觸發條件**：
- 發現新的錯誤決策模式
- 遇到新的正確決策情境
- Hook 系統檢測到新的逃避語言
- 用戶提供新的流程改進反饋

### 案例格式模板

```markdown
### 案例 N: [簡短描述]（YYYY-MM-DD）

**情境描述**：
- [Phase 狀態]
- [程式碼品質評估]
- [測試通過率]

**PM 決策**：
[決策內容]

**用戶反饋/結果**：
[反饋或執行結果]

**學習要點**：
1. [要點 1]
2. [要點 2]
3. [要點 3]
```

### 定期回顧機制

**SessionStart Hook 整合**（可選）：
```bash
# 隨機顯示一個案例作為提醒
CASE_COUNT=$(grep -c "^### 案例" "$CASES_FILE")
RANDOM_CASE=$(shuf -i 1-$CASE_COUNT -n 1)
log "[INFO] 今日案例回顧：案例 $RANDOM_CASE"
sed -n "/^### 案例 $RANDOM_CASE:/,/^### 案例/p" "$CASES_FILE" | head -n -1
```

### 版本標記

每個案例標記版本號和日期：
- 便於追蹤流程演進
- 識別改進時間點
- 關聯工作日誌和提交記錄

---

## 成效追蹤

### 衡量指標

**流程合規性**：
- Phase 4 三步驟完整執行率（目標：100%）
- 逃避語言檢測次數（目標：趨近 0）
- PM 檢查清單使用率（目標：100%）

**學習效果**：
- 重複錯誤發生率（目標：下降趨勢）
- 正確決策模式識別速度（目標：提升）
- 新案例發現頻率（目標：初期高，後期低）

**品質影響**：
- Phase 4 三步驟發現的改進機會數量
- 最終程式碼品質評分趨勢
- 技術債務累積率

---

## 總結

**本案例庫的核心價值**：
1. **可複製的學習**：新 PM/Agent 快速掌握正確流程
2. **即時參考**：決策時快速查詢相似案例
3. **持續改進**：累積經驗形成知識資產
4. **文化傳承**：保留專案的流程演進歷史

**使用建議**：
- 決策前：快速掃描相關案例
- 決策後：對照檢查清單驗證
- 發現問題：立即記錄新案例
- 定期回顧：強化流程記憶

**維護承諾**：
- 每個重要決策點都記錄
- 每個流程改進都更新
- 保持案例的實戰性和時效性

---

**Last Updated**: 2026-03-07
**Version**: 1.1.0 - 同步 Phase 4 三步驟流程（4a 多視角分析/4b 重構執行/4c 多視角再審核）；移除 emoji（0.1.1-W3-002）
