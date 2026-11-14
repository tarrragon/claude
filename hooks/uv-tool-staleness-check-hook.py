#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""
uv tool Staleness Check Hook（SessionStart）

掃描 skill CLI 的安裝狀態：shim（cwd-resolving，ARCH-APP-002）視同已同步；
仍以 uv tool 安裝的副本，比對 source vs installed 的 .py 檔 SHA256 集合，
提示 stale / missing 並給出修復指令。

存在必要（2026-11-13 評估）：SessionStart 安裝 shim 時，若 `~/.local/bin/<cli>`
已是 uv tool 安裝（symlink）就保留原檔不覆寫，這類副本不隨原始碼更新，仍需本
hook 偵測。修復指令一律引導改用 shim（先 uv tool uninstall，再執行
install-skill-clis.py），不再建議重裝 uv tool 副本。

支援兩種模組佈局：
  - 目錄模組（ticket / doc / mermaid-ascii / worktree / skill-sync /
    project-init）：source 目錄 vs installed site-packages 子目錄的
    rglob hash 集合比對
  - 單檔模組（version-release）：source 單檔 vs installed 單檔的 SHA256 比對
    （single_file=True）

註：branch-worktree-guardian 為非 uv tool（無 CLI entry、不在 uv tool list），
   已自 registry 移除，不再被 staleness 監控。

Hook Event: SessionStart
Exit Code: 永遠 0（不阻塊 session 啟動；錯誤降級為 suppressOutput）

設計理由（與 ticket-reinstall-hook 的差異）：
  - 本 hook 不自動 reinstall（7 skill 同時 reinstall 耗時、失敗風險高）
  - 提供 [OUTDATED] / [MISSING] 提示與修復指令（絕對路徑，免 cd、跨 shell 相容）：
    OUTDATED 為 `uv tool uninstall <package>` 後執行 install-skill-clis.py；
    MISSING 為直接執行 install-skill-clis.py
  - ticket-reinstall-hook 保留為單 skill 自動修復，本 hook 為其他 6 skill 的提示層補充
    （並對 ticket 提供雙重保險）
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
sys.path.insert(0, str(Path(__file__).parent.parent))
from lib import setup_hook_logging, run_hook_safely, get_project_root
from lib.uv_tool_utils import (
    compute_file_hashes,
    find_installed_module_dir,
    compare_hash_sets,
    is_shimmed_cli,
    STALENESS_EXCLUDE_DIRS,
)


INSTALL_SKILL_CLIS_SUBPATH = Path(".claude") / "scripts" / "install-skill-clis.py"


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
        ".claude/skills/skill-sync",
        ".claude/skills/skill-sync/skill_sync",
        "skill-sync", "skill_sync", "skill-sync",
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
    status: str              # "OK" | "OUTDATED" | "MISSING" | "ERROR" | "SHIMMED"
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
    # cwd-resolving shim（ARCH-APP-002）：shim CLI 無 site-packages 安裝，
    # 不適用 SHA 比對；回 SHIMMED 讓 reporting 略過（不報 OUTDATED/MISSING）。
    if is_shimmed_cli(skill.cli_name, logger):
        return SkillResult(skill, "SHIMMED")

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
    # shim CLI（ARCH-APP-002）視同已同步：不報 OUTDATED/MISSING，僅併入「同步」計數。
    shimmed = [r for r in results if r.status == "SHIMMED"]
    synced = ok + shimmed

    # AC5：全部同步簡潔訊息（OK 與 SHIMMED 皆視為同步）
    if len(synced) == len(SKILLS):
        return f"[UV Tool Staleness] 全部 {len(SKILLS)} 個 uv tool skill 已同步"

    install_shim = f'python3 "{project_root / INSTALL_SKILL_CLIS_SUBPATH}"'
    lines: List[str] = []
    for r in outdated:
        lines.append(
            f"[UV Tool Staleness] {r.skill.package_name} [OUTDATED] → "
            # 兩步分開寫、不用 &&：PowerShell 5.1 無 && chain operator
            f"改用 shim: 先 uv tool uninstall {r.skill.package_name}，再 {install_shim}"
        )
    for r in missing:
        lines.append(
            f"[UV Tool Staleness] {r.skill.package_name} [MISSING] → "
            f"安裝 shim: {install_shim}"
        )
    for r in errors:
        lines.append(
            f"[UV Tool Staleness] {r.skill.package_name} [ERROR] {r.detail or 'unknown'}"
        )
    if synced:
        lines.append(f"[UV Tool Staleness] 其他 {len(synced)} skill 已同步")
    return "\n".join(lines)


def main() -> int:
    logger = setup_hook_logging("uv-tool-staleness-check-hook")
    try:
        project_root = get_project_root()
        results = [check_single_skill(skill, project_root, logger) for skill in SKILLS]
        message = format_results(results, project_root)
        # 營運日誌記錄本次回報內容（additionalContext 不落檔，事後無從查證曾提示什麼）
        logger.info("staleness 結果: %s", " | ".join(message.splitlines()))

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
