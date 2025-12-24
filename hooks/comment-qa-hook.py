#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "pyyaml>=6.0",
# ]
# ///

"""
Comment Quality Assurance Hook - 註解品質保證檢查 (v3.0 多語言支援)

用途: 檢查程式碼的註解品質，確保事件處理函式和重要類別具備完整追溯資訊
觸發: PostToolUse Hook (matcher: Write|Edit|MultiEdit)
模式: 建議模式（不阻擋開發，提供改善建議）

支援語言:
✅ Dart (StatefulWidget, event handlers, UseCase functions)
✅ JavaScript (functions, classes, JSDoc)
✅ TypeScript (functions, classes, JSDoc)
🔜 PHP (functions, classes) - 可選啟用
🔜 Go (functions) - 可選啟用

檢查策略:
✅ 必須註解:
  - Dart: 事件處理函式 (handle*, on*, process*, emit*, dispatch*)
  - Dart: 獨立 Widget (StatefulWidget, ConsumerWidget, StreamBuilder, FutureBuilder)
  - JavaScript/TypeScript: 匯出函式、類別方法
  - 所有語言: UseCase 和 Domain 層的公開函式

❌ 可豁免註解:
  - 輔助函式 (_開頭的私有函式)
  - 測試檔案
  - 生成檔案

配置: .claude/hooks/comment-qa-config.yaml (可選)

參考規範:
- .claude/methodologies/comment-writing-methodology.md
- docs/event-driven-architecture-design.md

版本: v3.0
建立日期: 2025-01-10
更新日期: 2025-01-10
變更記錄:
- v3.0: 整合 ParserFactory，支援多語言（Dart, JavaScript, TypeScript）
- v2.0: Dart 專用版本
"""

import json
import sys
import os
import re
import yaml
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

# 動態載入 Parser 模組
try:
    sys.path.insert(0, str(PROJECT_ROOT / ".claude/hooks"))
    from parsers.base import Language, ParserFactory, Function
    PARSER_AVAILABLE = True
except ImportError as e:
    PARSER_AVAILABLE = False
    print(f"警告: 無法載入 Parser 模組 - {e}", file=sys.stderr)


@dataclass
class FunctionInfo:
    """函式資訊（統一格式）"""
    name: str
    signature: str
    line_number: int
    has_complete_comment: bool
    existing_comment: Optional[str] = None
    return_type: Optional[str] = None
    is_async: bool = False
    function_type: str = 'function'


@dataclass
class WidgetInfo:
    """Widget 資訊（Dart 專用）"""
    name: str
    base_class: str
    line_number: int
    is_private: bool
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


def load_config() -> dict:
    """
    載入配置檔

    優先順序:
    1. .claude/hooks/comment-qa-config.yaml
    2. 預設配置（向後相容）
    """
    config_path = PROJECT_ROOT / ".claude/hooks/comment-qa-config.yaml"

    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                log_message(f"載入配置檔: {config_path.name}")
                return config
        except Exception as e:
            log_message(f"警告: 配置檔載入失敗，使用預設配置 - {e}")

    # 預設配置（向後相容）
    return {
        'version': '3.0',
        'global': {
            'enabled': True,
            'strict_mode': False
        },
        'languages': {
            'dart': {'enabled': True, 'check_functions': True, 'check_widgets': True},
            'javascript': {'enabled': True, 'check_functions': True, 'check_jsdoc': True},
            'typescript': {'enabled': True, 'check_functions': True, 'check_jsdoc': True}
        },
        'exclude': {
            'patterns': ['**/test/**', '**/*_test.*', '**/*.g.dart', '**/*.freezed.dart'],
            'files': []
        },
        'priority_dirs': ['lib/domains/', 'lib/presentation/', 'lib/use_cases/']
    }


def should_process_file(file_path: str, config: dict) -> Tuple[bool, Optional[Language]]:
    """
    判斷是否需要處理此檔案

    Returns:
        (should_process, language) - 是否處理和語言類型
    """
    path = Path(file_path)

    # 檢查排除模式
    exclude_patterns = config.get('exclude', {}).get('patterns', [])
    for pattern in exclude_patterns:
        if path.match(pattern):
            return False, None

    # 檢查排除檔案
    exclude_files = config.get('exclude', {}).get('files', [])
    if path.name in exclude_files:
        return False, None

    # 使用 ParserFactory 檢測語言
    if not PARSER_AVAILABLE:
        # Fallback: 只處理 Dart
        if file_path.endswith('.dart'):
            return True, None
        return False, None

    try:
        language = ParserFactory.detect_language(path)

        if language == Language.UNKNOWN:
            return False, None

        # 檢查語言是否啟用
        lang_name = language.value
        lang_config = config.get('languages', {}).get(lang_name, {})

        if not lang_config.get('enabled', False):
            log_message(f"語言 {lang_name} 未啟用，跳過檔案")
            return False, None

        # Dart 專案優先目錄檢查
        if language == Language.DART:
            priority_dirs = config.get('priority_dirs', [])
            if priority_dirs and not any(d in file_path for d in priority_dirs):
                return False, None

        return True, language

    except Exception as e:
        log_message(f"語言檢測失敗: {e}")
        return False, None


def extract_functions_with_parser(file_path: Path, language: Language) -> List[FunctionInfo]:
    """
    使用 ParserFactory 提取函式

    Returns:
        函式列表（FunctionInfo 格式）
    """
    try:
        parser = ParserFactory.create_parser(language)
        code = file_path.read_text(encoding='utf-8')

        # 使用 Parser 提取函式
        parsed_functions = parser.extract_functions(code)

        # 轉換為 FunctionInfo 格式
        functions = []
        for func in parsed_functions:
            # 重建簽名（簡化版）
            signature = f"{func.return_type or 'void'} {func.name}(...)" if func.return_type else f"{func.name}(...)"

            func_info = FunctionInfo(
                name=func.name,
                signature=signature,
                line_number=func.line_number,
                has_complete_comment=func.has_comment,
                return_type=func.return_type,
                is_async=func.is_async,
                function_type=func.function_type
            )
            functions.append(func_info)

        return functions

    except Exception as e:
        log_message(f"Parser 提取失敗: {e}")
        return []


def extract_dart_widgets(file_path: Path) -> List[WidgetInfo]:
    """
    提取 Dart Widget（Dart 專用邏輯）
    """
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

        return widgets

    except Exception as e:
        log_message(f"錯誤: 提取 Widget 失敗 - {e}")
        return []


def is_event_handler_function(func_name: str, return_type: str = "") -> bool:
    """判斷是否為事件處理函式（Dart 專用）"""
    event_patterns = [
        r'^handle[A-Z]',
        r'^on[A-Z]',
        r'^process[A-Z]',
        r'^emit[A-Z]',
        r'^dispatch[A-Z]'
    ]

    for pattern in event_patterns:
        if re.search(pattern, func_name):
            return True

    # 檢查回傳類型
    if return_type:
        if any(t in return_type for t in ['Future', 'Stream', 'OperationResult']):
            if not func_name[0].isupper():
                return True

    return False


def is_auxiliary_function(func_name: str) -> bool:
    """判斷是否為輔助函式（可豁免註解）"""
    if not func_name.startswith('_'):
        return False

    auxiliary_patterns = [
        r'isValid', r'format', r'prepare', r'convert',
        r'validate', r'transform', r'parse', r'extract',
        r'check', r'build',
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

    has_requirement = any(keyword in comment_text for keyword in ['需求來源', '需求:', 'UC-', 'BR-'])
    has_traceability = any(keyword in comment_text for keyword in ['規格文件', '工作日誌', 'docs/'])

    return has_requirement and has_traceability


def find_related_work_log() -> Optional[Path]:
    """查找當前相關的工作日誌"""
    work_log_dir = PROJECT_ROOT / "docs/work-logs"

    if not work_log_dir.exists():
        return None

    try:
        pattern = r'v\d+\.\d+\.\d+.*\.md'
        work_logs = [
            f for f in work_log_dir.iterdir()
            if f.is_file() and re.match(pattern, f.name)
        ]

        if not work_logs:
            return None

        latest_log = max(work_logs, key=lambda f: f.stat().st_mtime)
        log_message(f"找到工作日誌: {latest_log.name}")
        return latest_log

    except Exception as e:
        log_message(f"錯誤: 查找工作日誌失敗 - {e}")
        return None


def extract_design_solution(work_log_path: Path) -> str:
    """從工作日誌提取設計方案描述"""
    try:
        content = work_log_path.read_text(encoding='utf-8')

        solution_patterns = [
            r'方案[A-Z]-\d+[^\n]*',
            r'設計方案[：:]\s*([^\n]+)',
            r'Phase 1.*?方案[：:]\s*([^\n]+)',
        ]

        for pattern in solution_patterns:
            match = re.search(pattern, content)
            if match:
                solution = match.group(0) if not match.groups() else match.group(1)
                return solution.strip()

        version = work_log_path.stem
        return f"{version} Phase 1 設計"

    except Exception as e:
        log_message(f"錯誤: 提取設計方案失敗 - {e}")
        return "請參考工作日誌"


def infer_usecase_from_path(file_path: str) -> str:
    """從檔案路徑推測相關的 UseCase"""
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


def find_related_spec_files() -> List[Path]:
    """查找相關的規格文件"""
    docs_dir = PROJECT_ROOT / "docs"
    if not docs_dir.exists():
        return []

    spec_files = []
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


def generate_comment_template(
    item: any,
    item_type: str,
    file_path: str,
    work_log_path: Optional[Path],
    design_solution: str
) -> str:
    """生成標準註解框架"""
    usecase = infer_usecase_from_path(file_path)

    spec_files = find_related_spec_files()
    if spec_files:
        spec_link = f"docs/{spec_files[0].name}"
    else:
        spec_link = "docs/app-requirements-spec.md"

    if work_log_path:
        work_log_ref = f"docs/work-logs/{work_log_path.name} - {design_solution}"
    else:
        work_log_ref = "請補充工作日誌連結"

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

    else:
        template = f"""/// 【需求來源】{usecase}
/// 【規格文件】{spec_link}
/// 【設計方案】{design_solution}
/// 【工作日誌】{work_log_ref}
/// 【修改約束】請補充此函式的修改約束條件
/// 【維護警告】請補充相依模組和影響範圍
{item.signature}"""

    return template


def generate_report(
    file_path: str,
    functions: List[FunctionInfo],
    widgets: List[WidgetInfo],
    work_log_path: Optional[Path],
    design_solution: str,
    language: Optional[Language]
) -> str:
    """生成完整的檢查報告（Markdown 格式）"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 分類函式
    event_handlers = []
    auxiliary_funcs = []
    regular_funcs = []

    for func in functions:
        return_type = func.return_type or ''
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
    lang_name = language.value if language else 'unknown'
    report_lines = [
        "# 註解品質檢查報告",
        "",
        "## 基本資訊",
        f"- **檢查時間**: {timestamp}",
        f"- **檔案路徑**: {file_path}",
        f"- **程式語言**: {lang_name}",
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

        for i, func in enumerate(regular_funcs[:5], 1):
            report_lines.append(f"### {i}. {func.name} (行 {func.line_number})")
            report_lines.append("")
            code_block = "```javascript" if lang_name in ['javascript', 'typescript'] else "```dart"
            report_lines.append(code_block)
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
        f"Hook 版本: v3.0 (多語言支援: {lang_name})",
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
        log_message("Comment QA Hook v3.0: 開始執行（多語言支援）")

        # 1. 載入配置
        config = load_config()

        # 2. 讀取 JSON 輸入
        input_data = json.load(sys.stdin)

        # 3. 提取工具資訊
        tool_name = input_data.get("tool_name", "")
        tool_input = input_data.get("tool_input", {})
        tool_response = input_data.get("tool_response", {})

        # 4. 檢查工具是否成功執行
        if not tool_response.get("success", False):
            log_message(f"工具 {tool_name} 執行失敗，跳過檢查")
            sys.exit(0)

        # 5. 檢查檔案是否需要處理（包含語言檢測）
        file_path = tool_input.get("file_path", "")
        should_process, language = should_process_file(file_path, config)

        if not should_process:
            log_message(f"檔案 {file_path} 不需要處理")
            sys.exit(0)

        log_message(f"處理檔案: {file_path} (語言: {language.value if language else 'dart'})")

        # 6. 提取函式和 Widget
        file_path_obj = Path(file_path)

        if PARSER_AVAILABLE and language:
            # 使用 ParserFactory
            functions = extract_functions_with_parser(file_path_obj, language)
        else:
            # Fallback: 只處理 Dart（向後相容）
            functions = []

        # Dart Widget（只在 Dart 檔案中提取）
        widgets = []
        if language == Language.DART or not PARSER_AVAILABLE:
            widgets = extract_dart_widgets(file_path_obj)

        log_message(f"發現 {len(functions)} 個函式, {len(widgets)} 個 Widget")

        # 7. 分類檢查
        event_handlers = []
        auxiliary_funcs = []
        regular_funcs = []

        for func in functions:
            return_type = func.return_type or ''
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

        # 8. 查找工作日誌
        work_log_path = find_related_work_log()

        # 9. 提取設計方案
        design_solution = extract_design_solution(work_log_path) if work_log_path else "請參考工作日誌"

        # 10. 生成報告
        report_content = generate_report(file_path, functions, widgets, work_log_path, design_solution, language)

        # 11. 儲存報告
        report_path = save_report(report_content)

        # 12. 輸出建議（友善格式）
        print("\n📝 註解品質檢查報告 (v3.0)\n")
        print(f"檔案: {file_path}")
        print(f"語言: {language.value if language else 'dart'}\n")

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

        log_message("Comment QA Hook v3.0: 執行完成")
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
