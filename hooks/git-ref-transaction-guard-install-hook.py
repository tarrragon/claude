#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# ///
"""
Git Ref Transaction Guard Install Hook - SessionStart Hook

安裝（冪等）原生 git `reference-transaction` hook shim，掛載內容掃描見
`.claude/hooks/git-ref-transaction-content-guard.py`（該檔 docstring含
完整選型依據與已知邊界）。

Hook Event: SessionStart

為何需要安裝步驟（而非直接把內容掃描腳本放進 `.git/hooks/`）：
`.git/` 不受版本控制，新 clone / 新 worktree 開啟新 session 時，
`.git/hooks/reference-transaction` 必然不存在，須每次 SessionStart 檢查
並補裝——與 `install-skill-clis.py`（`~/.local/bin/` shim）、
`ticket-reinstall-hook.py` 同一模式：機器產物由 SessionStart 冪等重建，
不依賴版本控制同步。

安裝位置：`git rev-parse --git-common-dir` 解析出的共用 hooks 目錄
（worktree 之間共用同一份，安裝一次即涵蓋所有 worktree，不需逐一安裝）。

冪等 / 所有權判斷（避免覆蓋使用者自訂 hook——outward-facing 且難以復原
的動作，覆蓋前必須能辨識所有權）：
- 檔案不存在 -> 直接寫入。
- 檔案存在且含 SHIM_MARKER -> 視為本機制先前所裝，覆寫更新（shim 本體
  可能隨版本演進而變動）。
- 檔案存在但不含 SHIM_MARKER -> 視為使用者自訂 hook，不覆寫，寫可見
  WARNING（規則 4：Hook 失敗必須可見，此處延伸為「保護未生效」亦須可見，
  避免使用者誤以為 commit-tree/update-ref/merge --continue 等路徑已有
  內容掃描保護）。

Shim 本體極小（純 POSIX sh）：只在 `prepared` 狀態才呼叫實質檢查腳本
（`committed`/`aborted` 狀態的離開碼被 git 忽略，呼叫無意義，見
git-ref-transaction-content-guard.py 檔頭「prepared / committed /
aborted 三態」段落），且以 `git rev-parse --show-toplevel` 於執行當下
即時解析專案路徑（與 install-skill-clis.py 的 shim 設計原則一致：shim
本身幾乎不含邏輯，實際邏輯由目標腳本承載，shim 只負責路徑解析與呼叫）。
"""

from __future__ import annotations

import stat
import subprocess
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib import setup_hook_logging, run_hook_safely  # noqa: E402
from lib.git_utils import get_project_root  # noqa: E402

SHIM_MARKER = "# git-ref-transaction-content-guard shim"
HOOK_FILENAME = "reference-transaction"


def _git_common_dir(project_root: Path) -> Optional[Path]:
    """`git rev-parse --git-common-dir`：worktree 間共用的 hooks 目錄
    所在，非各 worktree 各自的 `.git`。非 git repo 或命令失敗回傳 None。
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    out = result.stdout.strip()
    if not out:
        return None
    return (project_root / out).resolve()


def _shim_body() -> str:
    return f"""#!/bin/sh
{SHIM_MARKER} -- 由 .claude/hooks/git-ref-transaction-guard-install-hook.py 產生，勿手動修改。
if [ "$1" != "prepared" ]; then
  exit 0
fi
root=$(git rev-parse --show-toplevel 2>/dev/null)
target="$root/.claude/hooks/git-ref-transaction-content-guard.py"
if [ -n "$root" ] && [ -f "$target" ]; then
  exec uv run --quiet "$target" "$@"
fi
exit 0
"""


def main() -> int:
    logger = setup_hook_logging("git-ref-transaction-guard-install-hook")
    project_root = get_project_root()

    common_dir = _git_common_dir(project_root)
    if common_dir is None:
        logger.debug("非 git repo 或無法解析 git-common-dir，略過安裝")
        return 0

    hooks_dir = common_dir / "hooks"
    try:
        hooks_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        sys.stderr.write(f"[git-ref-transaction-guard-install] 無法建立 {hooks_dir}：{exc}\n")
        logger.warning("mkdir 失敗：%s", exc)
        return 0

    target = hooks_dir / HOOK_FILENAME
    if target.exists():
        existing = target.read_text(encoding="utf-8", errors="replace")
        if SHIM_MARKER not in existing:
            sys.stderr.write(
                f"[git-ref-transaction-guard-install] 偵測到既有的 {target}"
                "（非本機制所裝），跳過安裝以免覆蓋使用者自訂 hook。"
                "commit-tree/update-ref/merge --continue 等路徑目前無內容掃描"
                "保護，請手動整合本機制或改用其他掛載方式。\n"
            )
            logger.warning("既有 %s 非本機制所裝，跳過安裝", target)
            return 0
        if existing == _shim_body():
            logger.debug("shim 已是最新版本，略過重寫：%s", target)
            return 0

    target.write_text(_shim_body(), encoding="utf-8")
    mode = target.stat().st_mode
    target.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    logger.info("已安裝/更新 reference-transaction shim：%s", target)
    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "git-ref-transaction-guard-install-hook"))
