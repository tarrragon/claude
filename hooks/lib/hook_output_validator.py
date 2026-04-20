#!/usr/bin/env python3
"""Validate PostToolUse/PreToolUse Hook stdout JSON schema (IMP-055 regression guard).

功能：
- 從 .claude/settings.json 解析 PreToolUse / PostToolUse Hook 路徑
- 對每個 Hook 以 dummy input 執行（echo JSON | python3 HOOK.py）
- 驗證 stdout 符合規範：空輸出 OR 完整 {"hookSpecificOutput": {"hookEventName": "..."}}
- 列出所有 FAIL 的 Hook 與原因

使用方式：
    python3 .claude/hooks/lib/hook_output_validator.py
    python3 .claude/hooks/lib/hook_output_validator.py --hook .claude/hooks/foo.py
    python3 .claude/hooks/lib/hook_output_validator.py --verbose

規範來源：IMP-055 (.claude/error-patterns/implementation/IMP-055-hook-stdout-plain-text-breaks-json-validation.md)

合法 stdout 型態：
    1. 完全空字串（hook 選擇不輸出 = 靜默通過）
    2. JSON 物件含完整 {"hookSpecificOutput": {"hookEventName": "<EventName>", ...}}
    3. JSON 物件僅含頂層協議欄位（continue/decision/reason/stopReason/suppressOutput/systemMessage）

失敗變體：
    - 純文字 print()
    - 半結構化 {"additionalContext": "..."}（缺 hookSpecificOutput 包裹）
    - {"hookSpecificOutput": {}}（缺 hookEventName）
    - hookEventName 與註冊事件不符
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SETTINGS_PATH = PROJECT_ROOT / ".claude" / "settings.json"

# Hook events whose stdout MUST be JSON with hookSpecificOutput schema
JSON_SCHEMA_EVENTS = {"PreToolUse", "PostToolUse"}

# Dummy stdin payload（PostToolUse/PreToolUse 皆可吃）
DUMMY_STDIN = json.dumps({
    "tool_name": "Bash",
    "tool_input": {"command": "echo test"},
    "tool_response": {"stdout": "", "stderr": "", "exit_code": 0},
    "session_id": "validate-hook-schema-dummy",
    "cwd": str(PROJECT_ROOT),
})

# 環境變數替換表（settings.json command 中的 $VAR 展開）
ENV_SUBSTITUTIONS = {
    "CLAUDE_PROJECT_DIR": str(PROJECT_ROOT),
    "CLAUDE_FILE_PATH": str(PROJECT_ROOT / "CLAUDE.md"),
}

# 頂層協議允許欄位（Claude Code 官方認可）
ALLOWED_TOPLEVEL_FIELDS = {
    "continue",
    "stopReason",
    "suppressOutput",
    "decision",
    "reason",
    "systemMessage",
    "hookSpecificOutput",
}


def resolve_command(cmd: str) -> list[str]:
    """Resolve $VAR references and split into argv."""
    for var, value in ENV_SUBSTITUTIONS.items():
        cmd = cmd.replace(f"${var}", value)
    return shlex.split(cmd)


def load_target_hooks() -> list[tuple[str, str, str]]:
    """Return list of (event_name, matcher, hook_command) for JSON-schema events."""
    with SETTINGS_PATH.open("r", encoding="utf-8") as f:
        settings = json.load(f)

    hooks_config = settings.get("hooks", {})
    results: list[tuple[str, str, str]] = []

    for event_name, event_entries in hooks_config.items():
        if event_name not in JSON_SCHEMA_EVENTS:
            continue
        for entry in event_entries:
            matcher = entry.get("matcher", "*")
            for hook_def in entry.get("hooks", []):
                cmd = hook_def.get("command", "")
                if cmd:
                    results.append((event_name, matcher, cmd))
    return results


def validate_stdout(stdout: str, event_name: str) -> tuple[bool, str]:
    """Validate hook stdout. Return (passed, reason)."""
    stripped = stdout.strip()
    if not stripped:
        return True, "empty stdout (silent pass)"

    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError as e:
        preview = stripped[:100].replace("\n", " ")
        return False, f"stdout 不是合法 JSON: {e.msg} (content={preview!r})"

    if not isinstance(parsed, dict):
        return False, f"stdout JSON root 必須是 object，得到 {type(parsed).__name__}"

    # 檢查禁止的半結構化變體：最外層出現 additionalContext（IMP-055 主要失敗模式）
    if "additionalContext" in parsed and "hookSpecificOutput" not in parsed:
        return False, "additionalContext 必須包在 hookSpecificOutput 內（IMP-055）"

    # 檢查未知頂層欄位
    unknown = set(parsed.keys()) - ALLOWED_TOPLEVEL_FIELDS
    if unknown:
        return False, f"stdout 含未知頂層欄位 {sorted(unknown)}（合法欄位：{sorted(ALLOWED_TOPLEVEL_FIELDS)}）"

    hso = parsed.get("hookSpecificOutput")
    if hso is None:
        return True, "only top-level protocol fields, no hookSpecificOutput"

    if not isinstance(hso, dict):
        return False, f"hookSpecificOutput 必須是 object，得到 {type(hso).__name__}"

    hen = hso.get("hookEventName")
    if hen is None:
        return False, "hookSpecificOutput 缺 hookEventName 欄位（IMP-055）"
    if hen != event_name:
        return False, f"hookEventName={hen!r} 與註冊事件 {event_name!r} 不符"

    return True, f"valid schema (hookEventName={hen!r})"


def run_hook(cmd: str) -> tuple[int, str, str]:
    """Run hook with dummy stdin. Return (returncode, stdout, stderr)."""
    try:
        argv = resolve_command(cmd)
    except ValueError as e:
        return -4, "", f"[CMD PARSE ERROR] {e}"

    try:
        proc = subprocess.run(
            argv,
            input=DUMMY_STDIN,
            capture_output=True,
            text=True,
            timeout=15,
            cwd=str(PROJECT_ROOT),
            env={**os.environ, **ENV_SUBSTITUTIONS},
        )
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "[TIMEOUT after 15s]"
    except FileNotFoundError as e:
        return -2, "", f"[FILE NOT FOUND] {e}"
    except Exception as e:
        return -3, "", f"[EXEC ERROR] {type(e).__name__}: {e}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--hook", help="只驗證單一 hook 路徑（事件預設為 PostToolUse）")
    parser.add_argument("--event", default="PostToolUse", choices=sorted(JSON_SCHEMA_EVENTS),
                        help="搭配 --hook 使用，指定事件名稱")
    parser.add_argument("--verbose", "-v", action="store_true", help="顯示每個 hook 的 stdout/stderr")
    args = parser.parse_args()

    if args.hook:
        targets = [(args.event, "*", args.hook)]
    else:
        targets = load_target_hooks()

    print(f"[INFO] Validating {len(targets)} hook registrations against JSON schema...")
    print(f"[INFO] Project root: {PROJECT_ROOT}")
    print()

    results: list[dict] = []
    pass_count = 0
    fail_count = 0
    seen: set[tuple[str, str]] = set()

    for event_name, matcher, cmd in targets:
        key = (event_name, cmd)
        if key in seen:
            continue
        seen.add(key)

        try:
            hook_path = resolve_command(cmd)[0] if cmd else "<empty>"
        except ValueError:
            hook_path = cmd
        hook_name = Path(hook_path).name

        rc, stdout, stderr = run_hook(cmd)

        if rc < 0:
            passed, reason = False, stderr.strip() or f"exit code {rc}"
        else:
            passed, reason = validate_stdout(stdout, event_name)

        if passed:
            pass_count += 1
        else:
            fail_count += 1

        results.append({
            "event": event_name,
            "matcher": matcher,
            "hook": hook_name,
            "command": cmd,
            "passed": passed,
            "reason": reason,
            "returncode": rc,
            "stdout": stdout,
            "stderr": stderr,
        })

        marker = "[OK]  " if passed else "[FAIL]"
        print(f"{marker} {event_name}:{matcher:20s} {hook_name:55s} -> {reason}")
        if args.verbose or not passed:
            if stdout.strip():
                preview = stdout.strip()[:200].replace("\n", " ")
                print(f"        stdout: {preview!r}")
            if stderr.strip() and (args.verbose or not passed):
                preview = stderr.strip()[:200].replace("\n", " ")
                print(f"        stderr: {preview!r}")

    print()
    print(f"[SUMMARY] total={len(seen)} pass={pass_count} fail={fail_count}")

    if fail_count > 0:
        print()
        print("[FAILED HOOKS]")
        for r in results:
            if not r["passed"]:
                print(f"  - {r['event']}:{r['matcher']} {r['hook']}")
                print(f"      reason: {r['reason']}")

    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
