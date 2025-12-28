# CLAUDE.md

本文件為 Claude Code (claude.ai/code) 在此專案中的開發指導規範。

## 🔧 專案類型配置

本專案採用**通用規範 + 語言特定配置**的架構設計，支援多種語言和框架。

### 📋 當前專案配置

**專案類型**: 由 Startup Hook 自動識別
**識別方式**: 檢測專案根目錄的關鍵檔案

| 專案類型 | 識別特徵 | 語言配置檔案 | 執行代理人 |
|---------|---------|------------|-----------|
| **Flutter** | `pubspec.yaml` | [`FLUTTER.md`](./FLUTTER.md) | parsley-flutter-developer |
| **React** | `package.json` + React | `REACT.md`（未來） | react-developer（未來） |
| **Python** | `requirements.txt` | `PYTHON.md`（未來） | python-developer（未來） |
| **Vue** | `package.json` + Vue | `VUE.md`（未來） | vue-developer（未來） |

### 🎯 通用規範範圍

**CLAUDE.md 包含的通用規範**（跨語言/框架）:
- ✅ TDD 四階段流程
- ✅ 5W1H 決策框架
- ✅ Hook 系統機制
- ✅ 敏捷重構方法論
- ✅ 文件管理規範
- ✅ 永不放棄鐵律
- ✅ 測試設計哲學（抽象層級）
- ✅ 程式碼品質標準（設計原則層級）

**當前專案**: Flutter 移動應用程式
- 語言特定規範請參考：[`FLUTTER.md`](./FLUTTER.md)

---

## 🚨 任何行動前的強制檢查清單

**💡 記憶口訣**: 測試先行，問題必解，架構為王，品質不妥協

### 四大不可違反的鐵律

1. **測試通過率鐵律**
   **100% 通過率是最低標準**
   - 任何測試失敗 = 立即修正，其他工作全部暫停
   - 不存在「夠好的通過率」，只有 100% 或失敗

2. **永不放棄鐵律**
   **沒有無法解決的問題**
   - 遇到複雜問題 → 設計師分析 → 分解 → 逐一解決
   - 禁用詞彙：「太複雜」「暫時」「跳過」「之後再改」

3. **架構債務零容忍鐵律**
   **架構問題 = 立即停止功能開發**
   - 發現設計缺陷 → 立即修正 → 繼續開發
   - 修復成本隨時間指數增長，立即處理是唯一選擇
   - **判斷標準**：遇到引用問題先判斷是設計問題還是實作問題
   - **設計問題**：立即停止 → 全局分析 → 修正設計 → 繼續
   - **實作問題**：按原計劃修復

4. **TDD 四階段完整執行鐵律**
   **四階段流程不可中斷、不可簡化、不可跳過**
   - Phase 1-3 完成後 → 強制進入 Phase 4，無例外
   - 禁止 PM 判斷「可否跳過」→ 必須分派 cinnamon-refactor-owl 評估
   - 禁用詞彙：「跳過 Phase 4」「輕量級檢查」「簡化重構」「看起來很好不用重構」
   - **即使程式碼品質 A+，也要執行完整 Phase 4 評估**

### ⚡ 30秒快速檢查

- [ ] 測試通過率是否 100%？不是則立即修正
- [ ] 是否想跳過/暫緩任何問題？違反永不放棄原則
- [ ] 是否發現架構債務？立即停止功能開發優先修正
- [ ] Phase 3 完成後是否立即分派 Phase 4？不是則違反 TDD 鐵律
- [ ] Phase 4 完成後是否立即提交？不是則違反版本存檔原則

---

## 🔍 問題覺察與評估原則（決策前強制思考）

**核心問題**：避免「分批思維」導致的局部優化

### 全局分析優先原則

**錯誤的決策模式**：
- ❌ 遇到問題 → 立即修復 → 分批處理
- ❌ 提供選項A/B/C → 推薦「分階段處理」
- ❌ 發現設計問題 → 繼續其他步驟

**正確的決策模式**：
- ✅ 遇到問題 → 全局分析 → 策略規劃 → 系統性執行
- ✅ 提供選項 → 必須基於完整全局分析
- ✅ 發現設計問題 → 立即停止 → 修正設計 → 繼續

### 策略規劃先行原則

**強制執行順序**：
1. **全局分析**：完整識別所有相關問題和依賴
2. **策略規劃**：建立解決所有問題的完整策略
3. **Ticket 設計**：分解為可執行的最小單元
4. **系統執行**：按計劃逐一完成（可分批但已有全局規劃）

**分批執行的正確定義**：
- ✅ 正確：有完整策略和全部 Ticket → 按優先序逐一執行
- ❌ 錯誤：沒有完整策略 → 邊做邊規劃 → 局部優化

### 設計問題立即停止原則

**判斷標準**：
- **設計問題**：架構不合理、職責不清、引用關係錯誤
  - 處理方式：立即停止功能開發 → 修正設計 → 繼續
- **實作問題**：語法錯誤、邏輯缺陷、測試失敗
  - 處理方式：按原計劃修復

**關鍵問題**：
- 遇到引用問題時，不應該問「要先修復還是完成其他步驟」
- 應該問「這是設計問題還是實作問題」
- 設計問題 = 立即修正，無例外

### ⚡ 快速檢查

- [ ] 做決策前是否進行全局分析？
- [ ] 是否建立完整策略再執行？
- [ ] 遇到設計問題是否立即停止？
- [ ] 是否避免「分批思維」和局部優化？

**完整的問題覺察與評估方法論請參考**：[🔍 問題覺察與評估方法論]($CLAUDE_PROJECT_DIR/.claude/methodologies/problem-awareness-evaluation-methodology.md)

---

## 🎯 5W1H 自覺決策框架

**每個開發決策必須經過 5W1H 系統化思考框架**，確保決策品質和防止重複實作，並確保遵循敏捷重構原則。

### 🔍 5W1H 強制決策流程

**每個 todo 建立前必須回答**：
- ✅ **Who (誰)**：明確區分執行者和分派者，確保符合敏捷重構分工原則
- ✅ **What (什麼)**：功能定義清晰，符合單一職責原則
- ✅ **When (何時)**：觸發時機明確，副作用完整識別
- ✅ **Where (何地)**：執行位置正確，符合架構分層
- ✅ **Why (為什麼)**：需求依據充分，非逃避性動機
- ✅ **How (如何)**：任務類型明確，實作策略完整，遵循TDD原則

### 🔑 5W1H Token 強制執行機制

**所有對話必須遵循 5W1H 決策框架並以 Token 開頭**

- **格式**: `5W1H-{YYYYMMDD}-{HHMMSS}-{random}`
- **範例**: `5W1H-20250925-191735-a7b3c2`
- **生成**: SessionStart Hook 自動生成當前 Session Token
- **儲存位置**: `.claude/hook-logs/5w1h-tokens/session-*.token`

**強制回答格式**：

```text
🎯 5W1H-{當前Token}
Who: [責任歸屬分析]
What: [功能定義]
When: [觸發時機]
Where: [執行位置]
Why: [需求依據]
How: [實作策略]

[具體回答內容]
```

**完整的 5W1H 決策框架請參考**：[5W1H 自覺決策方法論]($CLAUDE_PROJECT_DIR/.claude/methodologies/5w1h-self-awareness-methodology.md)

### 📋 改進後的 5W1H 格式（敏捷重構合規）

**Who 格式**（明確區分執行者和分派者）：
```markdown
Who: {執行代理人} (執行者) | {分派者} (分派者)
```

**適用場景**：
- **代理人執行實作**：`Who: parsley-flutter-developer (執行者) | rosemary-project-manager (分派者)`
- **主線程自行執行職責**：`Who: rosemary-project-manager (自行執行 - 分派/驗收)`
- **文件代理人執行**：`Who: thyme-documentation-integrator (執行者) | rosemary-project-manager (分派者)`

**How 格式**（加入任務類型標記）：
```markdown
How: [Task Type: {任務類型}] {具體實作策略}
```

**任務類型分類**：
- **Implementation** - 程式碼實作（必須由執行代理人執行）
- **Dispatch** - 任務分派（主線程執行）
- **Review** - 驗收檢查（主線程執行）
- **Documentation** - 文件更新（文件代理人或主線程執行）
- **Analysis** - 問題分析（設計代理人或主線程執行）
- **Planning** - 策略規劃（主線程或設計代理人執行）

### 🚨 敏捷重構合規性檢查

**強制檢查規則**（防止主線程違反敏捷重構原則）：

**違反組合** ❌：
- `Task Type: Implementation` + `Who` 執行者是主線程 → 主線程不應執行程式碼實作
- `Task Type: Dispatch` + `Who` 執行者是代理人 → 代理人不應分派任務

**正確組合** ✅：
- `Task Type: Implementation` + `Who` 執行者是執行代理人
- `Task Type: Dispatch` + `Who` 執行者是主線程
- `Task Type: Review` + `Who` 執行者是主線程
- `Task Type: Documentation` + `Who` 執行者是文件代理人或主線程

**完整範例對照**：

❌ **錯誤範例**（違反敏捷重構原則）：
```markdown
🎯 5W1H-20251018-113517-WTKVy1
Who: 主線程建立缺失的 Domain 事件類別
What: 建立 7 個缺失的 Domain 事件
How: 參考現有事件設計模式 → 建立類別 → 加入 export
```
**問題**：主線程不應執行 Implementation 任務

✅ **正確範例**（遵循敏捷重構原則）：
```markdown
🎯 5W1H-20251018-120000-mfwuQf
Who: parsley-flutter-developer (執行者) | rosemary-project-manager (分派者)
What: 建立 7 個缺失的 Domain 事件類別
When: EventBus 實例化問題已解決，測試需要完整事件定義
Where: lib/domains/import/events/ 目錄
Why: 測試設計時規劃了這些事件，Phase 3b 需補齊實作
How: [Task Type: Implementation] 參考現有事件模式 → 建立類別 → 加入 export → 執行測試
```

---

## 🤖 Hook 系統 (品質保證機制)

本專案採用 Hook 系統作為 **5W1H 決策框架的技術實施**，提供自動化品質保證。

### 🔧 Hook 系統核心定位

**Hook 系統角色**：
- **主要機制**：5W1H 決策框架強制實施
- **品質保證**：自動化檢查和驗證
- **持續監控**：全方位開發品質追蹤

#### Hook 系統執行的檢查項目

- ✅ **環境檢查** - SessionStart Hook 於啟動時執行
- ✅ **合規性檢查** - UserPromptSubmit Hook 於每次用戶輸入時檢查
- ✅ **5W1H 決策檢查** - 5W1H Compliance Hook 確保每個todo經過完整思考
- ✅ **永不放棄鐵律** - Task Avoidance Detection Hook 偵測逃避行為並進入修復模式
- ✅ **程式碼品質** - Code Smell Detection Hook 即時偵測程式異味並追蹤問題
- ✅ **文件同步** - PostEdit Hook 於程式碼變更時提醒文件更新
- ✅ **效能監控** - Performance Monitor Hook 持續監控系統效能
- ✅ **版本推進** - Version Check Hook 分析工作狀態並建議版本推進策略
- ✅ **PM 觸發檢查** - PM Trigger Hook 檢測專案管理介入時機並啟動 PM 檢視

### 📋 Hook 系統參考文件

**完整的 Hook 系統技術規格和使用指南請參考**：
- [🚀 Hook 系統方法論]($CLAUDE_PROJECT_DIR/.claude/methodologies/hook-system-methodology.md) - 完整的設計原理和執行邏輯
- [🔧 Hook 系統快速參考]($CLAUDE_PROJECT_DIR/.claude/hook-system-reference.md) - 日常使用指南和故障排除
- [📚 Hook 開發參考文件體系]($CLAUDE_PROJECT_DIR/docs/hooks/README.md) - 完整的 Hook 開發指南和範例

### 🚨 重要提醒

1. **不要嘗試繞過 Hook 系統** - 它是品質保證的核心機制
2. **理解修復模式** - 系統檢測到問題時會進入修復模式，專注於修正問題
3. **查看報告** - Hook 系統會生成詳細報告，幫助理解和解決問題
4. **信任 Hook 系統** - Hook 系統比手動檢查更可靠和完整

### ⚙️ Hook 系統環境要求

**關鍵配置文件**：Hook 系統依賴 `.claude/settings.local.json` 配置文件才能正常運作

**重要**: 此配置文件包含專案的核心品質控制機制，必須在所有開發環境中保持一致。

---

## 📝 標準提交流程

### 🚨 小版本完成即提交原則（強制）

**核心原則**：小版本（vX.Y.Z）的 Phase 4 完成 = 立即提交做存底

**為什麼強制提交**：
- ✅ **安全性**：防止工作成果遺失
- ✅ **可回溯性**：提供版本回溯點
- ✅ **定期存檔**：確保工作進度有明確記錄
- ✅ **後續調整空間**：即使需要調整，也有提交記錄可以參考

**觸發條件**：
- Phase 4 完成，工作日誌標記版本完成
- 所有測試 100% 通過
- 重構評估完成（無論是否執行重構）

**強制要求**：
- ❌ 禁止「等一下再提交」
- ❌ 禁止「先做下一個版本再一起提交」
- ✅ 立即執行 git commit 並撰寫完整提交訊息
- ✅ 提交訊息必須包含 TDD 四階段摘要

### 🎯 Hook 系統提交管理

**所有提交相關的檢查和文件管理都由 Hook 系統執行**。

#### 可用指令

- `/commit-as-prompt` - Hook 系統提交流程（Claude Code 內建指令）

詳細流程請參考：[📝 標準提交流程文件]($CLAUDE_PROJECT_DIR/.claude/commit-workflow.md)

### 🚨 版本狀態評估強制流程（避免誤判）

**適用場景**：
- Session 啟動時評估當前版本進度
- 讀取工作日誌後判斷版本狀態
- 規劃下一步行動前確認當前狀態

**🔴 強制執行步驟（禁止跳過）**：

```bash
# 步驟 1: 先執行 git log 確認實際提交狀態
git log --oneline -5

# 步驟 2: 確認最新提交版本號
# 格式：feat(vX.Y.Z): [功能描述] - TDD 四階段完成

# 步驟 3: 對照工作日誌版本號
# 檢查是否一致
```

**版本狀態判斷標準**：

| 判斷項目 | 判斷依據 | 結論 |
|---------|---------|------|
| **已提交** | 最新 commit 訊息包含工作日誌版本號 | ✅ 版本已完成並提交 |
| **未提交** | 最新 commit 不是工作日誌版本號 | ❌ 需要立即提交 |
| **進行中** | 工作日誌顯示 Phase 1-3，Phase 4 未完成 | 🔄 繼續執行當前階段 |

---

## 🔍 主線程強制檢查清單（清單革命實踐）

本專案採用《清單革命》原則，建立三層檢查清單機制，確保主線程每次執行都經過完整檢查。

### 1️⃣ Session 啟動檢查清單

**使用時機**：每次 Session 啟動時執行
**使用模式**：DO-CONFIRM（操作確認模式）

**核心檢查項目**：
- [ ] Git 狀態確認
- [ ] 工作日誌存在且可讀取
- [ ] 思考過程記錄完整
- [ ] 三重文件一致性
- [ ] 明確本次 Session 目標任務

### 2️⃣ 任務執行檢查清單（派工前強制檢查）

**使用時機**：主線程分派任務給執行代理人之前
**使用模式**：READ-DO（步驟執行模式）

**核心檢查項目**：
- [ ] 派工理由已完整記錄
- [ ] Ticket 符合單一職責原則（參考 Atomic Ticket 方法論）
- [ ] 依賴和參考文件檢查
- [ ] 執行可行性檢查
- [ ] 品質保證檢查

### 3️⃣ 任務驗收檢查清單

**使用時機**：執行代理人完成任務提交 Review 時
**使用模式**：DO-CONFIRM（操作確認模式）

**核心檢查項目**：
- [ ] 所有驗收條件已逐項打勾確認
- [ ] TDD 四階段完整性檢查
- [ ] 測試通過率 100%
- [ ] 工作日誌已更新
- [ ] 三重文件一致性確認

**完整的檢查清單設計和使用模式請參考**：
- [🚀 敏捷重構方法論]($CLAUDE_PROJECT_DIR/.claude/methodologies/agile-refactor-methodology.md) - 包含協作檢查點、驗收暫停點設計

---

## 🚀 敏捷重構開發流程（標準運作方式）

本專案採用敏捷重構方法論，結合 TDD 四階段流程、三重文件協作原則和 Ticket 機制，建立完整的 Agent 分工協作模式。

### 📋 核心原則

#### 1. 主線程職責專一化

**主線程 (rosemary-project-manager) 職責**：
- 📋 依照主版本工作日誌分派任務給相應的子代理人
- 🎯 維持敏捷開發節奏和品質標準
- 📊 監控整體進度和三重文件一致性
- 🚨 處理升級請求和任務重新分派

**主線程禁止行為**：
- ❌ 禁止親自閱讀或修改程式碼
- ❌ 禁止執行具體的重構或實作工作
- ❌ 禁止繞過子代理人直接操作

#### 2. 三重文件協作原則

本專案採用三重文件機制（CHANGELOG + todolist + work-log）進行全方位進度管理和代理人協調：

**1️⃣ CHANGELOG.md** - 版本功能變動記錄（面向用戶）
**2️⃣ todolist.md** - 開發任務全景圖（任務狀態追蹤）
**3️⃣ work-log/** - 詳細實作記錄（技術細節和決策過程）

#### 3. 代理人協作機制

**執行代理人專業分工**：
- **lavender-interface-designer**: TDD Phase 1 功能設計
- **sage-test-architect**: TDD Phase 2 測試設計
- **pepper-test-implementer**: TDD Phase 3a 語言無關策略規劃
- **parsley-flutter-developer**: TDD Phase 3b Flutter 特定實作
- **cinnamon-refactor-owl**: TDD Phase 4 重構執行
- **mint-format-specialist**: 程式碼格式化和品質修正

**文件代理人職責**：
- **thyme-documentation-integrator**: 工作日誌 → 方法論轉化、方法論 → 核心文件整合、文件衝突檢測與解決
- **memory-network-builder**: 版本發布時從 `work-log` 提取功能變動到 `CHANGELOG.md`

### 📐 Ticket 系統

**核心原則**：Atomic Ticket = 一個 Action + 一個 Target（單一職責原則）

**可用指令**：
- `/ticket-create` - 建立符合單一職責的 Atomic Ticket
- `/ticket-track` - 查詢和更新 Ticket 狀態

**相關方法論**：
- [🎯 Atomic Ticket 方法論]($CLAUDE_PROJECT_DIR/.claude/methodologies/atomic-ticket-methodology.md) - 單一職責設計原則
- [📊 Frontmatter Ticket 追蹤方法論]($CLAUDE_PROJECT_DIR/.claude/methodologies/frontmatter-ticket-tracking-methodology.md) - 狀態追蹤機制
- [📋 Ticket 設計派工方法論]($CLAUDE_PROJECT_DIR/.claude/methodologies/ticket-design-dispatch-methodology.md) - 5W1H 設計標準
- [♻️ Ticket 生命週期管理方法論]($CLAUDE_PROJECT_DIR/.claude/methodologies/ticket-lifecycle-management-methodology.md) - 生命週期狀態

---

## 📚 分層文件管理規範

### 🏗 三層架構文件責任

本專案採用三層文件管理架構，**版本推進決策由 Version Check Hook 執行**：

**1️⃣ 工作日誌 (docs/work-logs/)** - 小版本開發追蹤
- 詳細的開發過程記錄
- TDD 四階段進度追蹤
- 技術實作過程文檔

**2️⃣ todolist.md** - 中版本功能規劃
- 當前版本系列目標規劃
- 功能模組優先級排序
- 下一步開發方向指引

**3️⃣ ROADMAP.md** - 大版本戰略藍圖
- 大版本里程碑定義
- 長期功能演進藍圖
- 架構演進計畫

詳細規範請參考：[📚 文件管理規範]($CLAUDE_PROJECT_DIR/.claude/document-responsibilities.md)

---

## 🎯 代理人分派機制（任務類型優先原則）

**🚨 重要原則：任務類型優先於專案類型**

### 📋 任務類型優先原則（強制遵循）

**Phase 3b 代理人分派決策樹**：

```text
1. 首先判斷任務類型：
   ├─ Hook 開發 → basil-hook-architect ✅
   ├─ 文件整合 → thyme-documentation-integrator ✅
   ├─ 程式碼格式化 → mint-format-specialist ✅
   ├─ 應用程式開發 → 進入步驟 2
   └─ 其他專業任務 → 對應專業代理人

2. 如果任務類型是「應用程式開發」，才判斷專案類型：
   ├─ Flutter 應用程式 → parsley-flutter-developer
   ├─ React 應用程式 → react-developer（未來）
   └─ 其他語言應用程式 → 對應語言代理人
```

### ⚠️ 常見錯誤與正確分派

| 任務描述 | ❌ 錯誤分派 | ✅ 正確分派 | 理由 |
|---------|-----------|-----------|------|
| **開發 Hook 腳本** | parsley-flutter-developer | **basil-hook-architect** | Hook 開發是專業任務 |
| **整合工作日誌到方法論** | parsley-flutter-developer | **thyme-documentation-integrator** | 文件整合是專業任務 |
| **格式化 Dart 程式碼** | 主線程 | **mint-format-specialist** | 格式化是專業任務 |
| **開發 Flutter Widget** | basil-hook-architect | **parsley-flutter-developer** | Flutter 應用程式開發 |

### 🔧 Startup Hook 自動分派（僅供參考）

**⚠️ 警告**：Startup Hook 的自動分派**僅基於專案類型**，無法判斷任務類型。

**主線程職責**：
- ✅ 必須根據**任務性質**手動判斷代理人
- ❌ 不應完全依賴 Startup Hook 自動分派
- ✅ Hook 開發、文件整合等專業任務 → 分派給專業代理人

**Startup Hook 分派邏輯**（僅供參考，不應直接使用）：

1. **檢測專案類型** - 檢查關鍵檔案 (pubspec.yaml, package.json, requirements.txt)
2. **載入語言配置** - 讀取對應的語言配置檔案 (FLUTTER.md, REACT.md, etc.)
3. **建議語言代理人** - 僅適用於應用程式開發任務

### ⚙️ TDD Phase 3 兩階段執行模式

**Phase 3a: 語言無關策略規劃**
- **執行代理人**: pepper-test-implementer
- **產出**: 虛擬碼、流程圖、架構決策（語言無關）

**Phase 3b: 語言/任務特定實作**
- **執行代理人**: **根據任務類型判斷**（參考上方決策樹）
- **輸入**: Phase 3a 虛擬碼 + 語言配置檔案
- **產出**: 可執行程式碼（符合語言規範）

### 📊 代理人專業領域清單

**專業任務代理人**（優先判斷）：
- **basil-hook-architect**: Hook 系統設計與實作
- **thyme-documentation-integrator**: 文件整合與轉化
- **mint-format-specialist**: 程式碼格式化和品質修正
- **lavender-interface-designer**: TDD Phase 1 功能設計
- **sage-test-architect**: TDD Phase 2 測試設計
- **pepper-test-implementer**: TDD Phase 3a 策略規劃
- **cinnamon-refactor-owl**: TDD Phase 4 重構執行
- **bay-quality-auditor**: 獨立技術品質審計專家（不考慮商業時程）
- **memory-network-builder**: 記憶網路建構

**語言特定代理人**（應用程式開發）：
- **parsley-flutter-developer**: Flutter/Dart 應用程式開發
- **react-developer** (未來): React 應用程式開發
- **vue-developer** (未來): Vue 應用程式開發
- **python-developer** (未來): Python 應用程式開發

### 🚨 主線程錯誤處理原則

**Hook 攔截後的自動恢復機制**

#### 錯誤識別與處理流程

**當 Hook 攔截到代理人分派錯誤時**：

1. **識別錯誤訊息格式**：
   ```text
   ❌ 代理人分派錯誤：
   任務類型：Hook 開發
   當前代理人：parsley-flutter-developer
   正確代理人：basil-hook-architect  ← 找這一行
   ```

2. **解析正確代理人**：
   - 從錯誤訊息中找到「正確代理人：XXX」
   - 這是應該重新分派的目標代理人

3. **重新分派任務**：
   ```python
   # 使用正確的代理人重新分派
   Task(
       subagent_type="basil-hook-architect",  # 正確代理人
       description="開發 Hook 腳本",
       prompt="[原始 prompt 內容]"
   )
   ```

#### 重試判斷標準

**需要重試的情況** ✅：
- 錯誤訊息包含「代理人分派錯誤」
- 錯誤訊息包含「正確代理人：」

**不需要重試的情況** ❌：
- 其他類型的錯誤（缺少參考文件、測試失敗等）
- 無法解析出正確代理人
- 已達最大重試次數（預設 1 次）

#### 無限循環防護

**內建保護機制**：
- **最大重試次數**：1 次（初始嘗試 + 1 次重試 = 最多 2 次調用）
- **解析失敗停止**：無法解析錯誤訊息時立即停止
- **非分派錯誤停止**：其他類型的錯誤不會觸發重試

#### 誤判處理

**常見誤判場景**：Phase 4 重構評估包含「Hook」關鍵字

**處理方式**：
```text
# 調整 prompt 移除混淆關鍵字
Before: "Phase 4: 代理人分派檢查 Hook 重構評估"
After:  "Phase 4: 代理人分派檢查功能重構評估"

# 或加入明確的任務類型前綴
After:  "[Phase 4 重構] 代理人分派檢查 Hook 重構評估"
```

#### 糾正歷史記錄（可選）

**記錄糾正歷史以追蹤分派錯誤模式**：

```python
from agent_dispatch_recovery import record_agent_correction

record_agent_correction(
    task_type="Hook 開發",
    wrong_agent="parsley-flutter-developer",
    correct_agent="basil-hook-architect",
    prompt_preview="建立 Hook 來檢查代理人分派"
)
```

**查看糾正歷史**：
```bash
# 查看最近 10 筆糾正記錄
python .claude/hooks/agent_dispatch_recovery.py history 10

# 查看統計資訊
python .claude/hooks/agent_dispatch_recovery.py stats
```

#### 參考文件

**完整使用指南**：
- [📖 代理人分派自動重試與錯誤恢復指南]($CLAUDE_PROJECT_DIR/docs/agent-dispatch-auto-retry-guide.md) - 完整指南
- [🚀 快速參考卡片]($CLAUDE_PROJECT_DIR/.claude/quick-ref-agent-dispatch-recovery.md) - 3 步驟快速恢復

**工具和實作**：
- [🔧 錯誤恢復工具模組]($CLAUDE_PROJECT_DIR/.claude/hooks/agent_dispatch_recovery.py) - Python 工具模組
- [🧪 測試套件]($CLAUDE_PROJECT_DIR/.claude/hooks/tests/test_error_recovery.py) - 15 個測試案例

---

## 🔧 開發工具和指令

### 🤖 Serena MCP - 智慧程式碼檢索與編輯工具

**Serena 是強大的程式碼代理工具包，提供類似 IDE 的語意程式碼檢索和編輯功能**

**核心功能**：
- **符號層級程式碼檢索** - 直接查找函式、類別、變數等程式符號
- **關係結構探索** - 分析程式碼間的依賴和引用關係
- **精準程式碼編輯** - 在特定符號位置插入或修改程式碼

**主要使用場景**：
1. 重構任務 - 快速找到所有引用並進行批量修改
2. 程式碼分析 - 理解複雜的依賴關係和呼叫鏈
3. 精準修改 - 在特定位置插入程式碼而不影響其他部分
4. 符號追蹤 - 追蹤函式或類別的使用情況

### 📚 Context7 MCP - 最新語法查詢工具

**Context7 MCP 是專門用於查詢最新 API 文件和語法的工具，用於解決棄用警告問題**

**使用時機**：
- 接收到棄用語法警告時 - 立即使用 Context7 查詢替代語法
- API 更新檢查 - 確保使用最新的 Flutter/Dart API
- 第三方套件升級 - 查詢套件最新版本的用法變更
- 最佳實踐確認 - 驗證當前實作是否符合最新標準

**語言特定工具鏈指令（測試、建置、品質檢查）請參考**：[`FLUTTER.md`](./FLUTTER.md)

---

## 🚨 錯誤處理規範強制要求

**專案採用原生 Exception + ErrorCode 簡化架構**

**所有錯誤修復和重構必須遵循**：[🔧 錯誤修復和重構方法論]($CLAUDE_PROJECT_DIR/.claude/methodologies/error-fix-refactor-methodology.md)

### 強制規範

**1. 統一導入語句**

```dart
// ✅ 統一導入錯誤處理系統
import 'package:book_overview_app/core/errors/errors.dart';
```

**2. 推薦使用順序**

**第一優先 - 預編譯錯誤** (最佳效能 < 0.01ms)：
```dart
throw CommonErrors.titleRequired;       // 標題必填
throw CommonErrors.networkTimeout;      // 網路超時
throw CommonErrors.bookNotFound;        // 書籍不存在
```

**第二選擇 - 專用異常類別**：
```dart
throw ValidationException.requiredField('author');
throw NetworkException.timeout(url: 'https://api.example.com');
throw BusinessException.bookNotFound('ISBN-123456');
```

**第三選擇 - AppException 通用類別**：
```dart
throw AppException(
  errorCode: ErrorCode.validationFailed,
  userMessage: '自訂錯誤訊息',
  context: {'additionalInfo': 'value'},
);
```

**錯誤類別分類**：
- **ValidationException**: 資料驗證錯誤
- **NetworkException**: 網路連線和 API 錯誤
- **BusinessException**: 業務邏輯錯誤
- **StorageException**: 儲存和檔案系統錯誤
- **PlatformException**: Flutter 平台特有錯誤
- **AppException**: 通用應用程式錯誤

詳細實作請參考：`lib/core/errors/errors.dart` 和 `lib/core/utils/operation_result.dart`

---

## 🎯 測試設計哲學強制原則

**核心原則**: 測試必須耦合到行為而非結構，重構時測試保持穩定

**適用範圍**: 本章節定義**語言無關的測試設計原則**，適用於所有程式語言和框架

### 🎯 測試行為而非結構（核心原則）⭐

> **"Tests should be coupled to the behavior of the code and decoupled from the structure of code."**
> — Kent Beck, Test Driven Development By Example

**關鍵區別**:

| 測試目標 | 耦合到行為 ✅ | 耦合到結構 ❌ |
|---------|------------|------------|
| 測試對象 | Module API（需求） | Class Methods（實作） |
| 測試知識 | 只知道Public API | 知道所有內部結構 |
| 重構影響 | 測試不變 | 測試破裂 |
| 維護成本 | 低 | 高 |

**驗證方法**: 如果你在重構時需要修改測試，表示測試耦合到結構（錯誤）。

### 🔍 Sociable vs Solitary Unit Tests

本專案推薦使用**Sociable Unit Tests**作為預設測試策略：

**Sociable Unit Tests** (Classical TDD - Kent Beck, Martin Fowler) ✅:
- **Unit** = Module（1個或多個類別）
- **Isolation** = 只隔離外部世界（Database, File System, External Services）
- **測試目標** = Module API（黑盒測試）
- **Mock策略** = 只Mock外部依賴，不Mock其他類別
- **優勢** = 測試穩定、重構安全、低維護成本

**Solitary Unit Tests** (Mockist TDD) ⚠️:
- **Unit** = Class
- **Isolation** = 隔離所有協作者（包括其他類別）
- **測試目標** = 每個類別的內部結構（白盒測試）
- **Mock策略** = Mock所有協作者
- **劣勢** = 測試脆弱、重構時破裂、高維護成本

**適用場景判斷表**:

| 專案類型 | 推薦方法 | 理由 |
|---------|---------|------|
| 業務應用程式 | ✅ Sociable | 關注業務流程，結構變化頻繁 |
| CRUD應用 | ✅ Sociable | 邏輯簡單，不需細粒度測試 |
| 數學演算法 | ⚠️ Solitary | 複雜計算需要細粒度驗證 |
| 金融計算 | 🔀 混合 | UseCase用Sociable，演算法用Solitary |

**預設原則**: 優先使用Sociable，只在確實需要細粒度驗證時才用Solitary。

### ✅ 正確的測試設計原則

**原則1: 測試耦合到行為**（最重要）
- 測試透過Module的Public API與系統互動
- 測試不知道Module內部有哪些類別
- 測試不知道類別之間的協作關係

**原則2: 只Mock外部依賴**
- Database → Mock（Test Double）
- File System → Mock（Test Double）
- External Services → Mock（Test Double）
- **其他類別 → 使用真實物件** ⭐
- **Domain Entities → 使用真實物件** ⭐

**原則3: 精確輸入輸出驗證**
- Mock N筆資料 → 必須產生 N筆結果
- 驗證可觀察的行為結果

**原則4: 行為驗證優於指標驗證**
- 驗證邏輯行為而非效能指標
- 問題暴露策略 - 效能問題 → 修改程式架構，不調整測試標準

**原則5: 可控資源原則**
- 只測試我們完全控制的輸入、處理、輸出
- 測試不依賴外部資源或假設性限制

### 🔄 重構安全性驗證

**檢查清單** - 驗證測試是否耦合到行為：

```markdown
重構類型檢查：
- [ ] 重構內部邏輯 → 測試無需修改？
- [ ] 改變演算法 → 測試無需修改？
- [ ] 調整類別結構 → 測試無需修改？
- [ ] 替換實作方式 → 測試無需修改？

如果全部「測試無需修改」→ 測試耦合到行為 ✅
如果任何「測試需修改」→ 測試耦合到結構 ❌
```

### 📚 語言特定測試實作

**測試設計原則是語言無關的，但測試實作方式依賴具體語言和框架**：

- **Flutter/Dart**: 參考 [`FLUTTER.md`](./FLUTTER.md) - Widget 測試、Mock 策略、測試框架使用
- **React** (未來): 參考 `REACT.md` - Component 測試、Jest/Testing Library
- **Python** (未來): 參考 `PYTHON.md` - pytest、mock、unittest
- **Vue** (未來): 參考 `VUE.md` - Component 測試、Vitest

### 🎓 相關方法論參考

完整的理論基礎和實務指引請參考：

- [🎯 行為優先TDD方法論]($CLAUDE_PROJECT_DIR/.claude/methodologies/behavior-first-tdd-methodology.md) - Sociable vs Solitary詳細對比、歷史證據
- [🧪 BDD測試方法論]($CLAUDE_PROJECT_DIR/.claude/methodologies/bdd-testing-methodology.md) - Given-When-Then格式
- [📋 混合測試策略方法論]($CLAUDE_PROJECT_DIR/.claude/methodologies/hybrid-testing-strategy-methodology.md) - 分層測試決策樹
- [🧭 程式碼品質範例彙編]($CLAUDE_PROJECT_DIR/.claude/code-quality-examples.md) - 具體範例

---

## 📚 專案特定規範與文檔體系

**本專案採用完整的文檔導向開發模式，所有開發活動必須遵循專案文檔規範**

### 📋 核心規範文檔

**Startup Check Hook 檢查以下核心文檔的存在和更新狀態**：

- `docs/app-requirements-spec.md` - 應用程式需求規格書
- `docs/app-use-cases.md` - 詳細用例說明
- `docs/ui_design_specification.md` - UI 設計規格書
- `docs/test-pyramid-design.md` - 測試金字塔設計
- `docs/code-quality-examples.md` - 程式碼品質範例
- `docs/app-error-handling-design.md` - 錯誤處理設計
- `test/TESTING_GUIDELINES.md` - Widget 測試指導原則
- `docs/domain-transformation-layer-design.md` - Domain轉換層整體架構設計
- `docs/event-driven-architecture-design.md` - 事件驅動架構詳細設計

### 📖 文檔優先開發原則

**開發流程必須遵循文檔規範**：

1. **需求變更**：先更新 `app-requirements-spec.md`
2. **UI 修改**：先確認 `ui_design_specification.md`
3. **架構調整**：先檢視 `event-driven-architecture-design.md`
4. **測試策略**：遵循 `test-pyramid-design.md` 和 `TESTING_GUIDELINES.md`
5. **錯誤處理**：按照 `app-error-handling-design.md` 設計模式

詳細文檔導引請參考：[📚 docs/README.md](./docs/README.md)

---

## 🏗 程式碼品質規範

### Package 導入路徑語意化規範（強制）

**所有程式碼必須遵循「[Package 導入路徑語意化方法論]($CLAUDE_PROJECT_DIR/.claude/methodologies/package-import-methodology.md)」**

**核心原則**：
- **架構透明性**：導入路徑清楚表達模組架構層級和責任
- **語意化格式**：使用 `package:book_overview_app/` 格式，禁用相對路徑
- **禁用別名和隱藏機制**：不允許使用 `as` 別名或 `hide` 機制，強制重構命名解決衝突
- **命名品質評估**：發現命名重複時應評估命名合理性，確保名稱正確傳達意義

**強制要求**：
- 100% 使用 package 格式導入，0% 相對路徑
- 禁用所有別名導入和 hide 機制，發現重名衝突必須重構命名
- 命名衝突處理原則：往上追溯使用更好的命名，而非使用導入機制繞過

### 程式碼自然語言化撰寫規範（強制）

**所有程式碼必須遵循「[程式碼自然語言化撰寫方法論]($CLAUDE_PROJECT_DIR/.claude/methodologies/natural-language-programming-methodology.md)」**

**核心原則**：
- **自然語言可讀性**：程式碼如同閱讀自然語言般流暢
- **五行函式單一職責**：每個函式控制在5-10行，確保單一職責
- **事件驅動語意化**：if/else 判斷必須正確分解為事件處理
- **變數職責專一化**：每個變數只承載單一類型資料，無縮寫

**強制要求**：
- 函式超過10行必須拆分
- 包含多個事件邏輯必須分解為事件驅動架構
- 變數不可兼用於不同用途

### 註解撰寫規範（強制）

**所有程式碼必須遵循「[程式碼註解撰寫方法論]($CLAUDE_PROJECT_DIR/.claude/methodologies/comment-writing-methodology.md)」**

**核心原則**：
- **程式碼自說明**：函式和變數命名必須完全可讀，不依賴註解理解
- **註解記錄需求**：註解不解釋程式做什麼，而是記錄為什麼這樣設計
- **維護指引**：提供修改約束和相依性警告，保護原始需求意圖

### 系統化除錯規範（強制）

**所有除錯修復必須遵循「[🔧 系統化除錯方法論]($CLAUDE_PROJECT_DIR/.claude/methodologies/systematic-debugging-methodology.md)」**

**核心原則**：
- **根因分析優先**：區分未完成實作vs過度設計vs程式碼風格問題
- **風險導向排序**：按業務風險等級確定修復優先序
- **主從分工模式**：主線程管控進度，代理人執行修復

詳細範例請參考：[🧭 程式碼品質範例彙編]($CLAUDE_PROJECT_DIR/.claude/code-quality-examples.md)

---

## 📚 重要文件參考

### 核心規範文件

- [🤝 TDD 協作開發流程]($CLAUDE_PROJECT_DIR/.claude/tdd-collaboration-flow.md) - 四階段開發流程
- [📚 專案文件責任明確區分]($CLAUDE_PROJECT_DIR/.claude/document-responsibilities.md) - 文件寫作規範
- [🤖 Agent 協作規範]($CLAUDE_PROJECT_DIR/.claude/agent-collaboration.md) - Sub-agent 使用指南
- [🚀 敏捷重構方法論]($CLAUDE_PROJECT_DIR/.claude/methodologies/agile-refactor-methodology.md) - Agent 分工協作模式和三重文件原則
- [🔧 錯誤修復和重構方法論]($CLAUDE_PROJECT_DIR/.claude/methodologies/error-fix-refactor-methodology.md) - 物件導向和測試驅動的修復標準
- [🔧 系統化除錯方法論]($CLAUDE_PROJECT_DIR/.claude/methodologies/systematic-debugging-methodology.md) - 基於v0.8.19實戰的unused警告修復標準流程

### Hook 系統文件

**核心方法論與參考**：
- [🚀 Hook 系統方法論]($CLAUDE_PROJECT_DIR/.claude/methodologies/hook-system-methodology.md) - 完整技術說明
- [🔧 Hook 系統快速參考]($CLAUDE_PROJECT_DIR/.claude/hook-system-reference.md) - 使用指南

**完整開發參考文件** (docs/hooks/ - 4,477 行, 100KB):
- [📚 Hook 開發索引]($CLAUDE_PROJECT_DIR/docs/hooks/README.md) - 完整文件索引和快速開始
- [🎯 Hook 基礎]($CLAUDE_PROJECT_DIR/docs/hooks/01-hook-fundamentals.md) - 9 種 Hook 類型和 JSON 格式
- [💡 Hook 最佳實踐]($CLAUDE_PROJECT_DIR/docs/hooks/02-hook-best-practices.md) - IndyDevDan 哲學和設計原則
- [🔧 UV Single-File Pattern]($CLAUDE_PROJECT_DIR/docs/hooks/03-uv-single-file-pattern.md) - Astral UV 和 PEP 723
- [📋 Hook 範例集]($CLAUDE_PROJECT_DIR/docs/hooks/04-hook-examples.md) - 10 個實用範例
- [🔊 語音通知整合]($CLAUDE_PROJECT_DIR/docs/hooks/05-voice-notification.md) - TTS 整合指南
- [✅ 開發檢查清單]($CLAUDE_PROJECT_DIR/docs/hooks/06-development-checklist.md) - 7 階段 100+ 檢查項

**技術規格與實作報告** (.claude/hook-specs/ - 3,575 行):
- [📋 敏捷重構 Hook 規格]($CLAUDE_PROJECT_DIR/.claude/hook-specs/agile-refactor-hooks-specification.md) - 5 個 Hook 完整規格
- [📖 Claude Code Hook 官方標準]($CLAUDE_PROJECT_DIR/.claude/hook-specs/claude-code-hooks-official-standards.md) - 官方規範總結
- [🔄 實作調整說明]($CLAUDE_PROJECT_DIR/.claude/hook-specs/implementation-adjustments.md) - 基於官方規範的調整
- [📊 功能重疊分析]($CLAUDE_PROJECT_DIR/.claude/hook-specs/agile-refactor-hooks-overlap-analysis.md) - 實作決策分析
- [✅ 完整實作總結]($CLAUDE_PROJECT_DIR/.claude/hook-specs/complete-implementation-summary.md) - 測試驗證和技術統計

**專業代理人**：
- [🏗 Basil Hook Architect]($CLAUDE_PROJECT_DIR/.claude/agents/basil-hook-architect.md) - Hook 設計與實作專家
- [🌿 Thyme Documentation Integrator]($CLAUDE_PROJECT_DIR/.claude/agents/thyme-documentation-integrator.md) - 文件整合專家

### 文件整合代理人支援文件

- [📖 Thyme 使用指南]($CLAUDE_PROJECT_DIR/.claude/docs/thyme-documentation-integrator-usage-guide.md) - 主線程分派任務手冊
- [🔧 Thyme MCP 整合指南]($CLAUDE_PROJECT_DIR/.claude/docs/thyme-mcp-integration-guide.md) - Serena 和 Context7 MCP 使用細節
- [🆘 Thyme 疑難排解指南]($CLAUDE_PROJECT_DIR/.claude/docs/thyme-troubleshooting-guide.md) - 常見問題快速解決參考

### 品質標準文件

- [🧭 程式碼品質範例彙編]($CLAUDE_PROJECT_DIR/.claude/code-quality-examples.md) - 具體範例
- [📋 格式化修正案例範例集]($CLAUDE_PROJECT_DIR/.claude/format-fix-examples.md) - 標準化修正模式

---

## 語言規範

**所有回應必須使用繁體中文 (zh-TW)**

參考文件：[專案用語規範字典]($CLAUDE_PROJECT_DIR/.claude/terminology-dictionary.md)

**核心原則**:
1. **精確性優先**: 使用具體、明確的技術術語
2. **台灣在地化**: 優先使用台灣慣用的程式術語
3. **技術導向**: 明確說明實際的技術實現方式

**重要禁用詞彙**:
- ❌ 「智能」→ ✅「Hook 系統腳本」、「規則比對」、「條件判斷」
- ❌ 「文檔」→ ✅「文件」
- ❌ 「數據」→ ✅「資料」
- ❌ 「默認」→ ✅「預設」

---

## 📊 任務追蹤管理

### Hook 系統任務管理

**所有任務記錄和狀態追蹤都由 Hook 系統執行**：

- 🤖 **Code Smell Detection Hook** - 偵測程式異味並啟動 agents 更新 todolist
- 📋 **問題強制追蹤** - Issue Tracking Hook 於發現問題時記錄到 `.claude/hook-logs/issues-to-track.md`
- 🔄 **狀態同步** - TodoWrite 工具管理任務狀態

### 任務管理檔案

- `docs/todolist.md` - 開發任務追蹤
- `docs/work-logs/` - 詳細開發工作日誌
- `CHANGELOG.md` - 版本變更記錄

### 里程碑追蹤

- v0.0.x: 基礎架構與測試框架
- v0.x.x: 開發階段，逐步實現功能
- v1.0.0: 完整功能，準備上架 Chrome Web Store

---

# important-instruction-reminders

**本專案所有品質控制、流程檢查、問題追蹤都由 Hook 系統執行。**

請信任並配合 Hook 系統的運作，專注於解決技術問題而非繞過檢查機制。Hook 系統是為了確保專案品質和開發效率的重要基礎設施。
