#!/bin/bash

# task-avoidance-detection-hook.sh
# UserPromptSubmit/Stop Hook: 偵測並阻止 AI 逃避困難任務

# 設定路徑和日誌
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOG_FILE="$PROJECT_ROOT/.claude/hook-logs/task-avoidance-$(date +%Y%m%d_%H%M%S).log"
AVOIDANCE_REPORT_DIR="$PROJECT_ROOT/.claude/hook-logs/avoidance-reports"

# 確保目錄存在
mkdir -p "$PROJECT_ROOT/.claude/hook-logs"
mkdir -p "$AVOIDANCE_REPORT_DIR"

# 日誌函數
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "🚨 Task Avoidance Detection Hook: 開始偵測任務逃避行為"

cd "$PROJECT_ROOT"

# 0. 檢查是否處於修復模式
FIX_MODE_FILE="$PROJECT_ROOT/.claude/TASK_AVOIDANCE_FIX_MODE"
if [ -f "$FIX_MODE_FILE" ]; then
    log "🔧 目前處於修復模式，允許修正逃避問題"

    # 檢查修復模式是否過期 (30分鐘)
    if [ -n "$(find "$FIX_MODE_FILE" -mmin +30 2>/dev/null)" ]; then
        log "⚠️  修復模式已過期，重新啟動檢查"
        rm -f "$FIX_MODE_FILE"
    else
        log "✅ 修復模式生效中，跳過逃避檢查"
        exit 0
    fi
fi

# 1. 定義禁用詞彙 (重新設計：專注於真正的逃避行為)
FORBIDDEN_PHRASES=(
    # 品質妥協和逃避責任
    "太複雜"
    "先將就"
    "暫時性修正"
    "症狀緩解"
    "先這樣處理"
    "臨時解決方案"
    "回避"
    "不想處理"
    "懶得改"
    "更簡單的方法"
    "採用更簡單的方法"
    "用更簡單的方法"
    "選擇更簡單的方法"
    "找更簡單的方法"
    "改用更簡單的方法"
    "用簡單的方式"
    "簡單的處理方式"
    "簡化處理"

    # 發現問題但不解決的逃避模式
    "發現問題但不處理"
    "架構問題先不管"
    "程式異味先忽略"
    "只加個 TODO"
    "先記錄到 TODO"
    "這個問題之後再看"
    "問題太多先跳過"
    "技術債務之後處理"

    # 測試品質妥協
    "簡化測試"
    "降低測試標準"
    "測試要求太嚴格"
    "放寬測試條件"
    "測試太複雜"
    "簡單測試就好"
    "基本測試即可"
    "簡化測試環境"

    # 英文逃避詞彙
    "workaround"
    "bypass"
    "too complex"
    "too complicated"
    "quick fix"
    "temporary fix"
    "hack"
    "ignore for now"
    "disable"
    "comment out"
    "just add todo"
    "will fix later"
    "skip for now"
    "avoid dealing with"
    "simpler approach"
    "simpler way"
    "easier approach"
    "take the simpler approach"
    "use a simpler method"

    # 模糊不精確詞彙
    "智能"

    # 測試品質妥協英文詞彙
    "simplify test"
    "simplified test"
    "basic test only"
    "lower test standard"
    "reduce test complexity"
    "test too strict"
    "relax test requirement"
    "minimal test"
    "simple test case"
    "easier test"
)

# 可接受的開發用語 (不觸發逃避檢測)
ACCEPTABLE_PHRASES=(
    # 分階段開發和計畫
    "v0.1 階段實作"
    "v0.2 階段實作"
    "分階段開發"
    "迭代開發"
    "最小可行實作"
    "TDD 最小實現"

    # 有計畫的功能規劃
    "規劃於後續版本"
    "列入下一個迭代"
    "功能拓展計畫"
    "介面預留設計"
    "架構擴展性考量"

    # 正當的範圍管理
    "不在本次範圍"
    "功能範圍界定"
    "需求邊界設定"

    # 英文可接受用語
    "planned for v0.2"
    "future enhancement"
    "out of scope"
    "not in this iteration"
    "minimal viable implementation"
    "interface for future extension"
)

# 2. 檢查最近的 Claude 輸出和工作日誌
log "🔍 檢查最近的工作記錄中是否包含逃避性語言"

AVOIDANCE_DETECTED=false
DETECTED_PHRASES=()
AVOIDANCE_SOURCES=()

# 檢查最新的工作日誌
LATEST_WORKLOG=$(ls "docs/work-logs/" 2>/dev/null | grep '^v[0-9]' | sort -V | tail -1)
if [ -n "$LATEST_WORKLOG" ]; then
    WORKLOG_PATH="docs/work-logs/$LATEST_WORKLOG"
    log "📋 檢查工作日誌: $LATEST_WORKLOG"

    for phrase in "${FORBIDDEN_PHRASES[@]}"; do
        if grep -q "$phrase" "$WORKLOG_PATH" 2>/dev/null; then
            # 檢查上下文是否包含可接受的計畫性用語
            CONTEXT_ACCEPTABLE=false
            MATCHING_LINES=$(grep -n "$phrase" "$WORKLOG_PATH" 2>/dev/null)

            while IFS= read -r line; do
                if [ -n "$line" ]; then
                    LINE_NUM=$(echo "$line" | cut -d: -f1)
                    # 檢查前後5行是否有可接受的用語或程式碼片段
                    CONTEXT=$(sed -n "$((LINE_NUM-5)),$((LINE_NUM+5))p" "$WORKLOG_PATH" 2>/dev/null)

                    # 檢查是否在程式碼片段中
                    if echo "$CONTEXT" | grep -q "\`\`\`" 2>/dev/null; then
                        CONTEXT_ACCEPTABLE=true
                        log "ℹ️  發現 '$phrase' 但在程式碼片段中，視為技術描述"
                    fi

                    # 檢查是否有計畫性用語
                    if [ "$CONTEXT_ACCEPTABLE" = false ]; then
                        for acceptable in "${ACCEPTABLE_PHRASES[@]}"; do
                            if echo "$CONTEXT" | grep -q "$acceptable" 2>/dev/null; then
                                CONTEXT_ACCEPTABLE=true
                                log "ℹ️  發現 '$phrase' 但有計畫性上下文: '$acceptable'"
                                break
                            fi
                        done
                    fi

                    # 檢查是否為技術名詞（如 eslint-disable）
                    if [ "$CONTEXT_ACCEPTABLE" = false ]; then
                        if echo "$CONTEXT" | grep -q "eslint-disable\|npm-disable\|git-disable" 2>/dev/null; then
                            CONTEXT_ACCEPTABLE=true
                            log "ℹ️  發現 '$phrase' 但為技術工具名稱，視為正當用法"
                        fi
                    fi

                    if [ "$CONTEXT_ACCEPTABLE" = false ]; then
                        AVOIDANCE_DETECTED=true
                        DETECTED_PHRASES+=("$phrase")
                        AVOIDANCE_SOURCES+=("工作日誌: $LATEST_WORKLOG")
                        log "⚠️  在工作日誌中發現逃避詞彙: '$phrase'"
                        break  # 只需要記錄一次這個詞彙
                    fi
                fi
            done <<< "$MATCHING_LINES"
        fi
    done
fi

# 檢查最近的 Git 提交訊息
RECENT_COMMITS=$(git log --oneline -5)
while IFS= read -r commit; do
    for phrase in "${FORBIDDEN_PHRASES[@]}"; do
        if echo "$commit" | grep -q "$phrase" 2>/dev/null; then
            AVOIDANCE_DETECTED=true
            DETECTED_PHRASES+=("$phrase")
            AVOIDANCE_SOURCES+=("Git 提交: $commit")
            log "⚠️  在提交訊息中發現禁用詞彙: '$phrase'"
        fi
    done
done <<< "$RECENT_COMMITS"

# 檢查 todolist.md 中的逃避性描述
if [ -f "docs/todolist.md" ]; then
    log "📋 檢查 todolist.md 中的任務描述"

    for phrase in "${FORBIDDEN_PHRASES[@]}"; do
        if grep -q "$phrase" "docs/todolist.md" 2>/dev/null; then
            AVOIDANCE_DETECTED=true
            DETECTED_PHRASES+=("$phrase")
            AVOIDANCE_SOURCES+=("TodoList: docs/todolist.md")
            log "⚠️  在 todolist 中發現禁用詞彙: '$phrase'"
        fi
    done
fi

# 3. 檢查未完成的測試或錯誤
log "🧪 檢查是否有未解決的問題被標記為'暫時跳過'"

# 檢查測試檔案中的 skip 或 pending (快速檢查)
SKIPPED_TESTS=$(find tests/ -name "*.test.js" -type f -exec grep -l "skip\|pending\|xdescribe\|xit" {} + 2>/dev/null)
if [ -n "$SKIPPED_TESTS" ]; then
    AVOIDANCE_DETECTED=true
    AVOIDANCE_SOURCES+=("測試檔案中發現跳過的測試")
    log "⚠️  發現被跳過的測試:"
    echo "$SKIPPED_TESTS" | while read test_file; do
        SKIP_COUNT=$(grep -c "skip\|pending\|xdescribe\|xit" "$test_file" 2>/dev/null || echo "0")
        log "  - $test_file: $SKIP_COUNT 個跳過的測試"
    done
fi

# 檢查 ESLint 錯誤是否被忽略而非修復 (快速檢查)
ESLINT_IGNORE_COUNT=$(find src/ -name "*.js" -type f -exec grep -c "eslint-disable" {} + 2>/dev/null | awk '{sum += $1} END {print sum+0}')
if [ "$ESLINT_IGNORE_COUNT" -gt 5 ]; then
    AVOIDANCE_DETECTED=true
    AVOIDANCE_SOURCES+=("發現過多的 ESLint 忽略指令 ($ESLINT_IGNORE_COUNT 處)")
    log "⚠️  發現過多的 ESLint 忽略指令: $ESLINT_IGNORE_COUNT 處"
fi

# 4. 檢查技術債務累積趨勢
log "📈 檢查技術債務累積趨勢"

# 統計 TODO/FIXME/HACK 標記 (快速檢查)
TODO_COUNT=$(find src/ -name "*.js" -type f -exec grep -c "TODO\|FIXME\|HACK" {} + 2>/dev/null | awk '{sum += $1} END {print sum+0}')
log "📊 當前技術債務標記總數: $TODO_COUNT"

# 檢查是否有新增的技術債務
if [ "$TODO_COUNT" -gt 15 ]; then
    AVOIDANCE_DETECTED=true
    AVOIDANCE_SOURCES+=("技術債務累積過多 ($TODO_COUNT 個標記)")
    log "⚠️  技術債務累積過多: $TODO_COUNT 個標記"
fi

# 5. 分析問題解決方式是否完整
log "🔍 分析問題解決完整性"

# 檢查最近的變更是否有完整的測試覆蓋
RECENT_SRC_CHANGES=$(git diff --name-only HEAD~1 2>/dev/null | grep "src/.*\.js$" | wc -l)
RECENT_TEST_CHANGES=$(git diff --name-only HEAD~1 2>/dev/null | grep "test.*\.js$" | wc -l)

if [ "$RECENT_SRC_CHANGES" -gt 0 ] && [ "$RECENT_TEST_CHANGES" -eq 0 ]; then
    AVOIDANCE_DETECTED=true
    AVOIDANCE_SOURCES+=("程式碼變更 ($RECENT_SRC_CHANGES 檔案) 但沒有對應的測試更新")
    log "⚠️  程式碼有變更但缺少測試更新"
fi

# 6. 如果偵測到逃避行為，生成阻止報告
if [ "$AVOIDANCE_DETECTED" = true ]; then
    log "🚨 偵測到任務逃避行為，生成阻止報告"

    REPORT_FILE="$AVOIDANCE_REPORT_DIR/avoidance-detected-$(date +%Y%m%d_%H%M%S).md"
    cat > "$REPORT_FILE" << EOF
# 🚨 任務逃避行為偵測報告

**偵測時間**: $(date)
**狀態**: ❌ 發現逃避行為，任務未完成

## 🚨 永不放棄鐵律違反

根據 CLAUDE.md 的永不放棄鐵律：
> **沒有無法解決的問題**
> - 遇到複雜問題 → 設計師分析 → 分解 → 逐一解決
> - 禁用詞彙：「太複雜」「暫時」「跳過」「之後再改」

## 🔍 偵測到的逃避行為

EOF

    # 列出發現的禁用詞彙
    if [ ${#DETECTED_PHRASES[@]} -gt 0 ]; then
        echo "### 禁用詞彙使用" >> "$REPORT_FILE"
        echo "" >> "$REPORT_FILE"
        for i in "${!DETECTED_PHRASES[@]}"; do
            echo "- **'${DETECTED_PHRASES[$i]}'** 在 ${AVOIDANCE_SOURCES[$i]}" >> "$REPORT_FILE"
        done
        echo "" >> "$REPORT_FILE"
    fi

    # 列出其他逃避行為
    echo "### 其他逃避模式" >> "$REPORT_FILE"
    echo "" >> "$REPORT_FILE"
    for source in "${AVOIDANCE_SOURCES[@]}"; do
        if [[ ! "$source" =~ "禁用詞彙" ]]; then
            echo "- $source" >> "$REPORT_FILE"
        fi
    done

    cat >> "$REPORT_FILE" << EOF

## 🛑 必須執行的修正行動

### 立即要求 (不可妥協)

1. **重新分析問題**
   - 將複雜問題分解為可管理的小步驟
   - 為每個步驟制定具體的解決方案
   - 不允許「暫時跳過」任何發現的問題

2. **移除所有逃避性語言**
   - 修改工作日誌，移除禁用詞彙
   - 重新描述任務，使用積極解決的語言
   - 將「暫時」改為「計劃在X步驟解決」

3. **完整解決技術債務**
   - 修復所有 ESLint 錯誤 (不允許 disable)
   - 為新程式碼補充缺失的測試
   - 重構所有標記為 TODO/FIXME 的程式碼

4. **恢復測試覆蓋**
   - 取消所有 skip 的測試
   - 修復失敗的測試，不允許忽略
   - 確保 100% 測試通過率

### 🔄 執行策略

#### 問題分解範例:
\`\`\`
原始表述: "這個功能太複雜，暫時簡化處理"
正確分解:
1. 分析功能需求的核心組件
2. 識別每個組件的技術挑戰
3. 為每個挑戰設計具體解決方案
4. 按優先級逐一實現
5. 整合並驗證完整功能
\`\`\`

#### 技術債務處理:
\`\`\`bash
# 不允許的做法
// TODO: 這部分太複雜，之後再處理

# 正確的做法
// 立即重構: 使用 Strategy Pattern 解決複雜邏輯
\`\`\`

## ⚡ 強制執行檢查清單

- [ ] 移除所有禁用詞彙
- [ ] 重新分解複雜問題
- [ ] 修復所有跳過的測試
- [ ] 處理所有技術債務標記
- [ ] 達到 100% ESLint 通過率
- [ ] 補充缺失的測試覆蓋
- [ ] 重新提交完整的解決方案

## 🚨 警告

**此報告表示當前任務未完成。**

根據永不放棄鐵律，**不允許提交、推進版本或繼續新任務**，直到所有逃避行為被糾正且問題被完整解決。

EOF

    log "📋 任務逃避阻止報告已生成: $REPORT_FILE"

    # 7. 設定修復模式 (取代阻止標記)
    cat > "$FIX_MODE_FILE" << EOF
FIX_MODE_STARTED=true
START_TIME="$(date)"
REPORT_FILE=$REPORT_FILE
DETECTED_ISSUES_COUNT=${#DETECTED_PHRASES[@]}
FIX_REASON="永不放棄鐵律違反 - 發現任務逃避行為"

# 此檔案表示系統進入修復模式，允許修正逃避問題
# 修復完成後請移除此檔案以重新啟動檢查
EOF

    log "🔧 已啟動修復模式: $FIX_MODE_FILE"

    # 8. 生成強制修正腳本
    FORCE_FIX_SCRIPT="$PROJECT_ROOT/.claude/hook-logs/force-fix-avoidance.sh"
    cat > "$FORCE_FIX_SCRIPT" << 'EOF'
#!/bin/bash

# force-fix-avoidance.sh
# 強制修正任務逃避行為的腳本

echo "🚨 強制修正任務逃避行為"
echo ""
echo "請按照以下步驟完成修正:"
echo ""
echo "1. 📋 檢查報告"
echo "   cat $1"
echo ""
echo "2. 🔧 修正工作日誌"
echo "   # 移除所有禁用詞彙，重新描述解決方案"
echo ""
echo "3. 🧪 修復測試"
echo "   # 取消所有 skip 的測試並修復"
echo "   npm test"
echo ""
echo "4. 🔍 修復 ESLint 錯誤"
echo "   npm run lint:fix"
echo ""
echo "5. 📝 處理技術債務"
echo "   # 將所有 TODO/FIXME 轉換為實際解決方案"
echo ""
echo "6. ✅ 確認修正完成"
echo "   # 確保所有檢查通過後執行:"
echo "   rm .claude/TASK_AVOIDANCE_FIX_MODE"
echo ""

EOF

    chmod +x "$FORCE_FIX_SCRIPT"
    log "🔧 強制修正腳本已建立: $FORCE_FIX_SCRIPT"

    # 9. 返回成功狀態 (不阻止操作，但記錄問題)
    log "⚠️  任務逃避行為偵測完成 - 已啟動修復模式"
    exit 0  # 不阻止操作，允許修復

else
    log "✅ 未偵測到任務逃避行為，開發流程正常"

    # 移除可能存在的修復模式
    if [ -f "$FIX_MODE_FILE" ]; then
        rm -f "$FIX_MODE_FILE"
        log "🔓 移除修復模式，恢復正常檢查"
    fi
fi

# 10. 清理舊的逃避報告 (保留最近5個)
find "$AVOIDANCE_REPORT_DIR" -name "avoidance-detected-*.md" | sort -r | tail -n +6 | xargs rm -f 2>/dev/null

log "✅ Task Avoidance Detection Hook 執行完成"

# 正常情況下返回成功
exit 0