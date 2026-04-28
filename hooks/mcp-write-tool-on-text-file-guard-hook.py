#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
MCP Write Tool On Text File Guard - PreToolUse Hook

偵測 mcp__serena__ 寫入工具用於非程式碼檔案（.md / .txt / .yaml / .yml / .json / .toml）
的情境，直接 deny 並提示改用 Edit / Write。落實 PC-112 三層防護的 hook 強制層。

觸發時機: 執行 mcp__serena__replace_content / replace_symbol_body /
         insert_after_symbol / insert_before_symbol / safe_delete_symbol 時
行為: 非程式碼副檔名 → exit 2 + deny；程式碼副檔名或無副檔名 → exit 0 allow

對應規則：.claude/rules/core/tool-selection.md 規則 1
動機案例：.claude/error-patterns/process-compliance/PC-112-*.md
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from hook_utils import (
    setup_hook_logging,
    run_hook_safely,
    read_json_from_stdin,
    emit_hook_output,
)

EXIT_ALLOW = 0
EXIT_BLOCK = 2

# 寫入類 serena MCP 工具集合（read-only 工具如 find_symbol 不在此列）
SERENA_WRITE_TOOLS = frozenset({
    "mcp__serena__replace_content",
    "mcp__serena__replace_symbol_body",
    "mcp__serena__insert_after_symbol",
    "mcp__serena__insert_before_symbol",
    "mcp__serena__safe_delete_symbol",
})

# 非程式碼副檔名（小寫比對，含前導點）
NON_CODE_EXTENSIONS = frozenset({
    ".md", ".txt", ".yaml", ".yml", ".json", ".toml",
})


def is_serena_write_tool(tool_name: str) -> bool:
    """判斷工具是否屬於 serena 寫入工具集合。"""
    return tool_name in SERENA_WRITE_TOOLS


def classify_extension(file_path: str) -> str:
    """
    取出檔案的最後一個副檔名（小寫）。

    多副檔名（如 `foo.test.md`）取最後一個（`.md`）。
    無副檔名或空字串回傳空字串。
    """
    if not file_path:
        return ""
    suffix = Path(file_path).suffix
    return suffix.lower()


def is_non_code_file(file_path: str) -> bool:
    """判斷檔案副檔名是否屬非程式碼類（受本 hook 約束）。"""
    ext = classify_extension(file_path)
    return ext in NON_CODE_EXTENSIONS


def extract_file_path(tool_input: dict) -> str:
    """
    從 serena 工具的 tool_input 取出檔案路徑。

    serena 工具參數命名常見：relative_path（多數）/ file_path（少數）。
    依序嘗試，回傳第一個非空字串。
    """
    for key in ("relative_path", "file_path"):
        value = tool_input.get(key)
        if value:
            return str(value)
    return ""


def build_deny_message(tool_name: str, file_path: str, ext: str) -> str:
    """組合 deny message，引用規則與案例。"""
    return (
        f"[DENY] {tool_name} 不應用於非程式碼檔案（{ext}）：{file_path}\n"
        f"請改用 Edit / Write 工具修改此檔。\n"
        f"依據：.claude/rules/core/tool-selection.md 規則 1；案例：PC-112。"
    )


def main() -> int:
    """主入口：讀取 stdin → 工具/副檔名分類 → 決策 allow / deny。"""
    logger = setup_hook_logging("mcp-write-tool-on-text-file-guard")

    input_data = read_json_from_stdin(logger)
    if not input_data:
        logger.debug("輸入為空或解析失敗，預設允許")
        emit_hook_output(
            "PreToolUse",
            permission_decision="allow",
            permission_decision_reason="輸入為空，預設允許",
        )
        return EXIT_ALLOW

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input") or {}

    if not is_serena_write_tool(tool_name):
        logger.debug(f"工具 {tool_name} 不在 serena 寫入工具範圍，跳過")
        emit_hook_output(
            "PreToolUse",
            permission_decision="allow",
            permission_decision_reason=f"工具 {tool_name} 不在本 hook 檢查範圍",
        )
        return EXIT_ALLOW

    file_path = extract_file_path(tool_input)
    if not file_path:
        logger.debug("無 file_path / relative_path，預設允許")
        emit_hook_output(
            "PreToolUse",
            permission_decision="allow",
            permission_decision_reason="無檔案路徑可分類，預設允許",
        )
        return EXIT_ALLOW

    if not is_non_code_file(file_path):
        ext = classify_extension(file_path) or "(無副檔名)"
        logger.info(f"檔案 {file_path} 副檔名 {ext} 屬程式碼類，允許 {tool_name}")
        emit_hook_output(
            "PreToolUse",
            permission_decision="allow",
            permission_decision_reason=f"副檔名 {ext} 不在非程式碼清單",
        )
        return EXIT_ALLOW

    ext = classify_extension(file_path)
    reason = build_deny_message(tool_name, file_path, ext)
    logger.info(f"DENY: {tool_name} on {file_path} (ext={ext})")
    emit_hook_output(
        "PreToolUse",
        permission_decision="deny",
        permission_decision_reason=reason,
    )
    return EXIT_BLOCK


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "mcp-write-tool-on-text-file-guard"))
