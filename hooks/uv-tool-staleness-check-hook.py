#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
uv tool Staleness Check Hook（SessionStart）

掃描全部 uv tool install 安裝的 skill，比對 source vs installed 的
.py 檔 SHA256 集合，提示 stale / missing 並給出修復指令。

支援兩種模組佈局：
  - 目錄模組（ticket / doc / mermaid-ascii / worktree / project-init）：
    source 目錄 vs installed site-packages 子目錄的 rglob hash 集合比對
  - 單檔模組（version-release）：source 單檔 vs installed 單檔的 SHA256 比對
    （single_file=True）

註：branch-worktree-guardian 為非 uv tool（無 CLI entry、不在 uv tool list），
   已自 registry 移除，不再被 staleness 監控（1.0.0-W1-068）。

Hook Event: SessionStart
Exit Code: 永遠 0（不阻塊 session 啟動；錯誤降級為 suppressOutput）

設計理由（與 ticket-reinstall-hook 的差異）：
  - 本 hook 不自動 reinstall（7 skill 同時 reinstall 耗時、失敗風險高）
  - 提供 [OUTDATED] / [MISSING] 提示與一鍵修復指令（uv tool install "<abs path>" --force --reinstall，免 cd、跨 shell 相容）
  - ticket-reinstall-hook 保留為單 skill 自動修復，本 hook 為其他 6 skill 的提示層補充
    （並對 ticket 提供雙重保險）

對應 W11-037.1 ticket。
"""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

# 導入 hook_utils 與共用 lib
sys.path.insert(0, str(Path(__file__).parent))
from hook_utils import setup_hook_logging, run_hook_safely, get_project_root
from lib.uv_tool_utils import (
    compute_file_hashes,
    find_installed_module_dir,
    compare_hash_sets,
    STALENESS_EXCLUDE_DIRS,
)


@dataclass(frozen=True)
class SkillEntry:
    source_subpath: str        # ".claude/skills/ticket"（修復指令的安裝路徑，免 cd）
    module_subpath: str        # 目錄模組：".claude/skills/ticket/ticket_system"（hash 計算來源）
                               # 單檔模組：".claude/skills/version-release/scripts/version_release.py"（單檔來源）
    package_name: str          # "ticket-system"（uv tool 安裝名 / 訊息顯示）
    package_dir_name: str      # 目錄模組：site-packages 子目錄名（"ticket_system"）
                               # 單檔模組：site-packages 下的單檔名（"version_release.py"）
    cli_name: str              # "ticket"（which 查詢用）
    single_file: bool = False  # True：source 與 installed 皆為單一 .py 檔（如 version-release）
                               # False（預設）：目錄模組，沿用「目錄 + rglob」比對模型


SKILLS: Tuple[SkillEntry, ...] = (
    SkillEntry(
        ".claude/skills/ticket",
        ".claude/skills/ticket/ticket_system",
        "ticket-system", "ticket_system", "ticket",
    ),
    SkillEntry(
        ".claude/skills/doc",
        ".claude/skills/doc/doc_system",
        "doc-system", "doc_system", "doc",
    ),
    SkillEntry(
        ".claude/skills/version-release",
        ".claude/skills/version-release/scripts/version_release.py",
        "version-release", "version_release.py", "version-release",
        single_file=True,
    ),
    SkillEntry(
        ".claude/skills/mermaid-ascii",
        ".claude/skills/mermaid-ascii/mermaid_ascii",
        "mermaid-ascii", "mermaid_ascii", "mermaid-ascii",
    ),
    SkillEntry(
        ".claude/skills/worktree",
        ".claude/skills/worktree/scripts",
        "worktree-skill", "scripts", "worktree",
    ),
    SkillEntry(
        ".claude/skills/project-init",
        ".claude/skills/project-init/project_init",
        "project-init", "project_init", "project-init",
    ),
)


@dataclass
class SkillResult:
    skill: SkillEntry
    status: str              # "OK" | "OUTDATED" | "MISSING" | "ERROR"
    detail: Optional[str] = None


def _has_any_py(directory: Path) -> bool:
    try:
        for _ in directory.rglob("*.py"):
            return True
    except Exception:
        return False
    return False


def _compute_single_file_hash(file_path: Path) -> str:
    """計算單一 .py 檔的 SHA256（單檔模組比對用）。"""
    with open(file_path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _check_single_file_skill(
    skill: SkillEntry, project_root: Path, logger
) -> SkillResult:
    """
    檢查單檔模組（如 version-release）的 source vs installed 同步狀態。

    source：project_root / module_subpath（單一 .py 檔）。
    installed：site-packages / package_dir_name（單一 .py 檔）。
    site-packages 透過 find_installed_module_dir(cli, ".", ...) 取得後再拼檔名。
    """
    source_file = project_root / skill.module_subpath
    if not source_file.is_file():
        logger.warning(f"source missing (single_file): {skill.module_subpath}")
        return SkillResult(skill, "ERROR", "source file missing")

    # package_dir_name="." → find_installed_module_dir 回傳 site-packages 本身
    site_packages = find_installed_module_dir(skill.cli_name, ".", logger)
    if site_packages is None:
        return SkillResult(skill, "MISSING")

    installed_file = site_packages / skill.package_dir_name
    if not installed_file.is_file():
        return SkillResult(skill, "MISSING")

    try:
        src_hash = _compute_single_file_hash(source_file)
        inst_hash = _compute_single_file_hash(installed_file)
    except Exception as e:
        # 規則 4：失敗可見（logger 預設雙通道 stderr + file）
        logger.error(f"single-file hash failed for {skill.cli_name}: {e}")
        return SkillResult(skill, "ERROR", str(e))

    if src_hash == inst_hash:
        return SkillResult(skill, "OK")
    return SkillResult(skill, "OUTDATED")


def check_single_skill(skill: SkillEntry, project_root: Path, logger) -> SkillResult:
    """檢查單一 skill 的 source vs installed 同步狀態。"""
    if skill.single_file:
        return _check_single_file_skill(skill, project_root, logger)

    source_dir = project_root / skill.module_subpath
    if not source_dir.exists():
        logger.warning(f"source missing: {skill.module_subpath}")
        return SkillResult(skill, "ERROR", "source dir missing")

    installed_dir = find_installed_module_dir(
        skill.cli_name, skill.package_dir_name, logger
    )
    if installed_dir is None or not _has_any_py(installed_dir):
        return SkillResult(skill, "MISSING")

    try:
        src_hashes = compute_file_hashes(source_dir, STALENESS_EXCLUDE_DIRS)
        inst_hashes = compute_file_hashes(installed_dir, STALENESS_EXCLUDE_DIRS)
    except Exception as e:
        # 規則 4：失敗可見（logger 預設雙通道 stderr + file）
        logger.error(f"hash computation failed for {skill.cli_name}: {e}")
        return SkillResult(skill, "ERROR", str(e))

    is_identical, _diff = compare_hash_sets(src_hashes, inst_hashes)
    if is_identical:
        return SkillResult(skill, "OK")
    return SkillResult(skill, "OUTDATED")


def format_results(results: List[SkillResult], project_root: Path) -> str:
    """組裝 additionalContext 訊息。"""
    ok = [r for r in results if r.status == "OK"]
    outdated = [r for r in results if r.status == "OUTDATED"]
    missing = [r for r in results if r.status == "MISSING"]
    errors = [r for r in results if r.status == "ERROR"]

    # AC5：全部同步簡潔訊息
    if len(ok) == len(SKILLS):
        return f"[UV Tool Staleness] 全部 {len(SKILLS)} 個 uv tool skill 已同步"

    lines: List[str] = []
    for r in outdated:
        lines.append(
            f"[UV Tool Staleness] {r.skill.package_name} [OUTDATED] → "
            f'修復: uv tool install "{project_root / r.skill.source_subpath}" --force --reinstall'
        )
    for r in missing:
        lines.append(
            f"[UV Tool Staleness] {r.skill.package_name} [MISSING] → "
            f'安裝: uv tool install "{project_root / r.skill.source_subpath}"'
        )
    for r in errors:
        lines.append(
            f"[UV Tool Staleness] {r.skill.package_name} [ERROR] {r.detail or 'unknown'}"
        )
    if ok:
        lines.append(f"[UV Tool Staleness] 其他 {len(ok)} skill 已同步")
    return "\n".join(lines)


def main() -> int:
    logger = setup_hook_logging("uv-tool-staleness-check-hook")
    try:
        project_root = get_project_root()
        results = [check_single_skill(skill, project_root, logger) for skill in SKILLS]
        message = format_results(results, project_root)

        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": message,
            },
            "suppressOutput": False,
        }, ensure_ascii=False, indent=2))
        return 0
    except Exception as e:
        # 全局未預期錯誤：log + suppressOutput；永不阻塊（AC7）
        logger.critical(f"hook failed: {e}", exc_info=True)
        print(json.dumps({"suppressOutput": True}, ensure_ascii=False))
        return 0


if __name__ == "__main__":
    exit_code = run_hook_safely(main, "uv-tool-staleness-check")
    sys.exit(exit_code)
