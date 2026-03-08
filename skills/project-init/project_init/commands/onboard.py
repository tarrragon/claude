"""onboard 指令 — 框架定制引導流程.

執行引導式流程，幫助新專案根據語言定制框架設定。
"""

from dataclasses import dataclass, field
from pathlib import Path

from project_init.lib import (
    OnboardMessages,
    check_claude_md,
    check_language_template,
    check_settings_local_json,
    detect_project_language,
    parse_hook_classification,
    check_hook_completeness,
)

# 狀態標記常數
STATUS_OK = "[OK]"
STATUS_TODO = "[TODO]"
STATUS_SKIP = "[SKIP]"

# 分隔線
SEPARATOR = "=" * 60
SUBSEPARATOR = "-" * 40


@dataclass
class TodoItem:
    """待辦項目."""

    description: str
    """項目描述."""
    hint: str = ""
    """額外提示或動作建議."""


@dataclass
class OnboardResult:
    """整個 onboard 流程的結果."""

    language: str
    """偵測到的專案語言."""
    all_ok: bool
    """是否所有檢查都通過."""
    todo_items: list[TodoItem] = field(default_factory=list)
    """待辦項目清單."""
    todo_count: int = 0
    """待辦項目數量."""


def run_onboard(project_root: Path) -> OnboardResult:
    """執行 onboard 引導流程.

    Args:
        project_root: 專案根目錄。

    Returns:
        OnboardResult: onboard 流程結果。同時輸出格式化文字到 stdout。
    """
    # Step 1: 偵測專案語言
    language_info = detect_project_language(project_root)
    language = language_info.language

    # Step 2: 讀取 Hook 語言分類
    hook_config_path = (
        project_root / ".claude" / "config" / "hook-language-classification.yaml"
    )
    hook_classification = parse_hook_classification(hook_config_path)

    # Step 3: 檢查 CLAUDE.md
    claude_md_info = check_claude_md(project_root)

    # Step 4: 檢查語言模板
    template_info = check_language_template(project_root, language)

    # Step 5: 檢查 settings.local.json
    settings_info = check_settings_local_json(project_root)

    # Step 6: 檢查 Hook 完整性
    hook_completeness = check_hook_completeness(project_root)

    # Step 7: 彙整待辦清單
    todo_items = _collect_todo_items(
        language, claude_md_info, template_info, settings_info, hook_completeness
    )

    result = OnboardResult(
        language=language,
        all_ok=len(todo_items) == 0,
        todo_items=todo_items,
        todo_count=len(todo_items),
    )

    # 輸出格式化結果
    _print_onboard_result(
        result, language_info, hook_classification, hook_completeness
    )

    return result


def _collect_todo_items(
    language: str, claude_md_info, template_info, settings_info, hook_completeness
) -> list[TodoItem]:
    """彙整待辦項目.

    Args:
        language: 偵測到的語言。
        claude_md_info: CLAUDE.md 檢查結果。
        template_info: 語言模板檢查結果。
        settings_info: settings.local.json 檢查結果。
        hook_completeness: Hook 完整性檢查結果。

    Returns:
        list[TodoItem]: 待辦項目清單。
    """
    items = []

    # CLAUDE.md 缺失
    if not claude_md_info.exists:
        items.append(
            TodoItem(
                description="CLAUDE.md 不存在",
                hint="從 .claude/templates/CLAUDE-template.md 複製",
            )
        )

    # 語言模板缺失（僅對已有模板的語言）
    if language == "flutter" and not template_info.exists:
        items.append(
            TodoItem(
                description=f"{language.upper()} 模板不存在",
                hint="檢查或複製 .claude/project-templates/FLUTTER.md",
            )
        )

    # settings.local.json 缺失
    if not settings_info.exists:
        items.append(
            TodoItem(
                description="settings.local.json 不存在",
                hint="根據 settings.json 建立並調整語言特定權限",
            )
        )

    # Hook 未完整登記
    if not hook_completeness.completeness_ok:
        unregistered_list = ", ".join(sorted(hook_completeness.unregistered_hooks))
        items.append(
            TodoItem(
                description=f"有 {len(hook_completeness.unregistered_hooks)} 個未登記的 Hook",
                hint=f"未登記: {unregistered_list[:80]}{'...' if len(unregistered_list) > 80 else ''} — 檢查是否需要在 settings.json 註冊或新增到 hook-exclude-list.json",
            )
        )

    return items


def _print_onboard_result(
    result: OnboardResult, language_info, hook_classification, hook_completeness
) -> None:
    """輸出格式化的 onboard 結果到 stdout."""
    print()
    _print_header()
    print()
    _print_language_section(language_info)
    _print_hook_classification_section(hook_classification)
    _print_hook_completeness_section(hook_completeness)
    _print_claude_md_section(result)
    _print_language_template_section(result)
    _print_settings_local_section(result)
    _print_todolist_section(result)


def _print_header() -> None:
    """輸出頁頭."""
    print(SEPARATOR)
    print(OnboardMessages.HEADER)
    print(SEPARATOR)


def _print_language_section(language_info) -> None:
    """輸出語言偵測部分."""
    print(f"[{OnboardMessages.LANGUAGE_SECTION}]")
    if language_info.is_available:
        language_display = _format_language_name(language_info.language)
        print(f"  {OnboardMessages.LANGUAGE_DETECTED.format(language=language_display)}")
        print(f"  {OnboardMessages.LANGUAGE_IDENTIFIER.format(identifier=language_info.identifier)}")
    else:
        print(f"  {OnboardMessages.LANGUAGE_UNKNOWN}")
    print()


def _print_hook_classification_section(hook_classification) -> None:
    """輸出 Hook 語言分類部分."""
    print(f"[{OnboardMessages.HOOK_CLASSIFICATION_SECTION}]")
    if hook_classification.is_available:
        if hook_classification.flutter_hooks:
            print(f"  {OnboardMessages.FLUTTER_HOOKS_LABEL}")
            for hook in hook_classification.flutter_hooks:
                print(f"    - {hook}")
        if hook_classification.project_specific_hooks:
            print(f"  {OnboardMessages.PROJECT_SPECIFIC_HOOKS_LABEL}")
            for hook in hook_classification.project_specific_hooks:
                print(f"    - {hook}")
        if not hook_classification.flutter_hooks and not hook_classification.project_specific_hooks:
            print("  無需調整的 Hook")
    else:
        print("  無法讀取 Hook 分類配置")
    print()


def _print_hook_completeness_section(hook_completeness) -> None:
    """輸出 Hook 完整性驗證部分."""
    print(f"[{OnboardMessages.HOOK_COMPLETENESS_SECTION}]")
    print(f"  {OnboardMessages.HOOK_REGISTERED_COUNT.format(count=len(hook_completeness.registered_hooks))}")
    print(f"  {OnboardMessages.HOOK_UNREGISTERED_COUNT.format(count=len(hook_completeness.unregistered_hooks))}")
    print(f"  {OnboardMessages.HOOK_EXCLUDED_COUNT.format(count=hook_completeness.excluded_count)}")
    print()

    if hook_completeness.completeness_ok:
        print(f"  {OnboardMessages.HOOK_COMPLETENESS_OK}")
    else:
        print(f"  {OnboardMessages.HOOK_COMPLETENESS_TODO}")
        print(f"  {OnboardMessages.HOOK_UNREGISTERED_LIST}")
        for hook in sorted(hook_completeness.unregistered_hooks)[:15]:
            print(f"    - {hook}")

        if len(hook_completeness.unregistered_hooks) > 15:
            remaining = len(hook_completeness.unregistered_hooks) - 15
            print(
                f"  {OnboardMessages.HOOK_UNREGISTERED_MORE.format(count=remaining)}"
            )

        print(f"  {OnboardMessages.HOOK_COMPLETENESS_HINT}")

    print()


def _print_claude_md_section(result: OnboardResult) -> None:
    """輸出 CLAUDE.md 部分."""
    print(f"[{OnboardMessages.CLAUDE_MD_SECTION}]")
    if result.language == "unknown":
        print(f"  {STATUS_SKIP} 無法確認需求")
    elif _has_todo_item(result.todo_items, "CLAUDE.md"):
        print(f"  {OnboardMessages.CLAUDE_MD_TODO}")
        print(f"  {OnboardMessages.CLAUDE_MD_COPY_HINT}")
    else:
        print(f"  {OnboardMessages.CLAUDE_MD_OK}")
    print()


def _print_language_template_section(result: OnboardResult) -> None:
    """輸出語言模板部分."""
    print(f"[{OnboardMessages.LANGUAGE_TEMPLATE_SECTION}]")
    if result.language == "flutter":
        if _has_todo_item(result.todo_items, "FLUTTER"):
            print(f"  {OnboardMessages.TEMPLATE_TODO.format(language='Flutter')}")
        else:
            print(f"  {OnboardMessages.TEMPLATE_OK.format(language='Flutter', template_file='FLUTTER.md')}")
    else:
        language_upper = result.language.upper()
        print(f"  {OnboardMessages.TEMPLATE_TODO.format(language=language_upper)}")
    print()


def _print_settings_local_section(result: OnboardResult) -> None:
    """輸出 settings.local.json 部分."""
    print(f"[{OnboardMessages.SETTINGS_LOCAL_SECTION}]")
    if result.language == "unknown":
        print(f"  {STATUS_SKIP} 無法確認需求")
    elif _has_todo_item(result.todo_items, "settings.local.json"):
        print(f"  {OnboardMessages.SETTINGS_LOCAL_TODO}")
        language_display = _format_language_name(result.language)
        print(f"  {OnboardMessages.SETTINGS_LOCAL_HINT.format(language=language_display)}")
    else:
        print(f"  {OnboardMessages.SETTINGS_LOCAL_OK}")
    print()


def _print_todolist_section(result: OnboardResult) -> None:
    """輸出待辦清單部分."""
    print(SEPARATOR)
    print(f"{OnboardMessages.TODOLIST_HEADER} ({_format_todo_count(result.todo_count)})")
    print(SEPARATOR)
    if result.todo_items:
        for i, item in enumerate(result.todo_items, 1):
            print(f"{i}. {item.description}")
            if item.hint:
                print(f"   → {item.hint}")
    else:
        print(f"  {OnboardMessages.TODOLIST_NONE}")
    print()


def _has_todo_item(items: list[TodoItem], keyword: str) -> bool:
    """檢查待辦清單中是否包含特定關鍵字."""
    return any(keyword in item.description for item in items)


def _format_language_name(language: str) -> str:
    """格式化語言名稱."""
    language_names = {
        "flutter": "Flutter/Dart",
        "go": "Go",
        "nodejs": "Node.js",
        "python": "Python",
        "unknown": "Unknown",
    }
    return language_names.get(language, language)


def _format_todo_count(count: int) -> str:
    """格式化待辦數量文字."""
    if count == 0:
        return OnboardMessages.TODOLIST_NONE
    return OnboardMessages.TODOLIST_COUNT.format(count=count)
