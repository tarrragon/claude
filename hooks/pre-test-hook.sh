#!/bin/bash

# pre-test-hook.sh
# PreToolUse Hook: 測試執行前環境檢查

# 設定路徑和日誌
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOG_FILE="$PROJECT_ROOT/.claude/hook-logs/pre-test-$(date +%Y%m%d_%H%M%S).log"

# 確保日誌目錄存在
mkdir -p "$PROJECT_ROOT/.claude/hook-logs"

# 日誌函數
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "🧪 PreToolUse Hook (Test): 開始執行測試前環境檢查"

cd "$PROJECT_ROOT"

# 1. 檢查測試環境準備
log "🔧 檢查測試環境準備"

# 檢查 Flutter 依賴
if [ -f "pubspec.lock" ]; then
    log "✅ pubspec.lock 存在，依賴項已解析"
else
    log "❌ pubspec.lock 不存在，測試可能失敗"
    log "💡 建議執行: flutter pub get"
fi

# 檢查 Flutter 測試環境
if [ -f "pubspec.yaml" ] && [ -d ".dart_tool" ]; then
    log "✅ Flutter 測試環境已準備"
else
    log "⚠️  Flutter 測試環境未完全準備"
fi

# 2. 檢查測試檔案狀態
log "📁 檢查測試檔案狀態"

# 計算測試檔案數量
UNIT_TEST_COUNT=$(find test -name "*_test.dart" -not -path "*/integration/*" 2>/dev/null | wc -l)
INTEGRATION_TEST_COUNT=$(find test/integration -name "*_test.dart" 2>/dev/null | wc -l)

log "📊 單元測試檔案: $UNIT_TEST_COUNT 個"
log "📊 整合測試檔案: $INTEGRATION_TEST_COUNT 個"

if [ "$UNIT_TEST_COUNT" -eq 0 ] && [ "$INTEGRATION_TEST_COUNT" -eq 0 ]; then
    log "⚠️  未找到測試檔案"
fi

# 3. 檢查是否有未提交的測試變更
log "📝 檢查未提交的測試變更"

TEST_CHANGES=$(git status --porcelain | grep -E "_test\.dart$" | wc -l)
if [ "$TEST_CHANGES" -gt 0 ]; then
    log "⚠️  發現 $TEST_CHANGES 個未提交的測試檔案變更"
    git status --porcelain | grep -E "_test\.dart$" | while read status file; do
        log "  $status $file"
    done
fi

# 4. 檢查上次測試結果
log "📈 檢查上次測試結果"

# 檢查測試狀態檔案
if [ -f "coverage-private/test-status.txt" ]; then
    LAST_STATUS=$(cat "coverage-private/test-status.txt")
    log "📊 上次測試狀態: $LAST_STATUS"

    if [ "$LAST_STATUS" != "pass" ]; then
        log "⚠️  上次測試未通過，本次測試需要特別關注"
    fi
else
    log "📋 未找到上次測試狀態記錄"
fi

# 5. 建立測試狀態追蹤
log "📋 建立測試狀態追蹤"

# 確保覆蓋率目錄存在
mkdir -p "coverage-private"

# 記錄測試開始時間
echo "$(date +%s)" > "coverage-private/test-start-time.txt"

# 記錄測試前狀態
echo "starting" > "coverage-private/test-status.txt"

# 6. 檢查記憶體和系統資源
log "💾 檢查系統資源"

# 檢查可用記憶體 (macOS)
if command -v vm_stat >/dev/null 2>&1; then
    FREE_PAGES=$(vm_stat | grep "Pages free" | awk '{print $3}' | tr -d '.')
    FREE_MB=$((FREE_PAGES * 4096 / 1024 / 1024))
    log "💾 可用記憶體: 約 ${FREE_MB}MB"

    if [ "$FREE_MB" -lt 1024 ]; then
        log "⚠️  可用記憶體不足1GB，測試可能較慢"
    fi
fi

# 7. 環境變數檢查
log "🌍 環境變數檢查"

# 檢查 Node.js 版本
if command -v node >/dev/null 2>&1; then
    NODE_VERSION=$(node --version)
    log "📦 Node.js 版本: $NODE_VERSION"
else
    log "❌ Node.js 未安裝"
fi

# 檢查 npm 版本
if command -v npm >/dev/null 2>&1; then
    NPM_VERSION=$(npm --version)
    log "📦 npm 版本: $NPM_VERSION"
fi

# 8. 提供測試執行建議
log "💡 測試執行建議"

# 根據檔案數量建議測試策略
TOTAL_TESTS=$((UNIT_TEST_COUNT + INTEGRATION_TEST_COUNT))
if [ "$TOTAL_TESTS" -gt 50 ]; then
    log "💡 建議使用 --maxWorkers=4 限制並行測試數量"
elif [ "$TOTAL_TESTS" -gt 20 ]; then
    log "💡 建議使用 --maxWorkers=2 適度並行測試"
fi

log "✅ PreToolUse Hook (Test) 環境檢查完成"

# 返回成功 (不阻止測試執行)
exit 0