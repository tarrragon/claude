#!/bin/bash
#
# test-summary.sh - 測試摘要腳本
# 功能: 執行 flutter test 並生成簡潔摘要
# 解決 flutter test 輸出過大問題 (4.6MB+ → <50KB)
#
# 使用: ./test-summary.sh [可選測試路徑]
#       例如: ./test-summary.sh test/unit/
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
TEMP_JSON="/tmp/flutter-test-results-$$.json"
HOOKS_DIR="$SCRIPT_DIR"

# 日誌設定
LOG_DIR="$PROJECT_ROOT/.claude/hook-logs/test-summary"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/execution-$(date +%Y%m%d-%H%M%S).log"

# 記錄執行開始
{
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] 測試摘要執行開始"
  echo "  專案根目錄: $PROJECT_ROOT"
  echo "  測試路徑: ${1:-.}"
  echo "  臨時檔案: $TEMP_JSON"
} >> "$LOG_FILE"

# 驗證專案根目錄
if [ ! -f "$PROJECT_ROOT/pubspec.yaml" ]; then
  cat >&2 << EOF
❌ 錯誤: 無法定位 Flutter 專案根目錄

當前路徑: $PROJECT_ROOT
預期檔案: $PROJECT_ROOT/pubspec.yaml

💡 修復建議:
1. 確認 CLAUDE_PROJECT_DIR 環境變數是否設定正確
2. 或在專案根目錄執行此腳本
3. 驗證 pubspec.yaml 是否存在

📝 詳細日誌: $LOG_FILE
EOF
  exit 2
fi

# 切換到專案目錄
cd "$PROJECT_ROOT"

# 執行測試並捕獲輸出
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 執行 flutter test 命令" >> "$LOG_FILE"

if ! flutter test --reporter json ${1:-.} > "$TEMP_JSON" 2>&1; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] flutter test 命令執行失敗 (exit code: $?)" >> "$LOG_FILE"
  # 即使測試失敗也繼續處理，因為我們需要分析失敗的測試
fi

# 驗證臨時檔案
if [ ! -f "$TEMP_JSON" ]; then
  cat >&2 << EOF
❌ 錯誤: 測試輸出檔案未生成

臨時檔案: $TEMP_JSON

💡 修復建議:
1. 檢查 flutter test 命令是否安裝
2. 檢查測試路徑是否正確
3. 檢查專案是否能正常構建

📝 詳細日誌: $LOG_FILE
EOF
  exit 2
fi

FILE_SIZE=$(stat -f%z "$TEMP_JSON" 2>/dev/null || stat -c%s "$TEMP_JSON" 2>/dev/null || echo "0")
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 測試輸出大小: $(numfmt --to=iec-i --suffix=B $FILE_SIZE 2>/dev/null || echo "${FILE_SIZE} bytes")" >> "$LOG_FILE"

# 調用 Python 解析器
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 調用 Python 解析器生成摘要" >> "$LOG_FILE"

if ! python3 "$HOOKS_DIR/parse-test-json.py" "$TEMP_JSON"; then
  cat >&2 << EOF
❌ 錯誤: 測試結果解析失敗

Python 解析器: $HOOKS_DIR/parse-test-json.py
輸入檔案: $TEMP_JSON

💡 修復建議:
1. 確認 parse-test-json.py 存在且可執行
2. 檢查 Python 版本 (需要 3.6+)
3. 檢查臨時檔案是否有效的 JSON

📝 詳細日誌: $LOG_FILE
EOF
  exit 2
fi

# 清理臨時檔案
rm -f "$TEMP_JSON"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 測試摘要執行完成" >> "$LOG_FILE"

exit 0
