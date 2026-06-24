#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6.0"]
# ///

"""
Sibling blockedBy Validator Hook

防護 ARCH-017 v1.1.0 引入的「串行兄弟」4 條件例外被濫用。

觸發時機：PreToolUse Bash，當命令為 `ticket track claim/complete <ticket_id>` 時。

檢查 4 條件：
  條件 1（單向）：兄弟 blockedBy 不可雙向，且不可同時依賴 >=2 個兄弟
  條件 2（無環）：siblings DAG 不存在環
  條件 3（規格→實作時序）：純 IMP→IMP 兄弟序列僅 warn（啟發式）
  條件 4（不可深度化）：必須有 --acknowledge "理由" 顯式確認

行為分級：
  - 條件 1-2 違反 → BLOCK（exit 2）
  - 條件 3-4 違反 → WARN（exit 0，stderr 提示）
  - frontmatter 解析失敗 → fallback warn-only（exit 0）

對應 Ticket: 0.18.0-W10-040
對應 Error Pattern: ARCH-017 v1.1.0 / PC-066
"""

import sys
import re
import os
import json
from pathlib import Path
from typing import Optional, Dict, Any, List

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))
from lib import setup_hook_logging, run_hook_safely, read_json_from_stdin, get_effort_level

try:
    import yaml
except ImportError:
    yaml = None


# ============================================================================
# 常數
# ============================================================================

SPEC_TYPES = {"ANA", "DOC"}
IMPL_TYPES = {"IMP"}

SEVERITY_BLOCK = "BLOCK"
SEVERITY_WARN = "WARN"
SEVERITY_PASS = "PASS"


# ============================================================================
# L1：純邏輯層 — 4 條件檢查
# ============================================================================

def check_condition_1_unidirectional(target: Dict, siblings_map: Dict[str, Dict]) -> Optional[Dict]:
    """條件 1：單向且單一前驅（A1, A2, A3）。"""
    blocked_by = target.get("blockedBy") or []
    sibling_deps = [s for s in blocked_by if s in siblings_map]

    for dep_id in sibling_deps:
        dep = siblings_map[dep_id]
        dep_blocked = dep.get("blockedBy") or []
        if target.get("id") in dep_blocked:
            return _violation(1, SEVERITY_BLOCK, "雙向依賴", "移除其中一向依賴")

    if len(sibling_deps) >= 2:
        return _violation(1, SEVERITY_BLOCK,
                          f"多兄弟依賴（{len(sibling_deps)} 個前驅兄弟）",
                          "限制單一前驅，或拆為父子深度")
    return None


def check_condition_2_acyclic(target: Dict, siblings_map: Dict[str, Dict]) -> Optional[Dict]:
    """條件 2：siblings 子圖無環（A4, A5, A6）。"""
    visited = set()

    def dfs(node_id: str, stack: set) -> bool:
        if node_id in stack:
            return True
        if node_id in visited:
            return False
        visited.add(node_id)
        stack.add(node_id)
        node = siblings_map.get(node_id)
        if node:
            for dep in (node.get("blockedBy") or []):
                if dep in siblings_map and dfs(dep, stack):
                    return True
        stack.discard(node_id)
        return False

    if dfs(target.get("id"), set()):
        return _violation(2, SEVERITY_BLOCK, "循環依賴", "打破環，重新梳理依賴方向")
    return None


def check_condition_3_spec_to_impl(target: Dict, siblings_map: Dict[str, Dict]) -> Optional[Dict]:
    """條件 3：規格→實作時序啟發式（A7, A8, A9）。"""
    target_type = (target.get("type") or "").upper()
    blocked_by = target.get("blockedBy") or []

    for dep_id in blocked_by:
        dep = siblings_map.get(dep_id)
        if not dep:
            continue
        dep_type = (dep.get("type") or "").upper()

        # 純 IMP→IMP
        if target_type in IMPL_TYPES and dep_type in IMPL_TYPES:
            return _violation(3, SEVERITY_WARN,
                              f"純 IMP→IMP 兄弟序列（{dep_id} → {target.get('id')}）",
                              "確認非規格→實作關係，或加 --acknowledge \"理由\"")
        # spec ← impl 時序錯反
        if target_type in SPEC_TYPES and dep_type in IMPL_TYPES:
            return _violation(3, SEVERITY_WARN,
                              f"時序錯反 IMP→spec（{dep_id} → {target.get('id')}）",
                              "規格類 ticket 應先於實作類")
    return None


def check_condition_4_no_deepening(target: Dict, ack: Optional[str]) -> Optional[Dict]:
    """條件 4：不可深度化必須 ack（A10, A11, A12）。"""
    blocked_by = target.get("blockedBy") or []
    if not blocked_by:
        return None
    if ack is None or not ack.strip():
        return _violation(4, SEVERITY_WARN,
                          "無法自動驗證「不可深度化」",
                          "加 --acknowledge \"<理由>\" 顯式確認此兄弟結構不應改為父子深度")
    return None


def _violation(condition: int, severity: str, message: str, suggestion: str) -> Dict:
    return {
        "condition": condition,
        "severity": severity,
        "message": message,
        "suggestion": suggestion,
    }


def evaluate(target: Dict, siblings_map: Dict[str, Dict], ack: Optional[str]) -> List[Dict]:
    """整合 4 條件檢查，回傳違規清單（已過濾 None）。"""
    results = [
        check_condition_1_unidirectional(target, siblings_map),
        check_condition_2_acyclic(target, siblings_map),
        check_condition_3_spec_to_impl(target, siblings_map),
        check_condition_4_no_deepening(target, ack),
    ]
    return [r for r in results if r is not None]


# ============================================================================
# L2：IO 層 — frontmatter / siblings 載入
# ============================================================================

_FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def parse_ticket_md(path: Path) -> Optional[Dict]:
    """解析 ticket md frontmatter；失敗回 None。"""
    if yaml is None:
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return None
    m = _FM_RE.match(text)
    if not m:
        return None
    try:
        data = yaml.safe_load(m.group(1))
        if isinstance(data, dict):
            return data
    except Exception:
        return None
    return None


def find_ticket_file(project_root: Path, ticket_id: str) -> Optional[Path]:
    """在 docs/work-logs 下找對應 ticket md。"""
    base = project_root / "docs" / "work-logs"
    if not base.exists():
        return None
    matches = list(base.rglob(f"{ticket_id}.md"))
    return matches[0] if matches else None


def load_siblings(project_root: Path, parent_id: str, exclude_id: str) -> Dict[str, Dict]:
    """掃描 docs/work-logs 載入同 parent_id 的兄弟 ticket frontmatter。"""
    base = project_root / "docs" / "work-logs"
    siblings: Dict[str, Dict] = {}
    if not base.exists():
        return siblings
    for md_path in base.rglob("*.md"):
        if "tickets" not in md_path.parts:
            continue
        fm = parse_ticket_md(md_path)
        if not fm:
            continue
        if fm.get("parent_id") == parent_id and fm.get("id") != exclude_id:
            siblings[fm["id"]] = fm
    return siblings


# ============================================================================
# L3：Hook 入口 — 命令解析、行為分級、輸出
# ============================================================================

# 形如：ticket track claim 0.18.0-W10-040 [--acknowledge "..."]
# 或：ticket track complete <id>
_CMD_RE = re.compile(
    r"\bticket\s+track\s+(claim|complete)\s+(\S+)"
)
_ACK_RE = re.compile(r"--acknowledge[=\s]+(?:\"([^\"]*)\"|'([^']*)'|(\S+))")


def parse_bash_command(command: str) -> Optional[Dict]:
    """從 bash 命令抽出 ticket_id 與 ack。回 None 表示非目標命令。"""
    m = _CMD_RE.search(command or "")
    if not m:
        return None
    ack_m = _ACK_RE.search(command)
    ack = None
    if ack_m:
        ack = ack_m.group(1) or ack_m.group(2) or ack_m.group(3)
    return {"action": m.group(1), "ticket_id": m.group(2), "acknowledge": ack}


def format_violation(ticket_id: str, v: Dict) -> str:
    return (
        f"[ARCH-017 串行兄弟條件 {v['condition']} 違反] {ticket_id} "
        f"[{v['severity']}]\n"
        f"  原因: {v['message']}\n"
        f"  建議: {v['suggestion']}\n"
        f"  參考: .claude/error-patterns/architecture/ARCH-017-sibling-hidden-dependency.md"
    )


def run_check(project_root: Path, ticket_id: str, ack: Optional[str], logger) -> int:
    """核心流程：載入 → 4 條件 → 分級 → 輸出。回傳 exit code。"""
    md = find_ticket_file(project_root, ticket_id)
    if md is None:
        logger.debug(f"ticket md 找不到：{ticket_id}（skip）")
        return 0

    target = parse_ticket_md(md)
    if not target:
        # C2 fallback
        print(f"[sibling-blockedby-validator fallback warn-only] "
              f"frontmatter 解析失敗：{ticket_id}", file=sys.stderr)
        return 0

    parent_id = target.get("parent_id")
    if not parent_id:
        logger.debug(f"{ticket_id} 無 parent_id，skip")
        return 0

    blocked_by = target.get("blockedBy") or []
    if not blocked_by:
        logger.debug(f"{ticket_id} 無 blockedBy，skip")
        return 0

    try:
        siblings_map = load_siblings(project_root, parent_id, exclude_id=ticket_id)
        # target 自身也納入 map 供環檢測
        siblings_map[ticket_id] = target
        violations = evaluate(target, siblings_map, ack)
    except Exception as e:
        print(f"[sibling-blockedby-validator fallback warn-only] {e}",
              file=sys.stderr)
        return 0

    if not violations:
        logger.info(f"{ticket_id} 通過 4 條件檢查")
        return 0

    has_block = any(v["severity"] == SEVERITY_BLOCK for v in violations)
    for v in violations:
        print(format_violation(ticket_id, v), file=sys.stderr)

    if has_block:
        print(f"[ARCH-017] {ticket_id} 結構性違規，請修正後重試。",
              file=sys.stderr)
        return 2

    # 全為 WARN：可選擇寫入 ack 至 ticket（簡化版：不直接寫檔，避免 race）
    if ack and ack.strip():
        logger.info(f"{ticket_id} WARN 通過（acknowledge 已提供）")
    else:
        print(f"[ARCH-017] {ticket_id} 警告通過（建議補 --acknowledge \"理由\"）",
              file=sys.stderr)
    return 0


def main() -> int:
    logger = setup_hook_logging("sibling-blockedby-validator")
    input_data = read_json_from_stdin(logger)
    if input_data is None:
        return 0

    # Effort 感知（v2.1.133+，W14-036）：low effort 短路放行
    effort = get_effort_level(input_data)
    if effort == "low":
        logger.info("effort=low，sibling-blockedby-validator 短路放行")
        return 0
    logger.info("effort=%s，執行完整 sibling-blockedby 驗證", effort)

    tool_name = input_data.get("tool_name") or input_data.get("tool")
    if tool_name not in (None, "Bash"):
        return 0

    tool_input = input_data.get("tool_input", {}) or {}
    command = tool_input.get("command", "")
    parsed = parse_bash_command(command)
    if not parsed:
        return 0

    project_root = Path(os.environ.get("CLAUDE_PROJECT_DIR", ".")).resolve()
    return run_check(project_root, parsed["ticket_id"], parsed["acknowledge"], logger)


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "sibling-blockedby-validator"))
