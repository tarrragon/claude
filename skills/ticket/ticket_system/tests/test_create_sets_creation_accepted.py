"""建票通過硬閘門後直接寫 creation_accepted: true 的 E2 對照測試。

正向：硬閘門全過 -> 落盤的票 creation_accepted 為 true（修正前為 false）。
對照：硬閘門失敗（缺必填欄位、未 --force）-> 不產生票檔。
"""
from __future__ import annotations

import yaml

from ticket_system.tests.test_create_acceptance_stored_report import (
    _capture,
    _make_args,
)


def _frontmatter(path):
    text = path.read_text(encoding="utf-8")
    return yaml.safe_load(text.split("---", 2)[1])


def _ticket_files(root):
    return sorted(root.rglob("1.0.1-W1-*.md"))


def test_create_passing_gates_writes_creation_accepted_true(seeded_repo_root):
    _out, _err, exit_code = _capture(_make_args())

    assert exit_code == 0
    files = _ticket_files(seeded_repo_root)
    assert len(files) == 1
    assert _frontmatter(files[0])["creation_accepted"] is True


def test_create_failing_checklist_gate_produces_no_ticket(seeded_repo_root):
    before = _ticket_files(seeded_repo_root)
    _out, _err, exit_code = _capture(_make_args(why=None))

    assert exit_code not in (0, None)
    assert _ticket_files(seeded_repo_root) == before
