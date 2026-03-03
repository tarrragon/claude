"""Onboard 檢查模組 — 偵測專案語言、檢查框架檔案和 Hook 分類.

此模組提供一組 onboard 相關的偵測函式，用於引導新專案使用框架。
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


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

    簡單文字解析 YAML 檔案（無外部依賴）。

    Args:
        config_path: hook-language-classification.yaml 的路徑。

    Returns:
        HookClassificationInfo: Hook 分類結果。
    """
    flutter_hooks = []
    project_specific_hooks = []

    try:
        if not config_path.exists():
            return HookClassificationInfo(
                flutter_hooks=[],
                project_specific_hooks=[],
                is_available=False,
            )

        text = config_path.read_text(encoding="utf-8")
        in_hooks_section = False

        for line in text.splitlines():
            stripped = line.strip()

            # 跳過空行和註解
            if not stripped or stripped.startswith("#"):
                continue

            # 進入 hooks 段落
            if stripped == "hooks:":
                in_hooks_section = True
                continue

            # 解析 hooks 段落中的 key: value 行
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
        # OSError: 檔案讀取失敗（權限、磁碟等）
        # UnicodeDecodeError: 編碼錯誤
        return HookClassificationInfo(
            flutter_hooks=[],
            project_specific_hooks=[],
            is_available=False,
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
