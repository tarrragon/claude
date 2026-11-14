"""已註冊 hook 的 payload 讀取欄位盤點（靜態掃描，對照欄位表）。

讀錯 payload 欄位的 hook 不會報錯：帶預設值的取值把缺失轉成空值，接著走
「條件不滿足」分支，退出碼與日誌都正常。本測試以 ast 找出每支已註冊 hook
從 payload、tool_input、tool_response 讀取的欄位名，與
references/hook-architect-technical-reference.md〈Hook payload 欄位對照表〉
比對；表外欄位使測試轉紅。欄位表的依據限官方文件與實機樣本，不從既有 hook
的寫法反推。

追蹤方式（同一檔案內、不分作用域）：
- payload：read_json_from_stdin／read_hook_input／json.load(sys.stdin) 等的回傳值，
  以及名為 input_data、hook_input、payload 的函式參數
- tool_input／tool_response：extract_tool_input／extract_tool_response 的回傳值、
  payload.get("tool_input") 等取值，以及同名函式參數
- 上述名稱的別名（a = b）一併追蹤
"""
from __future__ import annotations

import ast
import json
import re
from collections import defaultdict
from pathlib import Path

CLAUDE_DIR = Path(__file__).resolve().parents[2]
ROOT = CLAUDE_DIR.parent
REFERENCE = CLAUDE_DIR / "references" / "hook-architect-technical-reference.md"
TABLE_HEADING = "### Hook payload 欄位對照表"

PAYLOAD_SOURCES = {"read_json_from_stdin", "read_hook_input"}
SUB_SOURCES = {"extract_tool_input": "tool_input", "extract_tool_response": "tool_response"}
PAYLOAD_PARAMS = {"input_data", "hook_input", "payload"}
SUB_PARAMS = {"tool_input": "tool_input", "tool_response": "tool_response"}
SECTIONS = ("top", "tool_input", "tool_response")

# 已知偏差：盤點建立時（main 現況）就存在的表外讀取，每項都有處置票。
# 新增的表外讀取不得加進這裡，要修正讀取或以有依據的來源補欄位表。
# 處置完成的項目必須移除；清單內項目若已不再被讀取，測試同樣轉紅。
_WRONG = "讀錯欄位，功能失效"
_FALLBACK = "主欄位正確，另以 or 後備讀取無依據欄位"
_UNSOURCED = "欄位無官方文件或實機樣本依據"
KNOWN_DEVIATIONS: dict[tuple[str, str], str] = {
    (".claude/skills/dart-comment-traceability/hooks/comment-qa-hook.py", "tool_response.success"): f"{_WRONG}：3.4.0-W1-083",
    (".claude/hooks/file-ownership-guard-hook.py", "tool_input.id"): f"{_WRONG}：3.4.0-W1-084",
    (".claude/hooks/file-ownership-guard-hook.py", "tool_input.target_id"): f"{_WRONG}：3.4.0-W1-084",
    (".claude/hooks/file-ownership-guard-hook.py", "tool_input.ticket_id"): f"{_WRONG}：3.4.0-W1-084",
    (".claude/skills/ticket/hooks/stop-worklog-handoff-sync-check-hook.py", "top.session_start_timestamp"): f"{_WRONG}：3.4.0-W1-085",
    (".claude/hooks/5w1h-compliance-check-hook.py", "tool_input.content"): f"{_FALLBACK}：3.4.0-W1-086",
    (".claude/hooks/parallel-claim-audit-hook.py", "top.tool_result"): f"{_FALLBACK}：3.4.0-W1-086",
    (".claude/hooks/phase4-decision-enforcement-hook.py", "top.hookEventName"): f"{_FALLBACK}：3.4.0-W1-086",
    (".claude/hooks/sibling-blockedby-validator-hook.py", "top.tool"): f"{_FALLBACK}：3.4.0-W1-086",
    (".claude/skills/ticket/hooks/handoff-prompt-reminder-hook.py", "top.userInput"): f"{_FALLBACK}：3.4.0-W1-086",
    (".claude/hooks/agent-dispatch-logger-hook.py", "tool_response.result"): f"{_FALLBACK}：3.4.0-W1-086",
    (".claude/hooks/post-test-hook.py", "tool_input.file_path"): f"{_FALLBACK}（未註冊 Edit 的防禦路徑）：3.4.0-W1-086",
    (".claude/hooks/active-dispatch-tracker-hook.py", "tool_response.worktreePath"): f"{_UNSOURCED}：3.4.0-W1-087",
    (".claude/hooks/pre-test-hook.py", "tool_input.paths"): f"{_UNSOURCED}：3.4.0-W1-087",
    (".claude/hooks/pre-test-hook.py", "tool_input.roots"): f"{_UNSOURCED}：3.4.0-W1-087",
    **{
        (f".claude/hooks/{name}", "tool_input.edits"): f"{_UNSOURCED}（MultiEdit）：3.4.0-W1-087"
        for name in (
            "presence-detection-hook.py",
            "proposal-evaluation-gate-hook.py",
            "reference-stability-rule8-guard-hook.py",
            "skill-description-length-check-hook.py",
            "uc-reference-validation-hook.py",
        )
    },
}


# ---------------------------------------------------------------------------
# 註冊清單
# ---------------------------------------------------------------------------

def registered_hooks() -> dict[str, set[tuple[str, str]]]:
    """回傳 {hook 相對路徑: {(事件, matcher)}}；matcher 缺省記為 "*"。"""
    out: dict[str, set[tuple[str, str]]] = defaultdict(set)
    settings = json.loads((CLAUDE_DIR / "settings.json").read_text(encoding="utf-8"))
    for event, matchers in settings["hooks"].items():
        for m in matchers:
            for h in m["hooks"]:
                cmd = h.get("command", "")
                if "hook-dispatcher.py" in cmd:
                    continue
                for rel in re.findall(r"\$CLAUDE_PROJECT_DIR/(\.claude/\S+?\.py)", cmd):
                    out[rel].add((event, m.get("matcher") or "*"))
    registry = json.loads((CLAUDE_DIR / "hooks" / "hook-dispatch-registry.json").read_text(encoding="utf-8"))
    for group, spec in registry["groups"].items():
        if isinstance(spec, dict) and "hooks" in spec:
            event, _, matcher = group.partition(":")
            for h in spec["hooks"]:
                out[h["path"]].add((event, matcher or "*"))
    return out


# ---------------------------------------------------------------------------
# 欄位表（references 單一來源）
# ---------------------------------------------------------------------------

def load_field_table(text: str | None = None) -> dict[str, set[str]]:
    """解析〈Hook payload 欄位對照表〉：{範圍: {欄位}}。範圍如 common、PreToolUse、
    tool_input:Bash、tool_response:Agent。"""
    text = REFERENCE.read_text(encoding="utf-8") if text is None else text
    start = text.index(TABLE_HEADING)
    table: dict[str, set[str]] = defaultdict(set)
    for line in text[start:].splitlines()[1:]:
        if line.startswith("#"):
            break
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 3 or cells[0] in ("範圍", "") or set(cells[0]) <= {"-", ":"}:
            continue
        for field in re.findall(r"`([^`]+)`", cells[1]):
            table[cells[0]].add(field)
    return table


# ---------------------------------------------------------------------------
# 讀取欄位掃描
# ---------------------------------------------------------------------------

def _str_key(node) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _call_name(node) -> str | None:
    if isinstance(node, ast.Call):
        f = node.func
        return f.attr if isinstance(f, ast.Attribute) else f.id if isinstance(f, ast.Name) else None
    return None


def _is_stdin_json(node) -> bool:
    return _call_name(node) in ("load", "loads") and "sys.stdin" in ast.unparse(node)


def _field_access(node) -> tuple[ast.expr, str] | None:
    """x.get("k", ...) 或 x["k"] → (x, "k")。"""
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "get" and node.args:
        key = _str_key(node.args[0])
        return (node.func.value, key) if key else None
    if isinstance(node, ast.Subscript):
        key = _str_key(node.slice)
        return (node.value, key) if key else None
    return None


def _strip_or(node):
    """(x or {}) → x。"""
    if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or):
        return node.values[0]
    return node


def _classify_value(node, kinds: dict[str, str]) -> str | None:
    node = _strip_or(node)
    if isinstance(node, ast.Name):
        return kinds.get(node.id)
    name = _call_name(node)
    if name in PAYLOAD_SOURCES or _is_stdin_json(node):
        return "top"
    if name in SUB_SOURCES:
        return SUB_SOURCES[name]
    access = _field_access(node)
    if access and isinstance(access[0], ast.Name) and kinds.get(access[0].id) == "top":
        if access[1] in ("tool_input", "tool_response"):
            return access[1]
    return None


def scan_reads(source: str) -> dict[str, set[str]]:
    tree = ast.parse(source)
    kinds: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for arg in node.args.args + node.args.kwonlyargs:
                if arg.arg in PAYLOAD_PARAMS:
                    kinds[arg.arg] = "top"
                elif arg.arg in SUB_PARAMS:
                    kinds[arg.arg] = SUB_PARAMS[arg.arg]
    changed = True
    while changed:
        changed = False
        for node in ast.walk(tree):
            if isinstance(node, (ast.Assign, ast.AnnAssign)) and node.value is not None:
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                kind = _classify_value(node.value, kinds)
                for t in targets:
                    if kind and isinstance(t, ast.Name) and kinds.get(t.id) != kind:
                        kinds[t.id] = kind
                        changed = True
    reads: dict[str, set[str]] = defaultdict(set)
    for node in ast.walk(tree):
        access = _field_access(node)
        if access and isinstance(_strip_or(access[0]), ast.Name):
            kind = kinds.get(_strip_or(access[0]).id)
            if kind:
                reads[kind].add(access[1])
        elif access:
            inner = _classify_value(access[0], kinds)
            if inner:
                reads[inner].add(access[1])
    return reads


# ---------------------------------------------------------------------------
# 比對
# ---------------------------------------------------------------------------

def _tools_for(matcher: str, table: dict[str, set[str]], section: str) -> list[str]:
    scopes = [s.split(":", 1)[1] for s in table if s.startswith(section + ":")]
    if matcher == "*":
        return scopes
    pattern = re.compile(rf"^(?:{matcher})$")
    return [t for t in scopes if pattern.match(t)]


def allowed_fields(registrations, table) -> dict[str, set[str]]:
    allowed = {s: set() for s in SECTIONS}
    allowed["top"] |= table.get("common", set())
    for event, matcher in registrations:
        allowed["top"] |= table.get(event, set())
        for section in ("tool_input", "tool_response"):
            for tool in _tools_for(matcher, table, section):
                allowed[section] |= table[f"{section}:{tool}"]
    return allowed


def violations_for(rel: str, registrations, table) -> list[str]:
    reads = scan_reads((ROOT / rel).read_text(encoding="utf-8"))
    allowed = allowed_fields(registrations, table)
    return [
        f"{rel}: {section}.{field}"
        for section in SECTIONS
        for field in sorted(reads.get(section, ()))
        if field not in allowed[section]
    ]


def all_violations() -> list[str]:
    table = load_field_table()
    out: list[str] = []
    for rel, regs in sorted(registered_hooks().items()):
        out.extend(violations_for(rel, regs, table))
    return out


# ---------------------------------------------------------------------------
# 測試
# ---------------------------------------------------------------------------

def _split(violation: str) -> tuple[str, str]:
    rel, _, field = violation.partition(": ")
    return rel, field


def test_registered_hooks_read_only_tabled_fields():
    new = [v for v in all_violations() if _split(v) not in KNOWN_DEVIATIONS]
    assert new == [], "表外欄位（讀錯欄位，或欄位表缺有據的欄位）：\n" + "\n".join(new)


def test_known_deviations_are_still_present():
    """已處置的偏差要從清單移除，避免清單成為永久豁免。"""
    current = {_split(v) for v in all_violations()}
    stale = sorted(k for k in KNOWN_DEVIATIONS if k not in current)
    assert stale == [], f"已不存在的已知偏差，請自 KNOWN_DEVIATIONS 移除：{stale}"


def test_every_table_row_cites_source():
    text = REFERENCE.read_text(encoding="utf-8")
    body = text[text.index(TABLE_HEADING):].split("\n#", 1)[0]
    rows = [l for l in body.splitlines() if l.startswith("|") and "`" in l]
    assert rows
    for row in rows:
        source = row.strip().strip("|").split("|")[2].strip()
        assert source, f"欄位列缺來源：{row}"


def test_wrong_field_sample_hook_is_reported(tmp_path):
    """正向對照：讀 tool_result（不存在的欄位）與 Bash 不存在的 exit_code 必須被抓出。"""
    sample = tmp_path / ".claude" / "hooks" / "sample-hook.py"
    sample.parent.mkdir(parents=True)
    sample.write_text(
        "from lib.hook_io import read_json_from_stdin, extract_tool_response\n"
        "def main():\n"
        "    input_data = read_json_from_stdin(None)\n"
        "    result = input_data.get('tool_result', {})\n"
        "    resp = extract_tool_response(input_data)\n"
        "    return resp.get('exit_code', 1), input_data.get('tool_name')\n",
        encoding="utf-8",
    )
    reads = scan_reads(sample.read_text(encoding="utf-8"))
    table = load_field_table()
    allowed = allowed_fields({("PostToolUse", "Bash")}, table)
    assert "tool_result" in reads["top"] and "tool_result" not in allowed["top"]
    assert "exit_code" in reads["tool_response"] and "exit_code" not in allowed["tool_response"]
    assert "tool_name" in allowed["top"]


if __name__ == "__main__":
    for v in all_violations():
        print(v)
