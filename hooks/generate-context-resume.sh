#!/bin/bash

# 🔄 上下文恢復提示詞生成器
#
# 功能：產生包含當前工作狀態和所有相關需求文件的提示詞
# 使用時機：上下文即將達到容量上限或需要恢復工作狀態時
# 輸出位置：$CLAUDE_PROJECT_DIR/.claude/hook-logs/context-resume-{timestamp}.md

set -e

# 設定變數
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
TIMESTAMP=$(date '+%Y%m%d_%H%M%S')
OUTPUT_FILE="${PROJECT_DIR}/.claude/hook-logs/context-resume-${TIMESTAMP}.md"

echo "🔄 生成上下文恢復提示詞..."
echo "📁 專案目錄: ${PROJECT_DIR}"
echo "📄 輸出檔案: ${OUTPUT_FILE}"

# 建立輸出目錄
mkdir -p "$(dirname "${OUTPUT_FILE}")"

# 開始生成提示詞
cat > "${OUTPUT_FILE}" << 'EOF'
# 🔄 上下文恢復提示詞

**生成時間**:
EOF

echo "$(date '+%Y-%m-%d %H:%M:%S')" >> "${OUTPUT_FILE}"

cat >> "${OUTPUT_FILE}" << 'EOF'

**重要**: 這是上下文容量接近上限時的工作狀態恢復提示詞，包含所有必要的執行細節和文件引用。

## 📋 當前工作狀態摘要

### 🎯 主要完成工作
EOF

# 檢查最近的工作日誌
echo "正在分析最近的工作內容..."

# 從 todolist 獲取狀態
if [ -f "${PROJECT_DIR}/docs/todolist.md" ]; then
    echo "" >> "${OUTPUT_FILE}"
    echo "### ✅ TodoList 當前狀態" >> "${OUTPUT_FILE}"
    echo "" >> "${OUTPUT_FILE}"
    echo '```markdown' >> "${OUTPUT_FILE}"
    tail -20 "${PROJECT_DIR}/docs/todolist.md" >> "${OUTPUT_FILE}"
    echo '```' >> "${OUTPUT_FILE}"
fi

# 檢查最近的工作日誌檔案
echo "" >> "${OUTPUT_FILE}"
echo "### 📝 最近工作日誌" >> "${OUTPUT_FILE}"
echo "" >> "${OUTPUT_FILE}"

# 查找最近修改的工作日誌
RECENT_WORKLOG=$(find "${PROJECT_DIR}/docs/work-logs" -name "*.md" -type f -exec stat -f "%m %N" {} \; 2>/dev/null | sort -nr | head -1 | cut -d' ' -f2- || echo "")

if [ -n "${RECENT_WORKLOG}" ]; then
    echo "**最新工作日誌**: \`$(basename "${RECENT_WORKLOG}")\`" >> "${OUTPUT_FILE}"
    echo "" >> "${OUTPUT_FILE}"
    echo "**路徑**: \`${RECENT_WORKLOG}\`" >> "${OUTPUT_FILE}"
    echo "" >> "${OUTPUT_FILE}"
fi

# 檢查 Git 狀態
echo "" >> "${OUTPUT_FILE}"
echo "### 🔧 Git 狀態" >> "${OUTPUT_FILE}"
echo "" >> "${OUTPUT_FILE}"

cd "${PROJECT_DIR}"

# Git status
echo '```bash' >> "${OUTPUT_FILE}"
echo "# Git Status" >> "${OUTPUT_FILE}"
git status --porcelain 2>/dev/null | head -20 >> "${OUTPUT_FILE}" || echo "Git status 無法獲取" >> "${OUTPUT_FILE}"
echo "" >> "${OUTPUT_FILE}"

# 最近提交
echo "# 最近 3 次提交" >> "${OUTPUT_FILE}"
git log --oneline -3 2>/dev/null >> "${OUTPUT_FILE}" || echo "Git log 無法獲取" >> "${OUTPUT_FILE}"
echo '```' >> "${OUTPUT_FILE}"

# 關鍵配置檔案
echo "" >> "${OUTPUT_FILE}"
echo "## 📚 關鍵文件引用" >> "${OUTPUT_FILE}"
echo "" >> "${OUTPUT_FILE}"

# 核心配置和規範檔案
CORE_FILES=(
    "CLAUDE.md"
    "\$CLAUDE_PROJECT_DIR/.claude/methodologies/agile-refactor-methodology.md"
    "docs/work-logs/v0.10.0-agile-refactoring-master-plan.md"
    "docs/todolist.md"
    "docs/app-requirements-spec.md"
    "docs/app-use-cases.md"
    "docs/ui_design_specification.md"
    "docs/test-pyramid-design.md"
    "docs/app-error-handling-design.md"
    "test/TESTING_GUIDELINES.md"
    "docs/event-driven-architecture-design.md"
    "docs/i18n_guide.md"
    "docs/terminology-dictionary.md"
    "\$CLAUDE_PROJECT_DIR/.claude/settings.local.json"
)

echo "### 🔴 核心規範檔案 (必讀)" >> "${OUTPUT_FILE}"
echo "" >> "${OUTPUT_FILE}"

for file in "${CORE_FILES[@]}"; do
    if [ -f "${PROJECT_DIR}/${file}" ]; then
        echo "- ✅ \`${file}\`" >> "${OUTPUT_FILE}"
    else
        echo "- ❌ \`${file}\` (缺失)" >> "${OUTPUT_FILE}"
    fi
done

# 最近修改的重要檔案
echo "" >> "${OUTPUT_FILE}"
echo "### 📝 最近修改的重要檔案" >> "${OUTPUT_FILE}"
echo "" >> "${OUTPUT_FILE}"

# 查找最近修改的檔案（排除一些臨時檔案）
find "${PROJECT_DIR}" -name "*.md" -o -name "*.dart" -o -name "*.json" -o -name "*.yaml" | \
    grep -E '\.(md|dart|json|yaml)$' | \
    grep -v '/\.git/' | \
    grep -v '/build/' | \
    grep -v '/node_modules/' | \
    xargs stat -f "%m %N" 2>/dev/null | \
    sort -nr | \
    head -10 | \
    while read -r timestamp filepath; do
        relative_path=${filepath#${PROJECT_DIR}/}
        mod_time=$(date -r "${timestamp}" '+%Y-%m-%d %H:%M')
        echo "- \`${relative_path}\` (${mod_time})" >> "${OUTPUT_FILE}"
    done 2>/dev/null || echo "- 無法獲取檔案修改資訊" >> "${OUTPUT_FILE}"

# 當前開發環境狀態
echo "" >> "${OUTPUT_FILE}"
echo "## 🛠 開發環境狀態" >> "${OUTPUT_FILE}"
echo "" >> "${OUTPUT_FILE}"

echo '```bash' >> "${OUTPUT_FILE}"
echo "# Flutter/Dart 版本" >> "${OUTPUT_FILE}"
flutter --version 2>/dev/null | head -5 >> "${OUTPUT_FILE}" || echo "Flutter 版本無法獲取" >> "${OUTPUT_FILE}"
echo "" >> "${OUTPUT_FILE}"

echo "# 專案依賴狀態" >> "${OUTPUT_FILE}"
if [ -f "${PROJECT_DIR}/pubspec.yaml" ]; then
    echo "pubspec.yaml 存在" >> "${OUTPUT_FILE}"
    if [ -f "${PROJECT_DIR}/pubspec.lock" ]; then
        echo "pubspec.lock 存在" >> "${OUTPUT_FILE}"
    else
        echo "pubspec.lock 缺失 - 需要執行 flutter pub get" >> "${OUTPUT_FILE}"
    fi
else
    echo "pubspec.yaml 缺失" >> "${OUTPUT_FILE}"
fi
echo '```' >> "${OUTPUT_FILE}"

# 恢復指引
echo "" >> "${OUTPUT_FILE}"
echo "## 🚀 恢復執行指引" >> "${OUTPUT_FILE}"
echo "" >> "${OUTPUT_FILE}"

echo "### 📋 立即執行步驟" >> "${OUTPUT_FILE}"
echo "" >> "${OUTPUT_FILE}"
echo "1. **讀取核心文件**：" >> "${OUTPUT_FILE}"
echo "   - 優先讀取 \`CLAUDE.md\` 了解專案規範" >> "${OUTPUT_FILE}"
echo "   - 檢查 \`\$CLAUDE_PROJECT_DIR/.claude/methodologies/agile-refactor-methodology.md\` 了解工作流程" >> "${OUTPUT_FILE}"
echo "   - 查看 \`docs/work-logs/v0.10.0-agile-refactoring-master-plan.md\` 了解當前計畫" >> "${OUTPUT_FILE}"
echo "" >> "${OUTPUT_FILE}"

echo "2. **檢查工作狀態**：" >> "${OUTPUT_FILE}"
echo "   - 檢查 \`docs/todolist.md\` 了解未完成任務" >> "${OUTPUT_FILE}"
echo "   - 執行 \`git status\` 檢查未提交變更" >> "${OUTPUT_FILE}"
echo "   - 執行 \`flutter analyze\` 檢查編譯狀態" >> "${OUTPUT_FILE}"
echo "" >> "${OUTPUT_FILE}"

echo "3. **恢復工作環境**：" >> "${OUTPUT_FILE}"
echo "   - 執行 \`flutter pub get\` 恢復依賴" >> "${OUTPUT_FILE}"
echo "   - 檢查測試狀態：\`dart test\` 和 \`flutter test\`" >> "${OUTPUT_FILE}"
echo "   - 確認 Hook 系統正常運作" >> "${OUTPUT_FILE}"
echo "" >> "${OUTPUT_FILE}"

echo "4. **繼續開發工作**：" >> "${OUTPUT_FILE}"
echo "   - 根據 todolist 繼續未完成任務" >> "${OUTPUT_FILE}"
echo "   - 遵循 v0.10.0 敏捷重構計畫" >> "${OUTPUT_FILE}"
echo "   - 執行階段完成驗證檢查" >> "${OUTPUT_FILE}"
echo "" >> "${OUTPUT_FILE}"

# 重要提醒
echo "### ⚠️ 重要提醒" >> "${OUTPUT_FILE}"
echo "" >> "${OUTPUT_FILE}"
echo "- **5W1H 決策框架**：所有對話必須遵循 5W1H 分析格式" >> "${OUTPUT_FILE}"
echo "- **階段完成驗證**：每個 v0.10.x 階段必須通過完整檢查清單" >> "${OUTPUT_FILE}"
echo "- **Hook 系統**：確保所有 Hook 正常運作，提供品質保證" >> "${OUTPUT_FILE}"
echo "- **測試通過率**：維持 100% 測試通過率，零容忍失敗" >> "${OUTPUT_FILE}"
echo "- **架構一致性**：遵循 Clean Architecture 和 package 導入規範" >> "${OUTPUT_FILE}"
echo "" >> "${OUTPUT_FILE}"

# 結尾
echo "---" >> "${OUTPUT_FILE}"
echo "" >> "${OUTPUT_FILE}"
echo "**此提示詞包含恢復工作所需的所有關鍵資訊，請依序執行恢復步驟。**" >> "${OUTPUT_FILE}"

echo "✅ 上下文恢復提示詞已生成: ${OUTPUT_FILE}"
echo ""
echo "📋 下一步："
echo "   1. 複製提示詞內容用於新對話"
echo "   2. 或使用 cat '${OUTPUT_FILE}' 檢視內容"
echo "   3. 恢復工作完成後執行: \$CLAUDE_PROJECT_DIR/.claude/scripts/resume-mission-complete.sh"
echo ""

# 顯示檔案大小
if [ -f "${OUTPUT_FILE}" ]; then
    file_size=$(wc -c < "${OUTPUT_FILE}")
    echo "📊 提示詞大小: ${file_size} bytes"
fi