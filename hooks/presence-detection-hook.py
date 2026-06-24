#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Presence-Detection Hook (PreToolUse on Edit / Write) —— language-pluggable 通用引擎

偵測「應有設施缺席」三類問題（user-facing 字串 / 裸顏色字面 / 魔術數字），
針對 greenfield 專案從不 bootstrap i18n / theme / 常數設施而使依賴設施缺席的結構盲區
（來源：1.2.0-W1-015）。本引擎為 language-pluggable 版本（1.2.0-W1-036）：

  - 通用偵測引擎（本檔）只懂「三類偵測 + override marker + 只掃變更內容」的流程，
    不寫死任何語言假設。
  - 語言專屬規則（pattern / 排除 / sink skip / marker）抽至 .claude/config/presence_profiles.py，
    引擎依副檔名選 profile。
  - 無對應副檔名 profile → no-op（exit 0）。這是安全上游的關鍵：非 Flutter 專案
    pull 後對其 .js / .py / .go 等檔案完全不誤觸，profile 集合可安全散佈。

防呆（避免癱瘓 remediation）：
  - 只偵測「變更內容」（Edit new_string / Write content / MultiEdit edits），不掃整檔。
  - Override marker：命中行或前一行含 profile 定義的 marker 即豁免。
  - 降級路徑：PRESENCE_HOOK_MODE=warn 時退化為純警告（exit 0）。預設 block。

Exit Codes：
  0 - 無命中 / 已 override / warn 模式 / 無對應 profile / 解析失敗（不阻塊原則）
  2 - block 模式且偵測到未豁免的缺席（permissionDecision: deny）
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "config"))

from lib import setup_hook_logging, run_hook_safely, read_json_from_stdin
from presence_profiles import get_profile_for_path


# ---------------------------------------------------------------------------
# 通用偵測引擎（依 profile 驅動，無語言假設）
# ---------------------------------------------------------------------------

def should_skip_file(file_path: str, profile) -> bool:
    """檔案是否在偵測範圍外（profile 定義的生成檔 / 測試 / 設施本體 sink）。"""
    normalised = file_path.replace("\\", "/")
    return any(p.search(normalised) for p in profile.skip_patterns)


def _line_is_overridden(lines: list, index: int, profile) -> bool:
    """命中行自身或前一行含 profile override marker。"""
    candidates = [lines[index]]
    if index > 0:
        candidates.append(lines[index - 1])
    joined = " ".join(candidates)
    return any(marker in joined for marker in profile.override_markers)


def detect_violations(content: str, profile) -> list:
    """
    對「變更內容」依 profile 掃描三類缺席。

    僅掃描傳入的 content（非整檔），避免重複攔截本次未觸及的既有舊問題。
    任一類別的 *_detect 為空清單時，引擎跳過該類（語言不適用即留空）。

    Returns: list of {line, category, snippet, suggestion}
    """
    violations = []
    lines = content.split("\n")

    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue

        # 1. user-facing 字串
        if profile.string_detect and not _matches_any(profile.string_exclude, line):
            if _matches_any(profile.string_detect, line):
                if not _line_is_overridden(lines, idx, profile):
                    violations.append(_violation(idx, "i18n", stripped,
                        "user-facing 字串應進 i18n（或標 // i18n-exempt）"))
                    continue  # 一行一類即可

        # 2. 裸顏色字面
        if profile.color_detect and _matches_any(profile.color_detect, line) \
                and not _matches_any(profile.color_exclude, line):
            if not _line_is_overridden(lines, idx, profile):
                violations.append(_violation(idx, "color", stripped,
                    "裸 Color 應改用 theme token（或標 // color-exempt）"))
                continue

        # 3. 魔術數字
        if profile.magic_detect and _matches_any(profile.magic_detect, line) \
                and not _matches_any(profile.magic_exclude, line):
            if not _line_is_overridden(lines, idx, profile):
                violations.append(_violation(idx, "magic-number", stripped,
                    "魔術數字應集中為常數（或標 // magic-exempt）"))

    return violations


def _matches_any(patterns: list, line: str) -> bool:
    return any(p.search(line) for p in patterns)


def _violation(idx: int, category: str, stripped: str, suggestion: str) -> dict:
    return {
        "line": idx + 1,
        "category": category,
        "snippet": stripped[:80],
        "suggestion": suggestion,
    }


def extract_changed_content(tool_name: str, tool_input: dict) -> str:
    """取得本次編輯實際寫入的內容（變更行而非全檔）。"""
    if tool_name == "Write":
        return tool_input.get("content", "") or ""
    if tool_name == "Edit":
        return tool_input.get("new_string", "") or ""
    if tool_name == "MultiEdit":
        edits = tool_input.get("edits") or []
        return "\n".join(e.get("new_string", "") or "" for e in edits)
    return ""


def build_block_message(file_path: str, violations: list) -> str:
    """組裝 block 訊息（含修復指引與 override 用法）。"""
    by_cat = {}
    for v in violations:
        by_cat.setdefault(v["category"], []).append(v)

    lines = [
        "[Presence Guard] 偵測到應有設施缺席（blocking-with-override）",
        f"檔案: {file_path}",
        "",
    ]
    cat_label = {
        "i18n": "硬編碼 user-facing 字串（應進 i18n）",
        "color": "裸 Color / Colors.xxx（應進 theme token）",
        "magic-number": "魔術數字字面（應集中常數）",
    }
    for cat, items in by_cat.items():
        lines.append(f"[{cat_label.get(cat, cat)}]")
        for v in items[:5]:
            lines.append(f"  變更行 {v['line']}: {v['snippet']}")
            lines.append(f"    → {v['suggestion']}")
        if len(items) > 5:
            lines.append(f"  ... 另有 {len(items) - 5} 處")
        lines.append("")

    lines.append("修復選項（擇一）：")
    lines.append("  1. 引入對應設施（i18n / theme token / 常數）後重試")
    lines.append("  2. 確屬例外時於命中行或前一行加 override marker：")
    lines.append("     // i18n-exempt  /  // color-exempt  /  // magic-exempt  /  // presence-exempt")
    lines.append("")
    lines.append("漸進部署：設 PRESENCE_HOOK_MODE=warn 可暫退為純警告（不阻擋）。")
    return "\n".join(lines)


def main() -> int:
    logger = setup_hook_logging("presence-detection")

    input_data = read_json_from_stdin(logger)
    if input_data is None:
        return 0

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input") or {}

    if tool_name not in ("Edit", "Write", "MultiEdit"):
        logger.debug("跳過: 工具 %s 不在 Edit/Write/MultiEdit 範圍", tool_name)
        return 0

    file_path = tool_input.get("file_path", "")

    # 安全上游關鍵：無對應副檔名 profile → no-op（非目標語言專案不誤觸）
    profile = get_profile_for_path(file_path)
    if profile is None:
        logger.debug("跳過: 無對應 profile 的副檔名 %s", file_path)
        return 0

    if should_skip_file(file_path, profile):
        logger.info("跳過: 範圍外檔案（生成檔/測試/設施本體）%s", file_path)
        return 0

    changed_content = extract_changed_content(tool_name, tool_input)
    if not changed_content.strip():
        logger.debug("跳過: 無變更內容 %s", file_path)
        return 0

    violations = detect_violations(changed_content, profile)
    mode = os.environ.get("PRESENCE_HOOK_MODE", "block").strip().lower()

    logger.info(
        "presence_check: file=%s, profile=%s, tool=%s, violations=%d, mode=%s",
        file_path, profile.name, tool_name, len(violations), mode,
    )

    if not violations:
        return 0

    message = build_block_message(file_path, violations)

    if mode == "warn":
        logger.info("warn 模式：偵測到 %d 處但不阻擋", len(violations))
        print(message, file=sys.stderr)
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "permissionDecisionReason": "presence warn 模式：僅提示不阻擋",
            }
        }
        print(json.dumps(output, ensure_ascii=False))
        return 0

    # block 模式：阻擋並回饋 Claude
    print(message, file=sys.stderr)
    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": message,
        }
    }
    print(json.dumps(output, ensure_ascii=False))
    return 2


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "presence-detection"))
