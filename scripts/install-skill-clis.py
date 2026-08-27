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
import importlib.util
import os
import stat
import sys
from pathlib import Path
from typing import Tuple


def _load_ownership_guard_skills() -> Tuple:
    """
    動態載入 uv-tool-ownership-guard-hook.py 取得 SKILLS 常數（單一來源）。

    SKILLS 由 (source_subpath, package_name, cli_name) 三元組成：
      - source_subpath: skill 目錄（如 ".claude/skills/ticket"）
      - package_name: uv tool 安裝名 / receipt 目錄名（如 "ticket-system"，
        僅供 ownership guard 定位 receipt 用，與本腳本產生 shim 無關）
      - cli_name: 命令首 token（如 "ticket"），本腳本唯一需要的欄位

    本腳本不手寫第二份清單，改以 importlib 直接載入該 hook 檔案取
    SKILLS，避免兩處清單漂移（ARCH-BAL-003 症狀變體）。hook 檔名含連字號
    非合法模組名，故用 spec_from_file_location 而非一般 import（與
    tests/test_uv_tool_ownership_guard_hook.py 的載入方式一致）。
    """
    hook_path = (
        Path(__file__).parent.parent / "hooks" / "uv-tool-ownership-guard-hook.py"
    )
    spec = importlib.util.spec_from_file_location(
        "uv_tool_ownership_guard_hook", hook_path
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["uv_tool_ownership_guard_hook"] = module
    spec.loader.exec_module(module)
    return module.SKILLS


# CLI_NAMES 只取 cli_name：skill 目錄名（source_subpath 的 basename）與
# entry point 名（pyproject.toml [project.scripts] 的 key）皆恆等於
# cli_name（7 個 skill 實測皆成立），故 shim_body() 只需 cli_name 即可組出
# skill_dir 路徑與執行指令；package_name 可能與 cli_name 不同（如
# ticket-system / ticket），但那只是 uv tool 全域安裝名，與 shim 執行路徑
# 無關，本腳本不使用。
CLI_NAMES: Tuple[str, ...] = tuple(
    entry.cli_name for entry in _load_ownership_guard_skills()
)

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
    print(f"[install-skill-clis] {len(CLI_NAMES)} 個 CLI 皆為 shim")
    return 0


def install() -> int:
    bd = bin_dir()
    bd.mkdir(parents=True, exist_ok=True)
    for cli in CLI_NAMES:
        target = bd / cli
        target.write_text(shim_body(cli), encoding="utf-8")
        target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        print(f"[install-skill-clis] 已安裝 shim: {target}")
    print(f"[install-skill-clis] 完成。確認 {bd} 在 PATH 中即可使用 {', '.join(CLI_NAMES)}。")
    return 0


def main() -> int:
    if "--check" in sys.argv[1:]:
        return check()
    return install()


if __name__ == "__main__":
    sys.exit(main())
