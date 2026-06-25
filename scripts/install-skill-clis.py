#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.10"
# ///
# presence-exempt: framework 安裝腳本，CLI 輸出字串非 app i18n 範疇
"""install-skill-clis.py — 安裝 cwd-resolving CLI shim 取代 uv tool install 全域安裝。

背景（framework issue tarrragon/claude#12 / ARCH-APP-002）：
  uv tool install <path> 以 package name 為全域唯一 key，多 consumer 專案共用
  同名 skill（ticket-system / doc-system / worktree-skill）會跨專案碰撞，最後
  reinstall 者搶占 ~/.local/bin/<cli>（last-write-wins），需要 staleness /
  ownership guard hook 不斷搶回 ownership。

解法：在 ~/.local/bin/ 安裝極小 POSIX sh shim。shim 執行時依
  git rev-parse --show-toplevel 解析「當前專案」的 skill 源碼，再
  uv run --directory 執行。永遠對應 cwd 所在專案 → 無全域碰撞、源碼即時生效、
  不需 reinstall（可移除上述兩個 guard hook）。

用法：
  python3 .claude/scripts/install-skill-clis.py          # 安裝 / 更新 shim
  python3 .claude/scripts/install-skill-clis.py --check  # 只檢查是否已是 shim（exit 0/1）

環境變數 SKILL_CLI_BIN_DIR 可覆寫安裝目錄（預設 ~/.local/bin）。
"""
import os
import stat
import sys
from pathlib import Path

# CLI 名稱與其 skill 目錄同名
CLI_NAMES = ("ticket", "doc", "worktree")

# shim 識別標記，供 --check 與 ownership 偵測辨認「這是 shim 非 uv tool bin」
SHIM_MARKER = "# cwd-resolving shim (ARCH-APP-002)"


def shim_body(cli: str) -> str:
    return f"""#!/bin/sh
{SHIM_MARKER} — '{cli}'，由 .claude/scripts/install-skill-clis.py 產生。
root=$(git rev-parse --show-toplevel 2>/dev/null)
skill_dir="$root/.claude/skills/{cli}"
if [ -n "$root" ] && [ -d "$skill_dir" ]; then
  exec uv run --quiet --directory "$skill_dir" {cli} "$@"
fi
echo "{cli}: 找不到當前專案的 .claude/skills/{cli}（cwd 不在已配置專案內，或非 git 倉庫）" >&2
exit 1
"""


def bin_dir() -> Path:
    return Path(os.environ.get("SKILL_CLI_BIN_DIR", str(Path.home() / ".local" / "bin")))


def check() -> int:
    bd = bin_dir()
    missing = []
    for cli in CLI_NAMES:
        target = bd / cli
        if not target.exists() or SHIM_MARKER not in target.read_text(encoding="utf-8", errors="replace"):
            missing.append(cli)
    if missing:
        print(f"[install-skill-clis] 尚未 shim 化: {', '.join(missing)}", file=sys.stderr)
        return 1
    print("[install-skill-clis] 三個 CLI 皆為 shim")
    return 0


def install() -> int:
    bd = bin_dir()
    bd.mkdir(parents=True, exist_ok=True)
    for cli in CLI_NAMES:
        target = bd / cli
        target.write_text(shim_body(cli), encoding="utf-8")
        target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        print(f"[install-skill-clis] 已安裝 shim: {target}")
    print(f"[install-skill-clis] 完成。確認 {bd} 在 PATH 中即可使用 ticket / doc / worktree。")
    return 0


def main() -> int:
    if "--check" in sys.argv[1:]:
        return check()
    return install()


if __name__ == "__main__":
    sys.exit(main())
