#!/bin/bash

# post-edit-task-doc-validation.sh
# PostEdit Hook: 檢查工作日誌參考文件和影響範圍完整性
#
# 功能：
# 1. 檢查工作日誌是否包含「📋 參考文件」章節
# 2. 檢查工作日誌是否包含「📁 影響範圍」章節
# 3. 驗證參考文件子章節完整性
# 4. 驗證影響範圍子章節完整性
# 5. 生成詳細檢查報告
# 6. 提供補充建議模板
#
# 執行時機：工作日誌檔案建立或修改後
# 觸發條件：docs/work-logs/v*.*.*.md 檔案變更

# 載入專案通用函數
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common-functions.sh"

# 設定專案環境
if ! setup_project_environment; then
    echo "錯誤: 無法設定專案環境" >&2
    exit 1
fi

# 設定日誌檔案
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
LOG_FILE="$CLAUDE_LOGS_DIR/task-doc-validation-$TIMESTAMP.log"
REPORT_DIR="$CLAUDE_LOGS_DIR/task-doc-validation"
mkdir -p "$REPORT_DIR"

# 日誌函數
log() {
    log_with_timestamp "$LOG_FILE" "$1"
}

# 取得觸發檔案（從環境變數或參數）
EDITED_FILE="${CLAUDE_EDITED_FILE:-$1}"

log "📋 Task Documentation Validation Hook: 開始檢查"

# 如果沒有提供檔案，檢查最近修改的工作日誌
if [ -z "$EDITED_FILE" ]; then
    # 查找最近修改的工作日誌檔案
    EDITED_FILE=$(find "$CLAUDE_PROJECT_DIR/docs/work-logs" -name "v*.md" -type f -exec ls -t {} + 2>/dev/null | head -1)
fi

# 檢查檔案是否存在
if [ -z "$EDITED_FILE" ] || [ ! -f "$EDITED_FILE" ]; then
    log "📝 未發現工作日誌檔案變更，跳過檢查"
    exit 0
fi

# 取得檔案名稱
FILE_NAME=$(basename "$EDITED_FILE")

# 檢查是否為工作日誌檔案
if [[ ! "$FILE_NAME" =~ ^v[0-9]+\.[0-9]+\.[0-9]+ ]]; then
    log "📝 非工作日誌檔案: $FILE_NAME，跳過檢查"
    exit 0
fi

log "📄 檢查檔案: $EDITED_FILE"

# ============================================
# 檢查項目定義
# ============================================

# 強制章節
REQUIRED_SECTIONS=(
    "📋 參考文件"
    "📁 影響範圍"
)

# 參考文件必須的子章節
REQUIRED_REFERENCE_SUBSECTIONS=(
    "UseCase 參考"
    "流程圖參考"
    "架構規範"
    "依賴類別"
    "測試設計參考"
)

# 影響範圍必須的子章節
REQUIRED_IMPACT_SUBSECTIONS=(
    "需要建立的檔案"
    "需要修改的檔案"
    "預估影響的測試檔案"
    "影響的依賴關係"
)

# ============================================
# 檢查邏輯
# ============================================

# 檢查強制章節
missing_sections=()
for section in "${REQUIRED_SECTIONS[@]}"; do
    if ! grep -q "$section" "$EDITED_FILE"; then
        missing_sections+=("$section")
    fi
done

# 檢查參考文件子章節
missing_ref_subsections=()
if grep -q "📋 參考文件" "$EDITED_FILE"; then
    for subsection in "${REQUIRED_REFERENCE_SUBSECTIONS[@]}"; do
        if ! grep -q "$subsection" "$EDITED_FILE"; then
            missing_ref_subsections+=("$subsection")
        fi
    done
else
    # 如果連主章節都沒有，所有子章節都算缺失
    missing_ref_subsections=("${REQUIRED_REFERENCE_SUBSECTIONS[@]}")
fi

# 檢查影響範圍子章節
missing_impact_subsections=()
if grep -q "📁 影響範圍" "$EDITED_FILE"; then
    for subsection in "${REQUIRED_IMPACT_SUBSECTIONS[@]}"; do
        if ! grep -q "$subsection" "$EDITED_FILE"; then
            missing_impact_subsections+=("$subsection")
        fi
    done
else
    # 如果連主章節都沒有，所有子章節都算缺失
    missing_impact_subsections=("${REQUIRED_IMPACT_SUBSECTIONS[@]}")
fi

# ============================================
# 判斷檢查結果等級
# ============================================

check_status=""
status_emoji=""

if [ ${#missing_sections[@]} -gt 0 ]; then
    # 等級 3: 嚴重缺失（缺少強制章節）
    check_status="嚴重缺失"
    status_emoji="❌"
elif [ ${#missing_ref_subsections[@]} -gt 0 ] || [ ${#missing_impact_subsections[@]} -gt 0 ]; then
    # 等級 2: 部分缺失（強制章節存在，但子章節不完整）
    check_status="部分缺失"
    status_emoji="⚠️"
else
    # 等級 1: 完全符合
    check_status="完全符合規範"
    status_emoji="✅"
fi

# ============================================
# 生成檢查報告
# ============================================

REPORT_FILE="$REPORT_DIR/validation-$TIMESTAMP.md"

cat > "$REPORT_FILE" << EOF
# 任務文件合規性檢查報告

**檔案**: $EDITED_FILE
**檢查時間**: $(date '+%Y-%m-%d %H:%M:%S')
**檢查結果**: $status_emoji $check_status

---

## 📋 強制章節檢查

EOF

# 強制章節檢查結果
for section in "${REQUIRED_SECTIONS[@]}"; do
    if grep -q "$section" "$EDITED_FILE"; then
        echo "- [x] $section" >> "$REPORT_FILE"
    else
        echo "- [ ] ❌ $section **（缺失）**" >> "$REPORT_FILE"
    fi
done

cat >> "$REPORT_FILE" << EOF

---

## 📋 參考文件子章節檢查

EOF

# 參考文件子章節檢查結果
for subsection in "${REQUIRED_REFERENCE_SUBSECTIONS[@]}"; do
    if grep -q "$subsection" "$EDITED_FILE"; then
        echo "- [x] $subsection" >> "$REPORT_FILE"
    else
        echo "- [ ] ⚠️ $subsection **（缺失）**" >> "$REPORT_FILE"
    fi
done

cat >> "$REPORT_FILE" << EOF

---

## 📁 影響範圍子章節檢查

EOF

# 影響範圍子章節檢查結果
for subsection in "${REQUIRED_IMPACT_SUBSECTIONS[@]}"; do
    if grep -q "$subsection" "$EDITED_FILE"; then
        echo "- [x] $subsection" >> "$REPORT_FILE"
    else
        echo "- [ ] ⚠️ $subsection **（缺失）**" >> "$REPORT_FILE"
    fi
done

cat >> "$REPORT_FILE" << EOF

---

## 🎯 檢查結論

EOF

# 根據等級輸出結論
case "$check_status" in
    "完全符合規範")
        cat >> "$REPORT_FILE" << EOF
✅ **完全符合規範**

所有強制章節和子章節都已包含，代理人可以直接執行此任務。

EOF
        ;;
    "部分缺失")
        cat >> "$REPORT_FILE" << EOF
⚠️ **部分缺失**

強制章節存在，但部分子章節缺失。建議補充完整以提升代理人執行效率。

**缺失的子章節**：
EOF
        if [ ${#missing_ref_subsections[@]} -gt 0 ]; then
            echo "" >> "$REPORT_FILE"
            echo "**參考文件**：" >> "$REPORT_FILE"
            for subsection in "${missing_ref_subsections[@]}"; do
                echo "- $subsection" >> "$REPORT_FILE"
            done
        fi
        if [ ${#missing_impact_subsections[@]} -gt 0 ]; then
            echo "" >> "$REPORT_FILE"
            echo "**影響範圍**：" >> "$REPORT_FILE"
            for subsection in "${missing_impact_subsections[@]}"; do
                echo "- $subsection" >> "$REPORT_FILE"
            done
        fi
        echo "" >> "$REPORT_FILE"
        ;;
    "嚴重缺失")
        cat >> "$REPORT_FILE" << EOF
❌ **嚴重缺失**

缺少強制章節，根據敏捷重構方法論，此任務規劃不合格。

**缺失的強制章節**：
EOF
        for section in "${missing_sections[@]}"; do
            echo "- $section" >> "$REPORT_FILE"
        done
        cat >> "$REPORT_FILE" << EOF

⚠️ **違規處理**: 缺少任何一項參考文件或影響範圍資訊，視為**任務規劃不合格**，必須立即補充後才能分派給代理人執行。

EOF
        ;;
esac

# ============================================
# 補充建議（缺失時提供）
# ============================================

if [ "$check_status" != "完全符合規範" ]; then
    cat >> "$REPORT_FILE" << 'EOF'
---

## 💡 補充建議

### 📋 參考文件補充模板

```markdown
## 📋 參考文件（強制完整填寫）

### UseCase 參考（必須）

- **[UC-XX: 功能名稱](../app-use-cases.md#uc-xx)**
  - 主流程：使用者操作 → 系統處理 → 結果回饋
  - 錯誤處理：格式錯誤、業務規則驗證失敗等
  - 進度回饋：即時顯示進度和結果

**關聯性**: 本任務為 UC-XX 的 [Layer] 層基礎

### 流程圖參考（必須，具體到 Event）

**主流程圖**: [UC-XX 流程](../use-cases/[feature]/[flow-name].md)

**相關 Events**:
- **Event 1-2**: 功能步驟1
  - Event 1: 描述 → 類別/方法
  - Event 2: 描述 → 類別/方法

- **Event 3-5**: 功能步驟2
  - Event 3: 描述 → 類別/方法
  - Event 4: 描述 → 類別/方法
  - Event 5: 描述 → 類別/方法

**說明**: 本任務建立 Event X, Y, Z 所需的類別和方法

### 架構規範（必須）

- **[Clean Architecture 分層設計](../app-requirements-spec.md#clean-architecture)**
  - Domain 層：業務邏輯和介面定義
  - Infrastructure 層：具體實作
  - 依賴反轉原則：依賴介面而非實作

- **[DDD Value Object 設計規範](../app-requirements-spec.md#value-objects)**
  - 不可變性：使用 const 建構子
  - 自我驗證：透過工廠方法確保正確性
  - 等值性：使用 Equatable 實現值比較

- **[錯誤處理規範](../app-error-handling-design.md)**
  - 使用 AppException 體系
  - ErrorHandlingStrategy 定義錯誤處理策略

### 依賴類別（前置任務產出）

**既有 Domain 實體**:
- `ClassName1` (既有) - 類別說明
- `ClassName2` (既有) - 類別說明

**前置任務產出**:
- `ClassName3` (vX.Y.Z) - 類別說明
- `ClassName4` (vX.Y.Z) - 類別說明

**說明**: 這些類別已存在，本任務將整合這些既有功能

### 測試設計參考（TDD 必須）

**測試設計文件**: [測試設計文件路徑]

**測試檔案**:
- `test/path/to/test_file_test.dart` - 測試說明（N 個測試）

**測試覆蓋目標**:
- ClassName: 100% (所有方法)
- 效能基準: 操作時間 < Xms

### 實作範例（參考）

**類似重構案例**:
- [類似案例](./vX.Y.Z-work-log.md) - 案例說明

**範例程式碼**:
- `lib/path/to/example.dart` - 範例說明
```

---

### 📁 影響範圍補充模板

```markdown
## 📁 影響範圍

### 需要建立的檔案

**Domain 層**:
- `lib/domains/[feature]/[file].dart` - 檔案說明

**Infrastructure 層**:
- `lib/infrastructure/[feature]/[file].dart` - 檔案說明

### 需要修改的檔案

**重構檔案**:
- `lib/path/to/existing.dart` - 修改內容說明

**更新引用**:
- `lib/path/to/usage.dart` - 更新內容說明

**可能影響的檔案** (待評估):
- 所有引用特定類別的檔案（需透過 grep 確認）

### 預估影響的測試檔案

**需要更新**:
- `test/path/to/existing_test.dart` - 既有 N 個測試

**需要新建**:
- `test/path/to/new_test.dart` - 新增 N 個測試

**測試通過率目標**:
- 既有測試：N/N 保持 100%
- 新增測試：N+/N+ 達成 100%

### 影響的依賴關係

**被影響的上層模組** (後續 Phase 會使用):
- UI Layer: 說明
- Provider: 說明

**被影響的下層模組** (需更新引用):
- Service: 說明
```

---

## 📚 參考文件

- **敏捷重構方法論**: `.claude/methodologies/agile-refactor-methodology.md` (第 1277-1332 行)
- **任務規劃模板**: 參考上述模板章節
- **實際範例**: `docs/work-logs/v0.12.1-domain-interfaces.md` (已補充完整)

EOF
fi

# 保存報告結束
cat >> "$REPORT_FILE" << EOF

---

**報告生成時間**: $(date '+%Y-%m-%d %H:%M:%S')
**Hook 版本**: v1.0.0
EOF

# ============================================
# 輸出到控制台
# ============================================

if [ ${#missing_sections[@]} -eq 0 ]; then
    log "✅ 強制章節檢查通過 (${#REQUIRED_SECTIONS[@]}/${#REQUIRED_SECTIONS[@]})"
else
    log "❌ 缺少強制章節 (${#missing_sections[@]} 項)"
    for section in "${missing_sections[@]}"; do
        log "  - $section"
    done
fi

if [ ${#missing_ref_subsections[@]} -eq 0 ]; then
    log "✅ 參考文件子章節檢查通過 (${#REQUIRED_REFERENCE_SUBSECTIONS[@]}/${#REQUIRED_REFERENCE_SUBSECTIONS[@]} 必須項)"
else
    log "⚠️ 缺少參考文件子章節 (${#missing_ref_subsections[@]} 項)"
fi

if [ ${#missing_impact_subsections[@]} -eq 0 ]; then
    log "✅ 影響範圍子章節檢查通過 (${#REQUIRED_IMPACT_SUBSECTIONS[@]}/${#REQUIRED_IMPACT_SUBSECTIONS[@]} 必須項)"
else
    log "⚠️ 缺少影響範圍子章節 (${#missing_impact_subsections[@]} 項)"
fi

log "📊 檢查結果: $status_emoji $check_status"
log "📋 詳細報告: $REPORT_FILE"

# 嚴重缺失時顯示警告
if [ "$check_status" == "嚴重缺失" ]; then
    log ""
    log "🚨 任務規劃不合格"
    log ""
    log "根據敏捷重構方法論，工作日誌必須包含以下強制章節："
    log ""
    log "1. 📋 參考文件（強制完整填寫）"
    log "   - UseCase 參考"
    log "   - 流程圖參考（具體到 Event）"
    log "   - 架構規範"
    log "   - 依賴類別"
    log "   - 測試設計參考"
    log ""
    log "2. 📁 影響範圍"
    log "   - 需要建立的檔案"
    log "   - 需要修改的檔案"
    log "   - 預估影響的測試檔案"
    log "   - 影響的依賴關係"
    log ""
    log "💡 請補充缺失章節後再分派給代理人執行"
    log "📖 參考: .claude/methodologies/agile-refactor-methodology.md (第 1277-1332 行)"
    log ""
fi

log "✅ Task Documentation Validation Hook 執行完成"

# 返回成功（不阻止後續操作，只提供資訊）
exit 0
