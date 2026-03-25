#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml"]
# ///

"""
Version Release Tool - 完整版本發布流程自動化工具

功能:
- Pre-flight 檢查：驗證 worklog、技術債務、版本同步
- 文件更新：CHANGELOG、todolist、pubspec.yaml 驗證
- Git 操作：合併、Tag、推送、分支清理
- 預覽模式：--dry-run 查看完整操作流程

使用方式:
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
# Phase 3b 新增：版本同步檢查（Monorepo 三層架構）
# ============================================================================

# 配置檔路徑
VERSION_RELEASE_CONFIG_FILE = ".version-release.yaml"

# 三層版本來源
MONOREPO_VERSION_SOURCE = "docs/todolist.yaml"
MONOREPO_VERSION_KEY = "current_version"
UI_VERSION_SOURCE = "ui/pubspec.yaml"
SERVER_VERSION_SOURCE = "server/go.mod"

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
        "monorepo": {
            "source": MONOREPO_VERSION_SOURCE,
            "key": MONOREPO_VERSION_KEY,
            "semantic_version": True,
            "description": "整個專案的發布版本（用於 Ticket、Wave、發布計劃）"
        },
        "ui": {
            "source": UI_VERSION_SOURCE,
            "key": "version",
            "semantic_version": True,
            "independent": True,
            "description": "Flutter 應用版本（用於 App Store）",
            "sync_policy": SYNC_POLICY_OPTIONAL,
            "sync_recommendation": "保持主版本號一致（如都是 v0.x.0）"
        },
        "server": {
            "source": None,
            "semantic_version": False,
            "independent": False,
            "description": "Go Server 版本由 monorepo 版本決定",
            "sync_policy": SYNC_POLICY_IMPLICIT
        }
    },
    "sync_rules": {
        "on_release": {
            "monorepo": {"required": True},
            "ui": {"required": False},
            "server": {"required": False}
        },
        "on_development": {
            "allow_version_mismatch": True
        },
        "conflict_detection": {
            "ui_ahead_of_monorepo": {
                "severity": SEVERITY_WARNING,
                "message": "UI 版本大於 monorepo，確認是否故意？"
            },
            "ui_behind_monorepo": {
                "severity": SEVERITY_INFO,
                "message": "UI 版本低於 monorepo（正常）"
            }
        }
    },
    "detection": {
        "version_files": [
            {"path": UI_VERSION_SOURCE, "type": "yaml", "key": "version", "context": "Flutter 應用版本"},
            {"path": SERVER_VERSION_SOURCE, "type": "toml", "key": None, "context": "Go module（無版本欄位）"},
            {"path": MONOREPO_VERSION_SOURCE, "type": "yaml", "key": MONOREPO_VERSION_KEY, "context": "權威的 monorepo 版本來源"}
        ]
    },
    "preflight_checks": {
        "version_sync": {
            "enabled": True,
            "fail_on_error": False,
            "warn_on_mismatch": True
        }
    }
}


# 版本檔配置：(相對路徑, 解析方式)
# 按優先順序排列，偵測專案語言
VERSION_FILE_CANDIDATES = [
    ("pubspec.yaml", "yaml"),           # Flutter（根目錄）
    ("ui/pubspec.yaml", "yaml"),        # Flutter（子目錄）
    ("package.json", "json"),           # Node.js
    ("pyproject.toml", "toml"),         # Python（需要 3.10+）
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
    print(f"{Colors.GREEN}✅{Colors.RESET} {message}")


def print_error(message: str):
    """打印錯誤訊息"""
    print(f"{Colors.RED}❌{Colors.RESET} {message}")


def print_warning(message: str):
    """打印警告訊息"""
    print(f"{Colors.YELLOW}⚠️{Colors.RESET} {message}")


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
    """取得專案根目錄"""
    return Path(__file__).parent.parent.parent.parent.parent


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
    version_files = detect_version_files(root)
    for file_path, parser_type in version_files:
        version = extract_version_from_file(file_path, parser_type)
        if version:
            return version

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


def check_worklog_completed(version: str) -> Tuple[bool, List[str]]:
    """檢查工作日誌是否完成"""
    root = get_project_root()
    worklog_dir = root / "docs" / "work-logs"

    errors = []
    major_minor = extract_major_minor(version)

    # 查詢相關的工作日誌
    # 優先檢查版本子目錄（新結構：docs/work-logs/v0.1.1/v0.1.1-main.md）
    worklog_files = []
    version_subdir = worklog_dir / f"v{version}"
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
        # fallback：檢查根目錄（舊結構）
        main_worklog = worklog_dir / f"v{major_minor}.0-main.md"

    if main_worklog.exists():
        try:
            with open(main_worklog, encoding="utf-8") as f:
                content = f.read()

            # 檢查 Phase 完成情況（多 Wave 版本可跳過）
            # 若工作日誌含 "status" 欄位標記為 completed，視為非 TDD 版本，跳過 Phase 檢查
            if re.search(r"^status:\s*completed|^completed$", content, re.MULTILINE):
                pass  # 非 TDD 版本，Phase 檢查跳過
            else:
                phases = {
                    "Phase 0": r"## Phase 0:.*?✅",
                    "Phase 1": r"## Phase 1:.*?✅",
                    "Phase 2": r"## Phase 2:.*?✅",
                    "Phase 3": r"## Phase 3.*?✅",
                    "Phase 4": r"## Phase 4.*?✅",
                }

                for phase_name, pattern in phases.items():
                    if not re.search(pattern, content, re.DOTALL):
                        errors.append(f"{main_worklog.name}: {phase_name} 未標記為完成")
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
    current_parts = tuple(int(p) for p in version.split("."))

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
    """
    config_path = root / VERSION_RELEASE_CONFIG_FILE

    if not config_path.exists():
        return DEFAULT_VERSION_RELEASE_CONFIG

    try:
        with open(config_path, encoding='utf-8') as f:
            config = yaml.safe_load(f)

        if config is None or not isinstance(config, dict):
            return DEFAULT_VERSION_RELEASE_CONFIG

        # 補充缺漏欄位（深層 merge）
        for key in ["versions", "sync_rules", "detection", "preflight_checks"]:
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
# 新增函式 2：get_monorepo_version
# ============================================================================

def get_monorepo_version(root: Path) -> Optional[str]:
    """
    從 docs/todolist.yaml 讀取 L1 monorepo 版本。

    需求：三層版本中 L1 為唯一權威來源
    邊界條件：
    - todolist.yaml 不存在 -> 回傳 None
    - current_version 欄位不存在 -> 回傳 None
    - 版本格式非 X.Y.Z -> 原樣回傳（不強制正規化）

    Args:
        root: 專案根目錄

    Returns:
        版本字串（例如 "0.1.1"）或 None
    """
    todolist_path = root / MONOREPO_VERSION_SOURCE

    if not todolist_path.exists():
        return None

    try:
        with open(todolist_path, encoding='utf-8') as f:
            data = yaml.safe_load(f)

        if not isinstance(data, dict):
            return None

        version = data.get(MONOREPO_VERSION_KEY)

        if version is None:
            return None

        if not isinstance(version, str):
            version = str(version)

        return version

    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.debug(f"讀取 monorepo 版本失敗: {e}")
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
        parts1 = [int(x) for x in v1.split(".")[:3]]
        parts2 = [int(x) for x in v2.split(".")[:3]]

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
# 新增函式 4：Helper — _read_l2_version
# ============================================================================

def _read_l2_version(root: Path, config: dict) -> Tuple[Optional[str], List[dict]]:
    """
    讀取 L2 (UI) 版本。

    Args:
        root: 專案根目錄
        config: 配置字典

    Returns:
        (l2_version or None, messages list)
    """
    messages = []
    l2_version = None
    ui_config = config.get("versions", {}).get("ui", {})
    ui_source = ui_config.get("source")
    l2_path = root / ui_source if ui_source else None

    if not l2_path or not l2_path.exists():
        messages.append({
            "level": SEVERITY_INFO,
            "layer": "l2",
            "text": f"{ui_source} 不存在，跳過 L2 檢查"
        })
        return l2_version, messages

    try:
        with open(l2_path, encoding='utf-8') as f:
            l2_data = yaml.safe_load(f)

        if isinstance(l2_data, dict):
            ui_key = ui_config.get("key", "version")
            l2_version = l2_data.get(ui_key)

            if l2_version and not isinstance(l2_version, str):
                l2_version = str(l2_version)

    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.debug(f"讀取 {ui_source} 失敗: {e}")
        messages.append({
            "level": SEVERITY_INFO,
            "layer": "l2",
            "text": f"讀取 {ui_source} 失敗，跳過 L2 檢查"
        })

    return l2_version, messages


# ============================================================================
# 新增函式 4.1：Helper — _compare_l2_version
# ============================================================================

def _compare_l2_version(l1_version: str, l2_version: str, config: dict) -> List[dict]:
    """
    比對 L2 版本與 L1 版本，生成訊息。

    Args:
        l1_version: L1 monorepo 版本
        l2_version: L2 UI 版本（含 build number）
        config: 配置字典

    Returns:
        訊息清單
    """
    messages = []

    # 去除 build number（"1.0.0+1" → "1.0.0"）
    l2_main = l2_version.split("+")[0]
    cmp_result = compare_semantic_versions(l2_main, l1_version)

    conflict_cfg = config.get("sync_rules", {}).get("conflict_detection", {})

    if cmp_result > 0:  # L2 > L1
        severity = conflict_cfg.get("ui_ahead_of_monorepo", {}).get("severity", SEVERITY_WARNING)
        messages.append({
            "level": severity,
            "layer": "l2",
            "text": "UI 版本大於 monorepo，確認是否故意？"
        })
    elif cmp_result < 0:  # L2 < L1
        severity = conflict_cfg.get("ui_behind_monorepo", {}).get("severity", SEVERITY_INFO)
        messages.append({
            "level": severity,
            "layer": "l2",
            "text": "UI 版本低於 monorepo（正常）"
        })
    else:  # L2 = L1
        messages.append({
            "level": SEVERITY_SUCCESS,
            "layer": "l2",
            "text": "UI 版本與 monorepo 版本一致"
        })

    return messages


# ============================================================================
# 新增函式 4.2：Helper — _check_l3_status
# ============================================================================

def _check_l3_status(config: dict) -> Tuple[bool, List[dict]]:
    """
    檢查 L3 (Server) 版本狀態。

    Args:
        config: 配置字典

    Returns:
        (l3_has_version, messages list)
    """
    messages = []
    server_config = config.get("versions", {}).get("server", {})
    server_source = server_config.get("source")
    l3_has_version = server_source is not None

    if server_source is None:
        messages.append({
            "level": SEVERITY_INFO,
            "layer": "l3",
            "text": "server/go.mod 無版本欄位，由 monorepo 版本決定"
        })

    return l3_has_version, messages


# ============================================================================
# 新增函式 4：check_monorepo_version_sync
# ============================================================================

def check_monorepo_version_sync(version: str, config: dict) -> dict:
    """
    執行三層版本同步檢查。

    需求：功能 2 三層版本對比
    邊界條件：
    - L2 版本不存在 -> 跳過 L2 檢查
    - L3 source 為 null -> 顯示 Server 版本由 monorepo 決定
    - L2 版本大於 L1 -> 輸出 warning（severity: "warning"）
    - L2 版本小於 L1 -> 輸出 info（severity: "info"）

    Args:
        version: L1 monorepo 版本（例如 "0.1.1"）
        config: load_version_release_config() 回傳的配置字典

    Returns:
        {
            "passed": bool,
            "l1_version": str,
            "l2_version": Optional[str],
            "l3_has_version": bool,
            "messages": List[dict],
            "summary": str
        }
    """
    messages = []

    # [檢查 L1]
    if not version:
        messages.append({
            "level": SEVERITY_ERROR,
            "layer": "l1",
            "text": "L1 monorepo 版本為空"
        })
        return {
            "passed": False,
            "l1_version": version,
            "l2_version": None,
            "l3_has_version": False,
            "messages": messages,
            "summary": "失敗（L1 monorepo 版本為空）"
        }

    # [檢查 L2]
    root = get_project_root()
    l2_version, l2_messages = _read_l2_version(root, config)
    messages.extend(l2_messages)

    if l2_version:
        l2_cmp_messages = _compare_l2_version(version, l2_version, config)
        messages.extend(l2_cmp_messages)

    # [檢查 L3]
    l3_has_version, l3_messages = _check_l3_status(config)
    messages.extend(l3_messages)

    # [最終判定]
    has_error = any(m["level"] == SEVERITY_ERROR for m in messages)
    passed = not has_error
    has_warning = any(m["level"] == SEVERITY_WARNING for m in messages)

    if passed and not has_warning:
        summary = "通過（版本策略符合 monorepo 三層架構）"
    elif passed and has_warning:
        summary = "通過（附警告）"
    else:
        summary = "失敗（version 檢查未通過）"

    return {
        "passed": passed,
        "l1_version": version,
        "l2_version": l2_version,
        "l3_has_version": l3_has_version,
        "messages": messages,
        "summary": summary
    }


# ============================================================================
# 新增函式 5：print_version_sync_report
# ============================================================================

def print_version_sync_report(sync_result: dict):
    """
    輸出三層版本對比報告（樹狀結構）。

    需求：功能 2 CLI 輸出格式
    邊界條件：
    - 無 L2 版本 -> 顯示 "ui/pubspec.yaml: 未偵測到"
    - 無 L3 版本 -> 顯示 "server/go.mod: 無版本欄位（正常）"

    Args:
        sync_result: check_monorepo_version_sync() 的回傳值

    Side effects:
        打印到 stdout
    """
    width = 60
    print(f"\n{Colors.BOLD}{'━' * width}{Colors.RESET}")
    print(f"{Colors.BOLD}版本同步檢查（Monorepo 三層架構）{Colors.RESET}")
    print(f"{Colors.BOLD}{'━' * width}{Colors.RESET}\n")

    # [打印 L1]
    l1 = sync_result.get("l1_version", "未知")
    print(f"L1 monorepo 版本: {l1} (docs/todolist.yaml)")
    print("|")

    # [打印 L2]
    l2 = sync_result.get("l2_version")
    if l2 is None:
        print("|-- L2 ui/pubspec.yaml: 未偵測到")
    else:
        print(f"|-- L2 ui/pubspec.yaml: {l2}")
        # 輸出 L2 相關的訊息（基於 layer 欄位）
        for msg in sync_result.get("messages", []):
            if msg.get("layer") == "l2":
                level_marker = f"[{msg['level'].upper()}]" if msg['level'] != SEVERITY_SUCCESS else "[OK]"
                print(f"|   +-- {level_marker} {msg['text']}")

    print("|")

    # [打印 L3]
    l3_has = sync_result.get("l3_has_version", False)
    if not l3_has:
        print("+-- L3 server/go.mod: 無版本欄位（正常）")
        print("    理由：Go module 無自身版本，由 monorepo 版本決定")

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


def check_version_sync(version: str) -> Tuple[bool, List[str]]:
    """檢查版本號同步（包括 Monorepo 三層架構）"""
    root = get_project_root()
    errors = []

    # [新增] 檢查 Monorepo 三層版本（優先於傳統檢查）
    print_info("  檢查 Monorepo 版本同步...")
    config = load_version_release_config(root)
    sync_result = check_monorepo_version_sync(version, config)
    print_version_sync_report(sync_result)

    # 偵測版本檔案（動態，語言感知）
    version_files = detect_version_files(root)

    if version_files:
        # 檢查所有偵測到的版本檔（僅警告，不阻塞）
        # Monorepo 場景：專案管理版本與子專案版本可能獨立管理
        # 優化：複用 sync_result 中已讀取的 L2 版本，避免重複讀取 ui/pubspec.yaml
        l2_version = sync_result.get("l2_version")
        ui_pubspec_path = root / "ui" / "pubspec.yaml"

        for file_path, parser_type in version_files:
            try:
                # 優化：若是 ui/pubspec.yaml 且已有 L2 版本，複用已讀版本
                if file_path == ui_pubspec_path and l2_version is not None:
                    file_version = l2_version
                else:
                    file_version = extract_version_from_file(file_path, parser_type)

                if file_version:
                    if file_version != version:
                        print_warning(
                            f"{file_path.name} 版本不匹配: {file_version} vs {version}"
                            "（monorepo 場景下此為預期行為）"
                        )
                    else:
                        print_success(f"{file_path.name} 版本一致: {version}")
                else:
                    print_warning(f"{file_path.name} 找不到 version 欄位")
            except Exception as e:
                print_warning(f"讀取 {file_path.name} 失敗: {e}")
    else:
        # 沒有找到版本檔（純規格版本或其他情況）
        print_warning("未偵測到版本檔案（pubspec.yaml/package.json/pyproject.toml）")
        print_info("  此可能是純規格版本或其他非程式碼專案")

    # 檢查當前分支（僅警告，不同專案可能有不同分支命名慣例）
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
    print_info("✓ 檢查工作日誌完成度...")
    wl_ok, wl_errors = check_worklog_completed(version)
    results["worklog"] = (wl_ok, wl_errors)

    if wl_ok:
        print_success("Worklog 目標達成")
    else:
        for error in wl_errors:
            print_error(error)

    # 1.2 檢查技術債務狀態（新增：詳細掃描）
    print_info("✓ 檢查技術債務處理狀態...")
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
    print_info("✓ 驗證技術債務分類...")
    td_ok, td_errors = check_technical_debt(version)
    results["tech_debt"] = (td_ok, td_errors)

    if not td_ok:
        for error in td_errors:
            print_error(error)

    # 1.4 檢查前版本未完成任務
    print_info("✓ 檢查前版本未完成任務...")
    pv_ok, pv_errors = check_previous_versions_completed(version)
    results["previous_versions"] = (pv_ok, pv_errors)

    if pv_ok:
        print_success("前版本任務已完成")
    else:
        for error in pv_errors:
            print_error(error)

    # 1.5 檢查版本同步
    print_info("✓ 檢查版本同步...")
    vs_ok, vs_errors = check_version_sync(version)
    results["version_sync"] = (vs_ok, vs_errors)

    if vs_ok:
        print_success("版本同步 ✅")
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

**✅ UC-XX 功能名稱 - TDD 四階段完成**

### Added
- 新增功能項目

### Changed
- 變更項目

### Fixed
- 修復項目

---

"""

        # 幂等性檢查：若版本已存在則跳過
        if f"## [{version}]" in changelog_content:
            print_warning(f"CHANGELOG.md 已包含 v{version} 條目，跳過插入")
            return True

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
    version_files = detect_version_files(root)

    if not version_files:
        print_warning("未偵測到版本檔案（pubspec.yaml/package.json/pyproject.toml）")
        print_info("  此可能是純規格版本", 1)
        return True  # 不阻塞發布流程

    # Monorepo 場景：版本不匹配為警告，不阻塞發布
    for file_path, parser_type in version_files:
        try:
            file_version = extract_version_from_file(file_path, parser_type)
            if file_version:
                if file_version == version:
                    print_success(f"{file_path.name} 版本正確: {version}")
                else:
                    print_warning(
                        f"{file_path.name} 版本不匹配: {file_version} vs {version}"
                        "（monorepo 場景下此為預期行為）"
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
    print_info("📝 更新 docs/todolist.yaml")
    if not update_todolist(version, dry_run):
        all_ok = False

    # 2.2 更新 CHANGELOG
    print_info("📝 更新 CHANGELOG.md")
    if not update_changelog(version, dry_run):
        all_ok = False

    # 2.3 驗證版本檔
    print_info("✅ 確認版本號")
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
                print_info("🔄 [預覽] 將提交檔案變更", 2)
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
    tag_name = f"v{version}-final"

    try:
        # 3.1 提交變更
        print_info("🔄 提交所有變更")
        if not commit_changes(version, dry_run):
            return False

        # 3.2 切換到 main 分支
        print_info("🔀 切換到 main 分支")
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
        print_info("📥 拉取最新 main")
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

        # 3.4 合併 feature 分支
        print_info("🔀 合併 feature 分支")
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
        print_info(f"🏷️ 建立 Tag: {tag_name}")
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
        print_info("📤 推送到遠端")
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

        # 3.7 刪除 feature 分支
        print_info("🗑️ 清理 feature 分支")
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
            print_info("\n📊 發布統計:")
            print_info("- 檔案更新: 2", 1)
            print_info("- 合併提交: 1", 1)
            print_info("- Tag 建立: 1", 1)
            print_info("- 分支清理: 2", 1)
            print_info("\n🎉 版本已推送到 main 分支", 1)
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
                print_info(f"📋 將待處理 TD 延後到版本 {defer_td}...")
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
