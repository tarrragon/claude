"""Tests for sync-claude-pull.py --audit 刪除預覽（0.2.1-W3-146）。

背景（0.2.1-W3-130 monitor canary 實測）：
  run_audit 原本只比對本地與上游 HEAD 兩方，不讀 base，故無法區分正向孤兒
  的兩個類別——曾存在於 base 者會被三方合併的刪除 delta 移除，從未進入
  base 者保留。monitor 的 13 個正向孤兒中 3 個屬前者被刪、10 個屬後者
  保留，audit 對兩者一視同仁列為候選，系統性低估刪除風險。

涵蓋 acceptance：
  - run_audit 輸出將正向孤兒分為將被刪除與將保留兩組（base 可達時）
  - base sha 缺失或不可達時輸出明示無法預測刪除，不靜默降級為空集合
  - 以 monitor canary 檔名為回歸案例：base 有的 3 檔歸將被刪除、
    base 無的 10 檔歸將保留（base_sha 本身無法重現，故用等價 fixture
    結構取代原始 sha，見 ticket Context Bundle「回歸案例」段）
  - 三情境：base 可達分兩組、base 缺失降級、base 不可達降級

測試約束（ticket 明列）：
  - 不對真實 remote 發 network 呼叫，clone_repo 全數以 fixture/mock 替代
  - 路徑一律用絕對路徑或 tmp_path（PC-BAL-009）
  - 斷言禁用計時門檻（test-assertion-design-rules D1）
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parent.parent / "sync-claude-pull.py"
_spec = importlib.util.spec_from_file_location(
    "sync_claude_pull_audit_delete_preview", _SCRIPT
)
assert _spec and _spec.loader
pull = importlib.util.module_from_spec(_spec)
sys.modules["sync_claude_pull_audit_delete_preview"] = pull
_spec.loader.exec_module(pull)  # type: ignore[union-attr]


# ============================================================================
# Helpers：建立可控的 git upstream repo fixture（比照 test_sync_claude_pull_
# threeway.py 既有模式）
# ============================================================================

def _git(args: list[str], cwd: Path) -> None:
    subprocess.run(
        ["git", *args], cwd=str(cwd), check=True,
        capture_output=True, text=True,
    )


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(["init", "-q"], repo)
    _git(["config", "user.email", "t@t.t"], repo)
    _git(["config", "user.name", "t"], repo)
    _git(["config", "commit.gpgsign", "false"], repo)


def _commit_all(repo: Path, msg: str) -> str:
    _git(["add", "-A"], repo)
    _git(["commit", "-q", "-m", msg], repo)
    out = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(repo),
        check=True, capture_output=True, text=True,
    )
    return out.stdout.strip()


def _write_tree(root: Path, files: dict[str, str]) -> None:
    for rel, content in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def _make_base_repo(repo: Path, base_files: dict[str, str]) -> str:
    """建立 git repo，commit base_files 作為 base，回傳 base sha。

    HEAD 工作區在 commit 後仍等於 base_files；呼叫端可再修改工作區檔案
    （不 commit）以表示上游目前 HEAD 已偏離 base 的狀態，因為
    collect_remote_files 走檔案系統而非 git index/objects。
    """
    _init_repo(repo)
    _write_tree(repo, base_files)
    return _commit_all(repo, "base")


# ============================================================================
# 單元：_list_base_files
# ============================================================================

def test_list_base_files_reachable_returns_relative_paths(tmp_path):
    """base sha 可達時，回傳該版本下全部相對路徑集合。"""
    repo = tmp_path / "up"
    sha = _make_base_repo(repo, {"a.txt": "1", "rules/b.md": "2"})

    result = pull._list_base_files(repo, sha)

    assert result == {"a.txt", "rules/b.md"}


def test_list_base_files_unreachable_returns_none(tmp_path):
    """base sha 不可達（未曾提交）時回傳 None，不可誤用為空集合。"""
    repo = tmp_path / "up"
    _make_base_repo(repo, {"a.txt": "1"})

    result = pull._list_base_files(repo, "deadbeef" * 5)

    assert result is None


# ============================================================================
# 單元：classify_orphans_by_base
# ============================================================================

def test_classify_orphans_by_base_splits_delete_and_keep():
    """曾存在於 base 的孤兒歸將被刪除；從未存在於 base 者歸將保留。"""
    orphans = ["a.txt", "b.txt", "c.txt"]
    base_files = {"a.txt", "b.txt"}  # c.txt 從未在 base

    will_delete, will_keep = pull.classify_orphans_by_base(orphans, base_files)

    assert will_delete == ["a.txt", "b.txt"]
    assert will_keep == ["c.txt"]


def test_classify_orphans_by_base_empty_base_files_keeps_all():
    """base_files 為空集合（base 真的無此檔，非不可達）時全歸將保留。"""
    orphans = ["a.txt"]

    will_delete, will_keep = pull.classify_orphans_by_base(orphans, set())

    assert will_delete == []
    assert will_keep == ["a.txt"]


# ============================================================================
# 整合：run_audit 三情境
# ============================================================================

def test_run_audit_base_reachable_splits_will_delete_and_will_keep(
    monkeypatch, tmp_path, capsys
):
    """base 可達：正向孤兒依是否曾存在於 base 分為將被刪除／將保留兩組。"""
    project_root = tmp_path / "proj"
    claude_dir = project_root / ".claude"
    upstream = tmp_path / "upstream"

    # base：曾有 will_be_deleted.md 與 shared.md
    base_sha = _make_base_repo(
        upstream, {"shared.md": "x", "will_be_deleted.md": "y"}
    )
    # 上游目前 HEAD（工作區，不 commit）：will_be_deleted.md 已被上游刪除，
    # shared.md 仍在（非孤兒，本地上游皆有）
    (upstream / "will_be_deleted.md").unlink()

    claude_dir.mkdir(parents=True)
    _write_tree(claude_dir, {
        "shared.md": "x",
        "will_be_deleted.md": "y",       # 曾在 base → 應歸將被刪除
        "local_only_new.md": "z",        # 從未在 base → 應歸將保留
    })
    (claude_dir / ".sync-state.json").write_text(
        json.dumps({"last_synced_base_sha": base_sha}), encoding="utf-8"
    )

    def _fake_clone(temp_dir: Path) -> None:
        temp_dir.mkdir(parents=True, exist_ok=True)
        for item in upstream.iterdir():
            if item.name == ".git":
                continue
            if item.is_file():
                (temp_dir / item.name).write_text(
                    item.read_text(encoding="utf-8"), encoding="utf-8"
                )
        # _list_base_files 需要在真正的 upstream git repo 上跑 git 指令，
        # 故複製 .git 目錄使 temp_dir 本身可回答 base_sha 是否可達
        import shutil as _shutil
        _shutil.copytree(upstream / ".git", temp_dir / ".git")

    monkeypatch.setattr(pull, "find_project_root", lambda: project_root)
    monkeypatch.setattr(pull, "clone_repo", _fake_clone)

    pull.run_audit()

    out = capsys.readouterr().out
    assert "將被刪除" in out
    assert "將保留" in out
    delete_line_idx = out.index("將被刪除")
    keep_line_idx = out.index("將保留")
    # will_be_deleted.md 應出現在「將被刪除」段落內（其索引介於兩標題之間）
    deleted_file_idx = out.index("will_be_deleted.md")
    kept_file_idx = out.index("local_only_new.md")
    assert delete_line_idx < deleted_file_idx < keep_line_idx
    assert keep_line_idx < kept_file_idx
    # shared.md 本地與上游皆有，非孤兒，不應出現在任何一組
    assert "! shared.md" not in out
    assert "+ shared.md" not in out


def test_run_audit_base_sha_missing_downgrades_with_message(
    monkeypatch, tmp_path, capsys
):
    """無 .sync-state.json（base sha 缺失）時明示無法預測，降級為單一清單。"""
    project_root = tmp_path / "proj"
    claude_dir = project_root / ".claude"
    claude_dir.mkdir(parents=True)
    _write_tree(claude_dir, {"orphan.md": "x"})

    def _fake_clone(temp_dir: Path) -> None:
        temp_dir.mkdir(parents=True, exist_ok=True)
        # 上游無 orphan.md

    monkeypatch.setattr(pull, "find_project_root", lambda: project_root)
    monkeypatch.setattr(pull, "clone_repo", _fake_clone)

    pull.run_audit()

    out = capsys.readouterr().out
    assert "base sha 缺失" in out
    assert "無法預測" in out
    assert "orphan.md" in out
    # 缺失情境不可誤判為分組輸出
    assert "將被刪除" not in out
    assert "將保留" not in out


def test_run_audit_base_sha_unreachable_downgrades_with_message(
    monkeypatch, tmp_path, capsys
):
    """.sync-state.json 存在但 base sha 在上游不可達時明示無法預測。"""
    project_root = tmp_path / "proj"
    claude_dir = project_root / ".claude"
    claude_dir.mkdir(parents=True)
    _write_tree(claude_dir, {"orphan.md": "x"})
    (claude_dir / ".sync-state.json").write_text(
        json.dumps({"last_synced_base_sha": "deadbeef" * 5}), encoding="utf-8"
    )

    def _fake_clone(temp_dir: Path) -> None:
        # 建立真正的 git repo，但其中不含 deadbeef...（不可達）
        _init_repo(temp_dir)
        _write_tree(temp_dir, {"unrelated.txt": "x"})
        _commit_all(temp_dir, "unrelated head")

    monkeypatch.setattr(pull, "find_project_root", lambda: project_root)
    monkeypatch.setattr(pull, "clone_repo", _fake_clone)

    pull.run_audit()

    out = capsys.readouterr().out
    assert "不可達" in out
    assert "無法預測" in out
    assert "orphan.md" in out
    assert "將被刪除" not in out
    assert "將保留" not in out


def test_run_audit_no_orphans_skips_base_classification(monkeypatch, tmp_path, capsys):
    """無正向孤兒時不需分類，維持既有「無正向孤兒」訊息（不迴歸既有行為）。"""
    project_root = tmp_path / "proj"
    claude_dir = project_root / ".claude"
    claude_dir.mkdir(parents=True)
    _write_tree(claude_dir, {"a.md": "a"})

    def _fake_clone(temp_dir: Path) -> None:
        temp_dir.mkdir(parents=True, exist_ok=True)
        (temp_dir / "a.md").write_text("a", encoding="utf-8")

    monkeypatch.setattr(pull, "find_project_root", lambda: project_root)
    monkeypatch.setattr(pull, "clone_repo", _fake_clone)

    pull.run_audit()

    out = capsys.readouterr().out
    assert "無正向孤兒" in out
    assert "將被刪除" not in out
    assert "將保留" not in out


# ============================================================================
# 回歸案例：monitor canary 檔名（0.2.1-W3-130 實測，13 正向孤兒 3 刪 10 留）
# ============================================================================

def test_run_audit_monitor_canary_regression_3_deleted_10_kept(
    monkeypatch, tmp_path, capsys
):
    """monitor 實測案例：base 中曾有的 3 檔歸將被刪除，其餘 10 檔歸將保留。

    base_sha 本身（e41fd8021b75）無法用 fixture 重現（git hash 由內容
    決定，無法偽造指定 sha），故以等價結構替代：3 檔存在於 base 且已被
    上游刪除，10 檔從未存在於 base——與 monitor 案例的分類結果同構。
    """
    project_root = tmp_path / "proj"
    claude_dir = project_root / ".claude"
    upstream = tmp_path / "upstream"

    will_be_deleted = [
        "hooks/memory-upgrade-reminder-hook.py",
        "hooks/test-timeout-post.py",
        "skills/continuous-learning/references/memory-capture-guide.md",
    ]
    will_be_kept = [
        ".gitattributes",
        "skills/worktree/build/lib/scripts/mod1.py",
        "skills/worktree/build/lib/scripts/mod2.py",
        "skills/worktree/build/lib/scripts/mod3.py",
        "skills/worktree/build/lib/scripts/mod4.py",
        "skills/worktree/worktree_skill.egg-info/PKG-INFO",
        "skills/worktree/worktree_skill.egg-info/SOURCES.txt",
        "skills/worktree/worktree_skill.egg-info/dependency_links.txt",
        "skills/worktree/worktree_skill.egg-info/top_level.txt",
        "skills/worktree/worktree_skill.egg-info/entry_points.txt",
    ]
    assert len(will_be_deleted) == 3
    assert len(will_be_kept) == 10

    base_sha = _make_base_repo(
        upstream, {rel: "content" for rel in will_be_deleted}
    )
    for rel in will_be_deleted:
        (upstream / rel).unlink()

    claude_dir.mkdir(parents=True)
    _write_tree(
        claude_dir,
        {rel: "content" for rel in will_be_deleted + will_be_kept},
    )
    (claude_dir / ".sync-state.json").write_text(
        json.dumps({"last_synced_base_sha": base_sha}), encoding="utf-8"
    )

    def _fake_clone(temp_dir: Path) -> None:
        temp_dir.mkdir(parents=True, exist_ok=True)
        import shutil as _shutil
        for item in upstream.rglob("*"):
            if ".git" in item.parts:
                continue
            if item.is_file():
                rel = item.relative_to(upstream)
                dst = temp_dir / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_text(item.read_text(encoding="utf-8"), encoding="utf-8")
        _shutil.copytree(upstream / ".git", temp_dir / ".git")

    monkeypatch.setattr(pull, "find_project_root", lambda: project_root)
    monkeypatch.setattr(pull, "clone_repo", _fake_clone)

    orphans = pull.compute_orphan_candidates(
        claude_dir, upstream, pull.load_preserve_list(claude_dir)
    )
    base_files = pull._list_base_files(upstream, base_sha)
    assert base_files is not None
    delete_group, keep_group = pull.classify_orphans_by_base(orphans, base_files)

    assert delete_group == sorted(will_be_deleted)
    assert keep_group == sorted(will_be_kept)

    pull.run_audit()
    out = capsys.readouterr().out
    assert "3 個將被刪除" in out
    assert "10 個將保留" in out
