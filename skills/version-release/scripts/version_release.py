#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml"]
# ///

"""
Version Release Tool - 完整版本發布流程自動化工具

功能:
- 版本啟動：建立新版本的 todolist 條目、worklog 結構、bump 版本檔案
- Pre-flight 檢查：驗證 worklog、技術債務、版本同步
- 文件更新：CHANGELOG、todolist、package.json/manifest.json 驗證
- Git 操作：合併、Tag、推送、分支清理
- 預覽模式：--dry-run 查看完整操作流程

使用方式:
  uv run version_release.py start --version X.Y.Z [--from X.Y.Z] [--description "..."] [--dry-run]
  uv run version_release.py release [--version X.Y.Z] [--dry-run]
  uv run version_release.py check [--version X.Y.Z]
  uv run version_release.py update-docs [--version X.Y.Z] [--dry-run]
"""

import os
import sys
import re
import json
import subprocess
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Tuple, Dict
import yaml


# ============================================================================
# 版本同步檢查（Chrome Extension 雙版本來源）
# ============================================================================

# 配置檔路徑
VERSION_RELEASE_CONFIG_FILE = ".version-release.yaml"

# 雙版本來源（Chrome Extension）
PACKAGE_VERSION_SOURCE = "package.json"
PACKAGE_VERSION_KEY = "version"
MANIFEST_VERSION_SOURCE = "manifest.json"
MANIFEST_VERSION_KEY = "version"

# 同步策略類型
SYNC_POLICY_REQUIRED = "required"
SYNC_POLICY_OPTIONAL = "optional"
SYNC_POLICY_IMPLICIT = "implicit"

# 衝突嚴重程度
SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"
SEVERITY_INFO = "info"
SEVERITY_SUCCESS = "success"

# 預設配置
DEFAULT_VERSION_RELEASE_CONFIG = {
    "versions": {
        "package": {
            "source": PACKAGE_VERSION_SOURCE,
            "key": PACKAGE_VERSION_KEY,
            "semantic_version": True,
            "description": "專案主版本（用於 Ticket、Wave、發布計劃）"
        },
        "manifest": {
            "source": MANIFEST_VERSION_SOURCE,
            "key": MANIFEST_VERSION_KEY,
            "semantic_version": True,
            "independent": False,
            "description": "Chrome Extension 發布版本（用於 Chrome Web Store）",
            "sync_policy": SYNC_POLICY_REQUIRED,
            "sync_recommendation": "必須與 package.json 版本一致"
        }
    },
    "sync_rules": {
        "on_release": {
            "package": {"required": True},
            "manifest": {"required": True}
        },
        "on_development": {
            "allow_version_mismatch": False
        },
        "conflict_detection": {
            "manifest_ahead_of_package": {
                "severity": SEVERITY_ERROR,
                "message": "manifest.json 版本大於 package.json，必須修正"
            },
            "manifest_behind_package": {
                "severity": SEVERITY_ERROR,
                "message": "manifest.json 版本低於 package.json，必須修正"
            }
        }
    },
    "detection": {
        "version_files": [
            {"path": PACKAGE_VERSION_SOURCE, "type": "json", "key": PACKAGE_VERSION_KEY, "context": "NPM 專案版本"},
            {"path": MANIFEST_VERSION_SOURCE, "type": "json", "key": MANIFEST_VERSION_KEY, "context": "Chrome Extension 版本"}
        ]
    },
    "preflight_checks": {
        "version_sync": {
            "enabled": True,
            "fail_on_error": True,
            "warn_on_mismatch": True
        }
    },
    # release_workflow：發布工作流模式
    #   "trunk"          — all-on-main，跳過 feature-branch merge 與分支清理（預設）
    #   "feature-branch" — 維持原行為，merge feature/v{major_minor} 並刪除分支
    "release_workflow": "trunk",
    # tag_format：tag 命名範本，{version} 會被實際版本替換
    #   預設 plain "v{version}"（與本專案既有 v0.18.0/v0.17.4 慣例一致）
    #   保留 "-final" 後綴需顯式設定 "v{version}-final"
    "tag_format": "v{version}",
    # worklog_path_pattern：worklog 目錄相對 repo root 的路徑範本
    #   支援 {version}（完整版本）、{major_minor}（X.Y）、{major}（X）佔位符
    #   巢狀範例："docs/work-logs/v{major}/v{major_minor}/v{version}"
    #   扁平範例（舊結構）："docs/work-logs/v{version}"
    "worklog_path_pattern": "docs/work-logs/v{major}/v{major_minor}/v{version}",
    # project_type：專案類型（影響版本偵測與 bump 策略）
    #   可選值：chrome-ext | flutter | go | php | python | monorepo | npm | None
    #   None 表示未指定，由自動偵測判定
    "project_type": None,
    # version_source：版本源配置
    #   primary: 主版本源檔案路徑（None 時依 VERSION_FILE_CANDIDATES 自動偵測）
    #   parser:  版本源 parser 類型（json | yaml | toml | git-tag；None 時由副檔名推斷）
    #   key:     版本 key（json/yaml/toml 用，預設 "version"）
    #   sync_targets: 版本 bump 時一併更新的檔案清單
    "version_source": None,
    # subprojects：monorepo 子專案配置（僅 project_type: monorepo 時使用）
    #   每個子專案為 dict，含 path 和 version_source 子配置
    "subprojects": None,
}


# 版本檔配置：(相對路徑, 解析方式)
# 按優先順序排列，偵測專案語言
VERSION_FILE_CANDIDATES = [
    ("pubspec.yaml", "yaml"),           # Flutter
    ("package.json", "json"),           # NPM / Chrome Extension
    ("manifest.json", "json"),          # Chrome Extension
    ("composer.json", "json"),          # PHP
    ("pyproject.toml", "toml"),         # Python
]


class Colors:
    """ANSI 顏色代碼"""
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


def print_header(title: str):
    """打印標題"""
    width = 60
    print(f"\n{Colors.BOLD}{Colors.BLUE}╔{'═' * (width - 2)}╗{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}║ {title:<{width - 4}} ║{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}╚{'═' * (width - 2)}╝{Colors.RESET}\n")


def print_section(title: str):
    """打印章節標題"""
    width = 60
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'━' * width}{Colors.RESET}")
    print(f"{Colors.BOLD}{title}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'━' * width}{Colors.RESET}")


def print_success(message: str):
    """打印成功訊息"""
    print(f"{Colors.GREEN}[OK]{Colors.RESET} {message}")


def print_error(message: str):
    """打印錯誤訊息"""
    print(f"{Colors.RED}[FAIL]{Colors.RESET} {message}")


def print_warning(message: str):
    """打印警告訊息"""
    print(f"{Colors.YELLOW}[WARN]️{Colors.RESET} {message}")


def print_info(message: str, indent: int = 0):
    """打印資訊訊息"""
    prefix = "  " * indent
    print(f"{prefix}{message}")


def parse_ticket_frontmatter(content: str) -> Optional[str]:
    """
    從 Markdown 內容提取 YAML frontmatter。

    Args:
        content: 完整的 Markdown 檔案內容

    Returns:
        frontmatter 字串（去除 --- 邊界符），或 None 如果沒有找到
    """
    match = re.search(r"^---\n(.*?)\n---", content, re.DOTALL)
    return match.group(1) if match else None


def get_project_root() -> Path:
    """取得專案根目錄。

    優先順序：
    1. cwd 本身為 git repo root（含 .git 或 package.json）→ 用 cwd
    2. cwd parents 向上找到 .git → 用該 ancestor
    3. dev mode fallback：__file__ 上溯（假設 source 在 .claude/skills/version-release/scripts/）
    4. 最後 fallback：cwd（後續檔案存取會自然 fail 並回報明確錯誤）

    Why: 原版用 Path(__file__).parent x5，假設 source tree 結構；
    uv tool install 後 __file__ 位於 site-packages，parent x5 進入 ~/.local/share/ 上層
    導致 docs/todolist.yaml / package.json 等檔案存取失敗。
    """
    cwd = Path.cwd()
    if (cwd / ".git").exists() or (cwd / "package.json").exists():
        return cwd
    for parent in cwd.parents:
        if (parent / ".git").exists():
            return parent
    dev_fallback = Path(__file__).parent.parent.parent.parent.parent
    if (dev_fallback / ".git").exists() or (dev_fallback / "package.json").exists():
        return dev_fallback
    return cwd


def detect_version_files(root: Path) -> List[Tuple[Path, str]]:
    """
    偵測專案中存在的版本檔案

    Args:
        root: 專案根目錄

    Returns:
        [(absolute_path, parser_type), ...] 依優先順序排列
    """
    found = []
    for rel_path, parser_type in VERSION_FILE_CANDIDATES:
        full_path = root / rel_path
        if full_path.exists():
            found.append((full_path, parser_type))
    return found


# 專案類型常數
PROJECT_TYPE_FLUTTER = "flutter"
PROJECT_TYPE_GO = "go"
PROJECT_TYPE_CHROME_EXT = "chrome-ext"
PROJECT_TYPE_PHP = "php"
PROJECT_TYPE_NPM = "npm"
PROJECT_TYPE_PYTHON = "python"
PROJECT_TYPE_MONOREPO = "monorepo"
PROJECT_TYPE_UNKNOWN = "unknown"

# 根目錄檔案 → 專案類型的對應（順序即優先序）
_PROJECT_TYPE_MARKERS = [
    ("pubspec.yaml", PROJECT_TYPE_FLUTTER),
    ("go.mod", PROJECT_TYPE_GO),
    ("composer.json", PROJECT_TYPE_PHP),
    ("pyproject.toml", PROJECT_TYPE_PYTHON),
]

# monorepo 子目錄偵測用的版本檔名稱集合
_SUBPROJECT_VERSION_FILES = {"pubspec.yaml", "package.json", "go.mod", "composer.json", "pyproject.toml"}


def detect_project_type(root: Path) -> str:
    """
    依根目錄檔案自動判定專案類型。

    優先序：
    1. pubspec.yaml → flutter
    2. go.mod → go
    3. package.json + manifest.json → chrome-ext
    4. composer.json → php
    5. package.json（無 manifest.json）→ npm
    6. pyproject.toml → python
    7. 子目錄（depth=1）含版本檔 → monorepo
    8. 全無 → unknown

    Args:
        root: 專案根目錄

    Returns:
        專案類型字串（PROJECT_TYPE_* 常數之一）
    """
    for marker_file, project_type in _PROJECT_TYPE_MARKERS:
        if (root / marker_file).exists():
            print(f"[INFO] 自動偵測專案類型：{project_type}（根據 {marker_file}）", file=sys.stderr)
            return project_type

    has_package_json = (root / "package.json").exists()
    has_manifest_json = (root / "manifest.json").exists()

    if has_package_json and has_manifest_json:
        print("[INFO] 自動偵測專案類型：chrome-ext（根據 package.json + manifest.json）", file=sys.stderr)
        return PROJECT_TYPE_CHROME_EXT

    if has_package_json:
        print("[INFO] 自動偵測專案類型：npm（根據 package.json）", file=sys.stderr)
        return PROJECT_TYPE_NPM

    # monorepo：根目錄無版本檔但子目錄（depth=1）有
    try:
        for entry in sorted(root.iterdir()):
            if not entry.is_dir() or entry.name.startswith("."):
                continue
            for vf in _SUBPROJECT_VERSION_FILES:
                if (entry / vf).exists():
                    print(
                        f"[INFO] 自動偵測專案類型：monorepo（子目錄 {entry.name}/ 含 {vf}）",
                        file=sys.stderr,
                    )
                    return PROJECT_TYPE_MONOREPO
    except PermissionError:
        pass

    print("[INFO] 自動偵測專案類型：unknown（未找到已知版本檔）", file=sys.stderr)
    print("[INFO] 若偵測不正確，請建立 .version-release.yaml 指定 project_type", file=sys.stderr)
    return PROJECT_TYPE_UNKNOWN


def resolve_version_source(root: Path, config: Optional[dict] = None) -> Tuple[Optional[Path], str]:
    """
    依 config 或自動偵測選擇版本源。

    優先序：
    1. config 指定 version_source.primary → 使用指定檔案
    2. 無 config 或無 primary → 依 VERSION_FILE_CANDIDATES 順序掃描
    3. 所有候選檔案都不存在 → fallback 到 git-tag（回傳 (None, "git-tag")）

    Args:
        root: 專案根目錄
        config: .version-release.yaml 配置字典（None 時自動載入）

    Returns:
        (file_path, parser_type) — file_path 為 None 時表示 git-tag 策略
    """
    if config is None:
        config = load_version_release_config(root)

    version_source = config.get("version_source")
    if isinstance(version_source, dict):
        primary = version_source.get("primary")
        if primary:
            primary_path = root / primary
            if primary_path.exists():
                parser = version_source.get("parser")
                if not parser:
                    suffix = Path(primary).suffix.lstrip(".")
                    parser_map = {"json": "json", "yaml": "yaml", "yml": "yaml", "toml": "toml"}
                    parser = parser_map.get(suffix, "json")
                return (primary_path, parser)
            print(f"[WARNING] config 指定版本源 {primary} 不存在，fallback 到自動偵測", file=sys.stderr)
        if version_source.get("parser") == "git-tag":
            return (None, "git-tag")

    found = detect_version_files(root)
    if found:
        return found[0]

    go_mod = root / "go.mod"
    if go_mod.exists():
        return (None, "git-tag")

    return (None, "git-tag")


def extract_version_from_file(file_path: Path, parser_type: str) -> Optional[str]:
    """
    從版本檔提取版本號

    Args:
        file_path: 版本檔路徑
        parser_type: 解析方式 ("yaml", "json", "toml")

    Returns:
        版本號字串或 None
    """
    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()

        if parser_type == "yaml":
            # YAML 格式：version: X.Y.Z
            match = re.search(r"^version:\s+(.+)$", content, re.MULTILINE)
            if match:
                return match.group(1).strip()

        elif parser_type == "json":
            # JSON 格式：{ "version": "X.Y.Z" }
            data = json.loads(content)
            if "version" in data:
                return str(data["version"]).strip()

        elif parser_type == "toml":
            # TOML 格式：version = "X.Y.Z"
            # 使用正則表達式因為 requires-python >= 3.10 沒有 tomllib
            match = re.search(r'^version\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
            if match:
                return match.group(1).strip()

    except Exception:
        pass

    return None


def strip_build_metadata(version: Optional[str]) -> Optional[str]:
    """
    剝離語義版本號的 build metadata 後綴。

    Flutter pubspec.yaml 慣用 `X.Y.Z+build`（如 `1.1.0+2`，+2 為 build number），
    SemVer 亦允許 `X.Y.Z-pre+meta`。版本比較與 int 解析只需 `X.Y.Z` 核心，
    後綴若混入會在 `int("0+2")` 等拆分解析點崩潰。

    Args:
        version: 原始版本字串（可能含 `+build` / `-pre` 後綴），或 None

    Returns:
        剝除 `+...` 與 `-...` 後綴的核心版本字串；None 原樣回傳

    Examples:
        >>> strip_build_metadata("1.1.0+2")
        '1.1.0'
        >>> strip_build_metadata("1.2.0")
        '1.2.0'
        >>> strip_build_metadata("1.0.0-rc1+5")
        '1.0.0'
        >>> strip_build_metadata(None) is None
        True
    """
    if not version:
        return version
    # 先切 build metadata（+），再切 pre-release（-）
    core = version.split("+", 1)[0]
    core = core.split("-", 1)[0]
    return core.strip()


def detect_indev_worklog_version(root: Path, pattern: str) -> Optional[str]:
    """
    從 worklog 目錄偵測開發中（in-dev）的最高版本。

    monorepo 場景下版本源檔（如 pubspec.yaml 的 build-number 版）可能落後實際
    開發中的版本——worklog 目錄已建立 v{version} 子目錄但版本檔尚未 bump。
    此時應以 worklog 偵測到的最高版本為目標，而非誤採落後的版本檔。

    掃描策略：依 worklog_path_pattern 推導 work-logs 根，遞迴尋找符合
    `vX.Y.Z` 命名的最深層版本目錄，取語義排序最高者。

    Args:
        root: 專案根目錄
        pattern: worklog_path_pattern（決定 work-logs 根位置）

    Returns:
        最高 in-dev 版本字串（`X.Y.Z`），無則 None
    """
    # pattern 形如 "docs/work-logs/v{major}/v{major_minor}/v{version}"
    # 取第一個含佔位符之前的固定前綴作為 work-logs 根
    base_parts: List[str] = []
    for seg in pattern.split("/"):
        if "{" in seg:
            break
        base_parts.append(seg)
    worklog_root = root.joinpath(*base_parts) if base_parts else root / "docs" / "work-logs"
    if not worklog_root.exists():
        return None

    version_dir_pattern = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")
    best: Optional[Tuple[int, int, int]] = None
    # 遞迴掃描（巢狀或扁平結構皆涵蓋）
    for path in worklog_root.rglob("v*"):
        if not path.is_dir():
            continue
        match = version_dir_pattern.match(path.name)
        if not match:
            continue
        parts = (int(match.group(1)), int(match.group(2)), int(match.group(3)))
        if best is None or parts > best:
            best = parts
    if best is None:
        return None
    return f"{best[0]}.{best[1]}.{best[2]}"


def detect_version() -> Optional[str]:
    """自動偵測版本號"""
    root = get_project_root()

    # 1. 嘗試從 git 分支名稱偵測
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            branch = result.stdout.strip()
            match = re.search(r"feature/v([\d.]+)", branch)
            if match:
                return match.group(1)
    except Exception:
        pass

    # 2. 嘗試從版本檔案偵測（語言感知）
    # Gap 2：優先採 resolve_version_source（honor version_source.primary，含子目錄），
    #        fallback 至 root 掃描，使 monorepo 子目錄版本檔可被偵測
    config = load_version_release_config(root)
    version_files = resolve_sync_version_files(root, config)
    file_version: Optional[str] = None
    for file_path, parser_type in version_files:
        raw = extract_version_from_file(file_path, parser_type)
        if raw:
            # 剝離 Flutter pubspec 的 +build 後綴（如 1.1.0+2 → 1.1.0），
            # 避免後綴混入版本比較 / int 解析造成崩潰
            file_version = strip_build_metadata(raw)
            break

    # monorepo：版本源檔可能落後開發中版本（worklog 已建 v{version} 子目錄、
    # 版本檔尚未 bump）。若 worklog 偵測到更高的 in-dev 版本，優先採之。
    pattern = config.get(
        "worklog_path_pattern",
        DEFAULT_VERSION_RELEASE_CONFIG["worklog_path_pattern"],
    )
    indev_version = detect_indev_worklog_version(root, pattern)
    if indev_version and file_version:
        try:
            indev_parts = tuple(int(p) for p in indev_version.split("."))
            file_parts = tuple(int(p) for p in file_version.split("."))
            if indev_parts > file_parts:
                print(
                    f"[INFO] 版本源 {file_version} 落後開發中 worklog 版本 "
                    f"{indev_version}，採用 worklog 版本",
                    file=sys.stderr,
                )
                return indev_version
        except (ValueError, TypeError):
            pass
    if file_version:
        return file_version
    if indev_version:
        return indev_version

    # 3. 嘗試從 git tag 偵測
    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            tag = result.stdout.strip()
            match = re.search(r"v([\d.]+)", tag)
            if match:
                return match.group(1)
    except Exception:
        pass

    return None


def normalize_version(version: Optional[str]) -> str:
    """規範化版本號"""
    if not version:
        detected = detect_version()
        if not detected:
            raise ValueError("無法自動偵測版本號，請使用 --version 指定")
        version = detected

    # 剝離 build metadata 後綴（如 --version 1.1.0+2），確保下游拆分解析不崩潰
    version = strip_build_metadata(version)

    # 確保版本格式正確
    parts = version.split(".")
    if len(parts) == 2:
        # X.Y → X.Y.0
        return f"{version}.0"
    elif len(parts) == 3:
        return version
    else:
        raise ValueError(f"版本格式不正確: {version} (應為 X.Y 或 X.Y.Z)")


def extract_major_minor(version: str) -> str:
    """
    從語義版本號提取主版本和次版本號。

    從 X.Y.Z 格式的版本號中提取 X.Y 部分，
    用於版本系列識別（如 v0.19、v0.20）。

    Args:
        version: 完整版本號字串（例如 "0.19.8"、"0.1"）

    Returns:
        主版本.次版本 格式的字串（例如 "0.19"、"0.1"）

    Examples:
        >>> extract_major_minor("0.19.8")
        "0.19"
        >>> extract_major_minor("0.1")
        "0.1"
        >>> extract_major_minor("1.2.3")
        "1.2"
    """
    return ".".join(version.split(".")[:2])


def resolve_worklog_dir(root: Path, version: str, pattern: str) -> Path:
    """
    依 worklog_path_pattern 範本解析 worklog 版本子目錄。

    支援佔位符：
    - {version}      完整版本（X.Y.Z）
    - {major_minor}  主次版本（X.Y）
    - {major}        主版本（X）

    Args:
        root: 專案根目錄
        version: 完整版本號（例如 "0.19.0"）
        pattern: 路徑範本（相對 root，例如 "docs/work-logs/v{major}/v{major_minor}/v{version}"）

    Returns:
        解析後的版本子目錄絕對路徑

    Examples:
        巢狀：docs/work-logs/v{major}/v{major_minor}/v{version}
          -> <root>/docs/work-logs/v0/v0.19/v0.19.0
        扁平：docs/work-logs/v{version}
          -> <root>/docs/work-logs/v0.19.0
    """
    major_minor = extract_major_minor(version)
    major = version.split(".")[0]
    relative = pattern.format(
        version=version,
        major_minor=major_minor,
        major=major,
    )
    return root / relative


def check_worklog_completed(version: str) -> Tuple[bool, List[str]]:
    """檢查工作日誌是否完成"""
    root = get_project_root()
    worklog_dir = root / "docs" / "work-logs"

    errors = []
    major_minor = extract_major_minor(version)

    # 依 config worklog_path_pattern 解析版本子目錄（支援巢狀路徑）
    config = load_version_release_config(root)
    pattern = config.get(
        "worklog_path_pattern",
        DEFAULT_VERSION_RELEASE_CONFIG["worklog_path_pattern"],
    )
    version_subdir = resolve_worklog_dir(root, version, pattern)

    # 查詢相關的工作日誌
    # 優先檢查版本子目錄（依 config 範本解析）
    worklog_files = []
    if version_subdir.exists():
        for f in version_subdir.glob(f"v{version}*.md"):
            worklog_files.append(f)

    # 如果版本子目錄中找不到，則檢查根目錄（向後相容舊結構）
    if not worklog_files and worklog_dir.exists():
        for f in worklog_dir.glob(f"v{major_minor}*.md"):
            worklog_files.append(f)

    if not worklog_files:
        errors.append(f"找不到版本 v{version} 的工作日誌檔案")
        return False, errors

    # 檢查主工作日誌
    # 優先檢查版本子目錄中的主工作日誌
    main_worklog = version_subdir / f"v{version}-main.md"
    if not main_worklog.exists():
        # Gap 5 fallback 1：版本子目錄內任一 v{version}*.md 視為主日誌
        #   （並非所有專案都用 -main.md 命名慣例；放寬避免誤 FAIL）
        if version_subdir.exists():
            candidates = sorted(version_subdir.glob(f"v{version}*.md"))
            if candidates:
                main_worklog = candidates[0]
    if not main_worklog.exists():
        # fallback 2：檢查根目錄（舊結構）
        main_worklog = worklog_dir / f"v{major_minor}.0-main.md"

    if main_worklog.exists():
        try:
            with open(main_worklog, encoding="utf-8") as f:
                content = f.read()

            # 檢查 Ticket 完成情況（透過掃描 tickets 目錄的 YAML frontmatter）
            tickets_dir = version_subdir / "tickets" if version_subdir.exists() else None
            if tickets_dir and tickets_dir.exists():
                total, pending = 0, 0
                for ticket_file in tickets_dir.glob("*.md"):
                    try:
                        with open(ticket_file, encoding="utf-8") as tf:
                            ticket_content = tf.read()
                        status_match = re.search(r"^status:\s*(\S+)", ticket_content, re.MULTILINE)
                        if status_match:
                            total += 1
                            if status_match.group(1) in ("pending", "in_progress"):
                                pending += 1
                    except Exception:
                        pass
                if pending > 0:
                    errors.append(f"版本 v{version} 有 {pending}/{total} 個未完成的 Ticket")
        except Exception as e:
            errors.append(f"讀取 {main_worklog} 失敗: {e}")
    else:
        errors.append(f"找不到主工作日誌: {main_worklog.name}")

    return len(errors) == 0, errors


def check_technical_debt_status(version: str) -> Dict:
    """
    檢查目標版本的技術債務處理狀態

    Args:
        version: 版本號 (例如 "0.20.5")

    Returns:
        {
            "passed": bool,
            "pending_count": int,
            "pending_tds": list[dict],  # 包含 ticket_id, target, status
            "message": str
        }
    """
    root = get_project_root()
    major_minor = extract_major_minor(version)
    version_series = f"v{major_minor}"  # v0.20

    # 掃描版本系列的票目錄
    # 修復 Bug 2b：使用完整版本號而非硬編碼 .0
    worklog_dir = root / "docs" / "work-logs"
    tickets_dir = worklog_dir / f"v{version}" / "tickets"

    result = {
        "passed": True,
        "pending_count": 0,
        "pending_tds": [],
        "message": "",
    }

    if not tickets_dir.exists():
        result["message"] = f"找不到票目錄: {tickets_dir}"
        return result

    # 掃描所有 TD 檔案
    td_files = list(tickets_dir.glob("*-TD-*.md"))

    if not td_files:
        result["message"] = f"找不到任何技術債務票 (v{major_minor}.x)"
        return result

    for td_file in sorted(td_files):
        try:
            with open(td_file, encoding="utf-8") as f:
                content = f.read()

            # 解析 frontmatter
            frontmatter = parse_ticket_frontmatter(content)
            if not frontmatter:
                continue

            # 提取關鍵欄位
            ticket_id_match = re.search(r"ticket_id:\s+(.+)", frontmatter)
            status_match = re.search(r"status:\s+(.+)", frontmatter)
            version_match = re.search(r"version:\s+(.+)", frontmatter)
            deferred_match = re.search(r"deferred_from:\s+(.+)", frontmatter)
            target_match = re.search(r"target:\s+(.+)", frontmatter)

            ticket_id = ticket_id_match.group(1).strip() if ticket_id_match else ""
            status = status_match.group(1).strip() if status_match else "unknown"
            target_version = (
                version_match.group(1).strip() if version_match else "unknown"
            )
            deferred_from = (
                deferred_match.group(1).strip() if deferred_match else None
            )
            target_desc = target_match.group(1).strip() if target_match else ""

            # 檢查是否為當前版本系列的待處理 TD
            is_current_version = (
                target_version == major_minor or target_version == f"0.{major_minor}"
            )
            is_pending = status == "pending"

            if is_current_version and is_pending:
                result["pending_count"] += 1
                result["pending_tds"].append(
                    {
                        "ticket_id": ticket_id,
                        "target": target_desc,
                        "status": status,
                        "file": td_file.name,
                    }
                )

        except Exception as e:
            # 忽略解析錯誤，繼續掃描
            pass

    # 設定檢查結果
    if result["pending_count"] > 0:
        result["passed"] = False
        result["message"] = (
            f"發現 {result['pending_count']} 個待處理技術債務（目標版本 v{major_minor}.x）"
        )
    else:
        result["passed"] = True
        result["message"] = f"技術債務已處理或延遲完畢"

    return result


def check_technical_debt(version: str) -> Tuple[bool, List[str]]:
    """檢查技術債務狀態"""
    root = get_project_root()
    todolist_path = root / "docs" / "todolist.yaml"
    errors = []

    if not todolist_path.exists():
        errors.append("找不到 docs/todolist.yaml")
        return False, errors

    try:
        import yaml
        with open(todolist_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        # 檢查 tickets 清單中的 pending 狀態 TD
        tickets = data.get('tickets', [])
        major_minor = extract_major_minor(version)

        pending_tds = []
        for ticket in tickets:
            if ticket.get('status') == 'pending' and '-TD-' in str(ticket.get('id', '')):
                target_version = ticket.get('target_version')
                if not target_version or target_version == major_minor:
                    pending_tds.append(ticket.get('id'))

        if pending_tds:
            # 有待處理的 TD
            return True, []  # 允許發布，由 check_technical_debt_status 處理

        return True, []

    except Exception as e:
        errors.append(f"讀取 todolist.yaml 失敗: {e}")
        return False, errors


def check_previous_versions_completed(version: str) -> Tuple[bool, List[str]]:
    """檢查前版本是否有未完成的 Ticket"""
    root = get_project_root()
    worklog_dir = root / "docs" / "work-logs"
    errors = []

    if not worklog_dir.exists():
        return True, []

    version_pattern = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")
    # 防禦性剝離 build metadata（如 1.1.0+2），避免 int("0+2") 崩潰
    current_parts = tuple(int(p) for p in strip_build_metadata(version).split("."))

    for version_dir in sorted(worklog_dir.iterdir()):
        if not version_dir.is_dir():
            continue
        match = version_pattern.match(version_dir.name)
        if not match:
            continue

        dir_parts = (int(match.group(1)), int(match.group(2)), int(match.group(3)))
        if dir_parts >= current_parts:
            continue

        # 掃描此版本的 tickets 目錄
        tickets_dir = version_dir / "tickets"
        if not tickets_dir.exists():
            continue

        pending_count = 0
        in_progress_count = 0

        # 排除 TDD Phase 附件檔案（非獨立 Ticket）
        tdd_suffixes = ("-phase1-design", "-phase2-test", "-phase3a-strategy",
                        "-phase3b-", "-phase4-", "-refactor", "-analysis",
                        "-feature-spec", "-feature-design", "-test-design",
                        "-test-case", "-execution-report", "-execution-log")
        for ticket_file in tickets_dir.glob("*.md"):
            if any(s in ticket_file.stem for s in tdd_suffixes):
                continue
            try:
                with open(ticket_file, encoding="utf-8") as f:
                    content = f.read()
                frontmatter = parse_ticket_frontmatter(content)
                if not frontmatter:
                    continue
                status_match = re.search(r"status:\s+(\S+)", frontmatter)
                if not status_match:
                    continue
                status = status_match.group(1).strip()
                # 已完成的 Ticket 跳過（status: completed 或有 completed_at 欄位）
                if status == "completed":
                    continue
                has_completed_at = re.search(r"completed_at:", frontmatter) is not None
                if has_completed_at:
                    continue
                if status == "pending":
                    pending_count += 1
                elif status == "in_progress":
                    in_progress_count += 1
            except Exception:
                continue

        total = pending_count + in_progress_count
        if total > 0:
            ver_str = version_dir.name[1:]  # 移除 v 前綴
            errors.append(
                f"v{ver_str} 有 {total} 個未完成 Ticket "
                f"({pending_count} pending, {in_progress_count} in_progress)"
            )

    if errors:
        errors.append("請先完成前版本任務，或使用 /ticket migrate 遷移到當前版本")

    return len(errors) == 0, errors


# ============================================================================
# 新增函式 1：load_version_release_config
# ============================================================================

def load_version_release_config(root: Path) -> dict:
    """
    讀取 .version-release.yaml 配置檔。

    需求：功能 1 配置檔讀取
    邊界條件：
    - 配置檔不存在 -> 回傳 DEFAULT_VERSION_RELEASE_CONFIG
    - 配置檔格式錯誤 -> 輸出 warning，回傳 DEFAULT_VERSION_RELEASE_CONFIG
    - 部分欄位缺漏 -> dict.get() 帶預設值

    Args:
        root: 專案根目錄（Path 物件）

    Returns:
        配置字典，結構與 .version-release.yaml 一致
        保證回傳值不為 None

    配置檔位置查找順序（root 優先，.claude/ 為 fallback）：
    - <root>/.version-release.yaml
    - <root>/.claude/.version-release.yaml（branch-verify 豁免路徑，
      使 all-on-main 工作流可直接 commit 到 main 而不被保護分支 hook 阻擋）
    """
    candidate_paths = [
        root / VERSION_RELEASE_CONFIG_FILE,
        root / ".claude" / VERSION_RELEASE_CONFIG_FILE,
    ]
    config_path = next((p for p in candidate_paths if p.exists()), None)

    if config_path is None:
        return DEFAULT_VERSION_RELEASE_CONFIG

    try:
        with open(config_path, encoding='utf-8') as f:
            config = yaml.safe_load(f)

        if config is None or not isinstance(config, dict):
            return DEFAULT_VERSION_RELEASE_CONFIG

        # 補充缺漏欄位（深層 merge）
        for key in [
            "versions",
            "sync_rules",
            "detection",
            "preflight_checks",
            "release_workflow",
            "tag_format",
            "worklog_path_pattern",
            "project_type",
            "version_source",
            "subprojects",
        ]:
            if key not in config:
                config[key] = DEFAULT_VERSION_RELEASE_CONFIG.get(key, {})

        return config

    except yaml.YAMLError as e:
        print(f"[WARNING] .version-release.yaml 格式錯誤，使用內建預設配置", file=sys.stderr)
        print(f"         錯誤：{e}", file=sys.stderr)
        logger = logging.getLogger(__name__)
        logger.warning(f"YAML 解析失敗: {e}", exc_info=True)
        return DEFAULT_VERSION_RELEASE_CONFIG

    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"讀取 {config_path} 失敗: {e}", exc_info=True)
        return DEFAULT_VERSION_RELEASE_CONFIG


# ============================================================================
# 新增函式 2：get_package_version
# ============================================================================

def get_package_version(root: Path) -> Optional[str]:
    """
    從 package.json 讀取專案主版本。

    需求：Chrome Extension 專案以 package.json 為權威版本來源
    邊界條件：
    - package.json 不存在 -> 回傳 None
    - version 欄位不存在 -> 回傳 None
    - 版本格式非 X.Y.Z -> 原樣回傳（不強制正規化）

    Args:
        root: 專案根目錄

    Returns:
        版本字串（例如 "0.16.2"）或 None
    """
    package_path = root / PACKAGE_VERSION_SOURCE

    if not package_path.exists():
        return None

    try:
        with open(package_path, encoding='utf-8') as f:
            data = json.loads(f.read())

        if not isinstance(data, dict):
            return None

        version = data.get(PACKAGE_VERSION_KEY)

        if version is None:
            return None

        if not isinstance(version, str):
            version = str(version)

        return version

    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.debug(f"讀取 package.json 版本失敗: {e}")
        return None


# ============================================================================
# Helper：compare_semantic_versions
# ============================================================================

def compare_semantic_versions(v1: str, v2: str) -> int:
    """
    語義版本比較（返回 -1/0/1）。

    Args:
        v1, v2: 版本字串（格式 "X.Y.Z"）

    Returns:
        -1 (v1<v2), 0 (v1=v2), 1 (v1>v2)
    """
    try:
        # 剝離 build metadata 後綴（如 1.1.0+2），確保 int 解析不崩潰
        parts1 = [int(x) for x in strip_build_metadata(v1).split(".")[:3]]
        parts2 = [int(x) for x in strip_build_metadata(v2).split(".")[:3]]

        # 補齊缺漏部分（如 "0.1" → [0, 1, 0]）
        while len(parts1) < 3:
            parts1.append(0)
        while len(parts2) < 3:
            parts2.append(0)

        # 逐位比較
        for i in range(3):
            if parts1[i] > parts2[i]:
                return 1
            if parts1[i] < parts2[i]:
                return -1

        return 0  # 相等

    except (ValueError, AttributeError):
        # 版本格式無效，使用字符串比較
        if v1 > v2:
            return 1
        elif v1 < v2:
            return -1
        else:
            return 0


# ============================================================================
# 新增函式 4：Helper — _read_manifest_version
# ============================================================================

def _read_manifest_version(root: Path, config: dict) -> Tuple[Optional[str], List[dict]]:
    """
    讀取 manifest.json 版本。

    Args:
        root: 專案根目錄
        config: 配置字典

    Returns:
        (manifest_version or None, messages list)
    """
    messages = []
    manifest_version = None
    manifest_config = config.get("versions", {}).get("manifest", {})
    manifest_source = manifest_config.get("source", MANIFEST_VERSION_SOURCE)
    manifest_path = root / manifest_source if manifest_source else None

    if not manifest_path or not manifest_path.exists():
        messages.append({
            "level": SEVERITY_INFO,
            "layer": "manifest",
            "text": f"{manifest_source} 不存在，跳過 manifest 檢查"
        })
        return manifest_version, messages

    try:
        with open(manifest_path, encoding='utf-8') as f:
            manifest_data = json.loads(f.read())

        if isinstance(manifest_data, dict):
            manifest_key = manifest_config.get("key", "version")
            manifest_version = manifest_data.get(manifest_key)

            if manifest_version and not isinstance(manifest_version, str):
                manifest_version = str(manifest_version)

    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.debug(f"讀取 {manifest_source} 失敗: {e}")
        messages.append({
            "level": SEVERITY_INFO,
            "layer": "manifest",
            "text": f"讀取 {manifest_source} 失敗，跳過 manifest 檢查"
        })

    return manifest_version, messages


# ============================================================================
# 新增函式 4.1：Helper — _compare_manifest_version
# ============================================================================

def _compare_manifest_version(package_version: str, manifest_version: str, config: dict) -> List[dict]:
    """
    比對 manifest.json 版本與 package.json 版本，生成訊息。

    Args:
        package_version: package.json 版本
        manifest_version: manifest.json 版本
        config: 配置字典

    Returns:
        訊息清單
    """
    messages = []

    cmp_result = compare_semantic_versions(manifest_version, package_version)

    conflict_cfg = config.get("sync_rules", {}).get("conflict_detection", {})

    if cmp_result > 0:  # manifest > package
        severity = conflict_cfg.get("manifest_ahead_of_package", {}).get("severity", SEVERITY_ERROR)
        messages.append({
            "level": severity,
            "layer": "manifest",
            "text": "manifest.json 版本大於 package.json，必須修正"
        })
    elif cmp_result < 0:  # manifest < package
        severity = conflict_cfg.get("manifest_behind_package", {}).get("severity", SEVERITY_ERROR)
        messages.append({
            "level": severity,
            "layer": "manifest",
            "text": "manifest.json 版本低於 package.json，必須修正"
        })
    else:  # manifest = package
        messages.append({
            "level": SEVERITY_SUCCESS,
            "layer": "manifest",
            "text": "manifest.json 版本與 package.json 版本一致"
        })

    return messages


# （已移除 _check_l3_status — Chrome Extension 無 L3 Server 層）


# ============================================================================
# 新增函式 4：check_version_sync_dual
# ============================================================================

def check_version_sync_dual(version: str, config: dict) -> dict:
    """
    執行雙版本來源同步檢查（package.json + manifest.json）。

    需求：Chrome Extension 雙版本對比
    邊界條件：
    - manifest.json 版本不存在 -> 跳過 manifest 檢查
    - manifest 版本與 package 版本不一致 -> 輸出 error

    Args:
        version: package.json 版本（例如 "0.16.2"）
        config: load_version_release_config() 回傳的配置字典

    Returns:
        {
            "passed": bool,
            "package_version": str,
            "manifest_version": Optional[str],
            "messages": List[dict],
            "summary": str
        }
    """
    messages = []

    # [檢查 package.json 版本]
    if not version:
        messages.append({
            "level": SEVERITY_ERROR,
            "layer": "package",
            "text": "package.json 版本為空"
        })
        return {
            "passed": False,
            "package_version": version,
            "manifest_version": None,
            "messages": messages,
            "summary": "失敗（package.json 版本為空）"
        }

    # [檢查 manifest.json 版本]
    root = get_project_root()
    manifest_version, manifest_messages = _read_manifest_version(root, config)
    messages.extend(manifest_messages)

    if manifest_version:
        cmp_messages = _compare_manifest_version(version, manifest_version, config)
        messages.extend(cmp_messages)

    # [最終判定]
    has_error = any(m["level"] == SEVERITY_ERROR for m in messages)
    passed = not has_error
    has_warning = any(m["level"] == SEVERITY_WARNING for m in messages)

    if passed and not has_warning:
        summary = "通過（package.json 與 manifest.json 版本一致）"
    elif passed and has_warning:
        summary = "通過（附警告）"
    else:
        summary = "失敗（版本同步檢查未通過）"

    return {
        "passed": passed,
        "package_version": version,
        "manifest_version": manifest_version,
        "messages": messages,
        "summary": summary
    }


# ============================================================================
# 新增函式 5：print_version_sync_report
# ============================================================================

def print_version_sync_report(sync_result: dict):
    """
    輸出雙版本對比報告。

    需求：Chrome Extension 雙版本同步檢查輸出格式
    邊界條件：
    - 無 manifest 版本 -> 顯示 "manifest.json: 未偵測到"

    Args:
        sync_result: check_version_sync_dual() 的回傳值

    Side effects:
        打印到 stdout
    """
    width = 60
    print(f"\n{Colors.BOLD}{'━' * width}{Colors.RESET}")
    print(f"{Colors.BOLD}版本同步檢查（Chrome Extension 雙版本來源）{Colors.RESET}")
    print(f"{Colors.BOLD}{'━' * width}{Colors.RESET}\n")

    # [打印 package.json 版本]
    pkg_ver = sync_result.get("package_version", "未知")
    print(f"package.json 版本: {pkg_ver}")
    print("|")

    # [打印 manifest.json 版本]
    manifest_ver = sync_result.get("manifest_version")
    if manifest_ver is None:
        print("+-- manifest.json: 未偵測到")
    else:
        print(f"+-- manifest.json: {manifest_ver}")
        # 輸出 manifest 相關的訊息（基於 layer 欄位）
        for msg in sync_result.get("messages", []):
            if msg.get("layer") == "manifest":
                level_marker = f"[{msg['level'].upper()}]" if msg['level'] != SEVERITY_SUCCESS else "[OK]"
                print(f"    +-- {level_marker} {msg['text']}")

    # [打印所有訊息]
    print()
    for msg in sync_result.get("messages", []):
        level = msg.get("level", SEVERITY_INFO)
        text = msg.get("text", "")

        if level == SEVERITY_ERROR:
            print_error(text)
        elif level == SEVERITY_WARNING:
            print_warning(text)
        elif level == SEVERITY_INFO:
            print_info(text)
        elif level == SEVERITY_SUCCESS:
            print_success(text)

    # [打印結論]
    print()
    summary = sync_result.get("summary", "未知")
    if "失敗" in summary:
        print_error(f"結論：{summary}")
    elif "警告" in summary:
        print_warning(f"結論：{summary}")
    else:
        print_success(f"結論：{summary}")
    print()


def resolve_sync_version_files(
    root: Path, config: dict
) -> List[Tuple[Path, str]]:
    """決定版本同步/驗證時要檢查的版本檔清單。

    優先採 resolve_version_source（honor config.version_source.primary，
    含 monorepo 子目錄版本檔如 app/pubspec.yaml），fallback 至
    detect_version_files（只掃 root）以維持向後相容。

    Gap 2（unified-monorepo enabler）：使 project_type:monorepo + 頂層
    version_source（無 subprojects）的子目錄版本檔能被偵測、報告、驗證。

    Args:
        root: 專案根目錄
        config: load_version_release_config() 回傳的配置字典

    Returns:
        [(absolute_path, parser_type), ...]；空 list 表示走 git-tag 或無版本檔
    """
    primary_path, parser_type = resolve_version_source(root, config)
    if primary_path is not None:
        return [(primary_path, parser_type)]
    # primary 為 None：git-tag 策略或無 version_source，fallback 至 root 掃描
    return detect_version_files(root)


def check_version_sync(version: str) -> Tuple[bool, List[str]]:
    """檢查版本號同步（依 project_type 報告對應版本源）"""
    root = get_project_root()
    errors = []

    print_info("  檢查版本同步...")
    config = load_version_release_config(root)
    project_type = config.get("project_type") or detect_project_type(root)

    # Gap 1：僅 chrome-ext 印雙版本來源 dual report，其餘印對應版本源摘要
    if project_type == PROJECT_TYPE_CHROME_EXT:
        sync_result = check_version_sync_dual(version, config)
        print_version_sync_report(sync_result)

    # Gap 2：優先採 resolve_version_source（honor version_source.primary，含子目錄）
    version_files = resolve_sync_version_files(root, config)

    if version_files:
        # 檢查所有偵測到的版本檔（僅警告，不阻塞）
        for file_path, parser_type in version_files:
            try:
                file_version = extract_version_from_file(file_path, parser_type)

                if file_version:
                    if file_version != version:
                        print_warning(
                            f"{file_path.name} 版本不匹配: {file_version} vs {version}"
                        )
                    else:
                        print_success(f"{file_path.name} 版本一致: {version}")
                else:
                    print_warning(f"{file_path.name} 找不到 version 欄位")
            except Exception as e:
                print_warning(f"讀取 {file_path.name} 失敗: {e}")
    else:
        # 沒有找到版本檔（純規格版本 / git-tag 策略 / 其他情況）
        print_warning("未偵測到版本檔案")
        print_info("  請確認 .version-release.yaml 的 version_source 設定或專案根目錄版本檔")

    # 檢查當前分支（僅警告，不同專案可能有不同分支命名慣例）
    # Gap 3：trunk 工作流（all-on-main）無 feature 分支慣例，跳過此警告
    release_workflow = config.get(
        "release_workflow", DEFAULT_VERSION_RELEASE_CONFIG["release_workflow"]
    )
    if release_workflow != "trunk":
        try:
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=root,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                current_branch = result.stdout.strip()
                major_minor = extract_major_minor(version)
                expected_branch = f"feature/v{major_minor}"
                if current_branch != expected_branch:
                    print_warning(
                        f"當前分支: {current_branch} (慣例為 {expected_branch})"
                    )
        except Exception as e:
            print_warning(f"檢查 git 分支失敗: {e}")

    # 檢查工作目錄是否乾淨
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            print_warning(
                f"工作目錄有未提交的修改 ({len(result.stdout.splitlines())} 個檔案)"
            )
            # 這不是致命錯誤，但應該提示
    except Exception:
        pass

    return len(errors) == 0, errors


def preflight_check(version: str) -> Tuple[bool, Dict[str, Tuple[bool, List[str]]]]:
    """執行 Pre-flight 檢查"""
    print_section("Step 1: Pre-flight Check")

    results = {}

    # 1.1 檢查工作日誌
    print_info("[OK] 檢查工作日誌完成度...")
    wl_ok, wl_errors = check_worklog_completed(version)
    results["worklog"] = (wl_ok, wl_errors)

    if wl_ok:
        print_success("Worklog 目標達成")
    else:
        for error in wl_errors:
            print_error(error)

    # 1.2 檢查技術債務狀態（新增：詳細掃描）
    print_info("[OK] 檢查技術債務處理狀態...")
    td_status = check_technical_debt_status(version)
    results["tech_debt_status"] = td_status

    if td_status["passed"]:
        print_success(td_status["message"])
    else:
        print_error(td_status["message"])

        # 顯示待處理的 TD 詳情
        if td_status["pending_tds"]:
            print_info("\n待處理技術債務:", 1)
            for td in td_status["pending_tds"]:
                print_info(
                    f"  - {td['ticket_id']}: {td['target']} ({td['status']})", 2
                )

            # 提供修復建議
            print_info("\n解決方式:", 1)
            print_info("  1. 處理這些技術債務後再發布", 2)
            major_minor = extract_major_minor(version)
            next_version = f"{int(major_minor.split('.')[1]) + 1}"
            next_major_minor = f"{major_minor.split('.')[0]}.{next_version}"
            print_info(
                f"  2. 使用 --defer-td {next_major_minor} 明確延後到下一版本", 2
            )

    # 1.3 檢查舊的技術債務檢查（保留相容性）
    print_info("[OK] 驗證技術債務分類...")
    td_ok, td_errors = check_technical_debt(version)
    results["tech_debt"] = (td_ok, td_errors)

    if not td_ok:
        for error in td_errors:
            print_error(error)

    # 1.4 檢查前版本未完成任務
    print_info("[OK] 檢查前版本未完成任務...")
    pv_ok, pv_errors = check_previous_versions_completed(version)
    results["previous_versions"] = (pv_ok, pv_errors)

    if pv_ok:
        print_success("前版本任務已完成")
    else:
        for error in pv_errors:
            print_error(error)

    # 1.5 檢查版本同步
    print_info("[OK] 檢查版本同步...")
    vs_ok, vs_errors = check_version_sync(version)
    results["version_sync"] = (vs_ok, vs_errors)

    if vs_ok:
        print_success("版本同步 [OK]")
    else:
        for error in vs_errors:
            print_error(error)

    all_ok = wl_ok and td_status["passed"] and td_ok and pv_ok and vs_ok
    return all_ok, results


def extract_changelog_section(version: str) -> Optional[str]:
    """從工作日誌提取 CHANGELOG 區塊"""
    root = get_project_root()
    major_minor = extract_major_minor(version)
    worklog_dir = root / "docs" / "work-logs"

    # 查找相關的工作日誌
    worklog_file = None
    for f in worklog_dir.glob(f"v{major_minor}*.md"):
        if "phase4" in f.name.lower() or "final" in f.name.lower():
            worklog_file = f
            break

    if not worklog_file:
        return None

    try:
        with open(worklog_file, encoding="utf-8") as f:
            content = f.read()

        # 嘗試找到 CHANGELOG 相關的區塊
        # 通常在 Phase 4 報告中會有功能變動總結
        pattern = r"(?:## \[.*?\]|### Added|### Changed|### Fixed|### Removed)(.*?)(?=\n## |\n### |\Z)"
        matches = re.findall(pattern, content, re.DOTALL)

        if matches:
            return "\n".join(matches[:3])  # 取前 3 個區塊

    except Exception:
        pass

    return None


def update_changelog(version: str, dry_run: bool = False) -> bool:
    """更新 CHANGELOG.md"""
    root = get_project_root()
    changelog_path = root / "CHANGELOG.md"

    if not changelog_path.exists():
        print_error(f"找不到 {changelog_path}")
        return False

    try:
        with open(changelog_path, encoding="utf-8") as f:
            changelog_content = f.read()

        # 建立新的版本區塊
        today = datetime.now().strftime("%Y-%m-%d")
        new_version_block = f"""## [{version}] - {today}

**[OK] UC-XX 功能名稱 - TDD 四階段完成**

### Added
- 新增功能項目

### Changed
- 變更項目

### Fixed
- 修復項目

---

"""

        # finalize 優先：偵測既有 In-Development 區段（header 改發布日期 + 保留人寫內容）
        # 開發期 header 慣例為 "## [v{version}] - In Development" 或 "## [{version}] - In Development"
        finalize_pattern = re.compile(
            r"^## \[v?" + re.escape(version) + r"\] - In Development\s*$",
            re.MULTILINE,
        )
        finalize_match = finalize_pattern.search(changelog_content)
        if finalize_match:
            finalized_header = f"## [{version}] - {today}"
            updated_content = (
                changelog_content[: finalize_match.start()]
                + finalized_header
                + changelog_content[finalize_match.end():]
            )

            if not dry_run:
                with open(changelog_path, "w", encoding="utf-8") as f:
                    f.write(updated_content)

            print_success(f"CHANGELOG.md 已 finalize In-Development 區段為 {version}")
            return True

        # 幂等性檢查：若版本已 finalize（header 帶日期）則跳過，不重複插入
        if f"## [{version}]" in changelog_content or f"## [v{version}]" in changelog_content:
            print_warning(f"CHANGELOG.md 已包含 v{version} 條目，跳過插入")
            return True

        # 無 In-Development 區段且版本未存在：維持原有插入模板行為（向後相容）
        # 插入到 "## [" 之前（在 "格式基於" 之後）
        insert_pos = changelog_content.find("## [")
        if insert_pos > 0:
            updated_content = (
                changelog_content[:insert_pos]
                + new_version_block
                + changelog_content[insert_pos:]
            )

            if not dry_run:
                with open(changelog_path, "w", encoding="utf-8") as f:
                    f.write(updated_content)

            print_success(f"CHANGELOG.md 已更新版本 {version}")
            return True
        else:
            print_error("CHANGELOG.md 格式不符")
            return False

    except Exception as e:
        print_error(f"更新 CHANGELOG.md 失敗: {e}")
        return False


def defer_technical_debts(version: str, defer_to_version: str, dry_run: bool = False) -> bool:
    """
    將待處理的技術債務延後到下一版本

    Args:
        version: 當前版本 (例如 "0.20.5")
        defer_to_version: 延後到的版本 (例如 "0.21.0")
        dry_run: 預覽模式

    Returns:
        True 如果成功，False 如果失敗
    """
    root = get_project_root()
    major_minor = extract_major_minor(version)

    # 掃描版本系列的票目錄
    worklog_dir = root / "docs" / "work-logs"
    tickets_dir = worklog_dir / f"v{major_minor}.0" / "tickets"

    if not tickets_dir.exists():
        print_warning(f"找不到票目錄: {tickets_dir}")
        return True

    # 掃描所有 TD 檔案
    td_files = list(tickets_dir.glob("*-TD-*.md"))
    deferred_count = 0

    for td_file in sorted(td_files):
        try:
            with open(td_file, encoding="utf-8") as f:
                content = f.read()

            # 解析 frontmatter
            frontmatter = parse_ticket_frontmatter(content)
            if not frontmatter:
                continue

            # 提取關鍵欄位
            status_match = re.search(r"status:\s+(.+)", frontmatter)
            version_match = re.search(r"version:\s+(.+)", frontmatter)

            status = status_match.group(1).strip() if status_match else "unknown"
            target_version = (
                version_match.group(1).strip() if version_match else "unknown"
            )

            # 只延後當前版本系列的待處理 TD
            is_current_version = (
                target_version == major_minor or target_version == f"0.{major_minor}"
            )
            is_pending = status == "pending"

            if is_current_version and is_pending:
                # 更新 frontmatter
                new_frontmatter = frontmatter

                # 更新 version 欄位
                new_frontmatter = re.sub(
                    r"version:\s+(.+)",
                    f"version: {defer_to_version}",
                    new_frontmatter,
                )

                # 更新或新增 deferred_from 欄位
                if "deferred_from:" in new_frontmatter:
                    new_frontmatter = re.sub(
                        r"deferred_from:\s+(.+)",
                        f"deferred_from: {major_minor}",
                        new_frontmatter,
                    )
                else:
                    # 在 version 欄位後新增 deferred_from
                    new_frontmatter = re.sub(
                        r"(version:\s+.+\n)",
                        f"\\1deferred_from: {major_minor}\n",
                        new_frontmatter,
                    )

                # 更新或新增 defer_reason 欄位
                reason = f"版本 {version} 發布前延後至 {defer_to_version}"
                if "defer_reason:" in new_frontmatter:
                    new_frontmatter = re.sub(
                        r'defer_reason:\s+(.+)',
                        f'defer_reason: "{reason}"',
                        new_frontmatter,
                    )
                else:
                    # 在 deferred_from 欄位後新增 defer_reason
                    new_frontmatter = re.sub(
                        r"(deferred_from:\s+.+\n)",
                        f'\\1defer_reason: "{reason}"\n',
                        new_frontmatter,
                    )

                # 建立新的檔案內容
                new_content = re.sub(
                    r"^---\n(.*?)\n---",
                    f"---\n{new_frontmatter}\n---",
                    content,
                    count=1,
                    flags=re.DOTALL,
                )

                if not dry_run:
                    with open(td_file, "w", encoding="utf-8") as f:
                        f.write(new_content)

                ticket_id_match = re.search(r"ticket_id:\s+(.+)", frontmatter)
                ticket_id = (
                    ticket_id_match.group(1).strip() if ticket_id_match else "unknown"
                )

                print_success(
                    f"已延後 {ticket_id} 到版本 {defer_to_version}"
                )
                deferred_count += 1

        except Exception as e:
            print_warning(f"處理 {td_file.name} 時出錯: {e}")

    if deferred_count > 0:
        print_success(f"\n共延後 {deferred_count} 個技術債務")
        return True
    else:
        print_info("沒有找到待延後的技術債務")
        return True


def find_last_completed_version(todolist_path: Path) -> Optional[str]:
    """從 todolist.yaml 找出最後一個 completed 版本。

    遍歷 versions 列表，回傳最後一個 status 為 completed 的版本號。

    Args:
        todolist_path: todolist.yaml 的完整路徑

    Returns:
        版本號字串，或 None（找不到任何 completed 版本）
    """
    with open(todolist_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    last_completed = None
    for entry in data.get("versions", []):
        if entry.get("status") == "completed":
            last_completed = entry.get("version")
    return last_completed


def insert_version_to_todolist(
    todolist_path: Path,
    new_version: str,
    from_version: str,
    description: str,
    dry_run: bool = False,
) -> bool:
    """在 todolist.yaml 中插入新版本條目（字串操作，保留格式）。

    在 from_version 條目之後插入新版本條目，狀態設為 active。

    Args:
        todolist_path: todolist.yaml 路徑
        new_version: 新版本號
        from_version: 前一個版本號（插入位置參考）
        description: 版本描述
        dry_run: 預覽模式

    Returns:
        是否成功
    """
    with open(todolist_path, encoding="utf-8") as f:
        content = f.read()

    # 找到 from_version 條目
    from_major_minor = extract_major_minor(from_version)
    from_candidates = [from_version, from_major_minor]
    insert_pos = -1

    for ver_str in from_candidates:
        marker = f'version: "{ver_str}"'
        start = content.find(f"  - {marker}")
        if start == -1:
            start = content.find(f"- {marker}")
        if start == -1:
            continue

        # 找到該條目的結尾（下一個條目的開頭）
        next_entry = content.find("\n  - version:", start + 1)
        if next_entry == -1:
            next_entry = content.find("\n- version:", start + 1)

        if next_entry != -1:
            insert_pos = next_entry + 1  # 換行後
        else:
            # from_version 是最後一個條目，附加到末尾
            insert_pos = len(content)
            if not content.endswith("\n"):
                insert_pos = len(content)
        break

    if insert_pos == -1:
        print_error(f"在 todolist.yaml 中找不到版本 {from_version}")
        return False

    # 建立新條目
    new_entry = (
        f'\n  - version: "{new_version}"\n'
        f"    status: active\n"
        f'    description: "{description}"\n'
    )

    new_content = content[:insert_pos] + new_entry + content[insert_pos:]

    # 更新 last_updated
    today = datetime.now().strftime("%Y-%m-%d")
    new_content = re.sub(
        r'(last_updated: ")[^"]*(")',
        rf"\g<1>{today}\2",
        new_content,
        count=1,
    )

    if dry_run:
        print_info("[DRY RUN] 將在 todolist.yaml 插入:")
        print_info(new_entry.rstrip())
    else:
        with open(todolist_path, "w", encoding="utf-8") as f:
            f.write(new_content)

    return True


def mark_version_completed(
    todolist_path: Path,
    version: str,
    dry_run: bool = False,
) -> bool:
    """將 todolist.yaml 中對應版本的 status 標記為 completed（字串操作，保留格式）。

    release 成功後呼叫，將發布版本由 active 轉為 completed，避免後續 start
    下一版被前版本驗證（find_last_completed_version）阻擋。

    Args:
        todolist_path: todolist.yaml 路徑
        version: 要標記為 completed 的版本號
        dry_run: 預覽模式

    Returns:
        True 如果成功（含已是 completed 的冪等情況），False 如果找不到版本
    """
    if not todolist_path.exists():
        print_error(f"找不到 {todolist_path}")
        return False

    with open(todolist_path, encoding="utf-8") as f:
        content = f.read()

    # 定位版本條目：- version: "X" 後續行的 status: 欄位
    major_minor = extract_major_minor(version)
    candidates = [version, major_minor]
    entry_start = -1
    for ver_str in candidates:
        marker = f'version: "{ver_str}"'
        pos = content.find(f"- {marker}")
        if pos != -1:
            entry_start = pos
            break

    if entry_start == -1:
        print_error(f"在 todolist.yaml 中找不到版本 {version}")
        return False

    # 找到該條目範圍內第一個 status: 行（下一個 "- version:" 之前）
    next_entry = content.find("- version:", entry_start + 1)
    search_end = next_entry if next_entry != -1 else len(content)
    status_match = re.search(
        r"^(\s*status:\s*)(\S+)",
        content[entry_start:search_end],
        re.MULTILINE,
    )
    if not status_match:
        print_error(f"版本 {version} 條目缺少 status 欄位")
        return False

    current_status = status_match.group(2)
    if current_status == "completed":
        print_info(f"版本 {version} 已為 completed，跳過")
        return True

    abs_start = entry_start + status_match.start()
    abs_end = entry_start + status_match.end()
    new_content = content[:abs_start] + status_match.group(1) + "completed" + content[abs_end:]

    # 更新 last_updated
    today = datetime.now().strftime("%Y-%m-%d")
    new_content = re.sub(
        r'(last_updated: ")[^"]*(")',
        rf"\g<1>{today}\2",
        new_content,
        count=1,
    )

    if dry_run:
        print_info(f"[DRY RUN] 將標記 todolist.yaml 版本 {version}: {current_status} → completed")
    else:
        with open(todolist_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        print_success(f"todolist.yaml 版本 {version} 已標記 completed")

    return True


def activate_next_planned_version(
    todolist_path: Path, completed_version: str, dry_run: bool = False
) -> bool:
    """release 後自動將下一個 planned 版本推進為 active。

    掃描 todolist.yaml versions 清單，找到第一個 status 為 planned 的版本並設為 active。
    若無 planned 版本，印提示並回傳 True（非錯誤）。

    Args:
        todolist_path: todolist.yaml 路徑
        completed_version: 剛完成的版本號（用於日誌訊息）
        dry_run: 預覽模式

    Returns:
        True 如果成功或無 planned 版本，False 如果 IO 錯誤
    """
    if not todolist_path.exists():
        return False

    with open(todolist_path, encoding="utf-8") as f:
        content = f.read()

    pattern = re.compile(
        r'(- version: "([^"]+)".*?)(status:\s*)("planned"|planned)(?=\s|$)',
        re.DOTALL,
    )
    match = pattern.search(content)
    if not match:
        print_info("todolist.yaml 無 planned 版本可推進，跳過")
        return True

    next_version = match.group(2)
    was_quoted = match.group(4).startswith('"')
    active_value = '"active"' if was_quoted else "active"

    if dry_run:
        print_info(
            f"[DRY RUN] 將推進 todolist.yaml 版本 {next_version}: planned → active"
        )
    else:
        new_content = (
            content[: match.start(3)]
            + match.group(3)
            + active_value
            + content[match.end() :]
        )
        with open(todolist_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        print_success(
            f"todolist.yaml 版本 {next_version} 已推進 active（接續 {completed_version}）"
        )

    return True


def create_worklog_structure(
    version: str, description: str, dry_run: bool = False,
    worklog_path_pattern: Optional[str] = None,
) -> Tuple[bool, List[str]]:
    """建立版本 worklog 目錄結構和主檔案。

    建立 worklog 主檔案（從模板生成）。
    如果 middle worklog 不存在（nested 樣式時），也一併建立。

    Args:
        version: 版本號（如 "0.17.2"）
        description: 版本描述
        dry_run: 預覽模式
        worklog_path_pattern: worklog 路徑範本（None 時從 config 讀取）

    Returns:
        (是否成功, 建立的檔案/目錄清單)
    """
    root = get_project_root()
    major_minor = extract_major_minor(version)

    if not worklog_path_pattern:
        config = load_version_release_config(root)
        worklog_path_pattern = config.get(
            "worklog_path_pattern",
            DEFAULT_VERSION_RELEASE_CONFIG["worklog_path_pattern"],
        )

    version_dir = resolve_worklog_dir(root, version, worklog_path_pattern)
    tickets_dir = version_dir / "tickets"

    created_items: List[str] = []

    # 建立目錄
    if dry_run:
        print_info(f"[DRY RUN] 建立目錄: {tickets_dir.relative_to(root)}")
        created_items.append(str(tickets_dir.relative_to(root)))
    else:
        tickets_dir.mkdir(parents=True, exist_ok=True)
        created_items.append(str(tickets_dir.relative_to(root)))

    # 建立 middle worklog（nested 樣式時，如果不存在）
    minor_dir = version_dir.parent
    is_nested = minor_dir != version_dir and minor_dir.name.startswith("v")
    middle_worklog = minor_dir / f"v{major_minor}-main.md" if is_nested else None
    if middle_worklog and not middle_worklog.exists():
        middle_content = (
            f"# v{major_minor} 版本系列索引\n\n"
            f"| 版本 | 狀態 | 說明 |\n"
            f"|------|------|------|\n"
            f"| v{version} | 進行中 | {description} |\n"
        )
        if dry_run:
            print_info(
                f"[DRY RUN] 建立索引: {middle_worklog.relative_to(root)}"
            )
        else:
            middle_worklog.write_text(middle_content, encoding="utf-8")
        created_items.append(str(middle_worklog.relative_to(root)))

    # 建立 worklog 主檔案（從模板）
    template_path = (
        root / ".claude" / "skills" / "doc-flow" / "templates" / "worklog.md.template"
    )
    worklog_file = version_dir / f"v{version}-main.md"
    today = datetime.now().strftime("%Y-%m-%d")

    if template_path.exists():
        template = template_path.read_text(encoding="utf-8")
        worklog_content = (
            template.replace("{VERSION}", version)
            .replace("{START_DATE}", today)
            .replace("{ONE_LINE_GOAL}", description or "待定義")
            .replace("{WHY_THIS_VERSION}", "待補充")
            .replace("{INITIAL_CONTEXT}", "待補充")
            .replace("{LAST_UPDATE}", today)
        )
    else:
        # 模板不存在時的 fallback
        worklog_content = (
            f"# v{version} 版本工作日誌\n\n"
            f"**版本號**: v{version}\n"
            f"**開始日期**: {today}\n"
            f"**目標**: {description or '待定義'}\n"
            f"**狀態**: 進行中\n"
        )
        print_warning(f"模板不存在: {template_path.relative_to(root)}，使用簡易格式")

    if dry_run:
        print_info(f"[DRY RUN] 建立 worklog: {worklog_file.relative_to(root)}")
    else:
        worklog_file.write_text(worklog_content, encoding="utf-8")
    created_items.append(str(worklog_file.relative_to(root)))

    return True, created_items


def bump_json_version(file_path: Path, new_version: str, dry_run: bool = False) -> bool:
    """更新 JSON 檔案中的 version 欄位。

    讀取 JSON → 更新 version → 寫回（保留 2 空格縮排 + 結尾換行）。

    Args:
        file_path: JSON 檔案路徑
        new_version: 新版本號
        dry_run: 預覽模式

    Returns:
        是否成功
    """
    if not file_path.exists():
        print_error(f"找不到 {file_path}")
        return False

    with open(file_path, encoding="utf-8") as f:
        data = json.load(f)

    old_version = data.get("version", "unknown")
    data["version"] = new_version

    if dry_run:
        print_info(
            f"[DRY RUN] {file_path.name}: {old_version} -> {new_version}"
        )
    else:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")

    return True


def bump_yaml_version(file_path: Path, new_version: str, dry_run: bool = False) -> bool:
    """更新 YAML 檔案中的 version 欄位。

    支援 pubspec.yaml 的 X.Y.Z+build 格式：
    - 若原版本含 build number（如 1.0.0+1），bump 後自動遞增（如 2.0.0+2）
    - 若原版本無 build number，直接替換版本號

    以 regex 逐行替換保留檔案格式（不重新序列化整份 YAML）。

    Args:
        file_path: YAML 檔案路徑
        new_version: 新版本號（不含 build number 部分）
        dry_run: 預覽模式

    Returns:
        是否成功
    """
    if not file_path.exists():
        print_error(f"找不到 {file_path}")
        return False

    content = file_path.read_text(encoding="utf-8")

    version_pattern = re.compile(r"^(version:\s+)(.+)$", re.MULTILINE)
    match = version_pattern.search(content)
    if not match:
        print_error(f"{file_path.name} 中找不到 version 欄位")
        return False

    old_full = match.group(2).strip()
    build_match = re.match(r"^[\d.]+\+(\d+)$", old_full)

    if build_match:
        old_build = int(build_match.group(1))
        new_full = f"{new_version}+{old_build + 1}"
    else:
        new_full = new_version

    if dry_run:
        print_info(f"[DRY RUN] {file_path.name}: {old_full} -> {new_full}")
    else:
        new_content = version_pattern.sub(rf"\g<1>{new_full}", content, count=1)
        file_path.write_text(new_content, encoding="utf-8")

    return True


def bump_toml_version(file_path: Path, new_version: str, dry_run: bool = False) -> bool:
    """更新 TOML 檔案中的 version 欄位。

    以 regex 逐行替換保留檔案格式（不重新序列化整份 TOML）。
    支援 `version = "X.Y.Z"` 和 `version = 'X.Y.Z'` 兩種引號風格。

    Args:
        file_path: TOML 檔案路徑
        new_version: 新版本號
        dry_run: 預覽模式

    Returns:
        是否成功
    """
    if not file_path.exists():
        print_error(f"找不到 {file_path}")
        return False

    content = file_path.read_text(encoding="utf-8")

    version_pattern = re.compile(
        r'^(version\s*=\s*)(["\'])([^"\']+)\2', re.MULTILINE
    )
    match = version_pattern.search(content)
    if not match:
        print_error(f"{file_path.name} 中找不到 version 欄位")
        return False

    old_version = match.group(3)
    quote_char = match.group(2)

    if dry_run:
        print_info(f"[DRY RUN] {file_path.name}: {old_version} -> {new_version}")
    else:
        new_content = version_pattern.sub(
            rf"\g<1>{quote_char}{new_version}{quote_char}", content, count=1
        )
        file_path.write_text(new_content, encoding="utf-8")

    return True


def _resolve_worklog_pattern(root: Path, config: dict, project_type: str) -> str:
    """依使用者 config 或 project_type 決定 worklog 路徑範本。

    優先序：
    1. 使用者在 .version-release.yaml 明確設定 worklog_path_pattern → 使用
    2. 未設定 → flutter 用 nested-3，其餘用 flat
    """
    WORKLOG_NESTED_3 = "docs/work-logs/v{major}/v{major_minor}/v{version}"
    WORKLOG_FLAT = "docs/work-logs/v{version}"

    # 讀取原始 config 判斷使用者是否明確設定
    raw_config = _load_raw_version_release_config(root)
    if raw_config and "worklog_path_pattern" in raw_config:
        return raw_config["worklog_path_pattern"]

    if project_type == PROJECT_TYPE_FLUTTER:
        return WORKLOG_NESTED_3
    return WORKLOG_FLAT


def _load_raw_version_release_config(root: Path) -> Optional[dict]:
    """讀取原始 .version-release.yaml（不補 DEFAULT），用於判斷使用者是否明確設定。"""
    candidate_paths = [
        root / VERSION_RELEASE_CONFIG_FILE,
        root / ".claude" / VERSION_RELEASE_CONFIG_FILE,
    ]
    config_path = next((p for p in candidate_paths if p.exists()), None)
    if config_path is None:
        return None
    try:
        with open(config_path, encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception:
        return None


def cmd_start_version(
    version: str,
    from_version: Optional[str] = None,
    description: str = "",
    dry_run: bool = False,
) -> bool:
    """執行 start 子命令：程式化版本啟動流程。

    依序執行：前版本驗證 → 重複檢查 → 更新 todolist →
    建立 worklog 結構 → bump 版本檔案 → 摘要報告。

    Args:
        version: 新版本號（已 normalize）
        from_version: 前一個版本號（可選，自動偵測）
        description: 版本描述
        dry_run: 預覽模式

    Returns:
        是否成功
    """
    root = get_project_root()
    todolist_path = root / "docs" / "todolist.yaml"
    changed_files: List[str] = []

    if not todolist_path.exists():
        print_error("找不到 docs/todolist.yaml")
        return False

    # ── Step 1: 前版本驗證 ──
    print_section("Step 1: 前版本驗證")

    if not from_version:
        from_version = find_last_completed_version(todolist_path)
        if from_version:
            print_info(f"自動偵測前版本: {from_version}")
        else:
            print_error("無法自動偵測前版本，請使用 --from 指定")
            return False
    else:
        # 驗證指定的 from_version 為 completed
        with open(todolist_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        found = False
        for entry in data.get("versions", []):
            if entry.get("version") == from_version:
                if entry.get("status") != "completed":
                    print_error(
                        f"版本 {from_version} 狀態為 {entry.get('status')}，非 completed"
                    )
                    return False
                found = True
                break
        if not found:
            print_error(f"版本 {from_version} 不在 todolist.yaml 中")
            return False

    print_success(f"前版本: {from_version}")

    # 檢查 git tag
    try:
        result = subprocess.run(
            ["git", "tag", "-l", f"v{from_version}"],
            capture_output=True,
            text=True,
            cwd=root,
        )
        if result.stdout.strip():
            print_success(f"Git tag v{from_version} 存在")
        else:
            print_warning(f"Git tag v{from_version} 不存在（非致命）")
    except Exception:
        print_warning("無法檢查 git tag（非致命）")

    # ── 偵測專案類型與版本源 ──
    config = load_version_release_config(root)
    project_type = config.get("project_type")
    if not project_type:
        project_type = detect_project_type(root)

    version_file, parser_type = resolve_version_source(root, config)
    print_info(f"專案類型: {project_type}")
    if version_file:
        print_info(f"版本源: {version_file.name} ({parser_type})")
    else:
        print_info(f"版本源: git-tag")

    # worklog 預設路徑依 project_type 決定（使用者明確設定優先）
    WORKLOG_NESTED_3 = "docs/work-logs/v{major}/v{major_minor}/v{version}"
    WORKLOG_FLAT = "docs/work-logs/v{version}"
    worklog_pattern = _resolve_worklog_pattern(root, config, project_type)
    print_info(f"Worklog 路徑樣式: {worklog_pattern}")

    # ── Step 2: 重複檢查 ──
    print_section("Step 2: 重複檢查")

    with open(todolist_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    for entry in data.get("versions", []):
        if entry.get("version") == version:
            print_error(f"版本 {version} 已存在於 todolist.yaml（狀態: {entry.get('status')}）")
            return False
    print_success("todolist.yaml 中無重複版本")

    version_dir = resolve_worklog_dir(root, version, worklog_pattern)
    if version_dir.exists():
        print_error(f"Worklog 目錄已存在: {version_dir.relative_to(root)}")
        return False
    print_success("worklog 目錄不存在，可以建立")

    # ── Step 3: 更新 todolist.yaml ──
    print_section("Step 3: 更新 todolist.yaml")

    ok = insert_version_to_todolist(
        todolist_path, version, from_version, description or "待定義", dry_run
    )
    if not ok:
        return False
    print_success("todolist.yaml 已更新")
    changed_files.append("docs/todolist.yaml")

    # ── Step 4: 建立 worklog 目錄結構 ──
    print_section("Step 4: 建立 worklog 目錄結構")

    ok, created = create_worklog_structure(
        version, description or "待定義", dry_run,
        worklog_path_pattern=worklog_pattern,
    )
    if not ok:
        return False
    for item in created:
        print_success(f"建立: {item}")
    changed_files.extend(created)

    # ── Step 5: Bump 版本檔案 ──
    print_section("Step 5: Bump 版本檔案")

    bump_dispatch = {
        "json": bump_json_version,
        "yaml": bump_yaml_version,
        "toml": bump_toml_version,
    }

    if version_file and parser_type in bump_dispatch:
        bump_fn = bump_dispatch[parser_type]
        ok = bump_fn(version_file, version, dry_run)
        if not ok:
            return False
        print_success(f"{version_file.name} 版本已更新為 {version}")
        changed_files.append(str(version_file.relative_to(root)))

        # Chrome Extension：同步 bump manifest.json
        vs_config = config.get("version_source")
        sync_targets = vs_config.get("sync_targets", []) if isinstance(vs_config, dict) else []
        if not sync_targets and project_type == PROJECT_TYPE_CHROME_EXT:
            manifest_path = root / "manifest.json"
            if manifest_path.exists():
                sync_targets = [{"path": "manifest.json", "parser": "json"}]

        for target in sync_targets:
            target_path = root / target["path"]
            target_parser = target.get("parser", "json")
            if target_path.exists() and target_parser in bump_dispatch:
                ok = bump_dispatch[target_parser](target_path, version, dry_run)
                if ok:
                    print_success(f"{target['path']} 版本已同步為 {version}")
                    changed_files.append(target["path"])
    elif parser_type == "git-tag":
        print_info("版本由 git tag 管理，start 階段不 bump 檔案")
    else:
        print_warning(f"未知 parser 類型 {parser_type}，跳過版本 bump")

    # ── 摘要報告 ──
    print_section("摘要")

    mode_label = " (DRY RUN)" if dry_run else ""
    print_info(f"版本啟動完成{mode_label}:")
    print_info(f"  新版本: {version}")
    print_info(f"  前版本: {from_version}")
    print_info(f"  描述: {description or '待定義'}")
    print_info("")
    print_info("變更檔案:")
    for f in changed_files:
        print_info(f"  - {f}")
    print_info("")
    print_info("下一步建議:")
    print_info("  1. 建立第一批 Ticket（Wave 1）")
    print_info("  2. 執行 git add + commit 提交版本啟動變更")
    print_info(f"  3. 開始 v{version} 開發")

    return True


def update_todolist(version: str, dry_run: bool = False) -> bool:
    """更新 todolist.yaml - 使用字串替換保留格式和注釋

    支援版本格式：「0.31.0」（完整）和「0.31」（major.minor）。
    使用字串替換而非 yaml.dump，避免破壞注釋和原始格式。
    """
    root = get_project_root()
    todolist_path = root / "docs" / "todolist.yaml"

    if not todolist_path.exists():
        print_error(f"找不到 {todolist_path}")
        return False

    try:
        with open(todolist_path, encoding="utf-8") as f:
            content = f.read()

        major_minor = extract_major_minor(version)

        # 同時支援「0.31.0」和「0.31」兩種版本格式
        version_candidates = [version, major_minor]
        matched_ver = None
        new_content = content

        for ver_str in version_candidates:
            version_marker = f'version: "{ver_str}"'
            if version_marker not in new_content:
                continue

            # 找到版本條目的起始位置（考慮不同縮排）
            start = new_content.find(f'  - {version_marker}')
            if start == -1:
                start = new_content.find(f'- {version_marker}')
            if start == -1:
                continue

            # 找到下一個條目作為邊界
            next_entry = new_content.find('\n  - version:', start + 1)
            if next_entry == -1:
                next_entry = new_content.find('\n- version:', start + 1)

            # 取出版本區塊
            if next_entry != -1:
                block = new_content[start:next_entry]
            else:
                # 最後一個版本條目，找到下一個頂層區塊
                next_section = new_content.find('\n\n#', start)
                block = new_content[start:next_section] if next_section != -1 else new_content[start:]

            # 在區塊內替換 status
            if 'status: "active"' in block:
                new_block = block.replace('status: "active"', 'status: "completed"', 1)
                new_content = new_content[:start] + new_block + new_content[start + len(block):]
                matched_ver = ver_str
                break
            elif 'status: "completed"' in block:
                print_warning(f"todolist.yaml v{ver_str} 已是 completed 狀態，跳過")
                return True

        if not matched_ver:
            print_warning("todolist.yaml 沒有找到對應的 active 版本（可能版本格式不符或已完成）")
            return True  # 不是致命錯誤

        # 更新 meta.last_updated
        today = datetime.now().strftime("%Y-%m-%d")
        new_content = re.sub(
            r'(last_updated: ")[^"]*(")',
            rf'\g<1>{today}\2',
            new_content,
            count=1,
        )

        if not dry_run:
            with open(todolist_path, "w", encoding="utf-8") as f:
                f.write(new_content)

        print_success(f"todolist.yaml 已標記 v{matched_ver} 為已完成")
        return True

    except Exception as e:
        print_error(f"更新 todolist.yaml 失敗: {e}")
        return False


def verify_version_files(version: str) -> bool:
    """驗證所有版本檔"""
    root = get_project_root()
    # Gap 2：優先採 resolve_version_source（honor version_source.primary，含子目錄）
    config = load_version_release_config(root)
    version_files = resolve_sync_version_files(root, config)

    if not version_files:
        print_warning("未偵測到版本檔案")
        print_info("  請確認 .version-release.yaml 的 version_source 設定或專案根目錄版本檔", 1)
        return True  # 不阻塞發布流程

    for file_path, parser_type in version_files:
        try:
            file_version = extract_version_from_file(file_path, parser_type)
            if file_version:
                if file_version == version:
                    print_success(f"{file_path.name} 版本正確: {version}")
                else:
                    print_warning(
                        f"{file_path.name} 版本不匹配: {file_version} vs {version}"
                    )
            else:
                print_warning(f"{file_path.name} 找不到 version 欄位")
        except Exception as e:
            print_warning(f"讀取 {file_path.name} 失敗: {e}")

    return True


def update_documents(version: str, dry_run: bool = False) -> bool:
    """更新所有文件"""
    print_section("Step 2: Document Updates")

    all_ok = True

    # 2.1 清理 todolist
    print_info("[NOTE] 更新 docs/todolist.yaml")
    if not update_todolist(version, dry_run):
        all_ok = False

    # 2.2 更新 CHANGELOG
    print_info("[NOTE] 更新 CHANGELOG.md")
    if not update_changelog(version, dry_run):
        all_ok = False

    # 2.3 驗證版本檔
    print_info("[OK] 確認版本號")
    if not verify_version_files(version):
        all_ok = False

    if all_ok:
        print_success("文件更新完成")

    return all_ok


def commit_changes(version: str, dry_run: bool = False) -> bool:
    """提交檔案變更"""
    root = get_project_root()

    try:
        # 檢查是否有待提交的變更
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode == 0 and result.stdout.strip():
            # 有未提交的變更
            if dry_run:
                print_info("[SYNC] [預覽] 將提交檔案變更", 2)
            else:
                # 加入檔案
                subprocess.run(
                    ["git", "add", "docs/todolist.yaml", "CHANGELOG.md"],
                    cwd=root,
                    timeout=10,
                )

                # 提交
                result = subprocess.run(
                    [
                        "git",
                        "commit",
                        "-m",
                        f"docs: 版本 {version} 發布準備",
                    ],
                    cwd=root,
                    capture_output=True,
                    timeout=10,
                )

                if result.returncode == 0:
                    print_success("檔案變更已提交")
                else:
                    print_error("提交變更失敗")
                    return False

        return True

    except Exception as e:
        print_error(f"提交變更失敗: {e}")
        return False


def git_merge_and_push(version: str, dry_run: bool = False) -> bool:
    """執行 Git 操作"""
    print_section("Step 3: Git Operations")

    root = get_project_root()
    major_minor = extract_major_minor(version)
    feature_branch = f"feature/v{major_minor}"

    # 讀取 config：tag 命名 + 發布工作流模式
    config = load_version_release_config(root)
    tag_format = config.get(
        "tag_format", DEFAULT_VERSION_RELEASE_CONFIG["tag_format"]
    )
    tag_name = tag_format.format(version=version, major_minor=major_minor)

    release_workflow = config.get(
        "release_workflow", DEFAULT_VERSION_RELEASE_CONFIG["release_workflow"]
    )
    # trunk = all-on-main，跳過 feature-branch merge 與分支清理
    use_feature_branch = release_workflow == "feature-branch"

    try:
        # 3.1 提交變更
        print_info("[SYNC] 提交所有變更")
        if not commit_changes(version, dry_run):
            return False

        # 3.2 切換到 main 分支
        print_info("[SHUFFLE] 切換到 main 分支")
        if not dry_run:
            subprocess.run(
                ["git", "checkout", "main"],
                cwd=root,
                capture_output=True,
                timeout=10,
            )
        else:
            print_info("   [預覽] git checkout main", 2)

        # 3.3 拉取最新 main
        print_info("[IN] 拉取最新 main")
        if not dry_run:
            result = subprocess.run(
                ["git", "pull", "origin", "main"],
                cwd=root,
                capture_output=True,
                timeout=10,
            )
            if result.returncode == 0:
                print_success("main 分支已更新到最新", )
            else:
                print_error("拉取 main 失敗")
                return False
        else:
            print_info("   [預覽] git pull origin main", 2)

        # 3.4 合併 feature 分支（僅 feature-branch 工作流；trunk 模式跳過）
        if not use_feature_branch:
            print_info("[SKIP] trunk 工作流：跳過 feature 分支合併（all-on-main）")
        else:
            print_info("[SHUFFLE] 合併 feature 分支")
            if not dry_run:
                result = subprocess.run(
                    [
                        "git",
                        "merge",
                        feature_branch,
                        "--no-ff",
                        "-m",
                        f"Merge {feature_branch} into main",
                    ],
                    cwd=root,
                    capture_output=True,
                    timeout=10,
                )
                if result.returncode == 0:
                    print_success(f"已合併 {feature_branch} 到 main")
                else:
                    print_error(f"合併 {feature_branch} 失敗")
                    if "fatal: refusing to merge unrelated histories" not in result.stderr:
                        return False
            else:
                print_info(f"   [預覽] git merge {feature_branch} --no-ff", 2)

        # 3.5 建立 Tag
        print_info(f"[TAG]️ 建立 Tag: {tag_name}")
        if not dry_run:
            result = subprocess.run(
                [
                    "git",
                    "tag",
                    "-a",
                    tag_name,
                    "-m",
                    f"Release {tag_name}",
                ],
                cwd=root,
                capture_output=True,
                timeout=10,
            )
            if result.returncode == 0:
                print_success(f"Tag 已建立: {tag_name}")
            else:
                print_error(f"建立 Tag 失敗")
                return False
        else:
            print_info(f"   [預覽] git tag -a {tag_name}", 2)

        # 3.6 推送到遠端
        print_info("[OUT] 推送到遠端")
        if not dry_run:
            # 推送 main
            result = subprocess.run(
                ["git", "push", "origin", "main"],
                cwd=root,
                capture_output=True,
                timeout=10,
            )
            if result.returncode == 0:
                print_success("main 已推送")
            else:
                print_error("推送 main 失敗")
                return False

            # 推送 tag
            result = subprocess.run(
                ["git", "push", "origin", tag_name],
                cwd=root,
                capture_output=True,
                timeout=10,
            )
            if result.returncode == 0:
                print_success(f"Tag {tag_name} 已推送")
            else:
                print_error(f"推送 Tag 失敗")
                return False
        else:
            print_info("   [預覽] git push origin main", 2)
            print_info(f"   [預覽] git push origin {tag_name}", 2)

        # 3.7 刪除 feature 分支（僅 feature-branch 工作流；trunk 模式跳過）
        if not use_feature_branch:
            print_info("[SKIP] trunk 工作流：無 feature 分支需清理")
        else:
            print_info("[DEL]️ 清理 feature 分支")
            if not dry_run:
                # 本地刪除
                result = subprocess.run(
                    ["git", "branch", "-d", feature_branch],
                    cwd=root,
                    capture_output=True,
                    timeout=10,
                )
                if result.returncode == 0:
                    print_success(f"本地分支已刪除: {feature_branch}")
                else:
                    print_error(f"刪除本地分支失敗")

                # 遠端刪除
                result = subprocess.run(
                    ["git", "push", "origin", "--delete", feature_branch],
                    cwd=root,
                    capture_output=True,
                    timeout=10,
                )
                if result.returncode == 0:
                    print_success(f"遠端分支已刪除: origin/{feature_branch}")
                else:
                    print_warning(f"刪除遠端分支失敗（可能不存在）")
            else:
                print_info(f"   [預覽] git branch -d {feature_branch}", 2)
                print_info(f"   [預覽] git push origin --delete {feature_branch}", 2)

        return True

    except Exception as e:
        print_error(f"Git 操作失敗: {e}")
        return False


def print_summary(version: str, all_ok: bool, dry_run: bool = False):
    """打印完成摘要"""
    print_section("完成摘要")

    if all_ok:
        if dry_run:
            print_warning("預覽模式完成 - 未執行實際操作")
            print_info("執行以下指令進行實際發布:")
            print_info("  uv run version_release.py release", 1)
        else:
            print_success(f"版本 {version} 發布成功！")
            print_info("\n[STATS] 發布統計:")
            print_info("- 檔案更新: 2", 1)
            print_info("- 合併提交: 1", 1)
            print_info("- Tag 建立: 1", 1)
            print_info("- 分支清理: 2", 1)
            print_info("\n[DONE] 版本已推送到 main 分支", 1)
    else:
        print_error("發布失敗，請修正上述問題後重新執行")


def main():
    """主程式"""
    import argparse

    parser = argparse.ArgumentParser(
        description="版本發布整合工具 - 包含技術債務檢查和延後機制",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
常用範例:
  # 啟動新版本
  uv run version_release.py start --version 0.18.0 --description "測試重寫"

  # 啟動新版本（預覽模式）
  uv run version_release.py start --version 0.18.0 --dry-run

  # 檢查版本是否準備好發布
  uv run version_release.py check --version 0.20

  # 預覽發布流程
  uv run version_release.py release --dry-run

  # 標準發布流程
  uv run version_release.py release --version 0.20.5

  # 延後待處理 TD 後發布
  uv run version_release.py release --version 0.20.5 --defer-td 0.21.0

  # 預覽 TD 延後結果
  uv run version_release.py release --version 0.20.5 --defer-td 0.21.0 --dry-run

技術債務管理:
  • 自動掃描待處理 TD (status: pending)
  • 顯示詳細的 TD 清單和修復建議
  • 支援 --defer-td 選項延後 TD 到下一版本
  • 自動更新 version、deferred_from、defer_reason 欄位

詳細文檔: 參考 README.md 和 TECH_DEBT_GUIDE.md
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="可用的子命令")

    # start 子命令
    start_parser = subparsers.add_parser("start", help="啟動新版本")
    start_parser.add_argument("--version", required=True, help="新版本號 (X.Y 或 X.Y.Z)")
    start_parser.add_argument("--from", dest="from_version", help="前一個版本號（預設自動偵測）")
    start_parser.add_argument("--description", default="", help="版本描述")
    start_parser.add_argument("--dry-run", action="store_true", help="預覽模式")

    # release 子命令
    release_parser = subparsers.add_parser("release", help="完整發布流程")
    release_parser.add_argument("--version", help="版本號 (X.Y 或 X.Y.Z)")
    release_parser.add_argument("--dry-run", action="store_true", help="預覽模式")
    release_parser.add_argument("--force", action="store_true", help="強制執行")
    release_parser.add_argument("--defer-td", help="將待處理 TD 延後到指定版本 (例如 0.21.0)")

    # check 子命令
    check_parser = subparsers.add_parser("check", help="只執行檢查")
    check_parser.add_argument("--version", help="版本號")

    # update-docs 子命令
    update_parser = subparsers.add_parser("update-docs", help="只更新文件")
    update_parser.add_argument("--version", help="版本號")
    update_parser.add_argument("--dry-run", action="store_true", help="預覽模式")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    try:
        if args.command == "start":
            version = normalize_version(args.version)
            header = f"Version Start - {version}"
            if args.dry_run:
                header += " (DRY RUN)"
            print_header(header)

            if args.dry_run:
                print_warning("預覽模式：不會寫入任何檔案\n")

            ok = cmd_start_version(
                version=version,
                from_version=args.from_version,
                description=args.description,
                dry_run=args.dry_run,
            )
            return 0 if ok else 1

        # 規範化版本號
        version = normalize_version(args.version if hasattr(args, "version") else None)

        if args.command == "check":
            print_header(f"Version Release - Pre-flight Check ({version})")

            ok, results = preflight_check(version)

            if ok:
                print_success("所有檢查通過！該版本已準備好發布")
                print_info("\n發布指令:", 1)
                print_info(
                    f"uv run .claude/skills/version-release/scripts/version_release.py release",
                    2,
                )
                print_info("\n或預覽:", 1)
                print_info(
                    f"uv run .claude/skills/version-release/scripts/version_release.py release --dry-run",
                    2,
                )
            else:
                print_error("檢查失敗，請修正上述問題")
                return 1

        elif args.command == "update-docs":
            print_header(f"Update Documents ({version})")
            dry_run = args.dry_run if hasattr(args, "dry_run") else False

            if dry_run:
                print_warning("預覽模式 - 不會實際更新檔案")

            ok = update_documents(version, dry_run)

            if not ok:
                print_error("文件更新失敗")
                return 1

        elif args.command == "release":
            dry_run = args.dry_run if hasattr(args, "dry_run") else False
            defer_td = args.defer_td if hasattr(args, "defer_td") else None

            header = f"Version Release Tool - {version}"
            if dry_run:
                header += " (DRY RUN)"

            print_header(header)

            if dry_run:
                print_warning("預覽模式：不會執行實際的 git 操作\n")

            # 如果指定了 --defer-td，先延後 TD
            if defer_td:
                print_section("Step 0: Defer Technical Debts")
                print_info(f"[INFO] 將待處理 TD 延後到版本 {defer_td}...")
                defer_result = defer_technical_debts(version, defer_td, dry_run)

                if not defer_result:
                    print_error("\n技術債務延後失敗，發布已中止")
                    return 1

            # 執行 Pre-flight 檢查
            ok, results = preflight_check(version)

            if not ok and not (args.force if hasattr(args, "force") else False):
                print_error("\nPre-flight 檢查失敗，發布已中止")
                return 1

            # 更新文件
            ok = update_documents(version, dry_run)

            if not ok and not (args.force if hasattr(args, "force") else False):
                print_error("\n文件更新失敗，發布已中止")
                return 1

            # Git 操作
            ok = git_merge_and_push(version, dry_run)

            if not ok:
                print_error("\nGit 操作失敗，發布已中止")
                return 1

            # 標記 todolist 版本狀態 active → completed（避免後續 start 被前版本驗證阻擋）
            print_section("Step: Mark Version Completed")
            todolist_path = get_project_root() / "docs" / "todolist.yaml"
            completed_ok = mark_version_completed(todolist_path, version, dry_run)
            if not completed_ok:
                print_warning(
                    f"todolist.yaml 版本 {version} 標記 completed 失敗（不中止發布，請手動確認）"
                )

            # 自動推進下一個 planned 版本為 active
            print_section("Step: Activate Next Version")
            activate_ok = activate_next_planned_version(todolist_path, version, dry_run)
            if not activate_ok:
                print_warning(
                    "下一版本自動推進失敗（不中止發布，請手動設定 todolist.yaml active 版本）"
                )

            # 打印摘要
            print_summary(version, ok, dry_run)

        else:
            parser.print_help()
            return 1

        return 0

    except ValueError as e:
        print_error(str(e))
        return 1
    except KeyboardInterrupt:
        print_warning("\n操作被中止")
        return 1
    except Exception as e:
        print_error(f"發生未預期的錯誤: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
