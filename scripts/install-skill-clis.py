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
import argparse
import importlib.util
import os
import stat
import sys
from pathlib import Path
from typing import List, Optional, Tuple


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
_SKILLS = _load_ownership_guard_skills()
CLI_NAMES: Tuple[str, ...] = tuple(entry.cli_name for entry in _SKILLS)
# 跳過既有檔時，警告文字要給出 uv tool 的套件名（uninstall／--force 復原用）
_PACKAGE_BY_CLI = {entry.cli_name: entry.package_name for entry in _SKILLS}

# shim 識別標記，供 --check 與 ownership 偵測辨認「這是 shim 非 uv tool bin」
SHIM_MARKER = "# cwd-resolving shim (ARCH-APP-002)"


def shim_body(cli: str) -> str:
    return f"""#!/bin/sh
{SHIM_MARKER} — '{cli}'，由 .claude/scripts/install-skill-clis.py 產生。
root=$(git rev-parse --show-toplevel 2>/dev/null)
skill_dir="$root/.claude/skills/{cli}"
if [ -n "$root" ] && [ -d "$skill_dir" ]; then
  SKILL_CLI_CALLER_CWD=$(pwd) exec uv run --quiet --directory "$skill_dir" {cli} "$@"
fi
echo "{cli}: 找不到當前專案的 .claude/skills/{cli}（cwd 不在已配置專案內，或非 git 倉庫）" >&2
exit 1
"""


def bin_dir() -> Path:
    return Path(os.environ.get("SKILL_CLI_BIN_DIR", str(Path.home() / ".local" / "bin")))


# 目標檔狀態：只有 ABSENT 與 SHIM 可寫入；其餘一律不寫並警告。
ABSENT, SHIM, SYMLINK, FOREIGN, UNREADABLE = "absent", "shim", "symlink", "foreign", "unreadable"


def classify_target(target: Path) -> str:
    """判斷 <bin>/<cli> 能不能安全寫入 shim。

    以 lstat 判斷，不跟隨 symlink：uv tool install 在 bin 目錄放的是指向
    tool 環境入口檔的 symlink，順著寫會把 shim 寫進 tool 環境、改壞該環境。
    判定過程出錯一律回 UNREADABLE（保守側：不寫入）。
    """
    try:
        st = os.lstat(target)
    except FileNotFoundError:
        return ABSENT
    except OSError:
        return UNREADABLE
    if stat.S_ISLNK(st.st_mode):
        return SYMLINK
    if not stat.S_ISREG(st.st_mode):
        return FOREIGN
    try:
        content = target.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return UNREADABLE
    return SHIM if SHIM_MARKER in content else FOREIGN


def _uv_package_name(cli: str, target: Path) -> str:
    """uv tool 的 symlink 指向 <tool 目錄>/<套件名>/bin/<cli>，能解析就用實際套件名。"""
    try:
        resolved = Path(os.readlink(target))
        if resolved.parent.name == "bin" and resolved.parent.parent.name:
            return resolved.parent.parent.name
    except OSError:
        # 非 symlink 或讀不到連結：改用清單上的套件名，警告仍可給出指令
        pass
    return _PACKAGE_BY_CLI.get(cli, cli)


def skip_warning(cli: str, target: Path, state: str) -> str:
    pkg = _uv_package_name(cli, target)
    reason = {
        SYMLINK: "是 symlink（多半是 uv tool install 安裝的版本）",
        FOREIGN: "不是本機制產生的 shim",
        UNREADABLE: "狀態讀取失敗",
    }[state]
    return (
        f"[install-skill-clis] WARNING: {target} {reason}，未寫入 shim，保留原檔。"
        f"此 CLI 在框架專案內執行的是既有版本，不是當前專案的 skill 源碼。"
        f"要改用 shim：先 `uv tool uninstall {pkg}`（或移除該檔）再重開 session。"
        f"若非框架專案執行 {cli} 出現「找不到當前專案的 .claude/skills/{cli}」，"
        f"代表 uv tool 環境已被舊版本機制寫壞，以原安裝指令加 --force 復原，"
        f"例如 `uv tool install --force --from <skill 目錄> {pkg}`。"
    )


def _write_shim(target: Path, body: str) -> None:
    # O_NOFOLLOW：判定後若目標被換成 symlink，open 失敗而不是寫穿
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o755)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(body)
    target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def check() -> int:
    bd = bin_dir()
    missing = []
    for cli in CLI_NAMES:
        if classify_target(bd / cli) != SHIM:
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
        state = classify_target(target)
        if state not in (ABSENT, SHIM):
            # stdout 進 SessionStart context（模型可見），stderr 給用戶
            warning = skip_warning(cli, target, state)
            print(warning)
            print(warning, file=sys.stderr)
            continue
        try:
            _write_shim(target, shim_body(cli))
        except OSError as exc:
            warning = f"[install-skill-clis] WARNING: 寫入 {target} 失敗（{exc}），未安裝 shim。"
            print(warning)
            print(warning, file=sys.stderr)
            continue
        print(f"[install-skill-clis] 已安裝 shim: {target}")
    print(f"[install-skill-clis] 完成。確認 {bd} 在 PATH 中即可使用 {', '.join(CLI_NAMES)}。")
    return 0


def parse_args(argv: List[str]) -> argparse.Namespace:
    """解析引數；--help 與未知引數由 argparse 在安裝前結束行程（exit 0／2）。

    查用法的命令不得產生寫入副作用：舊版只比對 sys.argv 是否含 --check，
    其餘引數（含 --help）一律落到 install()，改寫 bin_dir() 下全部 shim。
    """
    parser = argparse.ArgumentParser(
        prog="install-skill-clis.py",
        description="安裝 cwd-resolving CLI shim 到 SKILL_CLI_BIN_DIR（預設 ~/.local/bin）。",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="只檢查各 CLI 是否已是 shim，不寫入（exit 0／1）",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.check:
        return check()
    return install()


if __name__ == "__main__":
    sys.exit(main())
