#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""
UC Fingerprint Drift Check Hook - PostToolUse Hook

docs/app-use-cases.md 被 Write/Edit 修改後，自動執行 fingerprint check，
偵測 UC 內容漂移並以 stderr WARNING 提示 PM。

Hook 類型：PostToolUse
匹配工具：Edit, Write
退出碼：一律 0（WARNING-only，不阻擋）
"""

import sys
from pathlib import Path

_HOOKS_DIR = Path(__file__).resolve().parent
_CLAUDE_DIR = _HOOKS_DIR.parent
_DOC_SKILL_DIR = _CLAUDE_DIR / "skills" / "doc"

sys.path.insert(0, str(_CLAUDE_DIR))
sys.path.insert(0, str(_DOC_SKILL_DIR))

from lib import (  # noqa: E402
    setup_hook_logging,
    read_json_from_stdin,
    extract_tool_input,
    get_project_root,
)


USE_CASES_SUFFIX = "docs/app-use-cases.md"


def main() -> int:
    logger = setup_hook_logging("uc-fingerprint-drift-check")

    input_data = read_json_from_stdin(logger)
    if not input_data:
        return 0

    tool_name = input_data.get("tool_name", "")
    if tool_name not in ("Write", "Edit"):
        return 0

    tool_input = extract_tool_input(input_data, logger)
    file_path = tool_input.get("file_path", "")
    if not file_path or not file_path.replace("\\", "/").endswith(USE_CASES_SUFFIX):
        return 0

    try:
        from doc_system.core.uc_registry import (
            check_fingerprints,
            get_fingerprint_sidecar_path,
        )
    except ImportError as exc:
        message = f"[uc-fingerprint-drift-check] uc_registry 載入失敗，跳過漂移偵測：{exc}"
        sys.stderr.write(message + "\n")
        logger.warning(message)
        return 0

    project_root = str(get_project_root())
    sidecar = get_fingerprint_sidecar_path(project_root)
    if not sidecar.is_file():
        logger.debug("指紋 sidecar 不存在，跳過漂移偵測")
        return 0

    drifted, added, removed = check_fingerprints(project_root)
    if not drifted and not added and not removed:
        return 0

    parts = ["[uc-fingerprint-drift-check] UC 內容已變更，下游引用可能需要更新："]
    if drifted:
        parts.append(f"  漂移: {', '.join(drifted)}")
    if added:
        parts.append(f"  新增: {', '.join(added)}")
    if removed:
        parts.append(f"  移除: {', '.join(removed)}")
    parts.append("  執行 `doc uc fingerprint update` 更新指紋。")

    message = "\n".join(parts)
    sys.stderr.write(message + "\n")
    logger.info(message)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        sys.stderr.write(f"[uc-fingerprint-drift-check] 未預期錯誤：{exc}\n")
        sys.exit(0)
