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


def _run_detection_checks(project_root: Path) -> tuple:
    """執行偵測和檢查步驟.

    Returns:
        tuple: (language_info, hook_classification, 其他檢查結果)
    """
    language_info = detect_project_language(project_root)
    language = language_info.language

    hook_config_path = (
        project_root / ".claude" / "config" / "hook-language-classification.yaml"
    )
    hook_classification = parse_hook_classification(hook_config_path)

    claude_md_info = check_claude_md(project_root)
    template_info = check_language_template(project_root, language)
    settings_info = check_settings_local_json(project_root)
    hook_completeness = check_hook_completeness(project_root)

    return (language_info, hook_classification, claude_md_info, template_info,
            settings_info, hook_completeness, language)


def _run_structure_checks(project_root: Path) -> tuple:
    """執行結構檢查和自動建立步驟.

    Returns:
        tuple: (docs_structure, gitignore_info, claude_dir_info, hook_config_info, config_dir_info)
    """
    docs_structure = check_docs_structure(project_root)
    _create_missing_docs_structure(project_root, docs_structure)
    docs_structure = check_docs_structure(project_root)

    gitignore_info = check_gitignore_completeness(project_root)
    claude_dir_info = check_claude_directory_structure(project_root)
    hook_config_info = check_hook_configurations(project_root)
    config_dir_info = check_claude_config_directory(project_root)

    return (docs_structure, gitignore_info, claude_dir_info, hook_config_info,
            config_dir_info)


def _run_final_checks(project_root: Path, language: str) -> tuple:
    """執行最終檢查步驟.

    Returns:
        tuple: (readme_info, language_standards_info)
    """
    readme_info = check_readme_md(project_root)
    language_standards_info = check_language_standards(project_root, language)
    return (readme_info, language_standards_info)


def _build_onboard_result(language: str, todo_items: list[TodoItem]) -> OnboardResult:
    """建立 onboard 結果物件."""
    return OnboardResult(
        language=language,
        all_ok=len(todo_items) == 0,
        todo_items=todo_items,
        todo_count=len(todo_items),
    )


def run_onboard(project_root: Path) -> OnboardResult:
    """執行 onboard 引導流程."""
    # 執行檢查
    lang_info, hook_class, claude_md, template, settings, hook_comp, lang = (
        _run_detection_checks(project_root))
    docs, gitignore, claude_dir, hook_cfg, cfg_dir = _run_structure_checks(project_root)
    readme, lang_standards = _run_final_checks(project_root, lang)

    # 彙整結果
    todo_items = _collect_todo_items(
        lang, claude_md, template, settings, hook_comp, docs, gitignore,
        claude_dir, hook_cfg, cfg_dir, readme, lang_standards)

    result = _build_onboard_result(lang, todo_items)

    # 輸出
    _print_onboard_result(result, lang_info, hook_class, hook_comp, docs,
        gitignore, claude_dir, hook_cfg, cfg_dir, readme, lang_standards)

    return result


def _collect_gitignore_items(gitignore_info) -> list[TodoItem]:
    """彙整 gitignore 相關待辦項目."""
    items = []
    if not gitignore_info.all_required_complete:
        missing_rules = ", ".join(gitignore_info.missing_rules[:3])
        hint = f"缺失: {missing_rules}{'...' if len(gitignore_info.missing_rules) > 3 else ''} — 新增到 .gitignore"
        items.append(TodoItem(description=".gitignore 缺失必須的框架規則", hint=hint))
    return items


def _collect_claude_dir_items(claude_dir_info) -> list[TodoItem]:
    """彙整 .claude 目錄相關待辦項目."""
    items = []
    if not claude_dir_info.all_required_complete:
        missing_dirs = ", ".join(claude_dir_info.missing_directories[:3])
        hint = f"缺失: {missing_dirs}{'...' if len(claude_dir_info.missing_directories) > 3 else ''} — 建立目錄"
        items.append(TodoItem(description=".claude 核心目錄結構缺失", hint=hint))
    return items


def _collect_hook_config_items(hook_config_info) -> list[TodoItem]:
    """彙整 Hook 配置檔相關待辦項目."""
    items = []
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
    return items


def _collect_config_dir_items(config_dir_info) -> list[TodoItem]:
    """彙整 .claude/config 目錄項目."""
    items = []
    if not config_dir_info.exists:
        items.append(
            TodoItem(
                description=".claude/config 目錄不存在",
                hint="建立 .claude/config 目錄並放入配置檔",
            )
        )
    return items


def _collect_claude_md_items(claude_md_info) -> list[TodoItem]:
    """彙整 CLAUDE.md 項目."""
    items = []
    if not claude_md_info.exists:
        items.append(
            TodoItem(
                description="CLAUDE.md 不存在",
                hint="從 .claude/templates/CLAUDE-template.md 複製",
            )
        )
    return items


def _collect_template_items(template_info, language) -> list[TodoItem]:
    """彙整語言模板項目."""
    items = []
    if language == "flutter" and not template_info.exists:
        items.append(
            TodoItem(
                description=f"{language.upper()} 模板不存在",
                hint="檢查或複製 .claude/project-templates/FLUTTER.md",
            )
        )
    return items


def _collect_settings_items(settings_info) -> list[TodoItem]:
    """彙整 settings.local.json 項目."""
    items = []
    if not settings_info.exists:
        items.append(
            TodoItem(
                description="settings.local.json 不存在",
                hint="根據 settings.json 建立並調整語言特定權限",
            )
        )
    return items


def _collect_core_file_items(
    claude_md_info, template_info, settings_info, config_dir_info, language
) -> list[TodoItem]:
    """彙整核心檔案相關待辦項目."""
    items = []
    items.extend(_collect_config_dir_items(config_dir_info))
    items.extend(_collect_claude_md_items(claude_md_info))
    items.extend(_collect_template_items(template_info, language))
    items.extend(_collect_settings_items(settings_info))
    return items


def _collect_hook_completeness_items(hook_completeness) -> list[TodoItem]:
    """彙整 Hook 完整性相關待辦項目."""
    items = []
    if not hook_completeness.completeness_ok:
        unregistered_list = ", ".join(sorted(hook_completeness.unregistered_hooks)[:3])
        hint = f"未登記: {unregistered_list}{'...' if len(hook_completeness.unregistered_hooks) > 3 else ''} — 檢查是否需要在 settings.json 註冊或新增到 hook-exclude-list.json"
        items.append(TodoItem(description=f"有 {len(hook_completeness.unregistered_hooks)} 個未登記的 Hook", hint=hint))
    return items


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
    """彙整 MUST 強制檢查項目."""
    items = []
    items.extend(_collect_gitignore_items(gitignore_info))
    items.extend(_collect_claude_dir_items(claude_dir_info))
    items.extend(_collect_hook_config_items(hook_config_info))
    items.extend(_collect_core_file_items(
        claude_md_info, template_info, settings_info, config_dir_info, language))
    items.extend(_collect_hook_completeness_items(hook_completeness))
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
    """彙整待辦項目（MUST + SHOULD）."""
    must_items = _collect_must_items(
        language, claude_md_info, template_info, settings_info,
        hook_completeness, gitignore_info, claude_dir_info,
        hook_config_info, config_dir_info)

    should_items = _collect_should_items(readme_info, language_standards_info)
    return must_items + should_items


def _print_core_sections(result: OnboardResult, language_info, hook_classification,
                         hook_completeness) -> None:
    """輸出核心區段."""
    print()
    _print_header()
    print()
    _print_language_section(language_info)
    _print_hook_classification_section(hook_classification)
    _print_hook_completeness_section(hook_completeness)


def _print_framework_sections(result: OnboardResult, docs_structure,
                              gitignore_info, claude_dir_info) -> None:
    """輸出框架檔案區段."""
    _print_claude_md_section(result)
    _print_language_template_section(result)
    _print_settings_local_section(result)
    _print_docs_structure_section(docs_structure)
    _print_gitignore_section(gitignore_info)
    _print_claude_directory_section(claude_dir_info)


def _print_config_sections(hook_config_info, config_dir_info,
                          readme_info, language_standards_info) -> None:
    """輸出配置和推薦區段."""
    _print_hook_config_section(hook_config_info)
    _print_config_directory_section(config_dir_info)
    _print_readme_section(readme_info)
    _print_language_standards_section(language_standards_info)


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
    _print_core_sections(result, language_info, hook_classification, hook_completeness)
    _print_framework_sections(result, docs_structure, gitignore_info, claude_dir_info)
    _print_config_sections(hook_config_info, config_dir_info, readme_info, language_standards_info)
    _print_todolist_section(result)


def _print_section_header(title: str) -> None:
    """輸出區段標題.

    Args:
        title: 區段標題文字。
    """
    print(f"[{title}]")


def _print_status_line(status: str, message: str, indent: int = 2) -> None:
    """輸出狀態行（含 [OK]/[TODO] 標記）.

    Args:
        status: 狀態標記（STATUS_OK, STATUS_TODO 等）。
        message: 訊息文字。
        indent: 縮排空格數（預設 2）。
    """
    print(f"{' ' * indent}{status} {message}")


def _print_hint_line(hint: str, indent: int = 2) -> None:
    """輸出提示行.

    Args:
        hint: 提示文字。
        indent: 縮排空格數（預設 2）。
    """
    if hint:
        print(f"{' ' * indent}→ {hint}")


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
    _print_section_header(".gitignore 框架規則")
    if gitignore_info.exists:
        if gitignore_info.all_required_complete:
            _print_status_line(STATUS_OK, "包含所有必須的框架排除規則")
        else:
            _print_status_line(STATUS_TODO, "缺失以下規則:")
            for rule in gitignore_info.missing_rules:
                print(f"      - {rule}")
    else:
        _print_status_line(STATUS_TODO, "檔案不存在")
    print()


def _print_claude_directory_section(claude_dir_info) -> None:
    """輸出 .claude 目錄結構檢查部分."""
    _print_section_header(".claude 核心目錄結構")
    if claude_dir_info.exists:
        if claude_dir_info.all_required_complete:
            _print_status_line(STATUS_OK, f"所有 {claude_dir_info.directory_count} 個必須目錄存在")
        else:
            _print_status_line(STATUS_TODO, f"缺失 {len(claude_dir_info.missing_directories)} 個目錄:")
            for directory in claude_dir_info.missing_directories:
                print(f"      - {directory}")
    else:
        _print_status_line(STATUS_TODO, ".claude 目錄不存在")
    print()


def _print_hook_config_section(hook_config_info) -> None:
    """輸出 Hook 配置檔檢查部分."""
    _print_section_header("Hook 配置檔")
    if not hook_config_info.config_dir_exists:
        _print_status_line(STATUS_TODO, ".claude/config 目錄不存在")
    elif hook_config_info.all_required_complete:
        _print_status_line(STATUS_OK, "所有配置檔都存在且格式有效")
        if hook_config_info.yaml_permission_info:
            perms = hook_config_info.yaml_permission_info
            perm_str = f"(讀: {perms.can_read}, 寫: {perms.can_write}, 執: {perms.can_execute})"
            print(f"    YAML 權限: {perm_str}")
    else:
        if hook_config_info.missing_files:
            _print_status_line(STATUS_TODO, "缺失以下檔案:")
            for file in hook_config_info.missing_files:
                print(f"      - {file}")
        if hook_config_info.format_errors:
            _print_status_line(STATUS_TODO, "格式錯誤:")
            for error in hook_config_info.format_errors:
                print(f"      - {error}")
    print()


def _print_config_directory_section(config_dir_info) -> None:
    """輸出 .claude/config 目錄檢查部分."""
    _print_section_header(".claude/config 目錄")
    if config_dir_info.exists:
        if config_dir_info.is_directory:
            _print_status_line(STATUS_OK, "目錄存在且可讀")
            print(f"    包含 {config_dir_info.config_file_count} 個檔案")
        else:
            _print_status_line(STATUS_TODO, "存在但不是目錄")
    else:
        _print_status_line(STATUS_TODO, "目錄不存在")
    print()


def _print_readme_section(readme_info) -> None:
    """輸出 README.md 檢查部分."""
    _print_section_header("README.md（推薦）")
    if readme_info.exists:
        if readme_info.is_nonempty:
            _print_status_line(STATUS_OK, f"檔案存在且非空（{readme_info.size_bytes} 位元組）")
        else:
            _print_status_line("[WARN]", "檔案存在但為空")
    else:
        _print_status_line(STATUS_SKIP, "檔案不存在（推薦建立）")
    print()


def _print_language_standards_section(language_standards_info) -> None:
    """輸出語言規範文件檢查部分."""
    _print_section_header("語言規範文件（推薦）")
    if language_standards_info.detected_language == "unknown":
        _print_status_line(STATUS_SKIP, "無法確認語言")
    elif language_standards_info.exists:
        _print_status_line(STATUS_OK, f"{language_standards_info.expected_standard_file} 存在")
    else:
        _print_status_line(STATUS_SKIP, f"{language_standards_info.expected_standard_file} 不存在（推薦建立）")

    if language_standards_info.standard_files_available:
        files_str = ", ".join(language_standards_info.standard_files_available)
        print(f"    可用的規範檔: {files_str}")
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
