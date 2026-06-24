#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6.0"]
# ///
"""
WRAP SKILL↔YAML 一致性檢查 Hook — wrap-skill-yaml-consistency-hook.py

觸發時機：
  - PreToolUse(Edit/Write) on:
      .claude/skills/wrap-decision/SKILL.md
      .claude/config/wrap-triggers.yaml

檢查項目（依 W10-055.1 ANA Solution 規格）：
  AC1 Signal orphan：每個 YAML signals[].id 在映射檔 signal_to_skill_triggers 有對應 SKILL 情境（警告）
  AC2 Keyword orphan：每個 YAML keywords[] / failure_detection.keywords[] 在映射檔
                       keyword_to_trigger_category 有 belongs_to 類別（警告）
  AC3 Version 非回退：YAML version 與 SKILL.md footer **Version**: 各自 >= git HEAD 對應值（警告）
  AC4 映射檔存在性：triggers-alignment.yaml 存在且可解析（阻擋 exit 2）

警告 vs 阻擋策略：
  - 警告：exit 0 + stderr（與 wrap-decision-tripwire-hook 的 advisory 模式一致）
  - 阻擋：exit 2（僅限映射檔缺失或無法解析；其他檢查無前提）

唯一觸發來源：.claude/config/wrap-triggers.yaml + 映射檔（W10-052 約束）
觀測性：依 .claude/rules/core/observability-rules.md 規則 1-3（雙通道 stderr + logger）
"""

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

_FRAMEWORK_HOOKS = str(Path(__file__).resolve().parents[3] / "hooks")
sys.path.insert(0, _FRAMEWORK_HOOKS)
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))  # .claude/ — for `from lib import ...`
from lib import (  # noqa: E402
    setup_hook_logging,
    run_hook_safely,
    read_json_from_stdin,
    get_project_root,
    extract_tool_input,
)


# ============================================================================
# 路徑常數
# ============================================================================

YAML_REL_PATH = ".claude/config/wrap-triggers.yaml"
SKILL_REL_PATH = ".claude/skills/wrap-decision/SKILL.md"
ALIGNMENT_REL_PATH = (
    ".claude/skills/wrap-decision/references/project-integration/triggers-alignment.yaml"
)

WATCHED_PATHS = (YAML_REL_PATH, SKILL_REL_PATH)
STDERR_PREFIX = "[WRAP Consistency]"


# ============================================================================
# 公用工具
# ============================================================================

def _normalize_rel(path_str: str, project_root: Path) -> str:
    """將 file_path（可能是絕對或相對）正規化為相對 project_root 的 POSIX 路徑。"""
    if not path_str:
        return ""
    p = Path(path_str)
    try:
        if p.is_absolute():
            rel = p.resolve().relative_to(project_root.resolve())
        else:
            rel = p
    except ValueError:
        return path_str.replace("\\", "/")
    return str(rel).replace("\\", "/")


def _is_watched(file_path: str, project_root: Path) -> Optional[str]:
    """若 file_path 命中 watched paths，返回 watched key；否則 None。"""
    rel = _normalize_rel(file_path, project_root)
    for watched in WATCHED_PATHS:
        if rel == watched or rel.endswith(watched):
            return watched
    return None


def _semver_tuple(v: str) -> Optional[Tuple[int, int, int]]:
    """將 'X.Y.Z' 轉為 (X, Y, Z)，無法解析返回 None。"""
    if not v:
        return None
    m = re.match(r"^\s*(\d+)\.(\d+)\.(\d+)", v.strip())
    if not m:
        return None
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)))


def _git_show(rev: str, rel_path: str, project_root: Path) -> Optional[str]:
    """讀取 git rev:rel_path 內容；失敗返回 None（檔案不存在於該 rev）。"""
    try:
        result = subprocess.run(
            ["git", "show", f"{rev}:{rel_path}"],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return None
        return result.stdout
    except (subprocess.SubprocessError, OSError):
        return None


def _extract_yaml_version(yaml_text: str) -> Optional[str]:
    """從 YAML 文字提取 version 欄位（不需完整 parse，避免格式錯誤時失敗）。"""
    if not yaml_text:
        return None
    m = re.search(r'^version:\s*"?([0-9]+\.[0-9]+\.[0-9]+)"?', yaml_text, re.MULTILINE)
    return m.group(1) if m else None


def _extract_skill_version(skill_text: str) -> Optional[str]:
    """從 SKILL.md 尾段提取 footer **Version**: X.Y.Z（取最後一個出現的）。"""
    if not skill_text:
        return None
    tail = "\n".join(skill_text.splitlines()[-30:])
    matches = re.findall(r"\*\*Version\*\*:\s*([0-9]+\.[0-9]+\.[0-9]+)", tail)
    return matches[-1] if matches else None


# ============================================================================
# 檢查邏輯
# ============================================================================

def load_alignment(project_root: Path, logger) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """載入映射檔。返回 (data, error_message)。error_message 非 None 時應阻擋。"""
    path = project_root / ALIGNMENT_REL_PATH
    if not path.exists():
        msg = f"映射檔不存在：{ALIGNMENT_REL_PATH}（請依映射檔規格新建，見 SKILL.md）"
        logger.error(msg)
        return None, msg
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            msg = f"映射檔頂層非 mapping：{ALIGNMENT_REL_PATH}"
            logger.error(msg)
            return None, msg
        return data, None
    except yaml.YAMLError as e:
        msg = f"映射檔 YAML 解析錯誤：{ALIGNMENT_REL_PATH}: {e}"
        logger.error(msg)
        return None, msg


def load_yaml_config(project_root: Path, logger) -> Optional[Dict[str, Any]]:
    """載入 wrap-triggers.yaml。失敗返回 None（記錄但不阻擋；可能是用戶正在編輯的暫態）。"""
    path = project_root / YAML_REL_PATH
    if not path.exists():
        logger.info(f"YAML 不存在（可能是新建）：{YAML_REL_PATH}")
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except yaml.YAMLError as e:
        logger.info(f"YAML parse 失敗（可能用戶正在編輯）：{e}")
        return None


def check_signal_orphan(
    yaml_data: Dict[str, Any], alignment: Dict[str, Any], logger
) -> List[str]:
    """AC1：每個 YAML signal id 在映射檔有對應 SKILL 情境。返回警告列表。"""
    warnings: List[str] = []
    signals = yaml_data.get("signals", []) if yaml_data else []
    mapping = alignment.get("signal_to_skill_triggers", {}) or {}
    for sig in signals:
        if not isinstance(sig, dict):
            continue
        sid = sig.get("id")
        if not sid:
            continue
        situations = mapping.get(sid)
        if not situations or not isinstance(situations, list) or len(situations) == 0:
            warnings.append(
                f"AC1 Signal orphan：YAML signal '{sid}' 在映射檔 signal_to_skill_triggers 無對應 SKILL 情境"
            )
    logger.info(f"AC1 signal_orphan check: {len(warnings)} warning(s)")
    return warnings


def check_keyword_orphan(
    yaml_data: Dict[str, Any], alignment: Dict[str, Any], logger
) -> List[str]:
    """AC2：每個 YAML keyword 在映射檔有 belongs_to 類別。返回警告列表。"""
    warnings: List[str] = []
    signals = yaml_data.get("signals", []) if yaml_data else []
    kw_map = alignment.get("keyword_to_trigger_category", {}) or {}
    for sig in signals:
        if not isinstance(sig, dict):
            continue
        sid = sig.get("id", "<unknown>")
        # 直接 keywords[]
        for kw in sig.get("keywords", []) or []:
            if kw not in kw_map:
                warnings.append(
                    f"AC2 Keyword orphan：signal '{sid}' keyword '{kw}' 在映射檔 keyword_to_trigger_category 無 belongs_to 類別"
                )
        # failure_detection.keywords[]
        fd = sig.get("failure_detection") or {}
        if isinstance(fd, dict):
            for kw in fd.get("keywords", []) or []:
                if kw not in kw_map:
                    warnings.append(
                        f"AC2 Keyword orphan：signal '{sid}' failure_detection keyword '{kw}' 無 belongs_to 類別"
                    )
    logger.info(f"AC2 keyword_orphan check: {len(warnings)} warning(s)")
    return warnings


def check_version_no_regress(project_root: Path, logger) -> List[str]:
    """AC3：YAML version 與 SKILL footer Version 各自 >= git HEAD 值。返回警告列表。"""
    warnings: List[str] = []

    # YAML version
    yaml_path = project_root / YAML_REL_PATH
    if yaml_path.exists():
        current_yaml = yaml_path.read_text(encoding="utf-8")
        current_v = _extract_yaml_version(current_yaml)
        head_text = _git_show("HEAD", YAML_REL_PATH, project_root)
        head_v = _extract_yaml_version(head_text) if head_text else None
        cur_t = _semver_tuple(current_v) if current_v else None
        head_t = _semver_tuple(head_v) if head_v else None
        if cur_t and head_t and cur_t < head_t:
            warnings.append(
                f"AC3 Version 回退：{YAML_REL_PATH} version {current_v} < HEAD {head_v}"
            )

    # SKILL footer Version
    skill_path = project_root / SKILL_REL_PATH
    if skill_path.exists():
        current_skill = skill_path.read_text(encoding="utf-8")
        current_v = _extract_skill_version(current_skill)
        head_text = _git_show("HEAD", SKILL_REL_PATH, project_root)
        head_v = _extract_skill_version(head_text) if head_text else None
        cur_t = _semver_tuple(current_v) if current_v else None
        head_t = _semver_tuple(head_v) if head_v else None
        if cur_t and head_t and cur_t < head_t:
            warnings.append(
                f"AC3 Version 回退：{SKILL_REL_PATH} footer Version {current_v} < HEAD {head_v}"
            )

    logger.info(f"AC3 version_no_regress check: {len(warnings)} warning(s)")
    return warnings


# ============================================================================
# Hook 入口
# ============================================================================

def main() -> int:
    logger = setup_hook_logging("wrap-skill-yaml-consistency")

    input_data = read_json_from_stdin(logger)
    if input_data is None:
        return 0

    tool_name = input_data.get("tool_name", "")
    if tool_name not in ("Edit", "Write"):
        logger.debug(f"skip non-Edit/Write tool: {tool_name}")
        return 0

    tool_input = extract_tool_input(input_data) or {}
    file_path = tool_input.get("file_path", "")
    if not file_path:
        return 0

    project_root = get_project_root()
    watched = _is_watched(file_path, project_root)
    if not watched:
        return 0

    logger.info(f"watched file edit: {watched}")

    # AC4：映射檔存在 + 可解析（阻擋級）
    alignment, err = load_alignment(project_root, logger)
    if alignment is None:
        sys.stderr.write(f"{STDERR_PREFIX} 映射檔錯誤（阻擋）：{err}\n")
        return 2

    # 載入 YAML（無法解析時跳過後續檢查，但不阻擋）
    yaml_data = load_yaml_config(project_root, logger)

    warnings: List[str] = []
    if yaml_data:
        warnings.extend(check_signal_orphan(yaml_data, alignment, logger))
        warnings.extend(check_keyword_orphan(yaml_data, alignment, logger))
    warnings.extend(check_version_no_regress(project_root, logger))

    if warnings:
        sys.stderr.write(f"{STDERR_PREFIX} 偵測到 {len(warnings)} 項一致性警告：\n")
        for w in warnings:
            sys.stderr.write(f"  - {w}\n")
        sys.stderr.write(
            f"{STDERR_PREFIX} 建議：修正 {ALIGNMENT_REL_PATH} 或當前編輯檔保持雙向同步。\n"
        )
        for w in warnings:
            logger.info(f"warning: {w}")
    else:
        logger.info("所有一致性檢查通過")

    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "wrap-skill-yaml-consistency"))
