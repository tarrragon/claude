#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Homoglyph Guard Hook - PreToolUse (Bash) 形似字混淆對掃描。

職責（事前防護）：
    當 `git commit` 將要執行時，掃描 `git diff --cached` 是否包含已知形似字
    混淆對的誤替換（例：汙 / 污 → 汲）。命中即 exit 2 阻擋並輸出 stderr，
    供 PM / agent 看見並修正後重 commit。

設計依據：
    - PC-150（subagent 形似字 normalize 誤替換，W11-028 案例 33% 錯誤率）
    - 0.18.0-W17-205 Solution（PC-150 防護方案 A）

混淆對清單（可擴充）：
    定義於 `HOMOGLYPH_PAIRS`，每組為 (誤改字, 候選正確字集合)。
    僅當「同一 hunk 內有 +line 含誤改字 且 -line 含候選正確字」才阻擋，
    避免一般正當使用（如「汲取」）誤判。

豁免：
    - commit msg / 命令含 `[skip homoglyph]` 標記
    - merge / revert 等非 `git commit -m` 形式（無 staged diff 比對意義時略過）
    - 非 `git commit` 命令

退出碼：
    - 0：通過 / 非 git commit / 無命中 / 例外（非阻塞原則的反面：本 hook 命中
        必阻擋以保護 normalize 品質；解析失敗則允許避免誤擋）
    - 2：偵測到混淆對誤替換（PreToolUse 阻擋 git commit）
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib import (  # noqa: E402
    setup_hook_logging,
    run_hook_safely,
    read_json_from_stdin,
    get_project_root,
)


EXIT_OK = 0
EXIT_BLOCK = 2

# 形似字混淆對：誤改字 → 同 hunk 內若見以下「正確候選字」即視為誤替換
# 來源：PC-150 / W11-028（汙 U+6C59 / 污 U+6C61 / 汲 U+6C72）
HOMOGLYPH_PAIRS: Dict[str, Set[str]] = {
    "汲": {"汙", "污"},  # 汲(U+6C72 汲取) 被誤用以替換 汙/污
}

SKIP_MARKER = "[skip homoglyph]"


def _is_git_commit_command(command: str) -> bool:
    """判斷是否為新建 commit 命令（排除 amend / log / diff / show / status）。"""
    if "git commit" not in command:
        return False
    for excluded in (
        "git commit --amend",
        "git log",
        "git show",
        "git diff",
        "git status",
    ):
        if excluded in command:
            return False
    return True


def _get_staged_diff(project_dir: Path, logger) -> str:
    """取得 staged diff（含 +/- 行與 hunk 標頭）。"""
    try:
        result = subprocess.run(
            ["git", "--no-optional-locks", "diff", "--cached", "-U0"],
            cwd=str(project_dir),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            logger.info("git diff --cached 失敗（rc=%s）：%s", result.returncode, result.stderr.strip())
            return ""
        return result.stdout
    except Exception as e:
        logger.info("執行 git diff --cached 例外：%s", e)
        return ""


def _scan_diff_for_homoglyph(diff_text: str) -> List[Tuple[str, str, str, str]]:
    """掃描 diff，回傳命中清單 [(file, hunk_header, removed_line, added_line)]。

    判定條件：同一 hunk 內，存在 -line 含正確候選字 X 與 +line 含誤改字 Y，
    且 (Y, X) ∈ HOMOGLYPH_PAIRS。
    """
    hits: List[Tuple[str, str, str, str]] = []
    if not diff_text:
        return hits

    current_file = ""
    hunk_header = ""
    removed_lines: List[str] = []
    added_lines: List[str] = []

    def _flush_hunk() -> None:
        if not removed_lines or not added_lines:
            return
        for added in added_lines:
            for wrong_char, correct_chars in HOMOGLYPH_PAIRS.items():
                if wrong_char not in added:
                    continue
                for removed in removed_lines:
                    if any(c in removed for c in correct_chars):
                        hits.append((current_file, hunk_header, removed, added))
                        break

    for line in diff_text.splitlines():
        if line.startswith("diff --git"):
            _flush_hunk()
            removed_lines, added_lines = [], []
            # diff --git a/path b/path
            m = re.match(r"diff --git a/(\S+) b/(\S+)", line)
            current_file = m.group(2) if m else ""
            hunk_header = ""
            continue
        if line.startswith("@@"):
            _flush_hunk()
            removed_lines, added_lines = [], []
            hunk_header = line
            continue
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+"):
            added_lines.append(line[1:])
        elif line.startswith("-"):
            removed_lines.append(line[1:])

    _flush_hunk()
    return hits


def _format_block_message(hits: List[Tuple[str, str, str, str]]) -> str:
    sample = hits[:5]
    lines = [
        "[Homoglyph Guard] 偵測到形似字混淆對誤替換（PC-150）。",
        "",
        "可能將「汙 / 污」誤改為「汲」（汲取之意，語意完全不同）。",
        "命中示例（最多 5 筆）：",
    ]
    for f, hunk, removed, added in sample:
        lines.append(f"  - file: {f}")
        if hunk:
            lines.append(f"    hunk: {hunk}")
        lines.append(f"    - {removed.strip()[:120]}")
        lines.append(f"    + {added.strip()[:120]}")
    if len(hits) > 5:
        lines.append(f"  ...（共 {len(hits)} 處）")
    lines += [
        "",
        "修正建議：",
        "  1. 檢查上述 + 行，確認是否該為「汙」(U+6C59) 或「污」(U+6C61)，而非「汲」(U+6C72)。",
        "  2. 修正後重新 git add 並 commit。",
        "  3. 如確為合法使用（例：汲取），請於 commit msg 加入 `[skip homoglyph]` 標記。",
        "",
        "防護來源：.claude/error-patterns/process-compliance/PC-150-*.md / 0.18.0-W17-205",
    ]
    return "\n".join(lines)


def main() -> int:
    logger = setup_hook_logging("homoglyph-guard-hook")

    input_data = read_json_from_stdin(logger)
    if input_data is None:
        return EXIT_OK

    if input_data.get("tool_name", "") != "Bash":
        return EXIT_OK

    tool_input = input_data.get("tool_input") or {}
    command = tool_input.get("command", "")

    if not _is_git_commit_command(command):
        logger.debug("非 git commit 命令，跳過")
        return EXIT_OK

    if SKIP_MARKER in command:
        logger.info("命令含 %s，跳過 homoglyph 檢查", SKIP_MARKER)
        return EXIT_OK

    project_dir = get_project_root()
    diff_text = _get_staged_diff(project_dir, logger)
    if not diff_text:
        logger.debug("無 staged diff，跳過")
        return EXIT_OK

    hits = _scan_diff_for_homoglyph(diff_text)
    if not hits:
        logger.info("homoglyph 檢查通過（無命中混淆對）")
        return EXIT_OK

    msg = _format_block_message(hits)
    logger.info("homoglyph 阻擋：命中 %d 處", len(hits))
    # stderr 可見（規則 4）
    sys.stderr.write(msg + "\n")
    return EXIT_BLOCK


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "homoglyph-guard-hook"))
