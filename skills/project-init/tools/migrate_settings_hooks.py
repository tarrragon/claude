#!/usr/bin/env python3
"""Migration/reconciliation tool for settings.json hook registration form.

Invariant (canonical form): every hook `command` string in settings.json
must equal exactly one of:
  - "uv run --quiet <path> [trailing-args]"   (PEP 723 scripts)
  - "python3 <path> [trailing-args]"          (plain python3-shebang scripts)

Any other form — bare $CLAUDE_PROJECT_DIR path, "uv run <path>" missing
--quiet, or anything else — is non-canonical and rewritten (write mode) or
reported as a violation (--check mode). Classification (uv vs python3) is
always re-derived from the target script's own header (PEP 723 marker vs
python3 shebang), not from the existing command prefix, so drift in either
direction self-corrects. Fail-closed: any command whose target file cannot
be classified aborts the whole run with no write.

Idempotent: re-running against an already-canonical settings.json produces
no diff. Safe to re-run after new hooks are registered or when reconciling
future drift in hook registration form.

Usage:
    python3 migrate_settings_hooks.py          # rewrite non-canonical entries
    python3 migrate_settings_hooks.py --check  # reconciliation mode: report
                                                # non-canonical entries, exit
                                                # non-zero if any found, no write
"""
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
SETTINGS_PATH = PROJECT_ROOT / ".claude/settings.json"

PLACEHOLDER = "$CLAUDE_PROJECT_DIR"


def classify(abs_path: Path) -> str:
    """Return 'uv' or 'python3' for a hook script, or raise on ambiguity."""
    if not abs_path.exists():
        raise SystemExit(f"FATAL: hook script not found: {abs_path}")
    text = abs_path.read_text(errors="replace")
    lines = text.splitlines()
    head = "\n".join(lines[:40])
    has_pep723 = "# /// script" in head
    shebang = lines[0] if lines else ""
    is_python3_shebang = shebang.startswith("#!") and "python3" in shebang
    is_bash = shebang.startswith("#!") and ("bash" in shebang or "/sh" in shebang)

    if abs_path.suffix == ".sh" or is_bash:
        raise SystemExit(f"FATAL: non-python hook not covered by migration scope: {abs_path}")

    if has_pep723:
        return "uv"
    if is_python3_shebang:
        return "python3"
    raise SystemExit(f"FATAL: cannot classify hook script (no PEP723 marker, no python3 shebang): {abs_path}")


def canonical_form(kind: str, path_token: str, trailing: str) -> str:
    suffix = f" {trailing}" if trailing else ""
    if kind == "uv":
        return f"uv run --quiet {path_token}{suffix}"
    return f"python3 {path_token}{suffix}"


def extract_path_and_trailing(cmd: str):
    """Locate the $CLAUDE_PROJECT_DIR path token inside cmd regardless of
    whatever interpreter prefix (if any) currently precedes it."""
    idx = cmd.find(PLACEHOLDER)
    if idx == -1:
        raise SystemExit(f"FATAL: command has no {PLACEHOLDER} path: {cmd}")
    remainder = cmd[idx:]
    parts = remainder.split(" ", 1)
    path_token = parts[0]
    trailing = parts[1] if len(parts) > 1 else ""
    rel = path_token[len(PLACEHOLDER):]
    if rel.startswith("/"):
        rel = rel[1:]
    return path_token, rel, trailing


def rewrite_command(cmd: str) -> str:
    """Normalize cmd to its canonical form. Re-derives uv/python3 kind from
    the target script's own header every time (not from the existing
    command prefix), so this self-corrects drift in either direction."""
    cmd = cmd.strip()
    path_token, rel, trailing = extract_path_and_trailing(cmd)
    abs_path = PROJECT_ROOT / rel
    kind = classify(abs_path)
    return canonical_form(kind, path_token, trailing)


def walk_and_rewrite(hooks_obj):
    """Rewrite all commands in-place. Returns (stats, diffs) where diffs is
    a list of (event, old, new) tuples for entries that changed."""
    stats = {"uv": 0, "python3": 0, "unchanged": 0}
    diffs = []
    for event, entries in hooks_obj.items():
        for entry in entries:
            for hookdef in entry.get("hooks", []):
                old = hookdef["command"]
                new = rewrite_command(old)
                if new != old:
                    diffs.append((event, old, new))
                    if new.startswith("uv run"):
                        stats["uv"] += 1
                    else:
                        stats["python3"] += 1
                else:
                    stats["unchanged"] += 1
                hookdef["command"] = new
    return stats, diffs


def strip_commands(obj):
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k == "command":
                out[k] = "<STRIPPED>"
            else:
                out[k] = strip_commands(v)
        return out
    if isinstance(obj, list):
        return [strip_commands(v) for v in obj]
    return obj


def run_check(settings_path: Path) -> int:
    """Reconciliation mode: report non-canonical commands, write nothing.
    Returns process exit code (0 = all canonical, 1 = violations found)."""
    raw = settings_path.read_text()
    data = json.loads(raw)
    _, diffs = walk_and_rewrite(data["hooks"])  # data is a throwaway copy
    if diffs:
        print(f"FAIL: {len(diffs)} non-canonical hook command(s) found:")
        for event, old, new in diffs:
            print(f"  [{event}] {old!r} -> expected {new!r}")
        return 1
    print("OK: all hook commands are in canonical form")
    return 0


def run_migrate(settings_path: Path) -> int:
    raw = settings_path.read_text()
    data = json.loads(raw)
    before = json.loads(json.dumps(data))  # deep copy for structural diff

    stats, diffs = walk_and_rewrite(data["hooks"])

    # Structural comparison: only "command" strings inside hooks may differ;
    # everything else (event keys, matcher, order, timeout, other top-level
    # settings keys) must be byte-identical after normalizing commands.
    if strip_commands(before) != strip_commands(data):
        raise SystemExit("FATAL: structural diff detected beyond 'command' fields; aborting write")

    out_text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    settings_path.write_text(out_text)
    print(f"OK: uv={stats['uv']} python3={stats['python3']} unchanged={stats['unchanged']}")
    return 0


def main():
    check_mode = "--check" in sys.argv[1:]
    if check_mode:
        return run_check(SETTINGS_PATH)
    return run_migrate(SETTINGS_PATH)


if __name__ == "__main__":
    sys.exit(main())
