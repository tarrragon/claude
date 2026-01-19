#!/bin/bash

################################################################################
# Hook: 檢查硬編碼字串
#
# 目的: 防止 Presentation 層引入新的硬編碼 UI 字串
# 觸發: PreCommit（提交前檢查）
# 版本: v1.0
#
# 使用方式:
#   ./.claude/hooks/check-hardcoded-strings.sh [file_path]
#
# 舉例:
#   # 檢查單個檔案
#   ./.claude/hooks/check-hardcoded-strings.sh lib/presentation/import/widget.dart
#
#   # 檢查多個檔案
#   find lib/presentation -name "*.dart" -exec ./.claude/hooks/check-hardcoded-strings.sh {} \;
################################################################################

set -euo pipefail

# ============================================================================
# 配置
# ============================================================================

# 專案根目錄
PROJECT_ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || echo '/.')}"

# 日誌目錄
LOG_DIR="$PROJECT_ROOT/.claude/hook-logs/hardcoded-strings"
mkdir -p "$LOG_DIR"

# 時間戳
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
LOG_FILE="$LOG_DIR/check-$TIMESTAMP.log"
REPORT_FILE="$LOG_DIR/report-$TIMESTAMP.md"

# 檢查配置
ISSUES_FOUND=0
CHECKED_FILES=0

# ============================================================================
# 日誌函式
# ============================================================================

log_start() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ====== 硬編碼字串檢查開始 ======" >> "$LOG_FILE"
}

log_info() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 信息: $1" >> "$LOG_FILE"
}

log_error() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 錯誤: $1" >> "$LOG_FILE"
}

log_end() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ====== 檢查完成 ======" >> "$LOG_FILE"
}

# ============================================================================
# 檢查函式
# ============================================================================

check_hardcoded_strings() {
    local file_path="$1"

    # 驗證檔案存在
    if [ ! -f "$file_path" ]; then
        log_error "檔案不存在: $file_path"
        return 1
    fi

    # 排除測試檔案
    if [[ "$file_path" == *"/test/"* ]] || [[ "$file_path" == *"_test.dart" ]]; then
        log_info "跳過測試檔案: $file_path"
        return 0
    fi

    # 排除非 Presentation 層檔案（只檢查 presentation）
    if [[ "$file_path" != "lib/presentation/"* ]]; then
        log_info "跳過非 Presentation 層檔案: $file_path"
        return 0
    fi

    ((CHECKED_FILES++))

    # 檢查中文字串
    # 模式: 單引號或雙引號中的中文字符
    # 排除: AppLogger、日誌、註解、l10n 調用

    local matches=""
    local line_num=0

    while IFS= read -r line || [ -n "$line" ]; do
        ((line_num++))

        # 排除註解
        if [[ "$line" =~ ^[[:space:]]*// ]]; then
            continue
        fi

        # 排除 AppLogger 和日誌調用
        if [[ "$line" =~ AppLogger\.|print\(|debugPrint\(|log\( ]]; then
            continue
        fi

        # 排除 l10n 調用（l10n.xxx）
        if [[ "$line" =~ l10n\. ]]; then
            continue
        fi

        # 檢查中文字串模式
        # 檢查單引號中的中文
        if [[ "$line" =~ \'[^\']*[一-龥\u4E00-\u9FFF]+[^\']*\' ]]; then
            matches="$matches
檔案: $file_path (行 $line_num)
內容: $line"
        fi

        # 檢查雙引號中的中文
        if [[ "$line" =~ \"[^\"]*[一-龥\u4E00-\u9FFF]+[^\"]*\" ]]; then
            matches="$matches
檔案: $file_path (行 $line_num)
內容: $line"
        fi

    done < "$file_path"

    # 處理檢查結果
    if [ -n "$matches" ]; then
        log_error "在 $file_path 中檢測到硬編碼字串"
        ((ISSUES_FOUND++))
        echo "$matches" >> "$LOG_FILE"
        return 1
    else
        log_info "檢查通過: $file_path"
        return 0
    fi
}

# ============================================================================
# 報告生成
# ============================================================================

generate_report() {
    cat > "$REPORT_FILE" << EOF
# 硬編碼字串檢查報告

**檢查時間**: $(date '+%Y-%m-%d %H:%M:%S')
**檢查檔案數**: $CHECKED_FILES
**發現問題**: $ISSUES_FOUND

## 檢查結果

EOF

    if [ "$ISSUES_FOUND" -eq 0 ]; then
        cat >> "$REPORT_FILE" << EOF
✅ 所有檔案檢查通過，未發現硬編碼字串。

## 檢查詳情

檢查的檔案:
- lib/presentation/ 下所有 .dart 檔案
- 排除: test/ 目錄和 _test.dart 檔案

檢查規則:
- 單引號中的中文字符: '...[中文]...'
- 雙引號中的中文字符: "...[中文]..."

排除項:
- AppLogger 調用中的中文
- print/debugPrint 調用中的中文
- l10n 調用
- 測試檔案
- 註解

## 最佳實踐

### ✅ 正確做法

使用 AppLocalizations (l10n) 來管理所有 UI 文字:

\`\`\`dart
import 'package:book_overview_app/l10n/generated/app_localizations.dart';

Widget buildTitle(AppLocalizations l10n) {
  return Text(l10n.bookTitle); // 使用 l10n key
}
\`\`\`

### ❌ 錯誤做法

硬編碼字串:

\`\`\`dart
Widget buildTitle() {
  return Text('書籍標題'); // 硬編碼中文 - 不支援多語言
}
\`\`\`

### 📝 日誌可以使用中文

日誌訊息可以使用硬編碼的中文，無需 i18n:

\`\`\`dart
AppLogger.debug('檢查開始');
print('調試訊息: 載入完成');
\`\`\`

## 添加新的 i18n 字符

1. 編輯 lib/l10n/app_zh_TW.arb

\`\`\`json
{
  "newKey": "新的中文字符",
  "@newKey": {
    "description": "描述此字符的用途"
  }
}
\`\`\`

2. 執行代碼生成

\`\`\`bash
flutter gen-l10n
\`\`\`

3. 在 Dart 代碼中使用

\`\`\`dart
Text(l10n.newKey)
\`\`\`

## 詳細日誌

完整檢查日誌: \`$LOG_FILE\`

EOF
    else
        cat >> "$REPORT_FILE" << EOF
❌ 檢測到 $ISSUES_FOUND 處硬編碼字串，需要修復。

## 修復步驟

### Step 1: 查看詳細日誌

\`\`\`bash
cat $LOG_FILE
\`\`\`

### Step 2: 添加缺失的 i18n 字符

編輯 \`lib/l10n/app_zh_TW.arb\` 和 \`lib/l10n/app_en.arb\`:

\`\`\`json
{
  "newKey": "中文文字",
  "@newKey": {
    "description": "此字符的用途說明"
  }
}
\`\`\`

### Step 3: 生成 i18n 代碼

\`\`\`bash
flutter gen-l10n
\`\`\`

### Step 4: 更新 Dart 代碼

將硬編碼字符串改為 l10n 調用:

\`\`\`dart
// 之前
Text('書籍標題')

// 之後
Text(l10n.bookTitle)
\`\`\`

### Step 5: 重新提交

\`\`\`bash
git add .
git commit -m "fix(i18n): 完成硬編碼字符串 i18n"
\`\`\`

## 常見問題

### Q: 日誌訊息可以使用中文嗎？

A: 是的，日誌訊息不需要 i18n，可以使用硬編碼的中文:

\`\`\`dart
AppLogger.debug('檢查開始');
\`\`\`

### Q: 我想在 UI 中使用中文變數怎麼辦？

A: 使用 i18n 系統來管理所有 UI 文字。如果需要動態內容，可以使用 i18n 的參數功能。

### Q: 什麼時候修復硬編碼字符串？

A: 優先在 Phase 3 (實作階段) 完成。如發現存在的硬編碼字符串，建立 Ticket 在下個版本修復。

## 後續建議

1. 定期檢查新增的硬編碼字符串
2. 在 Code Review 中特別關注 Presentation 層變更
3. 更新開發指南，強調 i18n 的重要性
4. 考慮在 IDE 中添加 snippet，便利 i18n 使用

---

檢查日誌: $LOG_FILE
EOF
    fi
}

# ============================================================================
# 主程序
# ============================================================================

main() {
    log_start
    log_info "檢查開始"

    # 如果提供了檔案路徑，檢查該檔案
    if [ $# -gt 0 ]; then
        for file_path in "$@"; do
            check_hardcoded_strings "$file_path" || true
        done
    else
        # 否則檢查所有 Presentation 層檔案
        log_info "掃描 lib/presentation/ 目錄..."
        while IFS= read -r file_path; do
            check_hardcoded_strings "$file_path" || true
        done < <(find "$PROJECT_ROOT/lib/presentation" -name "*.dart" -type f)
    fi

    log_info "檢查完成。檢查檔案: $CHECKED_FILES，發現問題: $ISSUES_FOUND"
    generate_report
    log_end

    # 返回 Exit Code
    if [ "$ISSUES_FOUND" -gt 0 ]; then
        # 輸出報告到 stderr
        cat "$REPORT_FILE" >&2
        exit 2  # 阻塊錯誤
    fi

    exit 0
}

# 執行主程序
main "$@"
