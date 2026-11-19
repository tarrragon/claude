#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6.0"]
# ///
"""
WRAP SKILL↔YAML 一致性檢查 Hook — wrap-skill-yaml-consistency-hook.py

觸發時機：
  - PreToolUse(Edit/Write) on:
      .claude/skills/wrap-decision/SKILL.md（portability-allow: 本 skill 自我引用，consumer 共通安裝位置）
      .claude/config/wrap-triggers.yaml（portability-allow: 此 skill 對消費端環境的依賴，沿用時需提供對應設定檔）

檢查項目：
  AC3 Version 非回退：YAML version 與 SKILL.md footer **Version**: 各自 >= git HEAD 對應值（警告）

策略：
  - 警告：exit 0 + stderr（與 wrap-decision-tripwire-hook 的 advisory 模式一致）
  - 檢查例外：stderr + logger.error 後放行 exit 0
  - 不讀取映射檔（AC1/AC2/AC4 已移除）

唯一觸發來源：.claude/config/wrap-triggers.yaml（portability-allow: 同上依賴）
觀測性：依 .claude/rules/core/observability-rules.md 規則 1-3（雙通道 stderr + logger）（portability-allow: 架構性橋接至框架 auto-load 規則）
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
try:
    from lib import (  # noqa: E402
        setup_hook_logging,
        run_hook_safely,
        read_json_from_stdin,
        get_project_root,
        extract_tool_input,
        emit_model_reminder,
    )
    _LIB_AVAILABLE = True
except ImportError:
    # 消費端未提供 .claude/lib/ 時優雅降級（portability-allow: 選用性依賴，
    # 缺件優雅降級，非可攜性違規）：main() 開頭直接印出 [WARNING] 並
    # return 0（見 main() 開頭的降級分支）。
    _LIB_AVAILABLE = False


# ============================================================================
# 路徑常數
# ============================================================================

YAML_REL_PATH = ".claude/config/wrap-triggers.yaml"
SKILL_REL_PATH = ".claude/skills/wrap-decision/SKILL.md"  # portability-allow: hook 綁專案根目錄，隨專案部署、不隨 skill 搬遷

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
    if not _LIB_AVAILABLE:
        sys.stderr.write(
            f"{STDERR_PREFIX} 未執行：找不到 .claude/lib/，此為消費端需自行"
            "提供的框架共用模組（一致性檢查功能停用，不影響其他操作）。\n"
        )
        return 0
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

    # 檢查例外時放行（advisory hook，不因自身故障阻擋編輯），stderr + logger 雙通道
    try:
        warnings: List[str] = check_version_no_regress(project_root, logger)
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"{STDERR_PREFIX} check_version_no_regress 例外（放行）：{e}\n")
        logger.error(f"check_version_no_regress failed: {e}", exc_info=True)
        return 0

    if warnings:
        sys.stderr.write(f"{STDERR_PREFIX} 偵測到 {len(warnings)} 項一致性警告：\n")
        for w in warnings:
            sys.stderr.write(f"  - {w}\n")
        sys.stderr.write(
            f"{STDERR_PREFIX} 建議：修正 version 使其不低於 git HEAD。\n"
        )
        for w in warnings:
            logger.info(f"warning: {w}")
    else:
        logger.info("所有一致性檢查通過")

    return 0


if __name__ == "__main__":
    if _LIB_AVAILABLE:
        sys.exit(run_hook_safely(main, "wrap-skill-yaml-consistency"))
    else:
        sys.exit(main())
