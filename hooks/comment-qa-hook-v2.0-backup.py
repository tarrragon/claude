#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///

"""
Comment Quality Assurance Hook - 註解品質保證檢查

用途: 檢查 Dart 程式碼的註解品質，確保事件處理函式和獨立 Widget 具備完整追溯資訊
觸發: PostToolUse Hook (matcher: Write|Edit|MultiEdit)
模式: 建議模式（不阻擋開發，提供改善建議）

檢查策略:
✅ 必須註解:
  - 事件處理函式 (handle*, on*, process*, emit*, dispatch*)
  - 獨立 Widget (StatefulWidget, ConsumerWidget, StreamBuilder, FutureBuilder)
  - UseCase 和 Domain 層的所有公開函式

❌ 可豁免註解:
  - 輔助函式 (_isValid*, _format*, _prepare*, _convert*, _validate*, _transform*, _parse*, _extract*)
  - 依賴型 Widget (私有 StatelessWidget)

參考規範:
- .claude/methodologies/comment-writing-methodology.md
- docs/event-driven-architecture-design.md

版本: v2.0
建立日期: 2025-10-09
更新日期: 2025-10-09
"""

import json
import sys
import os
import re
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass
from typing import Optional, List, Dict, Tuple

# 專案根目錄
PROJECT_ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR", "."))
LOG_DIR = PROJECT_ROOT / ".claude/hook-logs"
REPORT_DIR = LOG_DIR / "comment-qa-reports"
LOG_FILE = LOG_DIR / f"comment-qa-execution-{datetime.now():%Y%m%d}.log"

# 確保目錄存在
LOG_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class FunctionInfo:
    """函式資訊"""
    name: str
    signature: str
    line_number: int
    has_complete_comment: bool
    existing_comment: Optional[str] = None


def log_message(message: str):
    """記錄訊息到日誌"""
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{timestamp}] {message}\n")
    except Exception as e:
        print(f"日誌記錄失敗: {e}", file=sys.stderr)


def should_process_file(file_path: str) -> bool:
    """
    判斷是否需要處理此檔案

    條件:
    1. 必須是 .dart 檔案
    2. 不處理測試檔案和生成檔案
    3. 必須在重點目錄（domains/presentation/use_cases）
    """
    # 1. 必須是 .dart 檔案
    if not file_path.endswith('.dart'):
        return False

    # 2. 不處理測試檔案和生成檔案
    if '/test/' in file_path or '_test.dart' in file_path:
        return False

    if '.g.dart' in file_path or '.freezed.dart' in file_path:
        return False

    # 3. 必須在重點目錄
    priority_dirs = ['lib/domains/', 'lib/presentation/', 'lib/use_cases/']
    return any(d in file_path for d in priority_dirs)


def is_event_handler_function(func_name: str, return_type: str = "") -> bool:
    """判斷是否為事件處理函式"""
    event_patterns = [
        r'^handle[A-Z]',  # handleBookAdded
        r'^on[A-Z]',      # onImportCompleted
        r'^process[A-Z]', # processBookEnrichment
        r'^emit[A-Z]',    # emitBookAdded
        r'^dispatch[A-Z]' # dispatchEvent
    ]

    for pattern in event_patterns:
        if re.search(pattern, func_name):
            return True

    # 檢查回傳類型
    if return_type:
        if any(t in return_type for t in ['Future', 'Stream', 'OperationResult']):
            # 非建構式且有異步特徵
            if not func_name[0].isupper():  # 建構式首字母大寫
                return True

    return False


def is_auxiliary_function(func_name: str) -> bool:
    """判斷是否為輔助函式（可豁免註解）"""
    # 必須是私有函式
    if not func_name.startswith('_'):
        return False

    # 輔助函式命名模式
    auxiliary_patterns = [
        r'isValid',     # _isValidIsbn
        r'format',      # _formatBookTitle
        r'prepare',     # _prepareRequestData
        r'convert',     # _convertToJson
        r'validate',    # _validateInput
        r'transform',   # _transformData
        r'parse',       # _parseResponse
        r'extract',     # _extractFields
        r'check',       # _checkPermission
        r'build',       # _buildWidget (私有 build 方法)
    ]

    for pattern in auxiliary_patterns:
        if re.search(pattern, func_name, re.IGNORECASE):
            return True

    return False


def has_complete_comment(comment_lines: list[str]) -> bool:
    """
    檢查是否已有完整註解

    完整註解標準:
    - 包含「需求來源」或「需求」
    - 包含「規格文件」或「工作日誌」
    """
    comment_text = ' '.join(comment_lines)

    # 檢查關鍵標記
    has_requirement = any(keyword in comment_text for keyword in ['需求來源', '需求:', 'UC-', 'BR-'])
    has_traceability = any(keyword in comment_text for keyword in ['規格文件', '工作日誌', 'docs/'])

    return has_requirement and has_traceability


@dataclass
class WidgetInfo:
    """Widget 資訊"""
    name: str
    base_class: str  # StatefulWidget, StatelessWidget, ConsumerWidget, etc.
    line_number: int
    is_private: bool
    has_complete_comment: bool
    existing_comment: Optional[str] = None


def extract_items_from_file(file_path: Path) -> Tuple[List[FunctionInfo], List[WidgetInfo]]:
    """
    從 Dart 檔案提取業務邏輯函式和 Widget

    Returns:
        (functions, widgets) - 函式列表和 Widget 列表
    """
    functions = []
    widgets = []

    try:
        content = file_path.read_text(encoding='utf-8')
        lines = content.split('\n')

        i = 0
        while i < len(lines):
            # 收集註解
            comment_lines = []
            while i < len(lines) and lines[i].strip().startswith('///'):
                comment_lines.append(lines[i].strip())
                i += 1

            if i >= len(lines):
                break

            line = lines[i].strip()

            # 檢查 Widget 定義
            widget_pattern = r'class\s+([_A-Z][a-zA-Z0-9_]*)\s+extends\s+(StatefulWidget|StatelessWidget|ConsumerWidget|StreamBuilder|FutureBuilder)'
            widget_match = re.search(widget_pattern, line)

            if widget_match:
                widget_name = widget_match.group(1)
                base_class = widget_match.group(2)
                is_private = widget_name.startswith('_')

                # 檢查是否已有完整註解
                has_complete = has_complete_comment(comment_lines)

                widget_info = WidgetInfo(
                    name=widget_name,
                    base_class=base_class,
                    line_number=i + 1,
                    is_private=is_private,
                    has_complete_comment=has_complete,
                    existing_comment=' '.join(comment_lines) if comment_lines else None
                )

                widgets.append(widget_info)
                i += 1
                continue

            # 匹配函式簽名模式
            function_pattern = r'^(?:(Future<[^>]+>|Stream<[^>]+>|OperationResult<[^>]+>|void|bool|int|String|double|List<[^>]+>|Map<[^>]+>)\s+)?(\w+)\s*\('
            func_match = re.search(function_pattern, line)

            if func_match:
                return_type = func_match.group(1) or ""
                func_name = func_match.group(2)

                # 排除建構函式、getter、setter
                if func_name in ['get', 'set', 'const']:
                    i += 1
                    continue

                # 提取完整函式簽名（可能跨多行）
                signature = line
                if not ('{' in line or ';' in line):
                    # 函式簽名跨多行，繼續讀取
                    j = i + 1
                    while j < len(lines) and not ('{' in lines[j] or ';' in lines[j]):
                        signature += ' ' + lines[j].strip()
                        j += 1
                    if j < len(lines):
                        signature += ' ' + lines[j].strip()

                # 清理簽名（移除 { 和後續內容）
                signature = re.sub(r'\s*\{.*', '', signature).strip()

                # 檢查是否已有完整註解
                has_complete = has_complete_comment(comment_lines)

                func_info = FunctionInfo(
                    name=func_name,
                    signature=signature,
                    line_number=i + 1,
                    has_complete_comment=has_complete,
                    existing_comment=' '.join(comment_lines) if comment_lines else None
                )

                # 儲存回傳類型以便後續判斷
                func_info.return_type = return_type  # 動態添加屬性

                functions.append(func_info)

            i += 1

        return functions, widgets

    except Exception as e:
        log_message(f"錯誤: 提取函式和 Widget 失敗 - {e}")
        return [], []


def find_related_work_log() -> Optional[Path]:
    """
    查找當前相關的工作日誌

    策略:
    1. 查找 docs/work-logs/ 目錄
    2. 找出最近修改的 v0.X.Y.md 檔案
    """
    work_log_dir = PROJECT_ROOT / "docs/work-logs"

    if not work_log_dir.exists():
        log_message("警告: 找不到 work-logs 目錄")
        return None

    try:
        # 找出所有 v0.X.Y.md 檔案
        pattern = r'v\d+\.\d+\.\d+.*\.md'
        work_logs = [
            f for f in work_log_dir.iterdir()
            if f.is_file() and re.match(pattern, f.name)
        ]

        if not work_logs:
            log_message("警告: 找不到工作日誌檔案")
            return None

        # 按修改時間排序，取最新的
        latest_log = max(work_logs, key=lambda f: f.stat().st_mtime)

        log_message(f"找到工作日誌: {latest_log.name}")
        return latest_log

    except Exception as e:
        log_message(f"錯誤: 查找工作日誌失敗 - {e}")
        return None


def extract_design_solution(work_log_path: Path) -> str:
    """
    從工作日誌提取設計方案描述

    策略:
    1. 查找 Phase 1 區段
    2. 提取方案名稱（如「方案C-1基礎版」）
    """
    try:
        content = work_log_path.read_text(encoding='utf-8')

        # 查找方案描述模式
        solution_patterns = [
            r'方案[A-Z]-\d+[^\n]*',
            r'設計方案[：:]\s*([^\n]+)',
            r'Phase 1.*?方案[：:]\s*([^\n]+)',
        ]

        for pattern in solution_patterns:
            match = re.search(pattern, content)
            if match:
                solution = match.group(0) if not match.groups() else match.group(1)
                log_message(f"提取設計方案: {solution}")
                return solution.strip()

        # 預設值
        version = work_log_path.stem
        return f"{version} Phase 1 設計"

    except Exception as e:
        log_message(f"錯誤: 提取設計方案失敗 - {e}")
        return "請參考工作日誌"


def infer_usecase_from_path(file_path: str) -> str:
    """
    從檔案路徑推測相關的 UseCase

    策略:
    - 檢查路徑關鍵字
    - 預設返回通用描述
    """
    path_lower = file_path.lower()

    if 'import' in path_lower or 'chrome' in path_lower:
        return "UC-01: Chrome Extension匯入書籍資料"
    elif 'export' in path_lower:
        return "UC-02: 匯出書籍資料多格式支援"
    elif 'isbn' in path_lower or 'scan' in path_lower:
        return "UC-03: ISBN 條碼掃描書籍識別"
    elif 'search' in path_lower or 'google' in path_lower:
        return "UC-04: Google Books API 書籍搜尋"
    elif 'library' in path_lower or 'list' in path_lower:
        return "UC-05: 雙模式書庫展示切換"
    elif 'loan' in path_lower or 'borrow' in path_lower:
        return "UC-06: 書籍借閱狀態管理"
    elif 'tag' in path_lower or 'label' in path_lower:
        return "UC-07: 書籍標籤分類系統"
    elif 'version' in path_lower:
        return "UC-08: 版本管理與歷史追蹤"
    elif 'error' in path_lower:
        return "UC-09: 錯誤處理與使用者回饋"
    else:
        return "UC-ALL: 通用功能"


def generate_comment_template(
    item: any,  # FunctionInfo or WidgetInfo
    item_type: str,  # "event_handler", "function", or "widget"
    file_path: str,
    work_log_path: Optional[Path],
    design_solution: str
) -> str:
    """
    生成標準註解框架

    基於: .claude/methodologies/comment-writing-methodology.md
    """
    # 推測 UseCase
    usecase = infer_usecase_from_path(file_path)

    # 規格文件連結
    spec_files = find_related_spec_files()
    if spec_files:
        spec_link = f"docs/{spec_files[0].name}"
    else:
        spec_link = "docs/app-requirements-spec.md"

    # 工作日誌路徑
    if work_log_path:
        work_log_ref = f"docs/work-logs/{work_log_path.name} - {design_solution}"
    else:
        work_log_ref = "請補充工作日誌連結"

    # 根據類型生成不同模板
    if item_type == "event_handler":
        template = f"""/// 【需求來源】{usecase}
/// 【規格文件】{spec_link}
/// 【設計方案】{design_solution}
/// 【工作日誌】{work_log_ref}
/// 【事件類型】[事件名稱] 事件處理
/// 【修改約束】修改時需確保事件流完整性，避免影響上游訂閱者
/// 【維護警告】檢查依賴此函式的 UseCase，修改前需確認影響範圍
{item.signature}"""

    elif item_type == "widget":
        widget_type = "獨立狀態管理 Widget" if not item.is_private else "依賴型 Widget"
        template = f"""/// 【需求來源】{usecase}
/// 【規格文件】{spec_link}
/// 【設計方案】{design_solution}
/// 【工作日誌】{work_log_ref}
/// 【Widget 類型】{widget_type}
/// 【修改約束】{'此 Widget 具備獨立狀態，下層刷新不觸發上層重建' if not item.is_private else '此 Widget 依賴上層狀態，避免引入獨立狀態'}
/// 【維護警告】修改前需確認子 Widget 依賴關係
class {item.name} extends {item.base_class}"""

    else:  # general function
        template = f"""/// 【需求來源】{usecase}
/// 【規格文件】{spec_link}
/// 【設計方案】{design_solution}
/// 【工作日誌】{work_log_ref}
/// 【修改約束】請補充此函式的修改約束條件
/// 【維護警告】請補充相依模組和影響範圍
{item.signature}"""

    return template


def find_related_spec_files() -> List[Path]:
    """查找相關的規格文件"""
    docs_dir = PROJECT_ROOT / "docs"
    if not docs_dir.exists():
        return []

    spec_files = []

    # 核心規格文件
    core_specs = [
        "app-requirements-spec.md",
        "event-driven-architecture-design.md",
        "app-use-cases.md",
    ]

    for spec in core_specs:
        spec_path = docs_dir / spec
        if spec_path.exists():
            spec_files.append(spec_path)

    return spec_files


def generate_report(
    file_path: str,
    functions: List[FunctionInfo],
    widgets: List[WidgetInfo],
    work_log_path: Optional[Path],
    design_solution: str
) -> str:
    """
    生成完整的檢查報告（Markdown 格式）
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 分類函式
    event_handlers = []
    auxiliary_funcs = []
    regular_funcs = []

    for func in functions:
        return_type = getattr(func, 'return_type', '')
        if is_event_handler_function(func.name, return_type):
            if not func.has_complete_comment:
                event_handlers.append(func)
        elif is_auxiliary_function(func.name):
            auxiliary_funcs.append(func)
        else:
            if not func.has_complete_comment:
                regular_funcs.append(func)

    # 分類 Widget
    independent_widgets = []
    dependent_widgets = []

    for widget in widgets:
        if widget.is_private and widget.base_class == 'StatelessWidget':
            dependent_widgets.append(widget)
        elif not widget.is_private and widget.base_class in ['StatefulWidget', 'ConsumerWidget', 'StreamBuilder', 'FutureBuilder']:
            if not widget.has_complete_comment:
                independent_widgets.append(widget)

    # 建立報告
    report_lines = [
        "# 註解品質檢查報告",
        "",
        "## 基本資訊",
        f"- **檢查時間**: {timestamp}",
        f"- **檔案路徑**: {file_path}",
        f"- **工作日誌**: {work_log_path.name if work_log_path else '無'}",
        "",
        "## 檢查統計",
        f"- 事件處理函式缺少註解: {len(event_handlers)} 個",
        f"- 一般函式缺少註解: {len(regular_funcs)} 個",
        f"- 獨立 Widget 缺少註解: {len(independent_widgets)} 個",
        f"- 輔助函式（已豁免）: {len(auxiliary_funcs)} 個",
        f"- 依賴型 Widget（已豁免）: {len(dependent_widgets)} 個",
        "",
    ]

    # 事件處理函式建議
    if event_handlers:
        report_lines.append("## ⚠️ 事件處理函式建議註解")
        report_lines.append("")

        for i, func in enumerate(event_handlers, 1):
            report_lines.append(f"### {i}. {func.name} (行 {func.line_number})")
            report_lines.append("")
            report_lines.append("```dart")
            template = generate_comment_template(func, "event_handler", file_path, work_log_path, design_solution)
            report_lines.append(template)
            report_lines.append("```")
            report_lines.append("")

    # 獨立 Widget 建議
    if independent_widgets:
        report_lines.append("## ⚠️ 獨立 Widget 建議註解")
        report_lines.append("")

        for i, widget in enumerate(independent_widgets, 1):
            report_lines.append(f"### {i}. {widget.name} (行 {widget.line_number})")
            report_lines.append("")
            report_lines.append("```dart")
            template = generate_comment_template(widget, "widget", file_path, work_log_path, design_solution)
            report_lines.append(template)
            report_lines.append("```")
            report_lines.append("")

    # 一般函式建議
    if regular_funcs:
        report_lines.append("## ⚠️ 一般函式建議註解")
        report_lines.append("")

        for i, func in enumerate(regular_funcs[:5], 1):  # 最多顯示 5 個
            report_lines.append(f"### {i}. {func.name} (行 {func.line_number})")
            report_lines.append("")
            report_lines.append("```dart")
            template = generate_comment_template(func, "function", file_path, work_log_path, design_solution)
            report_lines.append(template)
            report_lines.append("```")
            report_lines.append("")

        if len(regular_funcs) > 5:
            report_lines.append(f"... 還有 {len(regular_funcs) - 5} 個一般函式")
            report_lines.append("")

    # 良好實踐
    if auxiliary_funcs or dependent_widgets:
        report_lines.append("## ✅ 良好實踐（已豁免註解）")
        report_lines.append("")

        for func in auxiliary_funcs[:3]:
            report_lines.append(f"- `{func.name}` (行 {func.line_number}) - 輔助函式正確豁免")

        for widget in dependent_widgets[:3]:
            report_lines.append(f"- `{widget.name}` (行 {widget.line_number}) - 依賴型 Widget 正確豁免")

        if len(auxiliary_funcs) + len(dependent_widgets) > 6:
            report_lines.append(f"- ... 還有 {len(auxiliary_funcs) + len(dependent_widgets) - 6} 個項目")

        report_lines.append("")

    report_lines.extend([
        "## 📚 註解規範參考",
        "- `.claude/methodologies/comment-writing-methodology.md` - 註解撰寫方法論",
        "- `docs/event-driven-architecture-design.md` - 事件驅動架構規範",
        "- 註解必須記錄「為什麼」而非「做什麼」",
        "- 註解必須包含需求來源和工作日誌追溯",
        "",
        "---",
        f"報告生成時間: {timestamp}",
    ])

    return '\n'.join(report_lines)


def save_report(report_content: str) -> Path:
    """儲存報告到檔案"""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    report_path = REPORT_DIR / f"report-{timestamp}.md"

    try:
        report_path.write_text(report_content, encoding='utf-8')
        log_message(f"報告已儲存: {report_path.name}")
        return report_path
    except Exception as e:
        log_message(f"錯誤: 儲存報告失敗 - {e}")
        raise


def main():
    """主要邏輯"""
    try:
        log_message("Comment QA Hook v2.0: 開始執行")

        # 1. 讀取 JSON 輸入
        input_data = json.load(sys.stdin)

        # 2. 提取工具資訊
        tool_name = input_data.get("tool_name", "")
        tool_input = input_data.get("tool_input", {})
        tool_response = input_data.get("tool_response", {})

        # 3. 檢查工具是否成功執行
        if not tool_response.get("success", False):
            log_message(f"工具 {tool_name} 執行失敗，跳過檢查")
            sys.exit(0)

        # 4. 檢查檔案是否需要處理
        file_path = tool_input.get("file_path", "")

        if not should_process_file(file_path):
            log_message(f"檔案 {file_path} 不需要處理")
            sys.exit(0)

        log_message(f"處理檔案: {file_path}")

        # 5. 提取業務邏輯函式和 Widget
        file_path_obj = Path(file_path)
        functions, widgets = extract_items_from_file(file_path_obj)

        log_message(f"發現 {len(functions)} 個函式, {len(widgets)} 個 Widget")

        # 6. 分類檢查
        event_handlers = []
        auxiliary_funcs = []
        regular_funcs = []

        for func in functions:
            return_type = getattr(func, 'return_type', '')
            if is_event_handler_function(func.name, return_type):
                if not func.has_complete_comment:
                    event_handlers.append(func)
            elif is_auxiliary_function(func.name):
                auxiliary_funcs.append(func)
            else:
                if not func.has_complete_comment:
                    regular_funcs.append(func)

        independent_widgets = []
        dependent_widgets = []

        for widget in widgets:
            if widget.is_private and widget.base_class == 'StatelessWidget':
                dependent_widgets.append(widget)
            elif not widget.is_private and widget.base_class in ['StatefulWidget', 'ConsumerWidget', 'StreamBuilder', 'FutureBuilder']:
                if not widget.has_complete_comment:
                    independent_widgets.append(widget)

        total_issues = len(event_handlers) + len(regular_funcs) + len(independent_widgets)

        if total_issues == 0:
            log_message("所有核心項目都有完整註解，無需建議")
            sys.exit(0)

        log_message(f"發現 {total_issues} 個項目缺少完整註解")

        # 7. 查找工作日誌
        work_log_path = find_related_work_log()

        # 8. 提取設計方案
        design_solution = extract_design_solution(work_log_path) if work_log_path else "請參考工作日誌"

        # 9. 生成報告
        report_content = generate_report(file_path, functions, widgets, work_log_path, design_solution)

        # 10. 儲存報告
        report_path = save_report(report_content)

        # 11. 輸出建議（友善格式）
        print("\n📝 註解品質檢查報告\n")
        print(f"檔案: {file_path}\n")

        if event_handlers:
            print(f"⚠️  {len(event_handlers)} 個事件處理函式缺少註解：")
            for func in event_handlers[:2]:
                print(f"   - {func.name} (行 {func.line_number})")
            print()

        if independent_widgets:
            print(f"⚠️  {len(independent_widgets)} 個獨立 Widget 缺少註解：")
            for widget in independent_widgets[:2]:
                print(f"   - {widget.name} (行 {widget.line_number})")
            print()

        if regular_funcs:
            print(f"⚠️  {len(regular_funcs)} 個一般函式缺少註解：")
            for func in regular_funcs[:2]:
                print(f"   - {func.name} (行 {func.line_number})")
            print()

        if auxiliary_funcs or dependent_widgets:
            print(f"✅ {len(auxiliary_funcs)} 個輔助函式和 {len(dependent_widgets)} 個依賴型 Widget 已正確豁免")
            print()

        print(f"詳細報告已儲存: {report_path.relative_to(PROJECT_ROOT)}\n")
        print("📚 註解規範: .claude/methodologies/comment-writing-methodology.md\n")

        log_message("Comment QA Hook: 執行完成")
        sys.exit(0)

    except json.JSONDecodeError as e:
        log_message(f"錯誤: JSON 解析失敗 - {e}")
        print(f"Comment QA Hook 錯誤: JSON 輸入格式錯誤", file=sys.stderr)
        sys.exit(1)

    except Exception as e:
        log_message(f"錯誤: Hook 執行失敗 - {e}")
        import traceback
        log_message(f"Traceback: {traceback.format_exc()}")
        print(f"Comment QA Hook 錯誤: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
