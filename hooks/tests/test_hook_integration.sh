#!/bin/bash
# Hook 整合測試腳本

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOOK_SCRIPT="$SCRIPT_DIR/../ticket-quality-gate-hook.py"

echo "============================================================"
echo "Ticket Quality Gate Hook - 整合測試"
echo "============================================================"
echo ""

# 測試 1: God Ticket 檢測
echo "【測試 1】God Ticket 檢測"
echo "------------------------------------------------------------"

cat > /tmp/test-input.json << 'EOF'
{
  "tool_name": "Write",
  "tool_input": {
    "file_path": "docs/work-logs/v0.12.G.4-ticket-1.md",
    "content": "## 📋 實作步驟\n\n步驟 1: 修改 lib/domain/entities/rating.dart\n步驟 2: 修改 lib/usecases/calculate_rating.dart\n步驟 3: 修改 lib/application/rating_controller.dart\n步驟 4: 修改 lib/ui/widgets/rating_display.dart\n步驟 5: 新增測試 test/domain/rating_test.dart\n\n## ✅ 驗收條件\n\n- [ ] 條件 1\n- [ ] 條件 2\n- [ ] 條件 3\n\n## 🔗 參考文件\n\n- docs/test.md"
  },
  "tool_response": {
    "success": true
  }
}
EOF

python3 "$HOOK_SCRIPT" < /tmp/test-input.json > /tmp/test-output.json 2>&1 || true

if grep -q '"decision": "block"' /tmp/test-output.json 2>/dev/null; then
    echo "✅ 正確檢測到 God Ticket（層級跨度超標）"
else
    echo "❌ 未能檢測到 God Ticket"
    cat /tmp/test-output.json
    exit 1
fi

echo ""

# 測試 2: Incomplete Ticket 檢測
echo "【測試 2】Incomplete Ticket 檢測"
echo "------------------------------------------------------------"

cat > /tmp/test-input-2.json << 'EOF'
{
  "tool_name": "Write",
  "tool_input": {
    "file_path": "docs/work-logs/v0.12.G.4-ticket-2.md",
    "content": "## 📋 實作步驟\n\n步驟 1: 修改 lib/domain/entities/book.dart\n步驟 2: 撰寫測試 test/domain/book_test.dart\n\n## 🔗 參考文件\n\n- docs/app-requirements-spec.md"
  },
  "tool_response": {
    "success": true
  }
}
EOF

python3 "$HOOK_SCRIPT" < /tmp/test-input-2.json > /tmp/test-output-2.json 2>&1 || true

if grep -q '"decision": "block"' /tmp/test-output-2.json 2>/dev/null; then
    echo "✅ 正確檢測到 Incomplete Ticket（缺少驗收條件）"
else
    echo "❌ 未能檢測到 Incomplete Ticket"
    cat /tmp/test-output-2.json
    exit 1
fi

echo ""

# 測試 3: 正常 Ticket 通過
echo "【測試 3】正常 Ticket 通過檢測"
echo "------------------------------------------------------------"

cat > /tmp/test-input-3.json << 'EOF'
{
  "tool_name": "Write",
  "tool_input": {
    "file_path": "docs/work-logs/v0.12.G.4-ticket-3.md",
    "content": "[Layer 5] Domain Entity 實作\n\n## 目標\n\n負責實作 BookEntity 的 description 欄位，專注於 Domain 層級的實體設計。不包含 UI、UseCase 或 Application 層的變更。\n\n## 📋 實作步驟\n\n步驟 1: 修改 lib/domain/entities/book.dart（新增 description 欄位）\n步驟 2: 更新 BookEntity 測試\n步驟 3: 更新文件\n\n## ✅ 驗收條件\n\n- [ ] BookEntity 包含 description 欄位（Domain 層級）\n- [ ] description 欄位型別為 String（Value Object）\n- [ ] description 欄位可選（Domain 規則）\n\n## 🔗 參考文件\n\n- docs/app-requirements-spec.md\n\n修改檔案:\n- lib/domain/entities/book.dart\n- test/domain/book_test.dart\n\n## 工作日誌\n\ndocs/work-logs/v0.12.G.4-main.md"
  },
  "tool_response": {
    "success": true
  }
}
EOF

python3 "$HOOK_SCRIPT" < /tmp/test-input-3.json > /tmp/test-output-3.json 2>&1 || true

if grep -q '"decision": "allow"' /tmp/test-output-3.json 2>/dev/null; then
    echo "✅ 正確通過正常 Ticket 檢測"
else
    echo "❌ 正常 Ticket 未通過檢測"
    cat /tmp/test-output-3.json
    exit 1
fi

echo ""

# 清理測試檔案
rm -f /tmp/test-input*.json /tmp/test-output*.json

echo "============================================================"
echo "✅ 所有整合測試通過！"
echo "============================================================"
