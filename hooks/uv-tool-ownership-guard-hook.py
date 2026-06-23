#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
uv tool Ownership Guard Hook（PreToolUse: Bash）

防跨專案全域 uv tool 污染（W3-087 方案 A）。

問題背景：
  `uv tool install` 以 package name 為全域唯一 key（裝至
  ~/.local/share/uv/tools/<package>/，executable 連 ~/.local/bin/<exe>）。
  多專案的 skill 副本 package name 相同（ticket-system 等）→ 共用單一全域
  slot → 任一專案 reinstall 即覆蓋全域 executable，最後 reinstall 者勝。
  本專案的 source 修復會被其他專案的並行 session / hook 靜默覆蓋。
  SessionStart hook（ticket-reinstall / uv-tool-staleness）僅在啟動時對齊，
  無法防 mid-session 被並行專案覆蓋。

本 hook 的職責（mid-session 防線）：
  在每個 Bash 命令執行前，偵測命令是否呼叫本專案的 uv-tool skill CLI；
  若是，讀該工具 receipt 的 directory 欄位，若 ≠ 當前專案對應 source 目錄
  （ownership mismatch），先 reinstall 自當前專案再放行命令。

與既有 hook 的關係（不重複 / 不衝突）：
  - ticket-reinstall-hook（SessionStart, 單 skill, SHA 比對自動修）
  - uv-tool-staleness-check-hook（SessionStart, 7 skill, 僅提示）
  上兩者為啟動期防線；本 hook event 不同（PreToolUse）、判據不同
  （ownership directory 比對而非 SHA 比對），形成 mid-session 補強。

設計約束：
  - 開銷最小化：PreToolUse 跑在每個 Bash 上，非 uv-tool 命令必須 O(1)
    fast-path 立即 exit 0（先以 exe 名字串比對，命中才做 receipt IO）。
  - 無限迴圈防護：reinstall 命令（含 "uv tool install" 字面）一律放行，
    不再觸發 ownership 檢查。
  - 命令辨識：涵蓋 `ticket ...`、`(cd x && ticket ...)`、`A && doc ...`、
    `A; B`、`A | B` 等以 shell 連接符切段後各段首 token。
  - 可觀測性（quality-baseline 規則 4）：reinstall 動作雙通道（stderr + log）。
  - Exit code 永遠 0：不阻塊使用者命令；reinstall 失敗僅 warn。

對應 ticket 0.19.0-W3-090（source ANA 0.19.0-W3-087 方案 A）。
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# 導入 hook_utils（package 形式）
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))
from hook_utils import (  # noqa: E402
    setup_hook_logging,
    run_hook_safely,
    read_json_from_stdin,
    get_project_root,
)

HOOK_NAME = "uv-tool-ownership-guard"

# reinstall 子程序逾時（秒）
REINSTALL_TIMEOUT = 60


@dataclass(frozen=True)
class SkillEntry:
    """uv-tool skill 的對照資訊（與 uv-tool-staleness-check-hook 同源）。"""

    source_subpath: str  # ".claude/skills/ticket"（reinstall cwd 與 ownership 比對目標）
    package_name: str  # "ticket-system"（uv tool 安裝名 / receipt 目錄名）
    cli_name: str  # "ticket"（命令首 token 比對用）


# 本專案 7 個 uv-tool skill。cli_name 為命令辨識依據，package_name 為 receipt 定位依據。
SKILLS: Tuple[SkillEntry, ...] = (
    SkillEntry(".claude/skills/ticket", "ticket-system", "ticket"),
    SkillEntry(".claude/skills/doc", "doc-system", "doc"),
    SkillEntry(".claude/skills/version-release", "version-release", "version-release"),
    SkillEntry(".claude/skills/mermaid-ascii", "mermaid-ascii", "mermaid-ascii"),
    SkillEntry(".claude/skills/worktree", "worktree-skill", "worktree"),
    SkillEntry(
        ".claude/skills/branch-worktree-guardian",
        "branch-worktree-guardian",
        "branch-worktree-guardian",
    ),
    SkillEntry(".claude/skills/project-init", "project-init", "project-init"),
)

# cli_name -> SkillEntry，供命令辨識後快速查表
EXE_TO_SKILL: Dict[str, SkillEntry] = {s.cli_name: s for s in SKILLS}
# fast-path 用：所有受管理 exe 名集合
EXE_SET = frozenset(EXE_TO_SKILL.keys())

# 以 shell 連接符 / 分組符切段，取每段首 token。涵蓋 && || ; | ( ) 與換行。
_SEGMENT_SPLIT = re.compile(r"&&|\|\||[;\n|()]")


def _extract_invoked_exes(command: str) -> List[str]:
    """
    從 Bash 命令字串解析出所有「命令首 token」中屬於受管理 exe 的名稱。

    處理形式：
      "ticket track list"            -> ["ticket"]
      "(cd x && ticket track list)"  -> ["ticket"]（cd 段首 token 為 cd，被忽略）
      "doc build && ticket complete" -> ["doc", "ticket"]
      "echo hi | ticket list"        -> ["ticket"]

    僅做廉價字串切割，不做完整 shell 語法解析（避免開銷與過度設計）。
    """
    found: List[str] = []
    for segment in _SEGMENT_SPLIT.split(command):
        segment = segment.strip()
        if not segment:
            continue
        first_token = segment.split(maxsplit=1)[0]
        if first_token in EXE_SET and first_token not in found:
            found.append(first_token)
    return found


def _read_receipt_directory(package_name: str, logger) -> Optional[str]:
    """
    讀 ~/.local/share/uv/tools/<package>/uv-receipt.toml 的
    requirements[].directory 欄位（installed source 的 origin 目錄）。

    不依賴 toml 解析模組（保 py3.10 可攜性），以正則抓 directory 字串。

    Returns:
        directory 字串，或 None（receipt 不存在 / 無 directory 欄位 / 讀取失敗）。
    """
    receipt_path = (
        Path.home() / ".local" / "share" / "uv" / "tools" / package_name / "uv-receipt.toml"
    )
    if not receipt_path.exists():
        logger.debug(f"receipt 不存在: {receipt_path}")
        return None
    try:
        content = receipt_path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        logger.debug(f"讀 receipt 失敗 {receipt_path}: {e}")
        return None
    # 形如: { name = "ticket-system", directory = "/abs/path/.claude/skills/ticket" }
    match = re.search(r'directory\s*=\s*"([^"]+)"', content)
    if not match:
        logger.debug(f"receipt 無 directory 欄位: {receipt_path}")
        return None
    return match.group(1)


def _expected_source_dir(project_root: Path, skill: SkillEntry) -> Path:
    """當前專案下該 skill 的 source 目錄（ownership 比對的期望值）。"""
    return (project_root / skill.source_subpath).resolve()


def _is_owned_by_project(
    receipt_directory: str, expected_dir: Path
) -> bool:
    """receipt directory 解析後是否等於當前專案 source 目錄。"""
    try:
        return Path(receipt_directory).resolve() == expected_dir
    except Exception:
        return False


def _reinstall(skill: SkillEntry, project_root: Path, logger) -> bool:
    """
    自當前專案 reinstall 該 skill：在 source 目錄執行
    `uv tool install . --reinstall`。

    雙通道可觀測性：log + stderr（quality-baseline 規則 4）。

    Returns:
        True 表示 reinstall 成功；False 表示失敗（僅 warn，不阻塊命令）。
    """
    source_dir = project_root / skill.source_subpath
    if not source_dir.exists():
        logger.info(f"source 目錄不存在，跳過 reinstall: {source_dir}")
        return False

    msg = (
        f"[OwnershipGuard] {skill.cli_name} 全域工具非當前專案所有，"
        f"reinstall 自 {source_dir}"
    )
    logger.info(msg)
    sys.stderr.write(msg + "\n")

    try:
        result = subprocess.run(
            ["uv", "tool", "install", ".", "--reinstall"],
            cwd=str(source_dir),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=REINSTALL_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        warn = f"[OwnershipGuard] reinstall {skill.cli_name} 逾時（{REINSTALL_TIMEOUT}s）"
        logger.info(warn)
        sys.stderr.write(warn + "\n")
        return False
    except Exception as e:
        warn = f"[OwnershipGuard] reinstall {skill.cli_name} 失敗: {e}"
        logger.info(warn)
        sys.stderr.write(warn + "\n")
        return False

    if result.returncode != 0:
        warn = (
            f"[OwnershipGuard] reinstall {skill.cli_name} 非零退出"
            f"（code={result.returncode}）: {result.stderr.strip()[:200]}"
        )
        logger.info(warn)
        sys.stderr.write(warn + "\n")
        return False

    logger.info(f"[OwnershipGuard] reinstall {skill.cli_name} 成功")
    return True


def _guard_command(command: str, project_root: Path, logger) -> None:
    """
    對單一 Bash 命令執行 ownership guard。

    fast-path：命令字串不含任何受管理 exe 名 → O(命令長度) 立即返回。
    迴圈防護：命令含 "uv tool install" 字面 → 放行（reinstall 命令本身）。
    """
    # 無限迴圈防護：reinstall 命令不再觸發檢查
    if "uv tool install" in command:
        logger.debug("命令含 'uv tool install'，放行（迴圈防護）")
        return

    # fast-path：先廉價子字串掃描，無任何 exe 名即返回（避免 regex 切割開銷）
    if not any(exe in command for exe in EXE_SET):
        return

    invoked = _extract_invoked_exes(command)
    if not invoked:
        return

    for exe in invoked:
        skill = EXE_TO_SKILL[exe]
        receipt_dir = _read_receipt_directory(skill.package_name, logger)
        expected = _expected_source_dir(project_root, skill)

        if receipt_dir is not None and _is_owned_by_project(receipt_dir, expected):
            logger.debug(f"{exe} ownership 正確（{expected}），不動作")
            continue

        # mismatch 或 receipt 缺失 → reinstall 自當前專案
        logger.info(
            f"{exe} ownership mismatch："
            f"receipt={receipt_dir} expected={expected}"
        )
        _reinstall(skill, project_root, logger)


def main() -> int:
    logger = setup_hook_logging(HOOK_NAME)

    input_data = read_json_from_stdin(logger)
    if input_data is None:
        return 0

    if input_data.get("tool_name", "") != "Bash":
        return 0

    tool_input = input_data.get("tool_input") or {}
    command = tool_input.get("command", "")
    if not command:
        return 0

    project_root = get_project_root()
    _guard_command(command, project_root, logger)
    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, HOOK_NAME))
