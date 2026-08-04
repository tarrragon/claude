#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
uv tool Ownership Guard Hook（PreToolUse: Bash + SessionStart）

防跨專案全域 uv tool 污染（W3-087 方案 A）。

兩個事件，兩種職責：
  - PreToolUse: Bash — mid-session ownership 防線（見下方「本 hook 的職責」）
  - SessionStart — SKILLS 清單漂移檢查（0.2.1-W3-184）。掃描候選集合與本檔
    SKILLS 常數比對，漏列或冗列時輸出具體差異項。放在 SessionStart 而非
    PreToolUse 的理由見 `_check_skills_drift` docstring（成本差三個數量級）。

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
from lib import (  # noqa: E402
    setup_hook_logging,
    run_hook_safely,
    read_json_from_stdin,
    get_project_root,
)
from lib.uv_tool_utils import is_shimmed_cli  # noqa: E402

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
#
# 納入判準：`.claude/skills/<name>/pyproject.toml` 存在**且**定義 `[project.scripts]`。
# 後半是關鍵——無 `[project.scripts]` 者不產生任何 executable，沒有可被劫持的全域 slot，
# 列入即為幽靈項。校準指令（0.2.1-W3-181）：
#   for d in .claude/skills/*/; do [ -f "$d/pyproject.toml" ] && \
#     grep -q '^\[project.scripts\]' "$d/pyproject.toml" && basename "$d"; done
#   uv tool list
# 兩者實查（2026-07-31）皆為 7 項且成員相同，與本清單一致。
#
# 漏列的代價不對稱：漏列者完全不受保護且無任何告警（ARCH-BAL-003 症狀變體——名單語意為
# 「該保護誰」時，漏列不撞牆），skill-sync 曾因此被他專案副本佔用逾一個月，期間本專案對
# 其 source 的修改全數不生效。故新增有 CLI 入口的 skill 時必須同步此處。
#
# branch-worktree-guardian 曾列於本清單，實查其 pyproject.toml 無 `[project.scripts]`
# （僅 `[project]` 與 `[project.optional-dependencies]`），不符判準且該 executable 從未
# 存在，已於 0.2.1-W3-181 移除。
SKILLS: Tuple[SkillEntry, ...] = (
    SkillEntry(".claude/skills/ticket", "ticket-system", "ticket"),
    SkillEntry(".claude/skills/doc", "doc-system", "doc"),
    SkillEntry(".claude/skills/version-release", "version-release", "version-release"),
    SkillEntry(".claude/skills/mermaid-ascii", "mermaid-ascii", "mermaid-ascii"),
    SkillEntry(".claude/skills/worktree", "worktree-skill", "worktree"),
    SkillEntry(".claude/skills/skill-sync", "skill-sync", "skill-sync"),
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

        # cwd-resolving shim（ARCH-APP-002）：shim 依 cwd 解析源碼、無全域 ownership
        # 概念；reinstall 會把 shim 蓋回。偵測為 shim 即放行，不做 receipt 比對。
        if is_shimmed_cli(exe, logger):
            logger.debug(f"{exe} 為 cwd-resolving shim，放行不 reinstall")
            continue

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


def _scan_candidate_skills(project_root: Path) -> Dict[str, str]:
    """掃描 `.claude/skills/` 得候選集合：有 pyproject.toml 且定義 project.scripts 者。

    回傳 {skill 目錄名: package name}。判準的兩個條件缺一不可——只看 pyproject.toml
    會納入無 CLI 入口者（其 executable 從未存在，列入即幽靈項，0.2.1-W3-181 實證）。
    純文字比對不解析 TOML，與本 hook 其餘部分同一設計選擇（避免額外依賴）。
    """
    candidates: Dict[str, str] = {}
    skills_dir = project_root / ".claude" / "skills"
    if not skills_dir.is_dir():
        return candidates

    for pyproject in sorted(skills_dir.glob("*/pyproject.toml")):
        try:
            text = pyproject.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if "[project.scripts]" not in text:
            continue
        name_match = re.search(r'^name\s*=\s*"([^"]+)"', text, re.MULTILINE)
        if name_match:
            candidates[pyproject.parent.name] = name_match.group(1)
    return candidates


def _check_skills_drift(project_root: Path, logger) -> None:
    """比對 SKILLS 常數與候選集合，漏列或冗列時輸出具體差異項（WARNING 不阻擋）。

    Why：SKILLS 是靜態清單，新增有 CLI 入口的 skill 時若未同步，該 CLI 完全不受
    ownership 保護且無任何告警——名單語意為「該保護誰」時漏列不撞牆（ARCH-BAL-003
    症狀變體）。skill-sync 曾因此被他專案副本佔用逾一個月（0.2.1-W3-181）。

    為何在 SessionStart 而非 PreToolUse 做：本掃描讀 8 個 pyproject.toml 約 0.4 ms，
    PreToolUse 現行 fast-path 約 0.0002 ms，相差三個數量級；該事件跑在每個 Bash
    命令上，設計約束要求非 uv-tool 命令 O(1) 立即返回。SessionStart 每 session 僅
    一次，同樣成本可忽略（0.2.1-W3-184）。
    """
    candidates = _scan_candidate_skills(project_root)
    listed = {s.source_subpath.rsplit("/", 1)[-1] for s in SKILLS}

    missing = sorted(set(candidates) - listed)
    extra = sorted(listed - set(candidates))
    if not missing and not extra:
        logger.info(f"SKILLS 清單與候選集合一致（{len(listed)} 項），無漂移")
        return

    lines = ["=" * 60, "[uv-tool Ownership Guard] SKILLS 清單漂移", "=" * 60]
    if missing:
        lines.append(f"漏列（有 CLI 入口但不受保護）：{', '.join(missing)}")
        lines.append("  後果：該 CLI 的全域 slot 可被他專案副本佔用而無告警")
    if extra:
        lines.append(f"冗列（清單有但無 CLI 入口）：{', '.join(extra)}")
        lines.append("  後果：幽靈項，永遠不會被命令辨識命中")
    lines.append("修復：同步 uv-tool-ownership-guard-hook.py 的 SKILLS 常數")
    lines.append("背景：ARCH-BAL-003 症狀變體 / 0.2.1-W3-181")
    lines.append("=" * 60)
    warning = "\n".join(lines)
    print(warning, file=sys.stderr)
    logger.warning(warning)


def main() -> int:
    logger = setup_hook_logging(HOOK_NAME)

    input_data = read_json_from_stdin(logger)
    if input_data is None:
        return 0

    # SessionStart：跑清單漂移檢查（無 tool_name 欄位，與 PreToolUse 分流）
    if input_data.get("hook_event_name") == "SessionStart":
        _check_skills_drift(get_project_root(), logger)
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
