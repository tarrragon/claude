"""Onboard 檢查模組 — 偵測專案語言、檢查框架檔案和 Hook 分類.

此模組提供一組 onboard 相關的偵測函式，用於引導新專案使用框架。
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import json
import yaml
import stat


# 必須目錄清單常數
REQUIRED_DIRECTORIES = [
    ("rules", "rules/"),
    ("hooks", "hooks/"),
    ("skills", "skills/"),
    ("methodologies", "methodologies/"),
    ("references", "references/"),
    ("agents", "agents/"),
    ("config", "config/"),
]

# 必須的 .gitignore 規則
GITIGNORE_REQUIRED_RULES = [
    "coverage",
    "htmlcov",
    ".claude/hook-logs",
    ".claude/worktrees",
    ".claude/tool-results",
    ".claude/handoff",
]

# Hook 配置檔案名稱常數
HOOK_CONFIG_YAML = "hook-language-classification.yaml"
HOOK_CONFIG_EXCLUDE_JSON = "hook-exclude-list.json"
HOOK_CONFIG_SETTINGS_JSON = "settings.json"


@dataclass
class ProjectLanguageInfo:
    """專案語言偵測結果."""

    language: str
    """偵測到的語言: 'flutter', 'go', 'nodejs', 'python', 'unknown'."""
    identifier: str
    """識別依據（檔案名稱）."""
    is_available: bool
    """是否成功偵測."""


@dataclass
class HookClassificationInfo:
    """Hook 語言分類資訊."""

    flutter_hooks: list[str]
    """Flutter 特定的 Hook 列表."""
    project_specific_hooks: list[str]
    """專案特定的 Hook 列表."""
    is_available: bool
    """是否成功解析分類檔."""


@dataclass
class FrameworkFileInfo:
    """框架檔案狀態."""

    name: str
    """檔案名稱."""
    exists: bool
    """檔案是否存在."""
    path: Optional[Path] = None
    """檔案完整路徑."""


@dataclass
class DocsStructureInfo:
    """Docs 目錄結構狀態."""

    exists: bool
    """docs/ 目錄是否存在."""
    has_work_logs: bool
    """docs/work-logs/ 子目錄是否存在."""
    has_todolist: bool
    """docs/todolist.yaml 檔案是否存在."""
    all_complete: bool
    """所有必要目錄和檔案是否都存在."""


@dataclass
class GitignoreCheckInfo:
    """GitIgnore 完整性檢查結果."""

    exists: bool
    """檔案是否存在."""
    has_coverage_rules: bool
    """包含 coverage/ 規則."""
    has_hook_logs_rule: bool
    """包含 .claude/hook-logs/ 規則."""
    has_worktrees_rule: bool
    """包含 .claude/worktrees/ 規則."""
    has_tool_results_rule: bool
    """包含 .claude/tool-results/ 規則."""
    has_handoff_rule: bool
    """包含 .claude/handoff/ 規則."""
    all_required_complete: bool
    """所有必須規則都存在."""
    missing_rules: list[str] = field(default_factory=list)
    """缺失的規則清單."""


@dataclass
class ClaudeDirectoryCheckInfo:
    """Claude 核心目錄結構檢查結果."""

    exists: bool
    """目錄是否存在."""
    has_rules: bool
    """包含 rules 目錄."""
    has_hooks: bool
    """包含 hooks 目錄."""
    has_skills: bool
    """包含 skills 目錄."""
    has_methodologies: bool
    """包含 methodologies 目錄."""
    has_references: bool
    """包含 references 目錄."""
    has_agents: bool
    """包含 agents 目錄."""
    has_config: bool
    """包含 config 目錄."""
    all_required_complete: bool
    """所有必須目錄都存在."""
    missing_directories: list[str] = field(default_factory=list)
    """缺失目錄清單."""
    directory_count: int = 0
    """已驗證的目錄總數."""


@dataclass
class PermissionInfo:
    """檔案權限資訊."""

    can_read: bool
    """是否有讀取權限."""
    can_write: bool
    """是否有寫入權限."""
    can_execute: bool
    """是否有執行權限."""
    error_message: str = ""
    """權限檢查錯誤訊息."""


@dataclass
class HookConfigurationCheckInfo:
    """Hook 配置檔完整性檢查結果."""

    config_dir_exists: bool
    """設定目錄是否存在."""
    has_language_classification_yaml: bool
    """包含 hook-language-classification.yaml."""
    has_exclude_list_json: bool
    """包含 hook-exclude-list.json."""
    has_settings_json: bool
    """包含 settings.json."""
    all_required_complete: bool
    """所有必須檔案都存在."""
    missing_files: list[str] = field(default_factory=list)
    """缺失的檔案清單."""
    yaml_format_valid: bool = True
    """YAML 格式是否有效."""
    json_format_valid: bool = True
    """JSON 格式是否有效."""
    format_errors: list[str] = field(default_factory=list)
    """格式錯誤清單."""
    yaml_permission_info: PermissionInfo = field(default_factory=lambda: PermissionInfo(True, False, False))
    """YAML 檔案權限資訊."""
    json_permission_info: PermissionInfo = field(default_factory=lambda: PermissionInfo(True, False, False))
    """JSON 檔案權限資訊."""


@dataclass
class ClaudeConfigCheckInfo:
    """Claude 設定目錄檢查結果."""

    exists: bool
    """目錄是否存在."""
    is_directory: bool
    """確認是目錄而非檔案."""
    config_file_count: int = 0
    """設定檔數量."""
    total_size_bytes: int = 0
    """目錄總大小."""
    has_read_permissions: bool = True
    """有讀取權限."""


@dataclass
class ReadmeCheckInfo:
    """README.md 檢查結果."""

    exists: bool
    """檔案是否存在."""
    path: Optional[Path] = None
    """檔案路徑."""
    size_bytes: int = 0
    """檔案大小."""
    is_nonempty: bool = False
    """是否非空檔案."""


@dataclass
class LanguageStandardCheckInfo:
    """語言規範文件檢查結果."""

    detected_language: str
    """偵測到的語言."""
    expected_standard_file: str
    """預期的規範檔名."""
    exists: bool
    """規範檔是否存在."""
    path: Optional[Path] = None
    """檔案路徑."""
    standard_files_available: list[str] = field(default_factory=list)
    """可用的規範檔清單."""
    missing_standards: list[str] = field(default_factory=list)
    """缺失的規範檔清單."""


def detect_project_language(project_root: Path) -> ProjectLanguageInfo:
    """偵測專案語言.

    掃描專案根目錄特徵檔案：
    - pubspec.yaml → Flutter/Dart
    - go.mod → Go
    - package.json → Node.js
    - pyproject.toml (非 .claude/ 下) → Python
    - 無匹配 → unknown

    Args:
        project_root: 專案根目錄。

    Returns:
        ProjectLanguageInfo: 語言偵測結果。
    """
    # 檢查 pubspec.yaml (Flutter/Dart)
    pubspec = project_root / "pubspec.yaml"
    if pubspec.exists():
        return ProjectLanguageInfo(
            language="flutter",
            identifier="pubspec.yaml",
            is_available=True,
        )

    # 檢查 go.mod (Go)
    go_mod = project_root / "go.mod"
    if go_mod.exists():
        return ProjectLanguageInfo(
            language="go",
            identifier="go.mod",
            is_available=True,
        )

    # 檢查 package.json (Node.js)
    package_json = project_root / "package.json"
    if package_json.exists():
        return ProjectLanguageInfo(
            language="nodejs",
            identifier="package.json",
            is_available=True,
        )

    # 檢查 pyproject.toml (Python，但非 .claude/ 下的)
    pyproject = project_root / "pyproject.toml"
    if pyproject.exists():
        return ProjectLanguageInfo(
            language="python",
            identifier="pyproject.toml",
            is_available=True,
        )

    # 無匹配
    return ProjectLanguageInfo(
        language="unknown",
        identifier="N/A",
        is_available=False,
    )


def parse_hook_classification(config_path: Path) -> HookClassificationInfo:
    """解析 Hook 語言分類配置檔.

    使用結構化 YAML 解析，確保準確的配置識別。

    Args:
        config_path: hook-language-classification.yaml 的路徑。

    Returns:
        HookClassificationInfo: Hook 分類結果。
    """
    flutter_hooks = []
    project_specific_hooks = []

    if not config_path.exists():
        return HookClassificationInfo(
            flutter_hooks=[],
            project_specific_hooks=[],
            is_available=False,
        )

    # 使用結構化 YAML 解析
    data, errors = _parse_yaml_safely(config_path)

    if errors or data is None:
        # YAML 解析失敗，回到文字模式（向後相容）
        try:
            text = config_path.read_text(encoding="utf-8")
            in_hooks_section = False

            for line in text.splitlines():
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                if stripped == "hooks:":
                    in_hooks_section = True
                    continue
                if in_hooks_section and ":" in stripped:
                    parts = stripped.split(":", 1)
                    if len(parts) == 2:
                        hook_name = parts[0].strip()
                        hook_type = parts[1].strip()
                        if hook_type == "flutter":
                            flutter_hooks.append(hook_name)
                        elif hook_type == "project-specific":
                            project_specific_hooks.append(hook_name)

            return HookClassificationInfo(
                flutter_hooks=sorted(flutter_hooks),
                project_specific_hooks=sorted(project_specific_hooks),
                is_available=True,
            )
        except (OSError, UnicodeDecodeError):
            return HookClassificationInfo(
                flutter_hooks=[],
                project_specific_hooks=[],
                is_available=False,
            )

    # 結構化解析成功
    if isinstance(data, dict) and "hooks" in data:
        hooks_dict = data.get("hooks", {})
        if isinstance(hooks_dict, dict):
            for hook_name, hook_type in hooks_dict.items():
                if hook_type == "flutter":
                    flutter_hooks.append(hook_name)
                elif hook_type == "project-specific":
                    project_specific_hooks.append(hook_name)

    return HookClassificationInfo(
        flutter_hooks=sorted(flutter_hooks),
        project_specific_hooks=sorted(project_specific_hooks),
        is_available=True,
    )


def check_claude_md(project_root: Path) -> FrameworkFileInfo:
    """檢查 CLAUDE.md 是否存在.

    Args:
        project_root: 專案根目錄。

    Returns:
        FrameworkFileInfo: CLAUDE.md 的檢查結果。
    """
    claude_md = project_root / "CLAUDE.md"
    return FrameworkFileInfo(
        name="CLAUDE.md",
        exists=claude_md.exists(),
        path=claude_md if claude_md.exists() else None,
    )


def check_language_template(
    project_root: Path, language: str
) -> FrameworkFileInfo:
    """檢查語言特定模板是否存在.

    Args:
        project_root: 專案根目錄。
        language: 專案語言 ('flutter', 'go', 'nodejs', 'python', 'unknown')。

    Returns:
        FrameworkFileInfo: 模板檔的檢查結果。
    """
    # 目前只有 Flutter 模板
    if language == "flutter":
        template_file = project_root / ".claude" / "project-templates" / "FLUTTER.md"
        return FrameworkFileInfo(
            name="FLUTTER.md",
            exists=template_file.exists(),
            path=template_file if template_file.exists() else None,
        )

    # 其他語言暫無模板
    return FrameworkFileInfo(
        name=f"{language.upper()}.md",
        exists=False,
        path=None,
    )


def check_settings_local_json(project_root: Path) -> FrameworkFileInfo:
    """檢查 settings.local.json 是否存在.

    Args:
        project_root: 專案根目錄。

    Returns:
        FrameworkFileInfo: settings.local.json 的檢查結果。
    """
    settings_file = project_root / ".claude" / "settings.local.json"
    return FrameworkFileInfo(
        name="settings.local.json",
        exists=settings_file.exists(),
        path=settings_file if settings_file.exists() else None,
    )


def check_docs_structure(project_root: Path) -> DocsStructureInfo:
    """檢查 docs/ 目錄結構是否完整.

    檢查以下項目：
    - docs/ 目錄存在
    - docs/work-logs/ 子目錄存在
    - docs/todolist.yaml 檔案存在

    Args:
        project_root: 專案根目錄。

    Returns:
        DocsStructureInfo: docs 結構檢查結果。
    """
    docs_dir = project_root / "docs"
    work_logs_dir = docs_dir / "work-logs"
    todolist_file = docs_dir / "todolist.yaml"

    docs_exists = docs_dir.exists() and docs_dir.is_dir()
    work_logs_exists = work_logs_dir.exists() and work_logs_dir.is_dir()
    todolist_exists = todolist_file.exists() and todolist_file.is_file()

    all_complete = docs_exists and work_logs_exists and todolist_exists

    return DocsStructureInfo(
        exists=docs_exists,
        has_work_logs=work_logs_exists,
        has_todolist=todolist_exists,
        all_complete=all_complete,
    )


def _check_file_read_permission(file_path: Path) -> bool:
    """檢查檔案讀取權限."""
    try:
        file_path.read_bytes()
        return True
    except (OSError, PermissionError):
        return False


def _check_file_write_permission(file_path: Path) -> bool:
    """檢查檔案寫入權限."""
    try:
        with file_path.open('a'):
            pass
        return True
    except (OSError, PermissionError):
        return False


def _check_file_permissions(file_path: Path) -> PermissionInfo:
    """檢查檔案的讀/寫/執行權限.

    Args:
        file_path: 檔案路徑。

    Returns:
        PermissionInfo: 權限資訊。
    """
    if not file_path.exists():
        return PermissionInfo(
            can_read=False,
            can_write=False,
            can_execute=False,
            error_message="檔案不存在"
        )

    try:
        can_read = _check_file_read_permission(file_path)
        can_write = _check_file_write_permission(file_path)

        # 檢查執行權限
        file_mode = file_path.stat().st_mode
        can_execute = bool(file_mode & stat.S_IXUSR)

        return PermissionInfo(
            can_read=can_read,
            can_write=can_write,
            can_execute=can_execute
        )
    except Exception as e:
        return PermissionInfo(
            can_read=False,
            can_write=False,
            can_execute=False,
            error_message=str(e)
        )


def _parse_yaml_safely(file_path: Path) -> tuple[dict | list | None, list[str]]:
    """安全地解析 YAML 檔案.

    Args:
        file_path: YAML 檔案路徑。

    Returns:
        tuple: (解析結果, 錯誤清單)。
    """
    errors = []
    try:
        if not file_path.exists():
            errors.append("檔案不存在")
            return None, errors

        content = file_path.read_text(encoding="utf-8")
        try:
            data = yaml.safe_load(content)
            return data, errors
        except yaml.YAMLError as e:
            errors.append(f"YAML 格式錯誤: {str(e)[:100]}")
            return None, errors
    except (OSError, UnicodeDecodeError) as e:
        errors.append(f"檔案讀取失敗: {str(e)[:100]}")
        return None, errors


def _has_gitignore_rule(content: str, pattern: str) -> bool:
    """檢查 .gitignore 是否包含精確的前綴匹配規則.

    使用精確前綴匹配（不進行模糊匹配），以提高精確度。
    支援規則變體：coverage/, coverage, .claude/hook-logs/ 等。

    Args:
        content: .gitignore 檔案內容。
        pattern: 要檢查的規則模式（如 'coverage' 或 '.claude/hook-logs'）。

    Returns:
        bool: 規則是否存在。
    """
    # 標準化 pattern（移除末尾斜線和 /*)
    pattern_normalized = pattern.rstrip("/*").rstrip("/")

    for line in content.splitlines():
        # 移除空白和註解
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        # 標準化 line（移除末尾斜線和 /*)
        line_normalized = line.rstrip("/*").rstrip("/")

        # 精確比對
        if line_normalized == pattern_normalized:
            return True

    return False


def _create_missing_gitignore_result(exists: bool = False) -> GitignoreCheckInfo:
    """建立 .gitignore 缺失或無法讀取的結果.

    Args:
        exists: .gitignore 檔案是否存在（用於編碼錯誤情況）。

    Returns:
        GitignoreCheckInfo: 缺失項目的檢查結果。
    """
    return GitignoreCheckInfo(
        exists=exists,
        has_coverage_rules=False,
        has_hook_logs_rule=False,
        has_worktrees_rule=False,
        has_tool_results_rule=False,
        has_handoff_rule=False,
        all_required_complete=False,
        missing_rules=[
            "coverage/",
            "htmlcov/",
            ".claude/hook-logs/",
            ".claude/worktrees/",
            ".claude/tool-results/",
            ".claude/handoff/",
        ],
    )


def check_gitignore_completeness(project_root: Path) -> GitignoreCheckInfo:
    """檢查 .gitignore 是否包含所有必須的框架排除規則.

    驗證 .gitignore 包含所有 GITIGNORE_REQUIRED_RULES 中的規則。
    使用模糊匹配支援規則變體（如 /coverage/, coverage, coverage/* 等）。

    Args:
        project_root: 專案根目錄。

    Returns:
        GitignoreCheckInfo: .gitignore 檢查結果。
    """
    gitignore_path = project_root / ".gitignore"

    if not gitignore_path.exists():
        return _create_missing_gitignore_result(exists=False)

    try:
        content = gitignore_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return _create_missing_gitignore_result(exists=True)

    # 檢查每個必須規則
    has_coverage = _has_gitignore_rule(content, "coverage") or _has_gitignore_rule(content, "htmlcov")
    has_hook_logs = _has_gitignore_rule(content, ".claude/hook-logs")
    has_worktrees = _has_gitignore_rule(content, ".claude/worktrees")
    has_tool_results = _has_gitignore_rule(content, ".claude/tool-results")
    has_handoff = _has_gitignore_rule(content, ".claude/handoff")

    # 彙整缺失的規則
    missing = []
    if not has_coverage:
        missing.extend(["coverage/", "htmlcov/"])
    if not has_hook_logs:
        missing.append(".claude/hook-logs/")
    if not has_worktrees:
        missing.append(".claude/worktrees/")
    if not has_tool_results:
        missing.append(".claude/tool-results/")
    if not has_handoff:
        missing.append(".claude/handoff/")

    return GitignoreCheckInfo(
        exists=True,
        has_coverage_rules=has_coverage,
        has_hook_logs_rule=has_hook_logs,
        has_worktrees_rule=has_worktrees,
        has_tool_results_rule=has_tool_results,
        has_handoff_rule=has_handoff,
        all_required_complete=len(missing) == 0,
        missing_rules=missing,
    )


def check_claude_directory_structure(project_root: Path) -> ClaudeDirectoryCheckInfo:
    """檢查 .claude/ 核心目錄結構是否完整.

    驗證以下必須目錄存在：
    - rules/（規則和流程）
    - hooks/（Hook 系統）
    - skills/（Skill 工具）
    - methodologies/（方法論）
    - references/（參考檔案）
    - agents/（代理人定義）
    - config/（設定檔案）

    Args:
        project_root: 專案根目錄。

    Returns:
        ClaudeDirectoryCheckInfo: .claude 目錄結構檢查結果。
    """
    claude_dir = project_root / ".claude"

    if not claude_dir.exists() or not claude_dir.is_dir():
        return ClaudeDirectoryCheckInfo(
            exists=False,
            has_rules=False,
            has_hooks=False,
            has_skills=False,
            has_methodologies=False,
            has_references=False,
            has_agents=False,
            has_config=False,
            all_required_complete=False,
            missing_directories=[
                "rules/",
                "hooks/",
                "skills/",
                "methodologies/",
                "references/",
                "agents/",
                "config/",
            ],
            directory_count=0,
        )

    dir_status = {}
    missing = []
    count = 0

    for dir_name, display_name in REQUIRED_DIRECTORIES:
        dir_path = claude_dir / dir_name
        exists = dir_path.exists() and dir_path.is_dir()
        dir_status[dir_name] = exists
        count += 1
        if not exists:
            missing.append(display_name)

    return ClaudeDirectoryCheckInfo(
        exists=True,
        has_rules=dir_status.get("rules", False),
        has_hooks=dir_status.get("hooks", False),
        has_skills=dir_status.get("skills", False),
        has_methodologies=dir_status.get("methodologies", False),
        has_references=dir_status.get("references", False),
        has_agents=dir_status.get("agents", False),
        has_config=dir_status.get("config", False),
        all_required_complete=len(missing) == 0,
        missing_directories=missing,
        directory_count=count,
    )


def check_hook_configurations(project_root: Path) -> HookConfigurationCheckInfo:
    """檢查 Hook 配置檔完整性.

    驗證 .claude/config/ 下存在所有必須設定檔：
    - hook-language-classification.yaml
    - hook-exclude-list.json
    - settings.json

    同時驗證 YAML 和 JSON 格式的有效性，並記錄詳細的權限資訊。

    Args:
        project_root: 專案根目錄。

    Returns:
        HookConfigurationCheckInfo: Hook 配置檔檢查結果。
    """
    config_dir = project_root / ".claude" / "config"

    if not config_dir.exists() or not config_dir.is_dir():
        return HookConfigurationCheckInfo(
            config_dir_exists=False,
            has_language_classification_yaml=False,
            has_exclude_list_json=False,
            has_settings_json=False,
            all_required_complete=False,
            missing_files=[
                "hook-language-classification.yaml",
                "hook-exclude-list.json",
                "settings.json",
            ],
        )

    # 檢查檔案存在
    yaml_file = config_dir / HOOK_CONFIG_YAML
    json_exclude = config_dir / HOOK_CONFIG_EXCLUDE_JSON
    json_settings = config_dir / HOOK_CONFIG_SETTINGS_JSON

    has_yaml = yaml_file.exists()
    has_exclude = json_exclude.exists()
    has_settings = json_settings.exists()

    missing_files = []
    if not has_yaml:
        missing_files.append(HOOK_CONFIG_YAML)
    if not has_exclude:
        missing_files.append(HOOK_CONFIG_EXCLUDE_JSON)
    if not has_settings:
        missing_files.append(HOOK_CONFIG_SETTINGS_JSON)

    # 驗證格式和權限
    format_errors = []
    yaml_valid = True
    json_valid = True
    yaml_perm_info = PermissionInfo(False, False, False, "檔案不存在")
    json_perm_info = PermissionInfo(False, False, False, "檔案不存在")

    if has_yaml:
        yaml_perm_info = _check_file_permissions(yaml_file)
        # 嘗試結構化 YAML 驗證
        yaml_data, yaml_errors = _parse_yaml_safely(yaml_file)
        if yaml_errors:
            yaml_valid = False
            format_errors.extend([f"hook-language-classification.yaml: {err}" for err in yaml_errors])

    if has_exclude or has_settings:
        json_perm_info = _check_file_permissions(json_exclude if has_exclude else json_settings)

    if has_exclude:
        try:
            json.loads(json_exclude.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
            json_valid = False
            format_errors.append(f"hook-exclude-list.json: {str(e)[:50]}")

    if has_settings:
        try:
            json.loads(json_settings.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
            json_valid = False
            format_errors.append(f"settings.json: {str(e)[:50]}")

    all_complete = len(missing_files) == 0 and yaml_valid and json_valid

    return HookConfigurationCheckInfo(
        config_dir_exists=True,
        has_language_classification_yaml=has_yaml,
        has_exclude_list_json=has_exclude,
        has_settings_json=has_settings,
        all_required_complete=all_complete,
        missing_files=missing_files,
        yaml_format_valid=yaml_valid,
        json_format_valid=json_valid,
        format_errors=format_errors,
        yaml_permission_info=yaml_perm_info,
        json_permission_info=json_perm_info,
    )


def check_claude_config_directory(project_root: Path) -> ClaudeConfigCheckInfo:
    """檢查 .claude/config 目錄的存在和狀態.

    驗證目錄的存在性、讀取權限和檔案數量。

    Args:
        project_root: 專案根目錄。

    Returns:
        ClaudeConfigCheckInfo: 目錄檢查結果。
    """
    config_dir = project_root / ".claude" / "config"

    exists = config_dir.exists()
    is_dir = exists and config_dir.is_dir()

    file_count = 0
    total_size = 0
    has_permissions = True

    if is_dir:
        try:
            # 計算目錄中的檔案數和總大小
            for item in config_dir.iterdir():
                if item.is_file():
                    file_count += 1
                    try:
                        total_size += item.stat().st_size
                    except OSError:
                        pass
        except (OSError, PermissionError):
            has_permissions = False

    return ClaudeConfigCheckInfo(
        exists=exists,
        is_directory=is_dir,
        config_file_count=file_count,
        total_size_bytes=total_size,
        has_read_permissions=has_permissions,
    )


def check_readme_md(project_root: Path) -> ReadmeCheckInfo:
    """檢查 README.md 是否存在.

    此檢查為 [SHOULD] 優先級（推薦但非必須）。

    Args:
        project_root: 專案根目錄。

    Returns:
        ReadmeCheckInfo: README.md 檢查結果。
    """
    readme_path = project_root / "README.md"

    if not readme_path.exists():
        return ReadmeCheckInfo(
            exists=False,
            path=None,
            size_bytes=0,
            is_nonempty=False,
        )

    try:
        content = readme_path.read_text(encoding="utf-8")
        size = readme_path.stat().st_size
        is_nonempty = len(content.strip()) > 0
    except (OSError, UnicodeDecodeError):
        return ReadmeCheckInfo(
            exists=True,
            path=readme_path,
            size_bytes=0,
            is_nonempty=False,
        )

    return ReadmeCheckInfo(
        exists=True,
        path=readme_path,
        size_bytes=size,
        is_nonempty=is_nonempty,
    )


def check_language_standards(
    project_root: Path, detected_language: str
) -> LanguageStandardCheckInfo:
    """檢查語言特定的開發規範文件.

    根據偵測到的語言，驗證對應規範檔是否存在。
    此檢查為 [SHOULD] 優先級（推薦但非必須）。

    Args:
        project_root: 專案根目錄。
        detected_language: 偵測到的語言。

    Returns:
        LanguageStandardCheckInfo: 規範檔檢查結果。
    """
    templates_dir = project_root / ".claude" / "project-templates"

    # 語言與規範檔的對應關係
    language_mapping = {
        "flutter": "FLUTTER.md",
        "go": "GO.md",
        "nodejs": "NODEJS.md",
        "python": "PYTHON.md",
    }

    expected_file = language_mapping.get(detected_language, f"{detected_language.upper()}.md")

    # 掃描可用的規範檔
    available = []
    if templates_dir.exists() and templates_dir.is_dir():
        try:
            for file in templates_dir.iterdir():
                if file.suffix == ".md" and file.is_file():
                    available.append(file.name)
        except OSError:
            pass

    # 檢查期望的規範檔
    expected_path = templates_dir / expected_file if templates_dir.exists() else None
    file_exists = expected_path and expected_path.exists()

    # 識別缺失的規範檔
    missing = []
    if detected_language != "unknown" and not file_exists:
        missing.append(expected_file)

    return LanguageStandardCheckInfo(
        detected_language=detected_language,
        expected_standard_file=expected_file,
        exists=file_exists,
        path=expected_path if file_exists else None,
        standard_files_available=sorted(available),
        missing_standards=missing,
    )
