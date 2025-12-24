#!/bin/bash

# 多語系key完整性檢測腳本
# 使用方法: ./scripts/check_i18n.sh

set -e

echo "🌍 多語系 Key 完整性檢測"
echo "========================="

# 確保在專案根目錄
if [ ! -f "pubspec.yaml" ]; then
    echo "❌ 錯誤: 請在 Flutter 專案根目錄中執行此腳本"
    exit 1
fi

# 檢查 Dart 是否可用
if ! command -v dart &> /dev/null; then
    echo "❌ 錯誤: 找不到 Dart。請確保 Flutter/Dart 已正確安裝並加入 PATH"
    exit 1
fi

# 運行檢測腳本
echo "🚀 正在執行多語系 key 檢測..."
echo ""

dart scripts/check_i18n_keys.dart

# 檢測完成
echo ""
echo "ℹ️  如果發現問題，請根據上方報告修復後重新運行此腳本"
echo "💡 建議將此腳本加入 CI/CD 流程以自動檢測多語系問題"