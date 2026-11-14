#!/usr/bin/env bash
# test-hook-imports.sh — Runtime smoke test for all hook Python scripts.
# Verifies that each hook can be imported without ModuleNotFoundError.
# Loads each hook as a module (no __main__ run) with a python-side timeout;
# hooks that could not be executed at all (rc 126/127) are reported as failures.
# Usage: bash .claude/scripts/test-hook-imports.sh [--verbose]
#
# Exit codes: 0 = all pass, 1 = failures found

set -euo pipefail

CLAUDE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PROJECT_ROOT="$(cd "$CLAUDE_DIR/.." && pwd)"
VERBOSE="${1:-}"

pass=0
fail=0
undetermined=0
undetermined_list=()
fail_list=()

# 只載入模組（執行 module-level 程式碼），不以 __main__ 執行 hook 主流程：
# 主流程以假 payload 執行會產生副作用（寫日誌、安裝 shim 等），而本腳本只需要 import 結果。
# 逾時由 python 自己控制，不依賴 timeout 指令（macOS 預設沒有，缺指令時每支 hook
# 都以 command not found 結束、stderr 不含 import 錯誤，舊版因此全數回報通過）。
IMPORT_TIMEOUT_SECONDS=5
INTERPRETER_CACHE_DIR="$(mktemp -d)"
# 保留原結束碼：腳本中途出錯時不可讓清理動作把結束碼改成 0
trap 'status=$?; rm -rf "${INTERPRETER_CACHE_DIR}"; exit "${status}"' EXIT
# hook 檔頭含 PEP 723 dependencies 時，依宣告經 uv 帶依賴載入（與 runtime 的 uv run 一致）；
# 以系統 python3 直接載入會把宣告的依賴誤報為缺 import。
read -r -d '' IMPORT_DRIVER <<'PY' || true
import os, re, shutil, subprocess, sys
LOADER = (
    "import importlib.util, sys\n"
    "spec = importlib.util.spec_from_file_location('hook_under_test', sys.argv[1])\n"
    "module = importlib.util.module_from_spec(spec)\n"
    "spec.loader.exec_module(module)\n"
)
PEP723 = re.compile(r"^# /// script\s*$(.*?)^# ///\s*$", re.M | re.S)

def declared_dependencies(path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        match = PEP723.search(fh.read(4096))
    if not match:
        return []
    body = "\n".join(line[2:] if line.startswith("# ") else line.lstrip("#")
                     for line in match.group(1).splitlines())
    try:
        import tomllib  # PEP 723 參考實作的解析方式；依賴字串可含巢狀引號（環境標記）
        return list(tomllib.loads(body).get("dependencies", []))
    except ImportError:  # Python < 3.11：退回只取雙引號字串
        deps = re.search(r"dependencies\s*=\s*\[(.*?)\]", body, re.S)
        return re.findall(r"\"([^\"]+)\"", deps.group(1)) if deps else []

UNDETERMINED_EXIT = 3
UNDETERMINED_PREFIX = "UNDETERMINED:"

def undetermined(reason, cache_file):
    """依賴環境建不起來（uv 不存在、離線、解析失敗）：與 import 斷裂分開，歸為無法判定。

    同一組依賴的結果寫入快取，後續 hook 不重試 uv。
    """
    if cache_file:
        with open(cache_file, "w", encoding="utf-8") as fh:
            fh.write(UNDETERMINED_PREFIX + reason)
    sys.stderr.write(reason + "\n")
    sys.exit(UNDETERMINED_EXIT)

def interpreter_for(deps, cache_dir, timeout):
    """同一組依賴只經 uv 解析一次直譯器路徑，結果快取於 cache_dir（每支 hook 都跑 uv 會超過 sync-pull 的逾時）。"""
    key = re.sub(r"[^A-Za-z0-9._-]", "_", "+".join(sorted(deps)))
    cache_file = os.path.join(cache_dir, key) if cache_dir else None
    if cache_file and os.path.exists(cache_file):
        with open(cache_file, encoding="utf-8") as fh:
            cached = fh.read().strip()
        if cached.startswith(UNDETERMINED_PREFIX):
            undetermined(cached[len(UNDETERMINED_PREFIX):], None)
        return cached
    uv = shutil.which("uv")
    if not uv:
        undetermined("找不到 uv，無法依 PEP 723 宣告載入依賴", cache_file)
    cmd = [uv, "run", "--quiet", "--no-project"]
    for dep in deps:
        cmd += ["--with", dep]
    cmd += ["python", "-c", "import sys; print(sys.executable)"]
    try:
        proc = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True,
                              text=True, timeout=max(timeout, 60))
    except subprocess.TimeoutExpired:
        undetermined("uv 解析依賴逾時 {}".format(deps), cache_file)
    if proc.returncode != 0 or not proc.stdout.strip():
        detail = (proc.stderr.strip().splitlines() or [""])[-1]
        undetermined("uv 解析依賴失敗 rc={}（離線或套件不存在）: {}".format(proc.returncode, detail), cache_file)
    interpreter = proc.stdout.strip().splitlines()[-1]
    if cache_file:
        with open(cache_file, "w", encoding="utf-8") as fh:
            fh.write(interpreter)
    return interpreter

timeout = float(sys.argv[2])
deps = declared_dependencies(sys.argv[1])
interpreter = interpreter_for(deps, sys.argv[3] if len(sys.argv) > 3 else "", timeout) if deps else sys.executable
cmd = [interpreter, "-c", LOADER, sys.argv[1]]
try:
    proc = subprocess.run(
        cmd,
        stdin=subprocess.DEVNULL, capture_output=True, text=True,
        timeout=timeout,
    )
except subprocess.TimeoutExpired:
    sys.stderr.write("IMPORT_TIMEOUT\n")
    sys.exit(124)
sys.stderr.write(proc.stderr)
sys.exit(proc.returncode)
PY

test_hook() {
    local hook_path="$1"
    local rel_path="${hook_path#$PROJECT_ROOT/}"

    local stderr_output rc=0
    stderr_output=$(python3 -c "$IMPORT_DRIVER" "$hook_path" "$IMPORT_TIMEOUT_SECONDS" "$INTERPRETER_CACHE_DIR" 2>&1 >/dev/null) || rc=$?

    # 3：依賴環境建不起來（uv 不存在、離線、解析失敗），無法判定 import 是否正常；
    # 不算通過也不算 import 斷裂，示警後跳過（離線 consumer 不可因此每次 sync-pull 都失敗）
    if [[ $rc -eq 3 ]]; then
        local reason
        reason="$(echo "$stderr_output" | head -1)"
        undetermined=$((undetermined + 1))
        undetermined_list+=("${rel_path}: ${reason}")
        echo "[SKIP] ${rel_path} (無法判定：${reason})"
        return
    fi

    # 126/127：直譯器或指令不存在，hook 根本沒被載入，不可當成通過
    if [[ $rc -eq 126 || $rc -eq 127 ]]; then
        fail=$((fail + 1))
        # 變數一律加大括號：UTF-8 locale 下 bash 會把緊接的全形字元讀進變數名
        fail_list+=("${rel_path} (未執行 rc=${rc})")
        echo "[FAIL] ${rel_path} (未執行，rc=${rc})"
        if [[ "$VERBOSE" == "--verbose" ]]; then
            echo "       $(echo "$stderr_output" | head -1)"
        fi
        return
    fi

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
    # pytest 支援檔，不是 hook，執行期由 pytest 載入
    [[ "$(basename "$hook")" == "conftest.py" ]] && continue
    [[ "$(basename "$hook")" == "testpaths_coverage_warning.py" ]] && continue
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
total=$((pass + fail + undetermined))
echo "Total: ${total} | Pass: ${pass} | Fail: ${fail} | Undetermined: ${undetermined}"

if [[ ${#fail_list[@]} -gt 0 ]]; then
    echo ""
    echo "Failed hooks:"
    for f in "${fail_list[@]}"; do
        echo "  - $f"
    done
    exit 1
elif [[ ${#undetermined_list[@]} -gt 0 ]]; then
    echo ""
    echo "Hook import check incomplete: ${undetermined} hook(s) undetermined (dependency environment unavailable)."
    for u in "${undetermined_list[@]}"; do
        echo "  - ${u}"
    done
    echo "[WARNING] ${undetermined} 支 hook 未驗證 import，不代表通過；需要 uv 與可解析的依賴才能檢查" >&2
    exit 0
else
    echo "All hooks passed import check."
    exit 0
fi
