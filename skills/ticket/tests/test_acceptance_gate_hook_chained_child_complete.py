"""acceptance-gate 同鏈先 complete 子票，不再以鏈前票面擋父票（3.3.0-W1-213.8）。

閘門在整條命令執行前評估一次：`complete <子> && complete <父>` 時，子票在
評估當下仍是 in_progress。修正後，同鏈中排在父票之前 complete 的子票不計入
children 阻擋；不在鏈內的未完成子票仍擋（正向對照）。
"""
import importlib.util
import logging
from pathlib import Path

import pytest

PARENT = "0.0.0-W1-910"
CHILD_A = PARENT + ".1"
CHILD_B = PARENT + ".2"

PARENT_BODY = """---
id: {pid}
title: parent
type: IMP
status: in_progress
version: 0.0.0
priority: P2
children: [{children}]
acceptance:
- '[x] a'
---

## Solution

x
"""

CHILD_BODY = """---
id: {cid}
title: child
type: IMP
status: in_progress
version: 0.0.0
children: []
---

# Body
"""


def _load():
    path = Path(__file__).resolve().parents[1] / "hooks" / "acceptance-gate-hook.py"
    spec = importlib.util.spec_from_file_location("acceptance_gate_hook_ccc", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def repo(tmp_path):
    root = (tmp_path / "repo").resolve()
    tickets = root / "docs" / "work-logs" / "v0.0.0" / "tickets"
    tickets.mkdir(parents=True)
    (root / "CLAUDE.md").write_text("x", encoding="utf-8")

    def write(children):
        (tickets / f"{PARENT}.md").write_text(
            PARENT_BODY.format(pid=PARENT, children=", ".join(children)), encoding="utf-8"
        )
        for cid in children:
            (tickets / f"{cid}.md").write_text(CHILD_BODY.format(cid=cid), encoding="utf-8")

    return root, write


def _check(module, root, command):
    return module.check_acceptance_status(
        PARENT, root, logging.getLogger("test-ccc"), command
    )


def test_chained_child_complete_does_not_block_parent(repo):
    """修正前為紅：子票同鏈先 complete，父票仍因該子票 in_progress 被 children 擋下。"""
    module = _load()
    root, write = repo
    write([CHILD_A])
    command = f"ticket track complete {CHILD_A} && ticket track complete {PARENT}"

    result = _check(module, root, command)

    assert result.block_source != "children", result.message


def test_child_not_in_chain_still_blocks(repo):
    """正向對照：子票未 complete 且不在鏈內，父票照擋。"""
    module = _load()
    root, write = repo
    write([CHILD_A])

    result = _check(module, root, f"ticket track complete {PARENT}")

    assert result.should_block is True
    assert result.block_source == "children"


def test_partial_chain_still_blocks(repo):
    """兩個子票只有一個在鏈內：不在鏈內的那個仍擋。"""
    module = _load()
    root, write = repo
    write([CHILD_A, CHILD_B])
    command = f"ticket track complete {CHILD_A} && ticket track complete {PARENT}"

    result = _check(module, root, command)

    assert result.should_block is True
    assert result.block_source == "children"
    assert CHILD_B in result.message


def test_child_completed_after_parent_still_blocks(repo):
    """子票排在父票之後 complete：父票評估時子票尚未完成，仍擋。"""
    module = _load()
    root, write = repo
    write([CHILD_A])
    command = f"ticket track complete {PARENT} && ticket track complete {CHILD_A}"

    result = _check(module, root, command)

    assert result.should_block is True
    assert result.block_source == "children"


def test_parent_via_batch_complete_still_blocks(repo):
    """正向對照：父票以 batch-complete 完成時不套用同鏈略過。

    CLI 批次路徑不檢查 children，批次內子票失敗後迴圈照常往下，父票會被標
    completed；gate 是這條路徑唯一的 children 防線，必須照擋。
    """
    module = _load()
    root, write = repo
    write([CHILD_A])

    result = _check(module, root, f"ticket track batch-complete {CHILD_A},{PARENT}")

    assert result.should_block is True
    assert result.block_source == "children"


def test_child_via_batch_parent_single_complete_skips(repo):
    """子票以 batch-complete、父票以單張 complete：父票走 CLI 單張路徑，有 children 補償。"""
    module = _load()
    root, write = repo
    write([CHILD_A])
    command = f"ticket track batch-complete {CHILD_A} && ticket track complete {PARENT}"

    result = _check(module, root, command)

    assert result.block_source != "children", result.message


def test_parent_force_uses_existing_bypass(repo):
    """正向對照：父票帶 --force 時不套用同鏈略過，改走既有 force 旁路（保留稽核與旁路清單）。"""
    module = _load()
    root, write = repo
    write([CHILD_A])
    command = f"ticket track complete {CHILD_A} ; ticket track complete {PARENT} --force"

    result = _check(module, root, command)

    assert result.force_bypassed_children, result
    assert CHILD_A in result.force_bypassed_children[0]


@pytest.mark.parametrize(
    "command, expected",
    [
        (f"ticket track complete {CHILD_A} && ticket track complete {PARENT}", [CHILD_A]),
        (f"ticket track complete {PARENT}", []),
        (f"ticket track complete {PARENT} && ticket track complete {CHILD_A}", []),
        (f"ticket track complete {CHILD_A} 'oops && ticket track complete {PARENT}", []),
        ("", []),
    ],
    ids=["child-first", "parent-only", "parent-first", "unparsable", "empty"],
)
def test_chained_completes_before(command, expected):
    assert _load().chained_completes_before(command, PARENT) == expected


def test_detection_error_keeps_block(repo, monkeypatch):
    """判斷過程出錯時維持阻擋（fail-closed）。"""
    module = _load()
    root, write = repo
    write([CHILD_A])

    def boom(*_args, **_kwargs):
        raise RuntimeError("simulated")

    monkeypatch.setattr(module, "collect_incomplete_descendants_from_frontmatter", boom)
    command = f"ticket track complete {CHILD_A} && ticket track complete {PARENT}"

    result = _check(module, root, command)

    assert result.should_block is True
    assert result.block_source == "children"
