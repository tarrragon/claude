#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
zhtw-mcp Availability Check Hook

Hook Event: SessionStart

Purpose:
    zhtw-mcp（sysprog21/zhtw-mcp）是繁體中文用語、教育部標準字、全形標點、
    跨境用語正規化檢查的 MCP server，作為 basil-writing-critic 文字審查的
    機械化補強。本 hook 為**軟性檢查**（永不阻擋 session），僅依當前狀態
    輸出對應提示：

    1. Binary 不存在        → stderr 輸出安裝命令
    2. Binary 存在但未註冊  → stderr 輸出 MCP 註冊命令
    3. 全 OK                → stdout 單行確認

Skip mechanism:
    建立 .claude/.zhtw-mcp-skip 檔案即可永久跳過此檢查（per-project opt-out）。
    用於用戶確認該專案不需要繁體中文檢查（例如英文專案）。

Why soft check:
    跨專案 framework sync 場景下，不是所有專案都需要 zhtw-mcp。硬性阻擋
    會在英文專案造成假警報。輸出到 stderr 確保訊息可見（quality-baseline 規則 4），
    不影響 session 啟動。

Why file-based MCP probe (W17-143 / ARCH-022):
    依 ARCH-022「framework hook 不應對 user-scope 設定產生隱性副作用」，採直讀
    三層 scope 設定 JSON 檔（user / project / local），任一含 zhtw-mcp 即視為
    已註冊。早期版本曾用 `claude mcp list` spawn CLI 探測，平均耗 8-10s 且
    子 CLI 對所有遠端 MCP server（Gmail / Linear / Greptile / Calendar）發
    HTTP health check；現行設計耗時降至 < 50ms，無遠端副作用。

Exit codes:
    0 - Always (soft check, never blocks session)
"""

import json
import os
import platform
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from hook_utils import setup_hook_logging, run_hook_safely


HOOK_NAME = "zhtw-mcp-check"
INSTALL_URL = "https://github.com/sysprog21/zhtw-mcp"

# Hook 位於 .claude/hooks/<file>，故 parent.parent = .claude/，parent.parent.parent = project root
_HOOK_FILE = Path(__file__).resolve()
SKIP_FLAG = _HOOK_FILE.parent.parent / ".zhtw-mcp-skip"
PROJECT_DIR = Path(os.environ.get("CLAUDE_PROJECT_DIR") or _HOOK_FILE.parent.parent.parent)
USER_HOME = Path.home()


def _check_binary():
    """Locate zhtw-mcp on PATH.

    Note (W17-143 user decision): 不嘗試版本探測。zhtw-mcp 0.1.0 不支援
    `--version` flag；待上游發布 release 後再用標準探測（追蹤 ticket: W17-140）。
    當前版本欄位固定顯示 "unknown"，避免每次 spawn 子 process 抓不到結果浪費 IO。

    Returns:
        path (str) if zhtw-mcp on PATH, None otherwise.
    """
    return shutil.which("zhtw-mcp")


def _scope_has_zhtw_mcp(json_path: Path) -> "bool | None":
    """Read a JSON file's mcpServers section and check for zhtw-mcp registration.

    Returns:
        True  - file exists, parsed OK, contains "zhtw-mcp" key in mcpServers
        False - file does not exist (legitimate "not registered in this scope")
        None  - file exists but cannot be parsed (treat as unknown to surface in fallback)
    """
    if not json_path.exists():
        return False
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    mcp_servers = data.get("mcpServers") if isinstance(data, dict) else None
    if not isinstance(mcp_servers, dict):
        return False
    return "zhtw-mcp" in mcp_servers


def _check_mcp_registered():
    """File-based three-scope probe for zhtw-mcp registration.

    探測順序（任一 scope 命中即回 True）：
        1. user scope    : ~/.claude.json mcpServers
        2. project scope : <project_dir>/.mcp.json mcpServers
        3. local scope   : <project_dir>/.claude/settings.local.json mcpServers

    依 ARCH-022 設計原則改為 file-based 取代 spawn `claude mcp list`，避免
    對所有遠端 MCP server 發 health check HTTP 請求。

    Returns:
        True  - any scope has "zhtw-mcp" in mcpServers
        False - all scopes confirmed not registered (file missing or absent key)
        None  - any scope file exists but cannot be parsed (probe inconclusive)
    """
    scopes = [
        USER_HOME / ".claude.json",
        PROJECT_DIR / ".mcp.json",
        PROJECT_DIR / ".claude" / "settings.local.json",
    ]
    results = [_scope_has_zhtw_mcp(p) for p in scopes]
    if any(r is True for r in results):
        return True
    if any(r is None for r in results):
        return None
    return False


def _install_hint():
    system = platform.system().lower()
    if system in ("darwin", "linux"):
        return (
            "  curl --proto '=https' --tlsv1.2 -LsSf \\\n"
            "    https://github.com/sysprog21/zhtw-mcp/releases/latest/download/zhtw-mcp-installer.sh \\\n"
            "    | sh"
        )
    if system == "windows":
        return (
            "  powershell -ExecutionPolicy Bypass -c \"irm \\\n"
            "    https://github.com/sysprog21/zhtw-mcp/releases/latest/download/zhtw-mcp-installer.ps1 \\\n"
            "    | iex\""
        )
    return f"  see {INSTALL_URL}"


def _register_hint():
    return (
        "  # 方式 A: claude CLI（推薦，會寫入 settings.local.json）\n"
        "  claude mcp add zhtw-mcp -- zhtw-mcp\n"
        "\n"
        "  # 方式 B: 手動編輯 .claude/settings.local.json\n"
        "  #   {\n"
        "  #     \"mcpServers\": {\n"
        "  #       \"zhtw-mcp\": { \"command\": \"zhtw-mcp\" }\n"
        "  #     }\n"
        "  #   }"
    )


def _skip_hint():
    return "  跳過此檢查（本專案不需繁中校對）: touch .claude/.zhtw-mcp-skip"


def _print_section(title, body):
    bar = "=" * 60
    print(f"{bar}\n{title}\n{bar}\n{body}\n{bar}", file=sys.stderr)


def main():
    logger = setup_hook_logging(HOOK_NAME)

    if SKIP_FLAG.exists():
        logger.info(f"Skip flag found at {SKIP_FLAG}")
        return 0

    binary_path = _check_binary()

    if not binary_path:
        body = (
            "用途: 1100+ 詞彙規則、教育部標準字、全形標點、跨境用語正規化\n"
            f"專案: {INSTALL_URL}\n"
            "\n"
            "建議安裝（軟性提示，不影響 session 啟動）:\n"
            f"{_install_hint()}\n"
            "\n"
            "安裝後註冊到 Claude Code MCP:\n"
            f"{_register_hint()}\n"
            "\n"
            f"{_skip_hint()}"
        )
        _print_section("[zhtw-mcp Check] 繁體中文檢查工具未安裝", body)
        logger.info("zhtw-mcp not installed")
        return 0

    registered = _check_mcp_registered()

    if registered is False:
        body = (
            f"Binary: {binary_path}\n"
            "\n"
            "註冊命令:\n"
            f"{_register_hint()}\n"
            "\n"
            f"{_skip_hint()}"
        )
        _print_section("[zhtw-mcp Check] Binary 已安裝但未註冊到 MCP", body)
        logger.info(f"zhtw-mcp at {binary_path} not registered")
        return 0

    if registered is True:
        print(f"[zhtw-mcp Check] OK: {binary_path} (registered)")
        logger.info(f"zhtw-mcp OK at {binary_path}, registered")
    else:
        print(f"[zhtw-mcp Check] Binary OK: {binary_path} (scope probe inconclusive)")
        logger.warning(f"zhtw-mcp binary OK at {binary_path}, scope JSON parse failed")

    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, HOOK_NAME))
