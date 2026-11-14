"""parallel-suggestion-hook：同鏈判定改用 parent_id，移除全文 regex 回退。

驗證：
1. 最近完成票有 parent 時，同 parent 的 pending 子票被列出（修正前讀不存在的
   chain 欄位，恆為空）
2. 最近完成票為根票時，其 pending 子票被列出
3. 內文含 `project_root:` 的票不被當成鏈根（修正前全文 regex 回退會命中）
4. 正向對照：不同 parent 的 pending 票、非 pending 的同鏈票不列出

票檔寫在 tmp_path（function scope），經 extract_ticket_info 真實解析 frontmatter。
"""

import importlib.util
import logging
import os
import time
from pathlib import Path

import pytest

HOOK_PATH = Path(__file__).parent.parent / "parallel-suggestion-hook.py"


def _load():
    spec = importlib.util.spec_from_file_location("parallel_suggestion_parent_chain", HOOK_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


hook = _load()
LOG = logging.getLogger("test-parallel-suggestion-parent-chain")

P = "9.9.9" + "-W1-" + "40"   # 父票號（以片段組裝）


def _ticket(tmp_path, tid, status, parent=None, body="", mtime=None):
    lines = ["---", f"id: {tid}", f"title: {tid}", "type: IMP", f"status: {status}"]
    if parent:
        lines.append(f"parent_id: {parent}")
    lines += ["where:", "  files:", f"  - src/{tid}.py", "---", body]
    path = tmp_path / f"{tid}.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if mtime is not None:
        os.utime(path, (mtime, mtime))
    return hook.extract_ticket_info(path, LOG)


def test_siblings_of_latest_completed_listed(tmp_path):
    now = time.time()
    tickets = [
        _ticket(tmp_path, P, "in_progress"),
        _ticket(tmp_path, P + ".1", "completed", parent=P, mtime=now),
        _ticket(tmp_path, P + ".2", "pending", parent=P),
        _ticket(tmp_path, P + ".3", "pending", parent=P),
    ]
    root = hook.find_latest_completed_ticket_root(tickets, LOG)
    assert root == P
    pending = hook.find_pending_tickets_in_chain(root, tickets, LOG)
    assert sorted(t["id"] for t in pending) == [P + ".2", P + ".3"]


def test_children_of_completed_root_listed(tmp_path):
    tickets = [
        _ticket(tmp_path, P, "completed", mtime=time.time()),
        _ticket(tmp_path, P + ".1", "pending", parent=P),
    ]
    root = hook.find_latest_completed_ticket_root(tickets, LOG)
    assert root == P
    assert [t["id"] for t in hook.find_pending_tickets_in_chain(root, tickets, LOG)] == [P + ".1"]


def test_project_root_in_body_not_used_as_chain(tmp_path):
    t = _ticket(tmp_path, P + ".1", "completed",
                body="設定 project_root: /tmp/x\nchain root: Y")
    assert t["parent_id"] is None
    assert "chain" not in t


@pytest.mark.parametrize("other_parent,status", [
    ("9.9.9" + "-W1-" + "41", "pending"),   # 不同 parent
    (P, "completed"),                       # 同鏈但非 pending
    (P, "in_progress"),
])
def test_positive_control_not_listed(tmp_path, other_parent, status):
    tickets = [
        _ticket(tmp_path, P + ".1", "completed", parent=P, mtime=time.time()),
        _ticket(tmp_path, "X-1", status, parent=other_parent),
    ]
    root = hook.find_latest_completed_ticket_root(tickets, LOG)
    assert hook.find_pending_tickets_in_chain(root, tickets, LOG) == []
