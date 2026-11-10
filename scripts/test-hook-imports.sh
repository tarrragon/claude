#!/usr/bin/env bash
# test-hook-imports.sh — Runtime smoke test for all hook Python scripts.
# Verifies that each hook can be imported without ModuleNotFoundError.
# Usage: bash .claude/scripts/test-hook-imports.sh [--verbose]
#
# Exit codes: 0 = all pass, 1 = failures found

set -euo pipefail

CLAUDE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PROJECT_ROOT="$(cd "$CLAUDE_DIR/.." && pwd)"
VERBOSE="${1:-}"

pass=0
fail=0
fail_list=()

test_hook() {
    local hook_path="$1"
    local rel_path="${hook_path#$PROJECT_ROOT/}"

    # Feed minimal JSON to stdin; capture stderr for import errors.
    # Timeout 5s to avoid hooks that block on input.
    local stderr_output
    stderr_output=$(echo '{}' | timeout 5 python3 "$hook_path" 2>&1 >/dev/null) || true

    if echo "$stderr_output" | grep -qE "ModuleNotFoundError|ImportError|NameError.*is not defined"; then
        fail=$((fail + 1))
        fail_list+=("$rel_path")
        if [[ "$VERBOSE" == "--verbose" ]]; then
            echo "[FAIL] $rel_path"
            echo "       $(echo "$stderr_output" | grep -E "ModuleNotFoundError|ImportError|NameError" | head -1)"
        else
            echo "[FAIL] $rel_path"
        fi
    else
        pass=$((pass + 1))
        if [[ "$VERBOSE" == "--verbose" ]]; then
            echo "[PASS] $rel_path"
        fi
    fi
}

echo "=== Hook Import Smoke Test ==="
echo "Project: $PROJECT_ROOT"
echo ""

# Main hooks
echo "--- Main hooks (.claude/hooks/*.py) ---"
for hook in "$CLAUDE_DIR"/hooks/*.py; do
    [[ -f "$hook" ]] || continue
    # Skip __init__.py and test files
    [[ "$(basename "$hook")" == "__init__.py" ]] && continue
    [[ "$(basename "$hook")" == "eval_pyyaml.py" ]] && continue
    test_hook "$hook"
done

echo ""
echo "--- Skill hooks (.claude/skills/*/hooks/*.py) ---"
# Skill hooks (use process substitution to avoid subshell counter loss)
while IFS= read -r hook; do
    [[ -f "$hook" ]] || continue
    [[ "$(basename "$hook")" == "__init__.py" ]] && continue
    test_hook "$hook"
done < <(find "$CLAUDE_DIR/skills" -path "*/hooks/*.py" -name "*hook*" 2>/dev/null | sort)

echo ""
echo "=== Results ==="
total=$((pass + fail))
echo "Total: $total | Pass: $pass | Fail: $fail"

if [[ ${#fail_list[@]} -gt 0 ]]; then
    echo ""
    echo "Failed hooks:"
    for f in "${fail_list[@]}"; do
        echo "  - $f"
    done
    exit 1
else
    echo "All hooks passed import check."
    exit 0
fi
