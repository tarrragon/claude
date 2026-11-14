#!/usr/bin/env python3
"""
settings.json 語法閘門（git pre-commit 呼叫）

staged 的 `.claude/settings.json` 無法以 JSON 載入時阻擋 commit，並指出錯誤的
行列；範圍只限語法，不檢查 hook 註冊內容。

Why：settings.json 一個逗號錯誤就讓全部 Claude Code hook 不載入，失效本身沒有
任何訊號。CC hook 依賴 settings.json 載入，無法自己守住它，所以閘門放在 git 層
（tarrragon/claude#97）。

呼叫方式：由 git-ref-transaction-guard-install-hook.py 安裝的 pre-commit shim
呼叫；shim 只在 settings.json 位於 staged 名單時才啟動本腳本。本腳本只用標準
函式庫，以 python3 直接執行（不經 uv），減少 commit 路徑上的啟動成本與失敗點。

判定：
- 讀 index 中的內容（`git show :.claude/settings.json`），不讀工作區，
  避免「工作區已修好但 staged 的仍是壞版本」被誤放行
- JSON 解析失敗 -> stderr 列出行列與原因，exit 87（shim 轉為 exit 1，阻擋 commit）
- 未 staged、已刪除 -> exit 0
- git 指令本身失敗（非 repo、index 讀不到）-> stderr 警告，exit 0（放行但可見）

日誌：每次判定在 `.claude/hook-logs/settings-json-syntax-precommit/precommit.log`
追加一行（寫入失敗只略過，不影響判定）。
"""

from __future__ import annotations

import datetime
import json
import subprocess
import sys
from pathlib import Path

SETTINGS_REL = ".claude/settings.json"
LOG_HOOK_NAME = "settings-json-syntax-precommit"
LOG_FILENAME = "precommit.log"
EXIT_ALLOW = 0
# 判定阻擋的專用結束碼，pre-commit shim 只把它轉成 exit 1。python 未捕獲例外
# 也是 1，若以 1 代表阻擋，腳本自身出錯會被誤當成語法錯誤而擋住所有 commit。
# 87 的選擇理由同 git-ref-transaction-guard-install-hook.GUARD_BLOCK_EXIT_CODE。
EXIT_BLOCK = 87
TAG = "[settings.json 語法閘門]"


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True, timeout=30
    )


def find_syntax_error(text: str) -> str | None:
    """回傳語法錯誤說明（含行列）；可解析時回 None。"""
    try:
        json.loads(text)
    except json.JSONDecodeError as exc:
        return f"第 {exc.lineno} 行第 {exc.colno} 列：{exc.msg}"
    return None


def _log_path(repo_root: Path) -> Path:
    """日誌檔路徑：優先經 hook_logging.get_hook_log_dir（linked worktree 內解析到主 repo）。

    `.claude/lib` 不可達時（例如腳本被單獨複製）退回 repo_root 下的相對位置。
    """
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    try:
        from lib.hook_logging import get_hook_log_dir
    except ImportError:
        return repo_root / ".claude" / "hook-logs" / LOG_HOOK_NAME / LOG_FILENAME
    return get_hook_log_dir(LOG_HOOK_NAME) / LOG_FILENAME


def _log(repo_root: Path, message: str) -> None:
    try:
        log_path = _log_path(repo_root)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(f"[{stamp}] {message}\n")
    except OSError:
        # 日誌寫入失敗不影響判定（判定結果已走 stderr / 結束碼）
        pass


def check_staged_settings(repo_root: Path) -> int:
    """檢查 index 中的 settings.json；回傳 pre-commit 結束碼。"""
    staged = _git(
        ["diff", "--cached", "--name-only", "--diff-filter=ACMR", "--", SETTINGS_REL],
        repo_root,
    )
    if staged.returncode != 0:
        sys.stderr.write(f"{TAG} 無法讀取 staged 清單，已放行本次 commit：{staged.stderr.strip()}\n")
        _log(repo_root, "allow (git diff --cached failed)")
        return EXIT_ALLOW
    if SETTINGS_REL not in staged.stdout.split():
        return EXIT_ALLOW

    shown = _git(["show", f":{SETTINGS_REL}"], repo_root)
    if shown.returncode != 0:
        sys.stderr.write(f"{TAG} 無法讀取 staged 的 {SETTINGS_REL}，已放行本次 commit：{shown.stderr.strip()}\n")
        _log(repo_root, "allow (git show failed)")
        return EXIT_ALLOW

    error = find_syntax_error(shown.stdout)
    if error is None:
        _log(repo_root, "allow (valid JSON)")
        return EXIT_ALLOW
    sys.stderr.write(
        f"{TAG} staged 的 {SETTINGS_REL} 不是合法 JSON，已阻擋 commit。\n"
        f"  {error}\n"
        "  語法錯誤會讓全部 Claude Code hook 不載入。修正後重新 git add 再 commit。\n"
    )
    _log(repo_root, f"block ({error})")
    return EXIT_BLOCK


def main() -> int:
    top = _git(["rev-parse", "--show-toplevel"], Path.cwd())
    if top.returncode != 0 or not top.stdout.strip():
        sys.stderr.write(f"{TAG} 無法解析 repo 根目錄，已放行本次 commit\n")
        return EXIT_ALLOW
    return check_staged_settings(Path(top.stdout.strip()))


if __name__ == "__main__":
    sys.exit(main())
