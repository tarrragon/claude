"""onboard 指令 — 框架定制引導流程.

執行引導式流程，幫助新專案根據語言定制框架設定。
"""

from dataclasses import dataclass, field
from pathlib import Path

from project_init.lib import (
    OnboardMessages,
    check_claude_config_directory,
    check_claude_directory_structure,
    check_claude_md,
    check_docs_structure,
    check_gitignore_completeness,
    check_hook_configurations,
    check_hook_completeness,
    check_language_standards,
    check_language_template,
    check_readme_md,
    check_settings_local_json,
    detect_project_language,
    parse_hook_classification,
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

    # Step 7: 檢查 docs 目錄結構
    docs_structure = check_docs_structure(project_root)

    # Step 8: 自動建立缺失的 docs 結構
    _create_missing_docs_structure(project_root, docs_structure)

    # Step 8.5: 重新檢查 docs 結構（建立完成後）
    docs_structure = check_docs_structure(project_root)

    # Step 9: 檢查 .gitignore 完整性（MUST 項）
    gitignore_info = check_gitignore_completeness(project_root)

    # Step 10: 檢查 .claude 核心目錄結構（MUST 項）
    claude_dir_info = check_claude_directory_structure(project_root)

    # Step 11: 檢查 Hook 配置檔（MUST 項）
    hook_config_info = check_hook_configurations(project_root)

    # Step 12: 檢查 .claude/config 目錄（MUST 項）
    config_dir_info = check_claude_config_directory(project_root)

    # Step 13: 檢查 README.md（SHOULD 項）
    readme_info = check_readme_md(project_root)

    # Step 14: 檢查語言規範文件（SHOULD 項）
    language_standards_info = check_language_standards(project_root, language)

    # Step 15: 彙整待辦清單
    todo_items = _collect_todo_items(
        language,
        claude_md_info,
        template_info,
        settings_info,
        hook_completeness,
        docs_structure,
        gitignore_info,
        claude_dir_info,
        hook_config_info,
        config_dir_info,
        readme_info,
        language_standards_info,
    )

    result = OnboardResult(
        language=language,
        all_ok=len(todo_items) == 0,
        todo_items=todo_items,
        todo_count=len(todo_items),
    )

    # 輸出格式化結果
    _print_onboard_result(
        result,
        language_info,
        hook_classification,
        hook_completeness,
        docs_structure,
        gitignore_info,
        claude_dir_info,
        hook_config_info,
        config_dir_info,
        readme_info,
        language_standards_info,
    )

    return result


def _collect_must_items(
    language: str,
    claude_md_info,
    template_info,
    settings_info,
    hook_completeness,
    gitignore_info,
    claude_dir_info,
    hook_config_info,
    config_dir_info,
) -> list[TodoItem]:
    """彙整 MUST 強制檢查項目.

    Args:
        language: 偵測到的語言。
        claude_md_info: CLAUDE.md 檢查結果。
        template_info: 語言模板檢查結果。
        settings_info: settings.local.json 檢查結果。
        hook_completeness: Hook 完整性檢查結果。
        gitignore_info: .gitignore 檢查結果。
        claude_dir_info: .claude 目錄結構檢查結果。
        hook_config_info: Hook 配置檔檢查結果。
        config_dir_info: .claude/config 目錄檢查結果。

    Returns:
        list[TodoItem]: 強制檢查待辦項目。
    """
    items = []

    if not gitignore_info.all_required_complete:
        missing_rules = ", ".join(gitignore_info.missing_rules[:3])
        hint = f"缺失: {missing_rules}{'...' if len(gitignore_info.missing_rules) > 3 else ''} — 新增到 .gitignore"
        items.append(TodoItem(description=".gitignore 缺失必須的框架規則", hint=hint))

    if not claude_dir_info.all_required_complete:
        missing_dirs = ", ".join(claude_dir_info.missing_directories[:3])
        hint = f"缺失: {missing_dirs}{'...' if len(claude_dir_info.missing_directories) > 3 else ''} — 建立目錄"
        items.append(TodoItem(description=".claude 核心目錄結構缺失", hint=hint))

    if not hook_config_info.all_required_complete:
        if hook_config_info.missing_files:
            missing = ", ".join(hook_config_info.missing_files[:2])
            hint = f"缺失: {missing} — 新增或複製配置檔"
        elif hook_config_info.format_errors:
            error = hook_config_info.format_errors[0][:80]
            hint = f"格式錯誤: {error} — 修復檔案格式"
        else:
            hint = "檢查配置檔"
        items.append(TodoItem(description="Hook 配置檔不完整或格式錯誤", hint=hint))

    if not config_dir_info.exists:
        items.append(
            TodoItem(
                description=".claude/config 目錄不存在",
                hint="建立 .claude/config 目錄並放入配置檔",
            )
        )

    if not claude_md_info.exists:
        items.append(
            TodoItem(
                description="CLAUDE.md 不存在",
                hint="從 .claude/templates/CLAUDE-template.md 複製",
            )
        )

    if language == "flutter" and not template_info.exists:
        items.append(
            TodoItem(
                description=f"{language.upper()} 模板不存在",
                hint="檢查或複製 .claude/project-templates/FLUTTER.md",
            )
        )

    if not settings_info.exists:
        items.append(
            TodoItem(
                description="settings.local.json 不存在",
                hint="根據 settings.json 建立並調整語言特定權限",
            )
        )

    if not hook_completeness.completeness_ok:
        unregistered_list = ", ".join(sorted(hook_completeness.unregistered_hooks)[:3])
        hint = f"未登記: {unregistered_list}{'...' if len(hook_completeness.unregistered_hooks) > 3 else ''} — 檢查是否需要在 settings.json 註冊或新增到 hook-exclude-list.json"
        items.append(TodoItem(description=f"有 {len(hook_completeness.unregistered_hooks)} 個未登記的 Hook", hint=hint))

    return items


def _collect_should_items(
    readme_info,
    language_standards_info,
) -> list[TodoItem]:
    """彙整 SHOULD 推薦檢查項目.

    Args:
        readme_info: README.md 檢查結果。
        language_standards_info: 語言規範檔檢查結果。

    Returns:
        list[TodoItem]: 推薦檢查待辦項目。
    """
    items = []

    if not readme_info.exists:
        items.append(
            TodoItem(
                description="README.md 不存在（推薦）",
                hint="建立 README.md 記錄專案說明",
            )
        )

    if language_standards_info.missing_standards:
        missing = ", ".join(language_standards_info.missing_standards)
        hint = f"缺失: {missing} — 複製或建立規範檔"
        items.append(TodoItem(description=f"語言規範文件不存在（推薦）", hint=hint))

    return items


def _collect_todo_items(
    language: str,
    claude_md_info,
    template_info,
    settings_info,
    hook_completeness,
    docs_structure,
    gitignore_info,
    claude_dir_info,
    hook_config_info,
    config_dir_info,
    readme_info,
    language_standards_info,
) -> list[TodoItem]:
    """彙整待辦項目.

    分別收集 MUST（強制）和 SHOULD（推薦）項目，然後合併。

    Args:
        language: 偵測到的語言。
        claude_md_info: CLAUDE.md 檢查結果。
        template_info: 語言模板檢查結果。
        settings_info: settings.local.json 檢查結果。
        hook_completeness: Hook 完整性檢查結果。
        docs_structure: docs 目錄結構檢查結果。
        gitignore_info: .gitignore 檢查結果。
        claude_dir_info: .claude 目錄結構檢查結果。
        hook_config_info: Hook 配置檔檢查結果。
        config_dir_info: .claude/config 目錄檢查結果。
        readme_info: README.md 檢查結果。
        language_standards_info: 語言規範檔檢查結果。

    Returns:
        list[TodoItem]: 待辦項目清單。
    """
    must_items = _collect_must_items(
        language,
        claude_md_info,
        template_info,
        settings_info,
        hook_completeness,
        gitignore_info,
        claude_dir_info,
        hook_config_info,
        config_dir_info,
    )

    should_items = _collect_should_items(
        readme_info,
        language_standards_info,
    )

    return must_items + should_items


def _print_onboard_result(
    result: OnboardResult,
    language_info,
    hook_classification,
    hook_completeness,
    docs_structure,
    gitignore_info,
    claude_dir_info,
    hook_config_info,
    config_dir_info,
    readme_info,
    language_standards_info,
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
    _print_docs_structure_section(docs_structure)
    _print_gitignore_section(gitignore_info)
    _print_claude_directory_section(claude_dir_info)
    _print_hook_config_section(hook_config_info)
    _print_config_directory_section(config_dir_info)
    _print_readme_section(readme_info)
    _print_language_standards_section(language_standards_info)
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


def _print_docs_structure_section(docs_structure) -> None:
    """輸出 docs 目錄結構部分."""
    print(f"[{OnboardMessages.DOCS_STRUCTURE_SECTION}]")
    if docs_structure.all_complete:
        print(f"  {OnboardMessages.DOCS_STRUCTURE_OK}")
    else:
        print(f"  {OnboardMessages.DOCS_STRUCTURE_TODO}")
        print(f"  {OnboardMessages.DOCS_STRUCTURE_CREATE_HINT}")
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


def _print_gitignore_section(gitignore_info) -> None:
    """輸出 .gitignore 檢查部分."""
    print("[.gitignore 框架規則]")
    if gitignore_info.exists:
        if gitignore_info.all_required_complete:
            print("  [OK] 包含所有必須的框架排除規則")
        else:
            print("  [TODO] 缺失以下規則:")
            for rule in gitignore_info.missing_rules:
                print(f"    - {rule}")
    else:
        print("  [TODO] 檔案不存在")
    print()


def _print_claude_directory_section(claude_dir_info) -> None:
    """輸出 .claude 目錄結構檢查部分."""
    print("[.claude 核心目錄結構]")
    if claude_dir_info.exists:
        if claude_dir_info.all_required_complete:
            print(f"  [OK] 所有 {claude_dir_info.directory_count} 個必須目錄存在")
        else:
            print(f"  [TODO] 缺失 {len(claude_dir_info.missing_directories)} 個目錄:")
            for directory in claude_dir_info.missing_directories:
                print(f"    - {directory}")
    else:
        print("  [TODO] .claude 目錄不存在")
    print()


def _print_hook_config_section(hook_config_info) -> None:
    """輸出 Hook 配置檔檢查部分."""
    print("[Hook 配置檔]")
    if not hook_config_info.config_dir_exists:
        print("  [TODO] .claude/config 目錄不存在")
    elif hook_config_info.all_required_complete:
        print("  [OK] 所有配置檔都存在且格式有效")
    else:
        if hook_config_info.missing_files:
            print("  [TODO] 缺失以下檔案:")
            for file in hook_config_info.missing_files:
                print(f"    - {file}")
        if hook_config_info.format_errors:
            print("  [TODO] 格式錯誤:")
            for error in hook_config_info.format_errors:
                print(f"    - {error}")
    print()


def _print_config_directory_section(config_dir_info) -> None:
    """輸出 .claude/config 目錄檢查部分."""
    print("[.claude/config 目錄]")
    if config_dir_info.exists:
        if config_dir_info.is_directory:
            print("  [OK] 目錄存在且可讀")
            print(f"  包含 {config_dir_info.config_file_count} 個檔案")
        else:
            print("  [TODO] 存在但不是目錄")
    else:
        print("  [TODO] 目錄不存在")
    print()


def _print_readme_section(readme_info) -> None:
    """輸出 README.md 檢查部分."""
    print("[README.md（推薦）]")
    if readme_info.exists:
        if readme_info.is_nonempty:
            print(f"  [OK] 檔案存在且非空（{readme_info.size_bytes} 位元組）")
        else:
            print("  [WARN] 檔案存在但為空")
    else:
        print("  [SKIP] 檔案不存在（推薦建立）")
    print()


def _print_language_standards_section(language_standards_info) -> None:
    """輸出語言規範文件檢查部分."""
    print("[語言規範文件（推薦）]")
    if language_standards_info.detected_language == "unknown":
        print("  [SKIP] 無法確認語言")
    elif language_standards_info.exists:
        print(f"  [OK] {language_standards_info.expected_standard_file} 存在")
    else:
        print(f"  [SKIP] {language_standards_info.expected_standard_file} 不存在（推薦建立）")

    if language_standards_info.standard_files_available:
        print(f"  可用的規範檔: {', '.join(language_standards_info.standard_files_available)}")
    print()


def _create_missing_docs_structure(project_root: Path, docs_structure) -> None:
    """自動建立缺失的 docs 目錄結構.

    此函式嘗試建立缺失的 docs 目錄和檔案。如果建立失敗，將靜默失敗，
    待辦清單會在後續檢查時反映實際狀態。

    Args:
        project_root: 專案根目錄。
        docs_structure: docs 結構檢查結果。
    """
    docs_dir = project_root / "docs"
    work_logs_dir = docs_dir / "work-logs"
    todolist_file = docs_dir / "todolist.yaml"

    try:
        # 建立 docs/ 目錄
        docs_dir.mkdir(parents=True, exist_ok=True)

        # 建立 docs/work-logs/ 子目錄
        work_logs_dir.mkdir(parents=True, exist_ok=True)

        # 建立 docs/todolist.yaml 檔案
        todolist_file.touch(exist_ok=True)

    except (OSError, PermissionError):
        # 如果建立失敗，靜默失敗（因為這只是引導，不是關鍵操作）
        # 待辦清單會顯示結構缺失，使用者可手動處理
        pass
