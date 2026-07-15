"""uc 子命令群組 — UC 編號治理：list/verify/trace/context/acceptance-check。

規則來源：docs/spec/uc-numbering-convention.md（SSOT 解析規則第 3 節、豁免範圍第 5 節）。
白名單解析與豁免判定共用 doc_system.core.uc_registry，避免與 PreToolUse 寫入驗證 hook 各自實作導致規則漂移。
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from doc_system.core.file_locator import FileLocator
from doc_system.core.frontmatter_parser import parse_frontmatter_text
from doc_system.core.uc_registry import (
    CLI_SCANNABLE_EXTENSIONS,
    VALID_UC_FORMAT_RE,
    USE_CASES_SPEC_RELATIVE_PATH,
    check_fingerprints,
    find_uc_tokens_in_text,
    get_fingerprint_sidecar_path,
    get_uc_summary,
    get_valid_uc_map,
    is_exempt_path,
    is_violation_token,
    normalize_token,
    parse_ssot,
    update_fingerprints,
)

# 掃描時納入檢查的副檔名（含文件/設定檔，CLI 為全量掃描工具，範圍大於
# hook 的即時攔截；兩者差異理由與單點定義見 uc_registry.CLI_SCANNABLE_EXTENSIONS /
# HOOK_SCANNABLE_EXTENSIONS 註解）
SCANNABLE_EXTENSIONS = CLI_SCANNABLE_EXTENSIONS

# 掃描時排除的目錄（建置產物、依賴、VCS 內部目錄）
EXCLUDED_DIRS = {
    ".git",
    "__pycache__",
    ".venv",
    "node_modules",
    "build",
    ".dart_tool",
    "ios",
    "android",
    "Pods",
    ".claude",
}

# uc context / uc trace 輸出的 code 引用上限
MAX_REFERENCE_HITS = 10

# uc trace 預設輸出筆數上限（避免單次輸出過大燒 agent context，可用 --all 或 --limit 調整）
DEFAULT_TRACE_LIMIT = 20

# uc trace 輸出的語意分組順序：lib（實作）優先於 test/docs，避免命中被文件淹沒
TRACE_GROUP_ORDER = ("lib", "test", "docs", "other")

# ticket CLI 逾時秒數（context 解析 ticket-id 時使用）
TICKET_CLI_TIMEOUT_SECONDS = 10


def _iter_scannable_files(path: str) -> list[str]:
    """列出路徑下（單檔或遞迴目錄）所有可掃描的檔案，排除建置產物目錄。"""
    root = Path(path)
    if root.is_file():
        return [str(root)]
    if not root.is_dir():
        return []

    files: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        # 排除隱藏目錄（.git、.venv、備份目錄等）與已知建置產物目錄
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS and not d.startswith(".")]
        for filename in filenames:
            if filename.lower().endswith(SCANNABLE_EXTENSIONS):
                files.append(os.path.join(dirpath, filename))
    return sorted(files)


def _scan_project_for_uc(uc_id: str, project_root: str) -> list[tuple[str, int, str]]:
    """掃描整個專案，找出所有引用指定 UC 編號的位置（不套用 verify 的路徑豁免）。

    排除 SSOT 檔案自身（其標題行必然包含 UC 編號，屬定義而非「引用」）。
    """
    ssot_abs = str(Path(project_root) / USE_CASES_SPEC_RELATIVE_PATH)
    hits: list[tuple[str, int, str]] = []
    for file_path in _iter_scannable_files(project_root):
        if file_path == ssot_abs:
            continue
        try:
            with open(file_path, encoding="utf-8") as f:
                lines = f.read().splitlines()
        except (OSError, UnicodeDecodeError) as e:
            print(f"[uc] 略過無法讀取的檔案 {file_path}: {e}", file=sys.stderr)
            continue
        for lineno, line in enumerate(lines, start=1):
            for token, _ in find_uc_tokens_in_text(line):
                if normalize_token(token) == uc_id:
                    rel = os.path.relpath(file_path, project_root)
                    hits.append((rel, lineno, line.strip()))
    return hits


def _classify_trace_group(rel_path: str) -> str:
    """依路徑第一層目錄分類，用於 trace 輸出語意分組（lib 優先）。"""
    top = rel_path.split(os.sep, 1)[0] if rel_path else ""
    if top == "lib":
        return "lib"
    if top in ("test", "tests"):
        return "test"
    if top == "docs":
        return "docs"
    return "other"


def _group_trace_hits(
    hits: list[tuple[str, int, str]],
) -> list[tuple[str, list[tuple[str, int, str]]]]:
    """將引用位置依語意分組並依 TRACE_GROUP_ORDER 排序，空群組不輸出。"""
    groups: dict[str, list[tuple[str, int, str]]] = {g: [] for g in TRACE_GROUP_ORDER}
    for hit in hits:
        groups[_classify_trace_group(hit[0])].append(hit)
    return [(g, groups[g]) for g in TRACE_GROUP_ORDER if groups[g]]


def _fetch_ticket_full(ticket_id: str) -> tuple[str | None, str | None]:
    """呼叫 ticket track full，回傳 (stdout, error_reason)。

    共用 subprocess 呼叫 + 錯誤分類，供 _resolve_ticket_uc_ids 和
    _get_ticket_acceptance 複用。
    """
    try:
        result = subprocess.run(
            ["ticket", "track", "full", ticket_id],
            capture_output=True,
            text=True,
            timeout=TICKET_CLI_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return None, "timeout"
    except OSError:
        return None, "cli_error"
    if result.returncode != 0:
        return None, "not_found"
    return result.stdout, None


def _resolve_ticket_uc_ids(
    ticket_id: str, valid: dict[str, str]
) -> tuple[list[str], str | None]:
    """從 ticket 內容（frontmatter + body）解析出合法 UC 引用，依出現順序去重。

    回傳 (uc_ids, error_reason)：error_reason 為 None 表示查詢成功（即使結果為空），
    否則為 "timeout" / "cli_error" / "not_found" 供呼叫端區分故障原因並給出對應訊息。
    """
    stdout, error_reason = _fetch_ticket_full(ticket_id)
    if error_reason:
        _labels = {"timeout": "查詢逾時", "cli_error": "執行失敗", "not_found": "查詢失敗"}
        print(
            f"[uc context] ticket {ticket_id} {_labels.get(error_reason, error_reason)}",
            file=sys.stderr,
        )
        return [], error_reason

    found: list[str] = []
    seen: set[str] = set()
    for token, _lineno in find_uc_tokens_in_text(stdout):
        uc_id = normalize_token(token)
        if VALID_UC_FORMAT_RE.match(uc_id) and uc_id in valid and uc_id not in seen:
            seen.add(uc_id)
            found.append(uc_id)
    return found, None


def _print_uc_context(uc_id: str, ssot: dict[str, dict], project_root: str) -> None:
    """輸出單一 UC 的標題、spec 位置與 code 引用 top-N。"""
    info = ssot[uc_id]
    print(f"=== {uc_id}: {info['title']} ===")
    print(f"Spec 位置: {USE_CASES_SPEC_RELATIVE_PATH}:{info['line']}")

    hits = _scan_project_for_uc(uc_id, project_root)[:MAX_REFERENCE_HITS]
    print(f"Code 引用（前 {len(hits)} 筆）:")
    if not hits:
        print("  （無引用）")
        return
    for rel, lineno, context in hits:
        print(f"  {rel}:{lineno}: {context}")


def _cmd_list(args: argparse.Namespace) -> None:
    """列出所有合法 UC 編號與標題。"""
    project_root = FileLocator.get_project_root()
    valid = get_valid_uc_map(project_root)
    if not valid:
        print(f"找不到任何合法 UC 定義（SSOT 檔案缺失：{USE_CASES_SPEC_RELATIVE_PATH}）。")
        return

    print(f"{'UC 編號':<10} 標題")
    print("-" * 50)
    for uc_id in sorted(valid.keys()):
        print(f"{uc_id:<10} {valid[uc_id]}")


def _cmd_verify(args: argparse.Namespace) -> None:
    """驗證指定路徑（或整個專案）內 UC token 是否符合白名單，違規則 exit 1。

    環境/參數錯誤（路徑不存在、白名單解析為空）視為 fail-fast，exit 2，
    與 violation（exit 1）區分，避免假綠燈或誤導性全違規清單。
    """
    project_root = FileLocator.get_project_root()
    target = args.path or project_root

    if args.path and not Path(target).exists():
        print(f"錯誤：指定路徑不存在: {target}", file=sys.stderr)
        sys.exit(2)

    valid = get_valid_uc_map(project_root)
    if not valid:
        print(
            f"錯誤：合法 UC 白名單為空（SSOT 解析結果為空: {USE_CASES_SPEC_RELATIVE_PATH}），"
            "無法驗證，中止以避免誤導性全違規清單。",
            file=sys.stderr,
        )
        sys.exit(2)

    violations: list[tuple[str, int, str]] = []
    for file_path in _iter_scannable_files(target):
        if is_exempt_path(file_path, project_root):
            continue
        try:
            with open(file_path, encoding="utf-8") as f:
                text = f.read()
        except (OSError, UnicodeDecodeError) as e:
            print(f"[uc] 略過無法讀取的檔案 {file_path}: {e}", file=sys.stderr)
            continue
        for token, lineno in find_uc_tokens_in_text(text):
            if is_violation_token(token, valid):
                rel = os.path.relpath(file_path, project_root)
                violations.append((rel, lineno, normalize_token(token)))

    if not violations:
        print("UC 編號驗證通過，無違規 token。")
        sys.exit(0)

    print(f"發現 {len(violations)} 處違規 UC 編號:")
    for rel, lineno, token in violations:
        print(f"{rel}:{lineno}:{token}")
    sys.exit(1)


def _cmd_trace(args: argparse.Namespace) -> None:
    """列出指定 UC 編號的所有 code 引用位置，預設截斷 + 依 lib/test/docs 分組（lib 優先）。"""
    project_root = FileLocator.get_project_root()
    valid = get_valid_uc_map(project_root)
    uc_id = normalize_token(args.uc_id)

    if uc_id not in valid:
        print(f"找不到合法 UC 編號: {args.uc_id}（執行 `doc uc list` 查看合法清單）")
        sys.exit(1)

    hits = _scan_project_for_uc(uc_id, project_root)
    if not hits:
        print(f"{uc_id} 目前無任何 code 引用。")
        return

    show_all = getattr(args, "all", False)
    limit = getattr(args, "limit", None) or DEFAULT_TRACE_LIMIT
    total = len(hits)
    display_hits = hits if show_all else hits[:limit]

    print(f"=== {uc_id} 引用位置（共 {total} 筆）===")
    for group_name, group_hits in _group_trace_hits(display_hits):
        print(f"-- {group_name} --")
        for rel, lineno, context in group_hits:
            print(f"  {rel}:{lineno}: {context}")

    if not show_all and total > len(display_hits):
        print(
            f"（顯示 {len(display_hits)}/{total} 筆，加 --all 看全部，或 --limit N 調整數量）"
        )


def _cmd_context(args: argparse.Namespace) -> None:
    """輸出 UC 編號或 ticket ID 對應的定位資訊（標題+spec 位置+code 引用 top-N）。"""
    project_root = FileLocator.get_project_root()
    ssot = parse_ssot(project_root)
    target = args.target

    if VALID_UC_FORMAT_RE.match(normalize_token(target)):
        uc_id = normalize_token(target)
        if uc_id not in ssot:
            print(f"找不到合法 UC 編號: {target}（執行 `doc uc list` 查看合法清單）")
            sys.exit(1)
        _print_uc_context(uc_id, ssot, project_root)
        return

    uc_ids, error_reason = _resolve_ticket_uc_ids(
        target, {k: v["title"] for k, v in ssot.items()}
    )
    if not uc_ids:
        if error_reason == "timeout":
            print(f"ticket {target} 查詢逾時，請確認 ticket CLI 是否正常運作。")
        elif error_reason == "cli_error":
            print(f"ticket {target} 查詢失敗（ticket CLI 執行錯誤），請確認 ticket CLI 是否可用。")
        elif error_reason == "not_found":
            print(f"ticket {target} 不存在或查詢失敗（ticket CLI 回傳非零結果）。")
        else:
            print(f"ticket {target} 未找到有效 UC 引用（執行 `doc uc list` 查看合法清單）。")
        sys.exit(1)

    for uc_id in uc_ids:
        _print_uc_context(uc_id, ssot, project_root)


def _cmd_summary(args: argparse.Namespace) -> None:
    """輸出單一 UC 的標題+spec 位置+主流程摘要（供 Context Bundle 自動注入呼叫）。"""
    project_root = FileLocator.get_project_root()
    uc_id = normalize_token(args.uc_id)
    summary = get_uc_summary(uc_id, project_root)

    if summary is None:
        print(
            f"找不到合法 UC 編號: {args.uc_id}（執行 `doc uc list` 查看合法清單）",
            file=sys.stderr,
        )
        sys.exit(1)

    if getattr(args, "json", False):
        print(json.dumps(summary, ensure_ascii=False))
        return

    print(f"=== {summary['uc_id']}: {summary['title']} ===")
    print(f"Spec 位置: {summary['spec_path']}:{summary['spec_line']}")
    if not summary["main_flow"]:
        print("主要流程:")
        print("  （無主要流程步驟）")
        return
    if summary["is_section_summary"]:
        print("章節摘要（無「主要成功場景」，非主流程）:")
    else:
        print("主要流程:")
    for step in summary["main_flow"]:
        print(f"  {step}")


def _cmd_fingerprint_update(args: argparse.Namespace) -> None:
    """計算並寫入所有 UC 的內容指紋到 sidecar JSON。"""
    project_root = FileLocator.get_project_root()
    fingerprints = update_fingerprints(project_root)
    if not fingerprints:
        print(
            f"SSOT 解析結果為空（{USE_CASES_SPEC_RELATIVE_PATH}），無法計算指紋。",
            file=sys.stderr,
        )
        sys.exit(1)
    sidecar = get_fingerprint_sidecar_path(project_root)
    print(f"已更新 {len(fingerprints)} 個 UC 指紋 → {sidecar.name}")
    for uc_id in sorted(fingerprints):
        fp = fingerprints[uc_id]["fingerprint"][:12]
        print(f"  {uc_id}: {fp}...")


def _cmd_fingerprint_check(args: argparse.Namespace) -> None:
    """比對 sidecar 指紋與當前 spec 內容，列出漂移的 UC。"""
    project_root = FileLocator.get_project_root()
    sidecar = get_fingerprint_sidecar_path(project_root)
    if not sidecar.is_file():
        print("指紋 sidecar 不存在，請先執行 `doc uc fingerprint update`。")
        sys.exit(1)

    drifted, added, removed = check_fingerprints(project_root)

    if not drifted and not added and not removed:
        print("所有 UC 指紋一致，無漂移。")
        return

    if drifted:
        print(f"[漂移] {len(drifted)} 個 UC 內容已變更:")
        for uc_id in drifted:
            print(f"  {uc_id}")
    if added:
        print(f"[新增] {len(added)} 個 UC 未在指紋記錄中:")
        for uc_id in added:
            print(f"  {uc_id}")
    if removed:
        print(f"[移除] {len(removed)} 個 UC 已從 SSOT 中消失:")
        for uc_id in removed:
            print(f"  {uc_id}")

    print("\n執行 `doc uc fingerprint update` 以更新指紋。")
    sys.exit(1)


def _cmd_fingerprint(args: argparse.Namespace) -> None:
    """uc fingerprint 子命令路由。"""
    fp_cmd = getattr(args, "fp_command", None)
    _FP_HANDLERS = {
        "update": _cmd_fingerprint_update,
        "check": _cmd_fingerprint_check,
    }
    handler = _FP_HANDLERS.get(fp_cmd) if fp_cmd else None
    if handler is None:
        print("用法: doc uc fingerprint {update,check}")
        print("  update  計算並寫入 UC 內容指紋到 sidecar JSON")
        print("  check   比對指紋，列出漂移的 UC")
        sys.exit(1)
    handler(args)


def _get_ticket_acceptance(ticket_id: str) -> tuple[list[str], str | None]:
    """從 ticket frontmatter 提取 acceptance 清單。

    回傳 (acceptance_items, error_reason)：error_reason 為 None 表示成功。
    複用 _fetch_ticket_full（subprocess）和 parse_frontmatter_text（YAML 解析）。
    """
    stdout, error_reason = _fetch_ticket_full(ticket_id)
    if error_reason:
        return [], error_reason

    data = parse_frontmatter_text(stdout)
    if data is None:
        return [], "no_frontmatter"

    acceptance = data.get("acceptance", []) or []
    return [str(item) for item in acceptance], None


def _cmd_acceptance_check(args: argparse.Namespace) -> None:
    """解析 ticket acceptance 中的 UC token，檢查 SSOT 存在性 + 指紋漂移。"""
    project_root = FileLocator.get_project_root()
    ticket_id = args.ticket_id
    as_json = getattr(args, "json", False)

    acceptance, error_reason = _get_ticket_acceptance(ticket_id)
    if error_reason:
        _error_messages = {
            "timeout": f"ticket CLI 查詢逾時（{TICKET_CLI_TIMEOUT_SECONDS}s）: {ticket_id}，請確認 ticket CLI 可正常執行",
            "cli_error": f"ticket CLI 執行失敗: {ticket_id}，請確認 ticket CLI 已安裝",
            "not_found": f"ticket {ticket_id} 不存在或查詢失敗，請確認 ticket ID 正確",
            "no_frontmatter": f"ticket {ticket_id} 輸出無 YAML frontmatter，請確認 ticket 檔案格式正確",
        }
        msg = _error_messages.get(error_reason, f"未知錯誤: {error_reason}")
        if as_json:
            print(json.dumps({"ticket_id": ticket_id, "error": msg, "exit_code": 2}, ensure_ascii=False))
        else:
            print(f"錯誤：{msg}", file=sys.stderr)
        sys.exit(2)

    acceptance_text = "\n".join(acceptance)
    uc_tokens: list[str] = []
    seen: set[str] = set()
    for token, _lineno in find_uc_tokens_in_text(acceptance_text):
        uc_id = normalize_token(token)
        if uc_id not in seen:
            seen.add(uc_id)
            uc_tokens.append(uc_id)

    if not uc_tokens:
        if as_json:
            print(json.dumps({
                "ticket_id": ticket_id,
                "results": [],
                "summary": {"pass": 0, "drift": 0, "missing": 0},
                "exit_code": 0,
            }, ensure_ascii=False))
        else:
            print(f"acceptance-check {ticket_id}: acceptance 中無 UC 引用")
        sys.exit(0)

    valid = get_valid_uc_map(project_root)
    sidecar_path = get_fingerprint_sidecar_path(project_root)
    sidecar_exists = sidecar_path.is_file()

    drifted_set: set[str] = set()
    if sidecar_exists:
        drifted, _added, _removed = check_fingerprints(project_root)
        drifted_set = set(drifted)

    results: list[dict] = []
    for uc_id in uc_tokens:
        if uc_id not in valid:
            results.append({"uc_id": uc_id, "status": "MISSING", "title": None})
        elif uc_id in drifted_set:
            results.append({"uc_id": uc_id, "status": "DRIFT", "title": valid[uc_id]})
        else:
            results.append({"uc_id": uc_id, "status": "PASS", "title": valid[uc_id]})

    counts = {"pass": 0, "drift": 0, "missing": 0}
    for r in results:
        counts[r["status"].lower()] += 1

    has_issues = counts["drift"] > 0 or counts["missing"] > 0
    exit_code = 1 if has_issues else 0

    if as_json:
        print(json.dumps({
            "ticket_id": ticket_id,
            "results": results,
            "summary": counts,
            "sidecar_exists": sidecar_exists,
            "exit_code": exit_code,
        }, ensure_ascii=False))
    else:
        print(f"acceptance-check {ticket_id}:")
        for r in results:
            title = r["title"] or "(不存在)"
            print(f"  [{r['status']}] {r['uc_id']}: {title}")
        if not sidecar_exists:
            print("  [INFO] 指紋 sidecar 不存在，漂移偵測已略過（執行 doc uc fingerprint update 初始化）")
        if has_issues:
            parts = []
            if counts["drift"]:
                parts.append(f"{counts['drift']} DRIFT")
            if counts["missing"]:
                parts.append(f"{counts['missing']} MISSING")
            print(f"[FAIL] {', '.join(parts)}")
        else:
            print(f"[PASS] {counts['pass']} UC 引用全部通過")

    sys.exit(exit_code)


_UC_HANDLERS = {
    "list": _cmd_list,
    "verify": _cmd_verify,
    "trace": _cmd_trace,
    "context": _cmd_context,
    "summary": _cmd_summary,
    "fingerprint": _cmd_fingerprint,
    "acceptance-check": _cmd_acceptance_check,
}


def execute(args: argparse.Namespace) -> None:
    """uc 子命令群組路由入口。"""
    sub_command = getattr(args, "uc_command", None)
    if sub_command is None:
        print("用法: doc uc {list,verify,trace,context,summary,fingerprint,acceptance-check}")
        print("  doc uc list                              列出合法 UC 編號+標題")
        print("  doc uc verify [path]                     驗證路徑內 UC token（省略 path 掃描整個專案）")
        print("  doc uc trace <uc_id> [--limit N|--all]   列出 UC code 引用位置")
        print("  doc uc context <uc_id|ticket_id>         輸出 UC 或 ticket 對應的定位資訊")
        print("  doc uc summary <uc_id> [--json]          輸出 UC 標題+spec 位置+主流程摘要")
        print("  doc uc fingerprint {update,check}        UC 內容指紋漂移偵測")
        print("  doc uc acceptance-check <ticket_id>      檢查 ticket acceptance 中 UC 引用對齊")
        sys.exit(1)

    handler = _UC_HANDLERS.get(sub_command)
    if handler is None:
        print(
            f"錯誤：未知的 uc 子命令: {sub_command}（可用: {', '.join(sorted(_UC_HANDLERS))}）",
            file=sys.stderr,
        )
        sys.exit(2)
    handler(args)
