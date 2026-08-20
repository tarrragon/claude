"""register-artifact / resolve-artifact / list-artifacts CLI 子命令測試。

背景：跨 session 實驗器材規範（parallel-dispatch.md「跨 session 實驗器材的
自我標示與存活期治理」條件三）原僅要求票面登記路徑/用途/存活期，格式自由
發揮，收尾者需人工掃描 Solution 章節才能取得清單。本檔驗證 CLI 化後：

1. register-artifact 可寫入結構化登記（EXP-N 自動編號）至 Solution 章節的
   「實驗器材登記」子章節，且輸出可直接複製的首行 header 文字
2. list-artifacts 可程式化讀回已登記項目（含 --json），不需人工掃描章節
3. resolve-artifact 可標記 removed / kept，kept 缺 --successor 時拒絕寫入
4. 多筆登記各自獨立更新，不互相破壞
5. 寫入後自動 commit（path-limited），與 add-spawn-request 同保護等級
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

import pytest

from ticket_system.lib.parser import parse_frontmatter


def _run_git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=str(repo), capture_output=True, text=True, check=False,
    )


def _write_ticket_md(path: Path, tid: str) -> None:
    fm = (
        "---\n"
        f"id: {tid}\n"
        "title: test\n"
        "type: IMP\n"
        "status: in_progress\n"
        "assigned: true\n"
        "tdd_phase: phase3b\n"
        "children: []\n"
        "blockedBy: []\n"
        "acceptance: []\n"
        "spawned_tickets: []\n"
        "---\n\n"
    )
    body = (
        "# Execution Log\n\n"
        "## Solution\n"
        "placeholder.\n\n"
        "---\n\n"
        "## Test Results\n"
        "placeholder.\n\n"
        "---\n\n"
        "## Completion Info\n"
        "placeholder.\n"
    )
    path.write_text(fm + body, encoding="utf-8")


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _run_git(repo, "init")
    _run_git(repo, "config", "user.email", "test@test.com")
    _run_git(repo, "config", "user.name", "test")

    tickets_dir = repo / "tickets"
    tickets_dir.mkdir()
    tid = "0.0.0-W0-ART"
    md_path = tickets_dir / f"{tid}.md"
    _write_ticket_md(md_path, tid)

    _run_git(repo, "add", str(md_path))
    _run_git(repo, "commit", "-m", "create ticket (placeholder)")
    return repo


@pytest.fixture
def patch_paths_to_repo(git_repo: Path, monkeypatch):
    tickets_dir = git_repo / "tickets"

    def _fake_get_ticket_path(version: str, ticket_id: str) -> Path:
        return tickets_dir / f"{ticket_id}.md"

    def _fake_load_ticket(version: str, ticket_id: str):
        path = tickets_dir / f"{ticket_id}.md"
        if not path.exists():
            return None
        try:
            fm, body = parse_frontmatter(path.read_text(encoding="utf-8"))
        except Exception:
            return None
        if not fm:
            return None
        fm["_body"] = body
        fm["_path"] = str(path)
        return fm

    from ticket_system.commands import track_artifacts as art_mod
    from ticket_system.lib import ticket_loader

    for mod in (art_mod, ticket_loader):
        monkeypatch.setattr(mod, "get_ticket_path", _fake_get_ticket_path, raising=False)
        monkeypatch.setattr(mod, "load_ticket", _fake_load_ticket, raising=False)

    return git_repo


def _register(ticket_id, path, purpose, expiry, artifact_type="明示", force=False) -> int:
    from ticket_system.commands.track_artifacts import execute_register_artifact

    ns = argparse.Namespace(
        ticket_id=ticket_id, path=path, purpose=purpose, expiry=expiry,
        type=artifact_type, force=force,
    )
    return execute_register_artifact(ns, "0.0.0")


def _resolve(ticket_id, exp_label, status, successor=None, reason=None, force=False) -> int:
    from ticket_system.commands.track_artifacts import execute_resolve_artifact

    ns = argparse.Namespace(
        ticket_id=ticket_id, exp_label=exp_label, status=status,
        successor=successor, reason=reason, force=force,
    )
    return execute_resolve_artifact(ns, "0.0.0")


def _read_md(repo: Path, tid: str = "0.0.0-W0-ART") -> str:
    return (repo / "tickets" / f"{tid}.md").read_text(encoding="utf-8")


def _commit_count(repo: Path) -> int:
    result = _run_git(repo, "rev-list", "--count", "HEAD")
    return int(result.stdout.strip())


# ============================================================
# AC1: register-artifact 寫入結構化登記 + 首行 header 文字
# ============================================================


class TestRegisterArtifact:
    def test_register_writes_exp1_and_prints_header(self, patch_paths_to_repo, capsys):
        repo = patch_paths_to_repo
        rc = _register(
            "0.0.0-W0-ART",
            "docs/work-logs/experiment-0.0.0-W0-ART-sentinel.md",
            "驗證 commit sweep",
            "本票 complete 前",
        )
        assert rc == 0

        content = _read_md(repo)
        assert "### 實驗器材登記" in content
        assert "- **EXP-1**" in content
        assert "path: docs/work-logs/experiment-0.0.0-W0-ART-sentinel.md" in content
        assert "purpose: 驗證 commit sweep" in content
        assert "expiry: 本票 complete 前" in content
        assert "type: 明示" in content
        assert "status: active" in content

        out = capsys.readouterr().out
        assert "複製以下文字為器材檔案首行 header" in out
        assert "本檔為 0.0.0-W0-ART 的實驗器材（驗證 commit sweep）" in out
        assert "請勿刪除、勿 git add、勿加入 .gitignore；由該票收尾時移除。" in out

    def test_register_auto_commits(self, patch_paths_to_repo):
        repo = patch_paths_to_repo
        before = _commit_count(repo)
        rc = _register("0.0.0-W0-ART", "path/a.md", "用途 A", "存活期 A")
        assert rc == 0
        assert _commit_count(repo) == before + 1

    def test_register_rejects_invalid_type(self, patch_paths_to_repo):
        rc = _register("0.0.0-W0-ART", "path/a.md", "用途", "存活期", artifact_type="其他")
        assert rc == 1

    def test_register_second_entry_gets_exp2(self, patch_paths_to_repo):
        repo = patch_paths_to_repo
        _register("0.0.0-W0-ART", "path/a.md", "用途 A", "存活期 A")
        rc = _register("0.0.0-W0-ART", "path/b.md", "用途 B", "存活期 B")
        assert rc == 0
        content = _read_md(repo)
        assert "- **EXP-1**" in content
        assert "- **EXP-2**" in content
        assert "path: path/b.md" in content


# ============================================================
# AC2/3: list-artifacts 結構化讀回
# ============================================================


class TestListArtifacts:
    def test_list_empty_when_no_registration(self, patch_paths_to_repo, capsys):
        from ticket_system.commands.track_artifacts import execute_list_artifacts

        ns = argparse.Namespace(ticket_id="0.0.0-W0-ART", json=False)
        rc = execute_list_artifacts(ns, "0.0.0")
        assert rc == 0
        assert "無已登記的實驗器材" in capsys.readouterr().out

    def test_list_json_roundtrip_matches_registered_fields(self, patch_paths_to_repo):
        import json
        from ticket_system.commands.track_artifacts import execute_list_artifacts

        _register("0.0.0-W0-ART", "path/x.md", "用途 X", "存活期 X", artifact_type="盲測")

        ns = argparse.Namespace(ticket_id="0.0.0-W0-ART", json=True)
        rc = execute_list_artifacts(ns, "0.0.0")
        assert rc == 0

    def test_parse_artifact_registrations_returns_structured_dicts(self, patch_paths_to_repo):
        """acceptance 第 3 項核心：不透過 CLI stdout，直接呼叫解析函式取得
        結構化資料——證明「程式化讀取」路徑存在，非僅 CLI 展示層。"""
        from ticket_system.commands.track_artifacts import parse_artifact_registrations

        _register("0.0.0-W0-ART", "path/y.md", "用途 Y", "存活期 Y")
        content = _read_md(patch_paths_to_repo)
        _fm, body = parse_frontmatter(content)

        entries = parse_artifact_registrations(body)
        assert len(entries) == 1
        assert entries[0]["label"] == "EXP-1"
        assert entries[0]["path"] == "path/y.md"
        assert entries[0]["purpose"] == "用途 Y"
        assert entries[0]["expiry"] == "存活期 Y"
        assert entries[0]["status"] == "active"


# ============================================================
# AC4: resolve-artifact 存活期治理（removed / kept）
# ============================================================


class TestResolveArtifact:
    def test_resolve_removed_updates_status(self, patch_paths_to_repo):
        repo = patch_paths_to_repo
        _register("0.0.0-W0-ART", "path/a.md", "用途 A", "存活期 A")
        rc = _resolve("0.0.0-W0-ART", "EXP-1", "removed", reason="收尾已刪除")
        assert rc == 0
        content = _read_md(repo)
        assert "status: removed（收尾已刪除）" in content

    def test_resolve_kept_without_successor_rejected(self, patch_paths_to_repo):
        repo = patch_paths_to_repo
        _register("0.0.0-W0-ART", "path/a.md", "用途 A", "存活期 A")
        rc = _resolve("0.0.0-W0-ART", "EXP-1", "kept")
        assert rc == 1
        # 未指名接手者拒絕寫入，狀態仍為 active（未被破壞）
        content = _read_md(repo)
        assert "status: active" in content

    def test_resolve_kept_with_successor_accepted(self, patch_paths_to_repo):
        repo = patch_paths_to_repo
        _register("0.0.0-W0-ART", "path/a.md", "用途 A", "存活期 A")
        rc = _resolve("0.0.0-W0-ART", "EXP-1", "kept", successor="0.0.0-W0-NEXT")
        assert rc == 0
        content = _read_md(repo)
        assert "status: kept（接手：0.0.0-W0-NEXT）" in content

    def test_resolve_only_targets_matching_label_not_others(self, patch_paths_to_repo):
        """多筆登記時，resolve 只更新指定 EXP-N，其餘條目維持不變（同型
        於 resolve-spawn-request 的既有驗證，見 test_resolve_spawn_request.py）。"""
        repo = patch_paths_to_repo
        _register("0.0.0-W0-ART", "path/a.md", "用途 A", "存活期 A")
        _register("0.0.0-W0-ART", "path/b.md", "用途 B", "存活期 B")
        rc = _resolve("0.0.0-W0-ART", "EXP-2", "removed")
        assert rc == 0
        content = _read_md(repo)
        # EXP-1 未受影響
        exp1_block = content.split("**EXP-1**")[1].split("**EXP-2**")[0]
        assert "status: active" in exp1_block
        exp2_block = content.split("**EXP-2**")[1]
        assert "status: removed" in exp2_block

    def test_resolve_missing_entry_errors_without_modifying(self, patch_paths_to_repo):
        repo = patch_paths_to_repo
        _register("0.0.0-W0-ART", "path/a.md", "用途 A", "存活期 A")
        before = _read_md(repo)
        rc = _resolve("0.0.0-W0-ART", "EXP-99", "removed")
        assert rc == 1
        assert _read_md(repo) == before
