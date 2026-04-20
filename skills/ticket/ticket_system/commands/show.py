"""
ticket show 子命令

終端顯示 Ticket 內容，支援 Markdown 渲染、TTY 偵測與分頁。

設計目標（見 0.18.0-W17-015 Solution）：
- 單一短指令入口 `ticket show <id>`（取代 `ticket track full <id> | bat -l md`）
- TTY auto render（glow > mdcat > bat > raw fallback），非 TTY 自動 raw
- 短 flag 為主：-r/-R/-p/-P，細節靠 --help 說明
- 不強制任何外部渲染器，皆缺失時 fallback raw 不 crash

與 `ticket track full` 的差異：
- `track full` 永遠 raw 輸出（腳本友善，不變）
- `show` 預設渲染（閱讀友善，pipe 時自動降 raw）
"""

import argparse
import re
import shutil
import subprocess
import sys
from typing import Dict, List, Optional

import yaml

from ticket_system.lib.ticket_loader import resolve_version
from ticket_system.lib.ticket_ops import load_and_validate_ticket

# 渲染器偵測優先序（首個 shutil.which 命中者為 auto 結果）
RENDERER_PRIORITY: List[str] = ["glow", "mdcat", "bat"]

# 支援的 --renderer 值（加 auto 代表自動偵測）
SUPPORTED_RENDERERS: List[str] = RENDERER_PRIORITY + ["auto"]

# 各渲染器的 Homebrew 安裝指令（macOS 優先；Linux 用戶可依套件管理器調整）
RENDERER_INSTALL_HINTS: Dict[str, str] = {
    "glow": "brew install glow  # Linux: https://github.com/charmbracelet/glow",
    "mdcat": "brew install mdcat  # Linux: cargo install mdcat",
    "bat": "brew install bat  # Linux: apt install bat 或 cargo install bat",
}

# Short-ID 模式：W{wave}-{seq}[.sub...]，無版本前綴
SHORT_ID_RE = re.compile(r"^W\d+-\d+(?:\.\d+)*$")


def detect_installed_renderers() -> Dict[str, bool]:
    """偵測每個支援渲染器的安裝狀態。

    Returns:
        {renderer_name: is_installed} 對應 RENDERER_PRIORITY 順序。
    """
    return {name: shutil.which(name) is not None for name in RENDERER_PRIORITY}


def format_renderer_choices_help() -> str:
    """動態組裝 -R/--renderer 的 help 文字，標記每個渲染器的安裝狀態。

    Example:
        指定渲染器（預設 auto）。狀態：glow[已安裝]、mdcat[未安裝: brew install mdcat]、bat[已安裝]
    """
    status = detect_installed_renderers()
    parts = []
    for name in RENDERER_PRIORITY:
        if status[name]:
            parts.append(f"{name}[已安裝]")
        else:
            hint = RENDERER_INSTALL_HINTS.get(name, f"請安裝 {name}")
            parts.append(f"{name}[未安裝: {hint}]")
    return "指定渲染器（預設 auto）。狀態：" + "、".join(parts)


def register(subparsers: argparse._SubParsersAction) -> None:
    """註冊 show 子命令到 argparse 主入口。"""
    parser = subparsers.add_parser(
        "show",
        help="顯示 Ticket 內容（支援 Markdown 渲染）",
        description=(
            "顯示 Ticket 完整內容，TTY 下自動以 Markdown 渲染。\n\n"
            "範例：\n"
            "  ticket show 0.18.0-W17-015     # 完整 ID\n"
            "  ticket show W17-015            # 短 ID（自動補當前版本）\n"
            "  ticket show W17-015 -r         # 純文字輸出\n"
            "  ticket show W17-015 -R bat     # 指定渲染器\n"
            "  ticket show W17-015 | cat      # pipe 自動降 raw\n\n"
            "渲染器偵測順序：glow > mdcat > bat > raw fallback"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "ticket_id",
        help="Ticket ID（完整如 0.18.0-W17-015，或短 ID 如 W17-015）",
    )
    parser.add_argument(
        "--version",
        help="版本號（自動偵測，短 ID 展開用）",
    )
    parser.add_argument(
        "-r",
        "--raw",
        action="store_true",
        help="強制純文字輸出（不渲染）",
    )
    parser.add_argument(
        "-R",
        "--renderer",
        choices=SUPPORTED_RENDERERS,
        default="auto",
        help=format_renderer_choices_help(),
    )
    pager_group = parser.add_mutually_exclusive_group()
    pager_group.add_argument(
        "-p",
        "--pager",
        action="store_true",
        help="強制啟用分頁",
    )
    pager_group.add_argument(
        "-P",
        "--no-pager",
        action="store_true",
        help="停用分頁",
    )
    parser.set_defaults(func=lambda args: execute_show(args))


def expand_short_id(ticket_id: str, version: Optional[str]) -> str:
    """
    短 ID 自動補版本。

    規則：
    - 已有版本前綴（含 '.'）→ 原樣返回
    - 符合 W{wave}-{seq} 格式 → 補版本
    - 其他格式 → 原樣返回（讓下游 loader 處理錯誤）

    Examples:
        expand_short_id("W17-015", "0.18.0") → "0.18.0-W17-015"
        expand_short_id("0.18.0-W17-015", "0.18.0") → "0.18.0-W17-015"
        expand_short_id("W17-015.1", "0.18.0") → "0.18.0-W17-015.1"
    """
    if SHORT_ID_RE.match(ticket_id) and version:
        return f"{version}-{ticket_id}"
    return ticket_id


def build_full_content(ticket: dict) -> str:
    """
    重建 ticket 完整 Markdown 內容（frontmatter + body）。

    與 track_query.execute_full 邏輯一致，抽出以供渲染共用。
    """
    frontmatter = {k: v for k, v in ticket.items() if not k.startswith("_")}
    body = ticket.get("_body", "")
    frontmatter_yaml = yaml.dump(
        frontmatter,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    )
    return f"---\n{frontmatter_yaml}---\n\n{body}"


def detect_renderer(preferred: str) -> Optional[str]:
    """
    偵測可用渲染器。

    Args:
        preferred: auto / glow / mdcat / bat

    Returns:
        可執行的渲染器名稱，若指定特定渲染器但缺失則返回 None，
        若 auto 但全部缺失也返回 None。
    """
    if preferred == "auto":
        for renderer in RENDERER_PRIORITY:
            if shutil.which(renderer):
                return renderer
        return None
    # 指定特定渲染器：存在才返回，否則 None
    if shutil.which(preferred):
        return preferred
    return None


def build_renderer_command(renderer: str, pager_mode: str) -> List[str]:
    """
    組裝渲染器子程序命令。

    Args:
        renderer: glow / mdcat / bat
        pager_mode: "auto" / "always" / "never"

    Returns:
        subprocess.run 用的 argv list。
    """
    if renderer == "bat":
        cmd = ["bat", "-l", "md", "--style=plain"]
        if pager_mode == "always":
            cmd.append("--paging=always")
        elif pager_mode == "never":
            cmd.append("--paging=never")
        # auto：bat 預設 auto，不加 flag
        return cmd
    if renderer == "glow":
        cmd = ["glow", "-"]
        if pager_mode == "always":
            cmd.append("-p")
        return cmd
    if renderer == "mdcat":
        # mdcat 無內建 pager flag；always 情境由呼叫端另行 pipe 到 less
        return ["mdcat"]
    # 未知渲染器（理論上不會到此）
    return [renderer]


def run_renderer(content: str, cmd: List[str]) -> int:
    """
    以 subprocess 執行渲染器，將 content 從 stdin 餵入。

    Returns:
        子程序 exit code；若渲染器執行失敗返回非 0。
    """
    try:
        result = subprocess.run(
            cmd,
            input=content,
            text=True,
            check=False,
        )
        return result.returncode
    except FileNotFoundError:
        return 127


def execute_show(args: argparse.Namespace) -> int:
    """執行 show 命令主邏輯。"""
    # 版本解析（短 ID 展開需要）
    version = resolve_version(getattr(args, "version", None))

    # 短 ID 自動補版本
    full_id = expand_short_id(args.ticket_id, version)

    # 載入 ticket（load_and_validate_ticket 自行處理錯誤輸出）
    ticket, error = load_and_validate_ticket(version, full_id)
    if error:
        return 1

    content = build_full_content(ticket)

    # 決策：是否渲染
    # 規則：
    # - -r/--raw → 強制 raw
    # - stdout 非 TTY → 強制 raw（防 ANSI 污染 pipe consumer）
    # - 其他情況 → 嘗試渲染
    force_raw = bool(getattr(args, "raw", False)) or not sys.stdout.isatty()

    if force_raw:
        print(content)
        return 0

    # 偵測渲染器
    requested = getattr(args, "renderer", "auto") or "auto"
    renderer = detect_renderer(requested)

    if renderer is None:
        # 指定特定渲染器但缺失 → 明確報錯 exit 2，附安裝指令
        if requested != "auto":
            print(
                f"[ERROR] 指定的渲染器 '{requested}' 未安裝或不在 PATH 中",
                file=sys.stderr,
            )
            hint = RENDERER_INSTALL_HINTS.get(requested)
            if hint:
                print(f"  可執行：{hint}", file=sys.stderr)
            return 2
        # auto 但全部缺失 → fallback raw + stderr warning
        print(
            "[WARNING] 未偵測到任何 Markdown 渲染器（glow/mdcat/bat），"
            "fallback 為純文字輸出。",
            file=sys.stderr,
        )
        print(content)
        return 0

    # 決定 pager 模式
    if getattr(args, "pager", False):
        pager_mode = "always"
    elif getattr(args, "no_pager", False):
        pager_mode = "never"
    else:
        pager_mode = "auto"

    cmd = build_renderer_command(renderer, pager_mode)
    exit_code = run_renderer(content, cmd)
    return exit_code
