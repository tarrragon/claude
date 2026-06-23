#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
Error-Pattern Flat-ID Negative Gate - PreToolUse Hook

拒絕手動新建 flat 號（<CAT>-NNN，如 PC-179）error-pattern 檔案；放行前綴號
（<CAT>-<PROJ>-NNN，如 PC-V1-001）新建與既有 flat 檔編輯。

Why: flat base 是 V1/APP 共享凍結核心，獨立累加會再撞號（process-compliance/ 已有
     PC-010 x2、PC-018 x2 碰撞實證）。W1-019.3 的 allocator + skill.md 只能引導正確
     路徑，無法阻擋手動建檔——E1 linux F2：凍結 flat base 需 hook 強制非文件自律。

判定（依序）:
  tool ∈ {Write, Edit} AND file_path 在 error-patterns/ 子目錄且為 .md
  AND 檔名首 ID 為 flat（split('-') == 2 段）
  AND 目標不存在於磁碟（= 新建）           → exit 2 deny
  否則（前綴號 / 無 ID / 既有檔編輯 / 非 error-patterns）→ exit 0 allow

SSOT: 複用 .claude/lib/pattern_id.py 的 extract_pattern_id，禁再造 regex（ARCH-020）。
對應規則: quality-baseline 規則 4（deny 訊息寫 stderr + 引導 /error-pattern add）。
來源 ticket: 1.0.0-W1-021（source 1.0.0-W1-019.3）。
"""

import sys
from pathlib import Path

# 跨目錄 import：本 hook 位於 .claude/skills/error-pattern/hooks/，
# 需指向 .claude/hooks/ 載入 hook_utils 與 lib.pattern_id（SSOT）。
# parents[3] = .claude（hooks=[0] error-pattern=[1] skills=[2] .claude=[3]）
_CLAUDE_ROOT = Path(__file__).resolve().parents[3]
_HOOKS_ROOT = _CLAUDE_ROOT / "hooks"
sys.path.insert(0, str(_CLAUDE_ROOT))
sys.path.insert(0, str(_HOOKS_ROOT))

from hook_utils import (  # noqa: E402
    setup_hook_logging,
    run_hook_safely,
    read_json_from_stdin,
    emit_hook_output,
)
from lib.pattern_id import extract_pattern_id  # noqa: E402

EXIT_ALLOW = 0
EXIT_BLOCK = 2

WRITE_TOOLS = frozenset({"Write", "Edit"})
ERROR_PATTERNS_SEGMENT = "error-patterns"
MARKDOWN_SUFFIX = ".md"


def is_error_pattern_file(file_path: str) -> bool:
    """判斷 file_path 是否為 error-patterns 子目錄下的 .md 檔。

    根目錄非 pattern 檔（README.md / _project-registry.yaml）：README.md 經
    extract_pattern_id 回 None 自然放行；.yaml 在此先被副檔名濾除。
    """
    if not file_path:
        return False
    path = Path(file_path)
    if path.suffix.lower() != MARKDOWN_SUFFIX:
        return False
    return ERROR_PATTERNS_SEGMENT in path.parts


def is_flat_id(pattern_id) -> bool:
    """flat 號 = <CAT>-NNN（2 段）；前綴號 = <CAT>-<PROJ>-NNN（3+ 段）。

    例：PC-099 -> 2 段 flat；PC-V1-001 / PC-C2C-001 -> 3 段前綴。

    W1-036：extract_pattern_id 的 SSOT regex 允許前綴段含數字（V1/C2C 等專案碼
    本身含數字），故 `PC-099-3-layer-defense.md` 會被過度匹配為 `PC-099-3`（3 段），
    若僅以段數判定會誤判為前綴號而繞過凍結 gate。但 _project-registry.yaml 規定
    專案碼為「短大寫英數，語意可辨識」，實務上所有已註冊碼（V1/APP/SCLK/CCS/C2C）
    皆含字母——純數字中段不可能是合法專案碼，只可能是 flat 號被吸入的描述段數字。
    故 3 段且中段純數字者，仍判為 flat（真實 ID 為 <CAT>-<中段前的數字>）。
    """
    if pattern_id is None:
        return False
    parts = pattern_id.split("-")
    if len(parts) == 2:
        return True
    # 中段純數字 = flat 號描述段數字被 SSOT regex 過度吸入（PC-099-3-...）。
    if len(parts) == 3 and parts[1].isdigit() and parts[2].isdigit():
        return True
    return False


def extract_file_path(tool_input: dict) -> str:
    """從 Write/Edit 的 tool_input 取出 file_path（兩工具皆用此 key）。"""
    value = tool_input.get("file_path")
    return str(value) if value else ""


def build_deny_message(file_path: str, pattern_id: str) -> str:
    """組合 deny message，引導改用 /error-pattern add（規則 4 可觀測性）。"""
    return (
        f"[DENY] 拒絕手動新建 flat 號 error-pattern：{pattern_id}（{file_path}）\n"
        f"flat base（<CAT>-NNN）是 V1/APP 共享凍結核心，獨立新增會再撞號。\n"
        f"請改用 /error-pattern add，自動分配 <CAT>-<PROJ>-NNN 前綴號（ARCH-020 / W1-019）。\n"
        f"（編輯既有 flat 檔與前綴號檔不受此限。）"
    )


def decide(tool_name: str, tool_input: dict):
    """回傳 (permission_decision, reason, exit_code)。純函式，便於測試。"""
    if tool_name not in WRITE_TOOLS:
        return "allow", f"工具 {tool_name} 不在檢查範圍", EXIT_ALLOW

    file_path = extract_file_path(tool_input)
    if not is_error_pattern_file(file_path):
        return "allow", "非 error-patterns .md 檔，預設允許", EXIT_ALLOW

    pattern_id = extract_pattern_id(Path(file_path).name)
    if not is_flat_id(pattern_id):
        return "allow", f"ID {pattern_id} 非 flat 號（前綴 / 無 ID），允許", EXIT_ALLOW

    if Path(file_path).exists():
        return "allow", f"編輯既有 flat 檔 {pattern_id}，允許", EXIT_ALLOW

    return "deny", build_deny_message(file_path, pattern_id), EXIT_BLOCK


def main() -> int:
    """主入口：讀 stdin → decide → emit allow/deny。"""
    logger = setup_hook_logging("error-pattern-flat-gate")

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

    decision, reason, exit_code = decide(tool_name, tool_input)

    if decision == "deny":
        logger.info(f"DENY 新建 flat 號 error-pattern：{reason.splitlines()[0]}")
        sys.stderr.write(reason + "\n")
    else:
        logger.debug(f"ALLOW：{reason}")

    emit_hook_output(
        "PreToolUse",
        permission_decision=decision,
        permission_decision_reason=reason,
    )
    return exit_code


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "error-pattern-flat-gate"))
