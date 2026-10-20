"""ticket track move-lines 子命令測試（0.5.0-W1-362）。

驗證：
1. 搬移後來源減少行數等於目標增加行數，搬移段逐字相同（--at 行號 / end）。
2. E2：目標寫入失敗時非 0 且兩檔逐位元不變。
3. E2：src 或 dst 不在 where.files 內時拒絕且兩檔不變。
4. 行範圍非法、src 與 dst 相同、--at 超界時拒絕且兩檔不變。
"""
import argparse
import subprocess
from unittest.mock import patch

from ticket_system.commands import track_commit, track_move_lines

_TICKET_ID = "0.5.0-W1-999"
_VERSION = "0.5.0"


def _ticket(files):
    return {"id": _TICKET_ID, "type": "IMP", "where": {"files": files}}


def _args(lines, at, src="a.md", dst="b.md"):
    return argparse.Namespace(
        ticket_id=_TICKET_ID, src=src, lines=lines, dst=dst, at=at, worktree=None
    )


def _run(tmp_path, args, declared=("a.md", "b.md")):
    with patch.object(track_move_lines, "load_ticket", return_value=_ticket(list(declared))), \
         patch.object(track_move_lines, "resolve_project_cwd", return_value=str(tmp_path)):
        return track_move_lines.execute_move_lines(args, _VERSION)


def _setup(tmp_path):
    (tmp_path / "a.md").write_bytes(b"a1\na2\na3\na4\na5\n")
    (tmp_path / "b.md").write_bytes(b"b1\nb2\nb3\n")


def _snapshot(tmp_path):
    return (tmp_path / "a.md").read_bytes(), (tmp_path / "b.md").read_bytes()


class TestMoveLines:
    def test_moves_range_to_line_number(self, tmp_path):
        _setup(tmp_path)
        rc = _run(tmp_path, _args("2-3", "2"))
        assert rc == 0
        assert (tmp_path / "a.md").read_text() == "a1\na4\na5\n"
        assert (tmp_path / "b.md").read_text() == "b1\na2\na3\nb2\nb3\n"

    def test_moves_range_to_end(self, tmp_path):
        _setup(tmp_path)
        rc = _run(tmp_path, _args("1-1", "end"))
        assert rc == 0
        assert (tmp_path / "a.md").read_text() == "a2\na3\na4\na5\n"
        assert (tmp_path / "b.md").read_text() == "b1\nb2\nb3\na1\n"

    def test_end_when_dst_lacks_trailing_newline(self, tmp_path):
        _setup(tmp_path)
        (tmp_path / "b.md").write_bytes(b"b1\nb2")
        rc = _run(tmp_path, _args("1-2", "end"))
        assert rc == 0
        assert (tmp_path / "b.md").read_text() == "b1\nb2\na1\na2\n"

    def test_line_count_conserved(self, tmp_path):
        _setup(tmp_path)
        before = 5 + 3
        _run(tmp_path, _args("2-4", "1"))
        total = len((tmp_path / "a.md").read_text().splitlines()) + len(
            (tmp_path / "b.md").read_text().splitlines()
        )
        assert total == before


def _git_init(path):
    path.mkdir(exist_ok=True)
    subprocess.run(["git", "init", "-q", str(path)], check=True)


class TestSymlinkAndForeignWorktree:
    """0.5.0-W1-390：symlink 與他 repo --worktree 皆拒絕且檔案不變（E2）。"""

    def test_symlink_file_in_scope_is_rejected(self, tmp_path):
        _setup(tmp_path)
        (tmp_path / "real.md").write_bytes(b"r1\nr2\n")
        (tmp_path / "link.md").symlink_to(tmp_path / "real.md")
        before = (tmp_path / "real.md").read_bytes()
        rc = _run(tmp_path, _args("1-1", "end", dst="link.md"),
                  declared=("a.md", "link.md"))
        assert rc != 0
        assert (tmp_path / "link.md").is_symlink()
        assert (tmp_path / "real.md").read_bytes() == before

    def test_symlink_dir_pointing_outside_repo_is_rejected(self, tmp_path):
        repo, outside = tmp_path / "repo", tmp_path / "outside"
        repo.mkdir()
        outside.mkdir()
        _setup(repo)
        (outside / "b.md").write_bytes(b"x1\n")
        (repo / "sub").symlink_to(outside, target_is_directory=True)
        rc = _run(repo, _args("1-1", "end", dst="sub/b.md"),
                  declared=("a.md", "sub"))
        assert rc != 0
        assert (outside / "b.md").read_bytes() == b"x1\n"

    def test_worktree_of_foreign_repo_is_rejected(self, tmp_path):
        main, foreign = tmp_path / "main", tmp_path / "foreign"
        _git_init(main)
        _git_init(foreign)
        _setup(foreign)
        before = _snapshot(foreign)
        args = _args("1-1", "end")
        args.worktree = str(foreign)
        assert _run(main, args) != 0
        assert _snapshot(foreign) == before

    def test_git_query_failure_rejects_worktree(self, tmp_path):
        """保守一側：worktree list 查詢失敗時拒絕。"""
        main = tmp_path / "main"
        _git_init(main)
        _setup(main)
        before = _snapshot(main)
        args = _args("1-1", "end")
        args.worktree = str(main)
        failed = subprocess.CompletedProcess([], 128, "", "boom")
        real_run = subprocess.run

        def fake_run(cmd, *a, **kw):
            if "worktree" in cmd:
                return failed
            return real_run(cmd, *a, **kw)

        with patch.object(subprocess, "run", side_effect=fake_run):
            assert _run(main, args) != 0
        assert _snapshot(main) == before

    def test_own_repo_worktree_still_works(self, tmp_path):
        """E1：本 repo 的 worktree（含主 checkout 自身）行為不變。"""
        main = tmp_path / "main"
        _git_init(main)
        _setup(main)
        args = _args("1-1", "end")
        args.worktree = str(main)
        assert _run(main, args) == 0
        assert (main / "b.md").read_text() == "b1\nb2\nb3\na1\n"


class TestRejections:
    def test_write_failure_restores_both_files(self, tmp_path, capsys):
        """E2 正向對照：目標寫入失敗，非 0 且兩檔逐位元不變。"""
        _setup(tmp_path)
        before = _snapshot(tmp_path)
        real_replace = track_move_lines.os.replace

        def fail_on_dst(tmp, final):
            if str(final).endswith("b.md"):
                raise OSError("injected")
            return real_replace(tmp, final)

        with patch.object(track_move_lines.os, "replace", side_effect=fail_on_dst):
            rc = _run(tmp_path, _args("2-3", "end"))
        assert rc != 0
        assert _snapshot(tmp_path) == before
        assert sorted(p.name for p in tmp_path.iterdir()) == ["a.md", "b.md"]

    def test_conservation_failure_writes_nothing(self, tmp_path):
        """E2：守恆驗證失敗（植入錯誤的搬移計算）時非 0 且兩檔不變。"""
        _setup(tmp_path)
        before = _snapshot(tmp_path)
        with patch.object(track_move_lines, "_plan_move",
                          return_value=(["a1\n"], ["b1\n", "b2\n", "b3\n"], ["a2\n"])):
            rc = _run(tmp_path, _args("2-3", "end"))
        assert rc != 0
        assert _snapshot(tmp_path) == before

    def test_src_out_of_scope(self, tmp_path):
        _setup(tmp_path)
        before = _snapshot(tmp_path)
        assert _run(tmp_path, _args("1-1", "end"), declared=("b.md",)) != 0
        assert _snapshot(tmp_path) == before

    def test_dst_out_of_scope(self, tmp_path):
        _setup(tmp_path)
        before = _snapshot(tmp_path)
        assert _run(tmp_path, _args("1-1", "end"), declared=("a.md",)) != 0
        assert _snapshot(tmp_path) == before

    def test_invalid_ranges_rejected(self, tmp_path):
        _setup(tmp_path)
        before = _snapshot(tmp_path)
        for lines in ("0-2", "3-2", "4-9", "x", "2"):
            assert _run(tmp_path, _args(lines, "end")) != 0
        for at in ("0", "5", "zz"):
            assert _run(tmp_path, _args("1-1", at)) != 0
        assert _snapshot(tmp_path) == before

    def test_same_file_rejected(self, tmp_path):
        _setup(tmp_path)
        before = _snapshot(tmp_path)
        assert _run(tmp_path, _args("1-1", "end", dst="a.md")) != 0
        assert _snapshot(tmp_path) == before

    def test_permissions_preserved_on_success(self, tmp_path):
        _setup(tmp_path)
        (tmp_path / "a.md").chmod(0o755)
        (tmp_path / "b.md").chmod(0o640)
        assert _run(tmp_path, _args("1-1", "end")) == 0
        assert (tmp_path / "a.md").stat().st_mode & 0o777 == 0o755
        assert (tmp_path / "b.md").stat().st_mode & 0o777 == 0o640
        assert not list(tmp_path.glob(".move-lines-*"))

    def test_permissions_preserved_on_restore(self, tmp_path):
        _setup(tmp_path)
        (tmp_path / "a.md").chmod(0o755)
        (tmp_path / "b.md").chmod(0o640)
        real_replace = track_move_lines.os.replace

        def fail_on_dst(tmp, final):
            if str(final).endswith("b.md"):
                raise OSError("injected")
            return real_replace(tmp, final)

        with patch.object(track_move_lines.os, "replace", side_effect=fail_on_dst):
            assert _run(tmp_path, _args("1-1", "end")) != 0
        assert (tmp_path / "a.md").stat().st_mode & 0o777 == 0o755
        assert (tmp_path / "b.md").stat().st_mode & 0o777 == 0o640

    def test_line_boundary_is_newline_only(self, tmp_path):
        (tmp_path / "a.md").write_bytes(b"a1\na\x0c2\na3\n")
        (tmp_path / "b.md").write_bytes(b"b1\n")
        assert _run(tmp_path, _args("2-2", "end")) == 0
        assert (tmp_path / "a.md").read_bytes() == b"a1\na3\n"
        assert (tmp_path / "b.md").read_bytes() == b"b1\na\x0c2\n"

    def test_restore_failure_gives_clear_message(self, tmp_path, capsys):
        _setup(tmp_path)
        real_replace = track_move_lines.os.replace
        calls = {"a": 0}

        def fail(tmp, final):
            if str(final).endswith("b.md"):
                raise OSError("injected dst")
            if str(final).endswith("a.md"):
                calls["a"] += 1
                if calls["a"] >= 2:
                    raise OSError("injected restore")
            return real_replace(tmp, final)

        with patch.object(track_move_lines.os, "replace", side_effect=fail):
            rc = _run(tmp_path, _args("1-1", "end"))
        out = capsys.readouterr().err
        assert rc != 0
        assert "還原失敗" in out and "備份" in out
        backup = out.split("src 原始內容備份：")[1].split()[0]
        assert (tmp_path / backup.rsplit("/", 1)[-1]).read_bytes() == b"a1\na2\na3\na4\na5\n"

    def test_stat_failure_gives_clear_message(self, tmp_path, capsys):
        _setup(tmp_path)
        before = _snapshot(tmp_path)
        real_stat = track_move_lines.os.stat

        def fail(path, *a, **kw):
            if str(path).endswith("b.md"):
                raise OSError("injected stat")
            return real_stat(path, *a, **kw)

        with patch.object(track_move_lines.os, "stat", side_effect=fail):
            rc = _run(tmp_path, _args("1-1", "end"))
        assert rc != 0
        assert "injected stat" in capsys.readouterr().err
        assert _snapshot(tmp_path) == before

    def test_cleanup_failure_reports_and_continues(self, tmp_path, capsys):
        _setup(tmp_path)
        real_unlink = track_move_lines.os.unlink

        def fail(path, *a, **kw):
            if ".move-lines-" in str(path):
                raise OSError("injected unlink")
            return real_unlink(path, *a, **kw)

        with patch.object(track_move_lines.os, "unlink", side_effect=fail):
            rc = _run(tmp_path, _args("1-1", "end"))
        assert rc == 0
        assert "injected unlink" in capsys.readouterr().err
        assert (tmp_path / "b.md").read_text() == "b1\nb2\nb3\na1\n"

    def test_error_goes_to_stderr_and_logger(self, tmp_path, capsys, caplog):
        _setup(tmp_path)
        with caplog.at_level("ERROR"):
            rc = _run(tmp_path, _args("9-9", "end"))
        captured = capsys.readouterr()
        assert rc != 0
        assert "[ERROR]" in captured.err and "[ERROR]" not in captured.out
        assert any("超出來源檔範圍" in r.getMessage() and r.levelname == "ERROR"
                   for r in caplog.records)

    def test_stage_temp_unlink_failure_keeps_original_error(self, tmp_path, capsys, caplog):
        _setup(tmp_path)
        before = _snapshot(tmp_path)
        real_unlink = track_move_lines.os.unlink

        def fail_unlink(path, *a, **kw):
            if ".move-lines-" in str(path):
                raise OSError("injected unlink")
            return real_unlink(path, *a, **kw)

        with patch.object(track_move_lines.os, "chmod", side_effect=OSError("orig chmod")), \
             patch.object(track_move_lines.os, "unlink", side_effect=fail_unlink), \
             caplog.at_level("WARNING"):
            rc = _run(tmp_path, _args("1-1", "end"))
        assert rc != 0
        assert "orig chmod" in capsys.readouterr().err
        assert any("injected unlink" in r.getMessage() for r in caplog.records)
        assert _snapshot(tmp_path) == before

    def test_fullwidth_digits_rejected(self, tmp_path):
        _setup(tmp_path)
        assert _run(tmp_path, _args("１-２", "end")) != 0
        assert _run(tmp_path, _args("1-1", "１")) != 0

    def test_crlf_file_keeps_crlf_when_filling_newline(self, tmp_path):
        (tmp_path / "a.md").write_bytes(b"a1\r\na2\r\n")
        (tmp_path / "b.md").write_bytes(b"b1\r\nb2")
        assert _run(tmp_path, _args("1-1", "end")) == 0
        assert (tmp_path / "b.md").read_bytes() == b"b1\r\nb2\r\na1\r\n"

    def test_missing_ticket_error_to_stderr_and_logger(self, tmp_path, capsys, caplog):
        with patch.object(track_move_lines, "load_ticket", return_value=None), \
             caplog.at_level("ERROR"):
            rc = track_move_lines.execute_move_lines(_args("1-1", "end"), _VERSION)
        captured = capsys.readouterr()
        assert rc != 0
        assert "[ERROR]" in captured.err and "[ERROR]" not in captured.out
        assert any(r.levelname == "ERROR" for r in caplog.records)

    def test_invalid_worktree_error_to_stderr_and_logger(self, tmp_path, capsys, caplog):
        args = _args("1-1", "end")
        args.worktree = str(tmp_path)
        with patch.object(track_move_lines, "resolve_repo_root", return_value=None), \
             caplog.at_level("ERROR"):
            rc = _run(tmp_path, args)
        captured = capsys.readouterr()
        assert rc != 0
        assert "[ERROR]" in captured.err and "[ERROR]" not in captured.out
        assert any(r.levelname == "ERROR" for r in caplog.records)

    def test_missing_ticket(self, tmp_path):
        _setup(tmp_path)
        with patch.object(track_move_lines, "load_ticket", return_value=None):
            assert track_move_lines.execute_move_lines(_args("1-1", "end"), _VERSION) != 0
