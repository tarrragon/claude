"""
finish 前移順序測試（0.4.1-W1-046）

驗收對應：
- 前移依 ID 階層深度排序，父票先於子票（修正前 glob 字典序使子票先移）
- 已被父票子樹遷移帶走的票：略過並輸出 [INFO]，不中止
- E2：來源不存在且不在任何目標版本票的 previous_ids 中，仍判失敗
- pending 票的祖先為 completed／closed（W1-045 留在原版本）：輸出 [WARNING]
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import version_release as vr  # noqa: E402

SRC_VERSION = "0.1.0"
DST_VERSION = "0.1.1"


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _ticket_md(ticket_id: str, status: str, previous_ids=None) -> str:
    lines = ["---", f"id: {ticket_id}", f"title: t-{ticket_id}", "type: IMP", f"status: {status}"]
    if previous_ids:
        lines.append("previous_ids:")
        lines.extend(f"- {p}" for p in previous_ids)
    lines += ["---", "", "# Body"]
    return "\n".join(lines)


def _tickets_dir(root: Path, version: str) -> Path:
    major, minor, _ = version.split(".")
    return root / "docs" / "work-logs" / f"v{major}" / f"v{major}.{minor}" / f"v{version}" / "tickets"


def _setup(root: Path, tickets: dict) -> Path:
    src = _tickets_dir(root, SRC_VERSION)
    for tid, status in tickets.items():
        _write(src / f"{tid}.md", _ticket_md(tid, status))
    _write(root / "docs" / "todolist.yaml", f"versions:\n  - version: {SRC_VERSION}\n  - version: {DST_VERSION}\n")
    return src


def _retarget(ticket_id: str) -> str:
    return ticket_id.replace(SRC_VERSION, DST_VERSION, 1)


def _run(root: Path, fake_migrate):
    config = dict(vr.DEFAULT_VERSION_RELEASE_CONFIG)
    with patch.object(vr, "get_project_root", return_value=root), \
            patch.object(vr, "load_version_release_config", return_value=config), \
            patch.object(vr, "_run_ticket_migrate", side_effect=fake_migrate) as mock_migrate:
        ok = vr.migrate_overflow_tickets(SRC_VERSION)
    return ok, mock_migrate


def _subtree_migrator(root: Path, carried: dict):
    """模擬 ticket migrate：搬走來源票；carried 指定該來源連帶帶走的子孫（ID -> 是否記 previous_ids）。"""
    src = _tickets_dir(root, SRC_VERSION)
    dst = _tickets_dir(root, DST_VERSION)

    def fake(source_id, target_id, target_version, dry_run=False):
        (src / f"{source_id}.md").unlink()
        _write(dst / f"{target_id}.md", _ticket_md(target_id, "pending", [source_id]))
        for child_id, record in carried.get(source_id, {}).items():
            (src / f"{child_id}.md").unlink()
            new_id = _retarget(child_id)
            _write(dst / f"{new_id}.md", _ticket_md(new_id, "pending", [child_id] if record else None))
        return MagicMock(returncode=0, stdout=f"migrated {source_id}\n", stderr="")

    return fake


PARENT = "0.1.0-W1-001"
CHILD = "0.1.0-W1-001.1"


class TestParentFirstOrder:
    def test_parent_migrated_before_child(self, tmp_path):
        _setup(tmp_path, {PARENT: "pending", CHILD: "pending"})
        order = []
        base = _subtree_migrator(tmp_path, {})

        def recording(source_id, *args, **kwargs):
            order.append(source_id)
            return base(source_id, *args, **kwargs)

        ok, _ = _run(tmp_path, recording)

        assert ok is True
        assert order == [PARENT, CHILD]

    def test_same_depth_keeps_original_order(self, tmp_path):
        a, b = "0.1.0-W1-001", "0.1.0-W1-002"
        _setup(tmp_path, {b: "pending", a: "pending"})
        order = []
        base = _subtree_migrator(tmp_path, {})

        def recording(source_id, *args, **kwargs):
            order.append(source_id)
            return base(source_id, *args, **kwargs)

        _run(tmp_path, recording)

        assert order == [a, b]


class TestSkipAlreadyCarried:
    def test_child_carried_by_parent_is_skipped_with_info(self, tmp_path, capsys):
        _setup(tmp_path, {PARENT: "pending", CHILD: "pending"})
        fake = _subtree_migrator(tmp_path, {PARENT: {CHILD: True}})

        ok, mock_migrate = _run(tmp_path, fake)

        out = capsys.readouterr().out
        assert ok is True
        assert [c.args[0] for c in mock_migrate.call_args_list] == [PARENT]
        info_lines = [ln for ln in out.splitlines() if "[INFO]" in ln]
        assert any(CHILD in ln for ln in info_lines)

    def test_missing_source_without_previous_ids_still_fails(self, tmp_path, capsys):
        """E2：來源不存在且無任何新票的 previous_ids 指向它，不得誤判為已搬移。"""
        _setup(tmp_path, {PARENT: "pending", CHILD: "pending"})
        fake = _subtree_migrator(tmp_path, {PARENT: {CHILD: False}})

        ok, mock_migrate = _run(tmp_path, fake)

        out = capsys.readouterr().out
        assert ok is False
        assert [c.args[0] for c in mock_migrate.call_args_list] == [PARENT]
        assert not any("[INFO]" in ln and CHILD in ln for ln in out.splitlines())


class TestTerminalAncestorWarning:
    def test_warns_when_ancestor_is_completed(self, tmp_path, capsys):
        done_parent, orphan = "0.1.0-W1-002", "0.1.0-W1-002.3"
        _setup(tmp_path, {done_parent: "completed", orphan: "pending"})

        ok, _ = _run(tmp_path, _subtree_migrator(tmp_path, {}))

        out = capsys.readouterr().out
        warn_lines = [ln for ln in out.splitlines() if "[WARNING]" in ln]
        assert ok is True
        assert any(orphan in ln and done_parent in ln for ln in warn_lines)

    def test_no_warning_when_ancestor_is_pending(self, tmp_path, capsys):
        _setup(tmp_path, {PARENT: "pending", CHILD: "pending"})

        _run(tmp_path, _subtree_migrator(tmp_path, {}))

        assert "[WARNING]" not in capsys.readouterr().out
