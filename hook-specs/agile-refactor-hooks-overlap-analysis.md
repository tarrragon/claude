# 敏捷重構 Hook 功能重疊分析報告

## 📊 分析目的

在實作敏捷重構方法論 Hook 前，分析現有 Hook 系統是否已有類似功能，決定是擴充現有 Hook 還是新建獨立 Hook。

## 📋 現有 Hook 清單

### 1. SessionStart Hook
- **腳本**: `startup-check-hook.sh`
- **功能**: 環境檢查、Git 狀態、文件載入、5W1H Token 生成

### 2. UserPromptSubmit Hook
- **腳本**: `prompt-submit-hook.sh`
- **功能**: 測試通過率檢查、架構債務檢查、5W1H 合規性檢查、TDD Phase 完整性觸發
- **調用**: `tdd-phase-check-hook.sh`, `task-avoidance-detection-hook.sh`, `pre-design-dependency-check.sh`

### 3. PostToolUse Hook (Edit/Write)
- **腳本**: `post-edit-hook.sh`
- **功能**: 檔案變更偵測、技術債務標記、測試覆蓋提醒、文件同步檢查

### 4. TDD Phase Check Hook
- **腳本**: `tdd-phase-check-hook.sh`
- **功能**: 檢查 TDD 四階段完整性、逃避語言偵測、Phase 3→4 轉換檢查

### 5. Work Log Check Hook
- **腳本**: `check-work-log.sh`
- **功能**: 工作日誌完成狀態、技術債務指標、測試狀態、版本推進評估

### 6. Task Avoidance Detection Hook
- **腳本**: `task-avoidance-detection-hook.sh`
- **功能**: 逃避行為偵測、技術債務累積檢查、問題完整性分析

### 7. Code Smell Detection Hook
- **腳本**: `code-smell-detection-hook.sh`
- **功能**: 程式異味偵測並啟動 agents 更新 todolist

### 8. Pre-Commit Hook
- **腳本**: `pre-commit-hook.sh`
- **功能**: 提交前檢查

### 9. PM Trigger Hook
- **腳本**: `pm-trigger-hook.sh`
- **功能**: 專案管理介入時機檢測

---

## 🔍 新 Hook 需求與現有 Hook 功能對照

### Hook 1: 主線程職責檢查

#### 新 Hook 需求
- **目的**: 防止主線程親自修改程式碼
- **檢查項目**:
  - 偵測 Edit/Write 工具使用
  - 檢查 lib/ 目錄修改
  - 偵測 Bash 程式碼操作指令

#### 現有功能重疊分析
| 功能點 | 現有 Hook | 重疊程度 | 分析 |
|--------|----------|---------|------|
| 檔案修改偵測 | `post-edit-hook.sh` | 🟡 部分重疊 | 已偵測檔案變更，但未檢查**誰**修改 |
| 操作類型檢查 | `prompt-submit-hook.sh` | 🔴 無重疊 | 無檢查主線程操作類型 |
| 違規提醒 | 無 | 🔴 無重疊 | 無主線程職責違規機制 |

#### 決策：**擴充 `post-edit-hook.sh`**

**理由**：
- `post-edit-hook.sh` 已在 PostToolUse Hook 執行，觸發時機正確
- 可新增「主線程操作檢查」區塊
- 避免新增獨立 Hook 增加系統複雜度

**實作方式**：
```bash
# 新增到 post-edit-hook.sh

# 6. 主線程職責檢查 (敏捷重構方法論要求)
log "🔍 主線程職責檢查"

# 檢查是否修改 lib/ 目錄程式碼檔案
LIB_CHANGES=$(echo "$RECENT_CHANGES" | grep -E "^[AM].*lib/.*\.dart$" | wc -l)
if [ "$LIB_CHANGES" -gt 0 ]; then
    log "⚠️  偵測到主線程修改 lib/ 目錄程式碼"
    log "📋 敏捷重構方法論要求: 主線程禁止親自修改程式碼"
    log "✅ 正確做法: 使用 Task 工具分派給專業 agent 執行"

    # 進入修復模式
    REMINDER_FILE="$PROJECT_ROOT/.claude/hook-logs/main-thread-violation-$(date +%Y%m%d_%H%M%S).md"
    cat > "$REMINDER_FILE" <<EOF
## 🚨 主線程職責違規 - $(date)

### 違規行為
- 主線程直接修改 lib/ 目錄程式碼
- 修改檔案數: $LIB_CHANGES 個

### 正確做法
1. 使用 Task 工具分派任務給專業 agent
2. 例如: mint-format-specialist (格式化)
3. 例如: pepper-test-implementer (實作)
4. 例如: cinnamon-refactor-owl (重構)

### 參考文件
- 敏捷重構方法論: .claude/methodologies/agile-refactor-methodology.md
- 主線程職責: 只負責分派和統籌，禁止親自執行程式碼修改

EOF

    log "📋 已生成主線程違規追蹤: $REMINDER_FILE"
fi
```

---

### Hook 2: 任務分派準備度檢查

#### 新 Hook 需求
- **目的**: 確保任務分派前完成準備度檢查清單
- **檢查項目**:
  - UseCase 參考完整性
  - 流程圖 Event 具體性
  - 架構規範引用
  - 依賴類別列舉
  - 測試設計參考
  - 影響範圍評估

#### 現有功能重疊分析
| 功能點 | 現有 Hook | 重疊程度 | 分析 |
|--------|----------|---------|------|
| Pre-Design 依賴檢查 | `pre-design-dependency-check.sh` | 🟡 部分重疊 | 檢查 Phase 1 設計依賴 |
| 任務分派檢查 | 無 | 🔴 無重疊 | 無專門的任務分派準備度檢查 |
| 文件完整性 | 無 | 🔴 無重疊 | 無參考文件完整性檢查機制 |

#### 決策：**新建獨立 Hook**

**理由**：
- 現有 Hook 無專門的任務分派前檢查機制
- 需要在 **PreToolUse (Task)** 時觸發，現有 Hook 無此觸發點
- 準備度檢查項目多且專門，獨立 Hook 更清晰

**實作方式**：
```bash
# 新建 task-dispatch-readiness-check.sh
# 整合到 settings.local.json PreToolUse Hook

"PreToolUse": [
  {
    "matcher": "Task",
    "hooks": [
      {
        "type": "command",
        "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/task-dispatch-readiness-check.sh"
      }
    ]
  }
]
```

---

### Hook 3: 三重文件一致性檢查

#### 新 Hook 需求
- **目的**: 確保 CHANGELOG/todolist/work-log 三重文件同步
- **檢查項目**:
  - 版本號一致性
  - 任務狀態同步
  - 功能描述一致性

#### 現有功能重疊分析
| 功能點 | 現有 Hook | 重疊程度 | 分析 |
|--------|----------|---------|------|
| 版本同步檢查 | `check-version-sync.sh` | 🟢 高度重疊 | 已檢查版本同步 |
| 工作日誌檢查 | `check-work-log.sh` | 🟢 高度重疊 | 已檢查工作日誌狀態 |
| Todolist 檢查 | `prompt-submit-hook.sh` | 🟡 部分重疊 | 檢查 todolist 更新時間 |
| CHANGELOG 檢查 | 無 | 🔴 無重疊 | 無 CHANGELOG 一致性檢查 |

#### 決策：**擴充現有 Hook 組合**

**理由**：
- `check-version-sync.sh` 和 `check-work-log.sh` 已涵蓋大部分功能
- 只需新增 CHANGELOG 一致性檢查
- 可擴充 `check-version-sync.sh` 加入 CHANGELOG 檢查

**實作方式**：
```bash
# 擴充 check-version-sync.sh

# 新增 CHANGELOG 一致性檢查區塊
echo -e "${BLUE}📚 檢查 CHANGELOG 與 work-log 一致性${NC}"

# 提取 CHANGELOG 最新版本
CHANGELOG_VERSION=$(grep -E "^## v[0-9]+\.[0-9]+" "$PROJECT_ROOT/CHANGELOG.md" | head -1 | sed -E 's/^## v([0-9]+\.[0-9]+).*/\1/')

# 提取 work-log 最新主版本
LATEST_WORKLOG=$(ls -1 "$WORK_LOGS_DIR/" | grep -E "^v[0-9]+\.[0-9]+\.0-main\.md$" | sort -V | tail -1)
WORKLOG_VERSION=$(echo "$LATEST_WORKLOG" | sed -E 's/^v([0-9]+\.[0-9]+)\.0-main\.md$/\1/')

# 比較版本號
if [ "$CHANGELOG_VERSION" != "$WORKLOG_VERSION" ]; then
    echo -e "${RED}❌ 版本號不一致:${NC}"
    echo -e "   CHANGELOG: v$CHANGELOG_VERSION"
    echo -e "   work-log:  v$WORKLOG_VERSION"
    exit 1
fi
```

---

### Hook 4: 階段完成驗證

#### 新 Hook 需求
- **目的**: 強制執行 5 項檢查清單
- **檢查項目**:
  - 編譯完整性檢查
  - 依賴路徑一致性檢查
  - 測試通過率檢查 (100%)
  - 重複實作檢查
  - 架構一致性檢查

#### 現有功能重疊分析
| 功能點 | 現有 Hook | 重疊程度 | 分析 |
|--------|----------|---------|------|
| 編譯檢查 | `prompt-submit-hook.sh` | 🟡 部分重疊 | 有 lint 檢查，但不完整 |
| 測試通過率 | `post-test-hook.sh` | 🟢 高度重疊 | 已檢查測試結果 |
| 架構檢查 | `architecture-debt-detection-hook.sh` | 🟢 高度重疊 | 已檢查架構債務 |
| 路徑一致性 | 無 | 🔴 無重疊 | 無專門的路徑檢查 |
| 重複實作檢查 | `code-smell-detection-hook.sh` | 🟡 部分重疊 | 有程式異味檢查 |

#### 決策：**新建獨立 Hook**

**理由**：
- 階段完成驗證是**強制性品質門檻**，需要獨立機制
- 需要在 **Phase Completion** 時觸發（新觸發點）
- 5 項檢查需要統一執行和報告，獨立 Hook 更清晰

**實作方式**：
```bash
# 新建 stage-completion-validation-check.sh
# 整合到 Version Check Hook 或新建 Phase Completion Hook

# 在 check-work-log.sh 中，檢測到 Phase 完成時觸發
if [[ "$WORK_STATUS" == "COMPLETED" ]]; then
    # 執行階段完成驗證
    "$SCRIPT_DIR/stage-completion-validation-check.sh"
    validation_result=$?

    if [ $validation_result -ne 0 ]; then
        echo -e "${RED}❌ 階段完成驗證失敗，無法推進版本${NC}"
        exit 1
    fi
fi
```

---

### Hook 5: 代理人回報追蹤

#### 新 Hook 需求
- **目的**: 追蹤代理人回報問題並確保解決閉環
- **檢查項目**:
  - 回報記錄
  - 響應時間追蹤
  - 解決閉環確認

#### 現有功能重疊分析
| 功能點 | 現有 Hook | 重疊程度 | 分析 |
|--------|----------|---------|------|
| 問題追蹤 | `post-edit-hook.sh` | 🟡 部分重疊 | 記錄問題到 reminder 檔案 |
| Todolist 管理 | `check-todos.py` | 🟡 部分重疊 | 檢查 todo 狀態 |
| PM 觸發 | `pm-trigger-hook.sh` | 🟢 高度重疊 | 檢測專案管理介入時機 |
| 回報追蹤檔案 | 無 | 🔴 無重疊 | 無專門的回報追蹤機制 |

#### 決策：**擴充 `pm-trigger-hook.sh`**

**理由**：
- `pm-trigger-hook.sh` 已檢測專案管理介入時機
- 代理人回報追蹤是 PM 職責的延伸
- 可在 PM Trigger Hook 中新增回報追蹤區塊

**實作方式**：
```bash
# 擴充 pm-trigger-hook.sh

# 新增代理人回報追蹤區塊
log "📊 代理人回報追蹤檢查"

# 初始化追蹤檔案
REPORT_TRACKER="$CLAUDE_LOGS_DIR/agent-reports-tracker.md"
if [ ! -f "$REPORT_TRACKER" ]; then
    cat > "$REPORT_TRACKER" <<EOF
# 代理人回報追蹤記錄

## 進行中的回報

## 已解決的回報

EOF
fi

# 檢查進行中的回報
PENDING_REPORTS=$(grep -c "狀態.*待處理" "$REPORT_TRACKER" 2>/dev/null || echo "0")

if [ "$PENDING_REPORTS" -gt 0 ]; then
    log "⚠️  有 $PENDING_REPORTS 個待處理回報"
    log "💡 建議檢查回報響應時間和解決狀態"
fi
```

---

## 📊 總結決策表

| 新 Hook | 決策 | 整合方式 | 優先序 |
|---------|------|---------|--------|
| **Hook 1: 主線程職責檢查** | 擴充現有 | 擴充 `post-edit-hook.sh` | 🔴 高 (Phase 1) |
| **Hook 2: 任務分派準備度檢查** | 新建獨立 | 新建 `task-dispatch-readiness-check.sh` | 🟡 中 (Phase 2) |
| **Hook 3: 三重文件一致性檢查** | 擴充現有 | 擴充 `check-version-sync.sh` | 🟢 低 (Phase 3) |
| **Hook 4: 階段完成驗證** | 新建獨立 | 新建 `stage-completion-validation-check.sh` | 🔴 高 (Phase 1) |
| **Hook 5: 代理人回報追蹤** | 擴充現有 | 擴充 `pm-trigger-hook.sh` | 🟢 低 (Phase 4) |

---

## 🎯 實作計畫

### Phase 1: 核心檢查（立即實作）
1. ✅ **擴充 `post-edit-hook.sh`** - 新增主線程職責檢查區塊
2. ✅ **新建 `stage-completion-validation-check.sh`** - 實作 5 項檢查清單

### Phase 2: 準備度檢查（優先實作）
3. ✅ **新建 `task-dispatch-readiness-check.sh`** - 任務分派前強制檢查

### Phase 3: 一致性檢查（重要實作）
4. ✅ **擴充 `check-version-sync.sh`** - 新增 CHANGELOG 一致性檢查

### Phase 4: 追蹤管理（輔助實作）
5. ✅ **擴充 `pm-trigger-hook.sh`** - 新增代理人回報追蹤區塊

---

## 🔍 實作優勢分析

### 擴充現有 Hook 的優勢
- ✅ **降低系統複雜度** - 避免新增過多獨立 Hook
- ✅ **重用現有機制** - 利用已有的觸發點和日誌系統
- ✅ **維護成本低** - 集中管理相關功能
- ✅ **觸發效率高** - 減少 Hook 執行次數

### 新建獨立 Hook 的必要性
- ✅ **職責專一** - 任務分派和階段驗證需要獨立機制
- ✅ **觸發點不同** - PreToolUse (Task) 和 Phase Completion 是新觸發點
- ✅ **邏輯獨立** - 檢查邏輯複雜且專門，獨立更清晰

---

## 📋 下一步行動

### 立即執行
1. 更新 todo 狀態
2. 開始實作 Phase 1 核心檢查
3. 測試和驗證功能

### 分派任務
- **Hook 1 (擴充)**: `project-compliance-agent` - 擴充 post-edit-hook.sh
- **Hook 4 (新建)**: `sage-test-architect` - 新建 stage-completion-validation-check.sh
- **Hook 2 (新建)**: `project-compliance-agent` - 新建 task-dispatch-readiness-check.sh
- **Hook 3 (擴充)**: `memory-network-builder` - 擴充 check-version-sync.sh
- **Hook 5 (擴充)**: `rosemary-project-manager` - 擴充 pm-trigger-hook.sh

---

**版本**: v1.0
**建立日期**: 2025-10-09
**責任人**: rosemary-project-manager
**總結**: 5 個新 Hook 需求中，2 個新建、3 個擴充，避免系統複雜度提升同時確保功能完整。
