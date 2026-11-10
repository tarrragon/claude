"""Tests for sync-claude-pull.py 衝突處理標準化（1.0.0-W1-084）。

涵蓋 acceptance：
  - VERSION / CHANGELOG.md 衝突時自動採 upstream，.sync-conflicts/ 仍留對照副本，
    且不計入 conflicts 清單（已自動解決）
  - 非版本檔衝突：merged 結果（含 git 衝突標記）寫回工作區，upstream 非重疊
    hunk 不再隨衝突靜默消失，真正重疊處以標記待人工解決（0.2.1-W3-1207）
  - detect_conflict_residue：pull 開始時偵測 .sync-conflicts/ 既有殘留
    （mtime 早於本次、排除 .gitignore、目錄不存在回空）
  - warn_conflict_residue：殘留時 stdout 警告列出
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
import time
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parent.parent / "sync-claude-pull.py"
_spec = importlib.util.spec_from_file_location(
    "sync_claude_pull_conflict_handling", _SCRIPT
)
assert _spec and _spec.loader
pull = importlib.util.module_from_spec(_spec)
sys.modules["sync_claude_pull_conflict_handling"] = pull
_spec.loader.exec_module(pull)  # type: ignore[union-attr]


# ============================================================================
# Helpers：建立可控的 git upstream repo fixture
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


def _setup_version_conflict(tmp_path: Path):
    """建立版本檔 + 一般檔皆衝突的 fixture。

    上游 repo root 直接對應本地 .claude/。三檔皆 base / local / upstream 三方不同：
      - VERSION：版本檔，預期自動採 upstream
      - CHANGELOG.md：版本檔，預期自動採 upstream
      - rules/other.md：一般檔，預期維持原 local-保留路徑

    回傳 (project_root, upstream_repo, base_sha)。
    """
    upstream = tmp_path / "upstream"
    _init_repo(upstream)
    (upstream / "VERSION").write_text("1.0.0\n", encoding="utf-8")
    (upstream / "CHANGELOG.md").write_text(
        "# Changelog\n\n## 1.0.0\n- base\n", encoding="utf-8"
    )
    rules = upstream / "rules"
    rules.mkdir()
    (rules / "other.md").write_text("a\nb\nc\n", encoding="utf-8")
    base = _commit_all(upstream, "base")

    (upstream / "VERSION").write_text("1.2.0\n", encoding="utf-8")
    (upstream / "CHANGELOG.md").write_text(
        "# Changelog\n\n## 1.2.0\n- upstream bump\n", encoding="utf-8"
    )
    (rules / "other.md").write_text("a\nUPSTREAM\nc\n", encoding="utf-8")
    _commit_all(upstream, "head")

    project_root = tmp_path / "proj"
    claude = project_root / ".claude"
    (claude / "rules").mkdir(parents=True)
    # 本地三檔皆有別於 base 與 upstream 的修改 → 三方合併必衝突
    (claude / "VERSION").write_text("1.1.0-local\n", encoding="utf-8")
    (claude / "CHANGELOG.md").write_text(
        "# Changelog\n\n## 1.1.0-local\n- local drift\n", encoding="utf-8"
    )
    (claude / "rules" / "other.md").write_text("a\nLOCAL\nc\n", encoding="utf-8")
    return project_root, upstream, base


# ============================================================================
# 版本檔衝突自動採 upstream
# ============================================================================

def test_version_file_conflict_takes_upstream(tmp_path):
    """VERSION 衝突 → 本地檔自動覆蓋為 upstream 內容，不列入 conflicts。"""
    project_root, upstream, base = _setup_version_conflict(tmp_path)
    claude = project_root / ".claude"

    _applied, conflicts, _residue = pull.apply_upstream_delta(
        project_root, upstream, base
    )

    assert (claude / "VERSION").read_text(encoding="utf-8") == "1.2.0\n"
    assert "VERSION" not in conflicts


def test_changelog_conflict_takes_upstream(tmp_path):
    """CHANGELOG.md 衝突 → 同樣自動採 upstream。"""
    project_root, upstream, base = _setup_version_conflict(tmp_path)
    claude = project_root / ".claude"

    _applied, conflicts, _residue = pull.apply_upstream_delta(
        project_root, upstream, base
    )

    assert "upstream bump" in (claude / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "CHANGELOG.md" not in conflicts


def test_version_file_conflict_keeps_reference_copy(tmp_path):
    """自動採 upstream 後 .sync-conflicts/ 仍留對照副本（含衝突標記）。"""
    project_root, upstream, base = _setup_version_conflict(tmp_path)
    claude = project_root / ".claude"

    pull.apply_upstream_delta(project_root, upstream, base)

    version_copy = claude / ".sync-conflicts" / "VERSION"
    changelog_copy = claude / ".sync-conflicts" / "CHANGELOG.md"
    assert version_copy.exists()
    assert changelog_copy.exists()
    # 對照副本是 git merge-file 的衝突標記結果，含 local 與 upstream 雙方內容
    copy_text = version_copy.read_text(encoding="utf-8")
    assert "1.1.0-local" in copy_text
    assert "1.2.0" in copy_text


def test_version_file_auto_resolve_prints_note(tmp_path, capsys):
    """自動採 upstream 時 stdout 有註記。"""
    project_root, upstream, base = _setup_version_conflict(tmp_path)

    pull.apply_upstream_delta(project_root, upstream, base)

    out = capsys.readouterr().out
    assert "版本檔衝突自動採 upstream: VERSION" in out
    assert "版本檔衝突自動採 upstream: CHANGELOG.md" in out


def test_non_version_conflict_writes_merged_with_markers(tmp_path):
    """非版本檔衝突：merged 結果（含 git 衝突標記）寫回工作區，列入 conflicts，
    且 .sync-conflicts/ 仍留對照副本；upstream 內容不再靜默消失（0.2.1-W3-1207）。
    """
    project_root, upstream, base = _setup_version_conflict(tmp_path)
    claude = project_root / ".claude"

    _applied, conflicts, _residue = pull.apply_upstream_delta(
        project_root, upstream, base
    )

    assert "rules/other.md" in conflicts
    working_text = (claude / "rules" / "other.md").read_text(encoding="utf-8")
    # 雙方內容都可在工作區取得（本地 LOCAL 未消失、upstream UPSTREAM 已落地）
    assert "LOCAL" in working_text
    assert "UPSTREAM" in working_text
    assert "<<<<<<< local" in working_text
    assert ">>>>>>> upstream" in working_text
    assert (claude / ".sync-conflicts" / "rules" / "other.md").exists()


def test_version_files_whitelist_is_exact(tmp_path):
    """白名單限定 .claude/ 頂層 VERSION 與 CHANGELOG.md 兩檔。"""
    assert pull.VERSION_FILES_TAKE_UPSTREAM == frozenset({"VERSION", "CHANGELOG.md"})
    # 巢狀同名檔不在白名單（claude_rel 為完整相對路徑，精確比對）
    assert "rules/VERSION" not in pull.VERSION_FILES_TAKE_UPSTREAM


# ============================================================================
# 殘留偵測 detect_conflict_residue / warn_conflict_residue
# ============================================================================

def test_residue_empty_when_dir_absent(tmp_path):
    claude = tmp_path / ".claude"
    claude.mkdir()
    assert pull.detect_conflict_residue(claude) == []


def test_residue_lists_existing_files_excluding_gitignore(tmp_path):
    claude = tmp_path / ".claude"
    conflicts = claude / ".sync-conflicts"
    (conflicts / "rules").mkdir(parents=True)
    (conflicts / ".gitignore").write_text("*\n", encoding="utf-8")
    (conflicts / "VERSION").write_text("old conflict\n", encoding="utf-8")
    (conflicts / "rules" / "x.md").write_text("old conflict\n", encoding="utf-8")

    residue = pull.detect_conflict_residue(claude)

    assert residue == ["VERSION", "rules/x.md"]


def test_residue_respects_before_time(tmp_path):
    """mtime 晚於 before_time 的檔（本次新寫入）不列為殘留。"""
    claude = tmp_path / ".claude"
    conflicts = claude / ".sync-conflicts"
    conflicts.mkdir(parents=True)
    (conflicts / "stale.md").write_text("previous run\n", encoding="utf-8")
    cutoff = time.time() + 100  # 全部早於 cutoff → 殘留
    assert pull.detect_conflict_residue(claude, before_time=cutoff) == ["stale.md"]
    cutoff = time.time() - 100  # 全部晚於 cutoff → 非殘留
    assert pull.detect_conflict_residue(claude, before_time=cutoff) == []


def test_warn_conflict_residue_prints_listing(tmp_path, capsys):
    claude = tmp_path / ".claude"
    conflicts = claude / ".sync-conflicts"
    conflicts.mkdir(parents=True)
    (conflicts / "leftover.md").write_text("unhandled\n", encoding="utf-8")

    residue = pull.warn_conflict_residue(claude)

    out = capsys.readouterr().out
    assert residue == ["leftover.md"]
    assert "1 個前次 pull 衝突殘留未處理" in out
    assert "leftover.md" in out
    assert "pull 後檢查清單" in out


def test_warn_conflict_residue_silent_when_clean(tmp_path, capsys):
    claude = tmp_path / ".claude"
    claude.mkdir()

    residue = pull.warn_conflict_residue(claude)

    assert residue == []
    assert "殘留" not in capsys.readouterr().out


# ============================================================================
# 衝突標記殘留掃描只涵蓋 pull 同步範圍（tarrragon/claude#88）
# ============================================================================

_MARKER_TEXT = "a\n<<<<<<< local\nLOCAL\n=======\nUPSTREAM\n>>>>>>> upstream\nc\n"

# pull 不寫入的位置：local-only 目錄、local-only 檔名、pull 方向排除的根層目錄、
# REMOTE_ONLY 名稱、root-anchored 的 logs/
_OUT_OF_SCOPE_PATHS = (
    "hook-logs/some-hook/run.log",
    "handoff/pending/x.md",
    "settings.local.json",
    ".sync-conflicts/rules/conflict.md",
    ".github/workflows/ci.yml",
    "project-templates/FLUTTER.md",
    "logs/session.log",
    "skills/foo/__pycache__/mod.txt",
)


def _write(claude: Path, rel: str, text: str = _MARKER_TEXT) -> None:
    target = claude / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def test_scan_skips_out_of_scope_files_but_flags_in_scope(tmp_path):
    """同一 fixture 內：範圍外檔案含標記不列出，範圍內檔案含標記列出（E2 正反對照）。"""
    claude = tmp_path / ".claude"
    for rel in _OUT_OF_SCOPE_PATHS:
        _write(claude, rel)
    _write(claude, "rules/conflict.md")
    _write(claude, "skills/foo/state/kept.md")  # skill 內部同名 state/ 屬同步範圍

    hits = pull.scan_conflict_marker_residue(claude)

    assert hits == ["rules/conflict.md", "skills/foo/state/kept.md"]


def test_scan_skips_symlinked_files(tmp_path):
    claude = tmp_path / ".claude"
    outside = tmp_path / "outside.md"
    outside.write_text(_MARKER_TEXT, encoding="utf-8")
    (claude / "rules").mkdir(parents=True)
    (claude / "rules" / "link.md").symlink_to(outside)

    assert pull.scan_conflict_marker_residue(claude) == []


def test_check_residue_exit_zero_when_only_out_of_scope_hits(tmp_path, capsys):
    """hook-logs 等非同步範圍檔案含標記字樣時，pull 收尾判定為成功。"""
    claude = tmp_path / ".claude"
    for rel in _OUT_OF_SCOPE_PATHS:
        _write(claude, rel)
    _write(claude, "rules/clean.md", "正常內容\n")

    rc = pull.check_conflict_marker_residue(claude)

    assert rc == 0
    assert capsys.readouterr().err == ""


def test_check_residue_exit_one_lists_in_scope_hits(tmp_path, capsys):
    claude = tmp_path / ".claude"
    _write(claude, "hook-logs/run.log")
    _write(claude, "hooks/broken-hook.py")

    rc = pull.check_conflict_marker_residue(claude)

    err = capsys.readouterr().err
    assert rc == 1
    assert "hooks/broken-hook.py" in err
    assert "hook-logs" not in err


def test_scan_function_importable_without_pull_module(tmp_path):
    """掃描函式可由其他模組直接匯入，不需載入 pull 腳本或其執行狀態。"""
    claude_root = Path(__file__).resolve().parent.parent.parent
    code = (
        "import sys; from pathlib import Path\n"
        f"sys.path.insert(0, {str(claude_root)!r})\n"
        "from lib.sync_conflict_residue import scan_conflict_marker_residue\n"
        "print(scan_conflict_marker_residue(Path(sys.argv[1])))\n"
    )
    claude = tmp_path / ".claude"
    _write(claude, "rules/conflict.md")
    _write(claude, "hook-logs/run.log")

    result = subprocess.run(
        [sys.executable, "-c", code, str(claude)],
        capture_output=True, text=True, check=True,
    )

    assert result.stdout.strip() == "['rules/conflict.md']"
    assert "sync_claude_pull" not in result.stderr


# ============================================================================
# 衝突輪後的 base 收斂：pending base 與 --resolve-done（tarrragon/claude#88）
# ============================================================================

import json  # noqa: E402


def _state(claude: Path) -> dict:
    return json.loads((claude / ".sync-state.json").read_text(encoding="utf-8"))


def _conflict_round(tmp_path: Path):
    """建立上游 base→head 與本地同行修改，跑一輪 pull 產生衝突。"""
    upstream = tmp_path / "upstream"
    _init_repo(upstream)
    (upstream / "rules").mkdir()
    (upstream / "rules" / "conflict.md").write_text("a\nb\nc\n", encoding="utf-8")
    base = _commit_all(upstream, "base")
    (upstream / "rules" / "conflict.md").write_text("a\nUPSTREAM\nc\n", encoding="utf-8")
    head = _commit_all(upstream, "head")

    project_root = tmp_path / "proj"
    claude = project_root / ".claude"
    (claude / "rules").mkdir(parents=True)
    (claude / "rules" / "conflict.md").write_text("a\nLOCAL\nc\n", encoding="utf-8")
    (claude / ".sync-state.json").write_text(
        json.dumps({"last_synced_base_sha": base}), encoding="utf-8"
    )
    pull._sync_with_backup(project_root, upstream)
    return upstream, project_root, claude, base, head


def _second_upstream_round(upstream: Path, project_root: Path) -> str:
    """上游再前進一個與衝突檔無關的 commit，跑第二輪 pull。"""
    (upstream / "rules" / "other.md").write_text("new\n", encoding="utf-8")
    head2 = _commit_all(upstream, "head2")
    pull._sync_with_backup(project_root, upstream)
    return head2


def test_conflict_round_records_pending_base_without_advancing(tmp_path):
    _, _, claude, base, head = _conflict_round(tmp_path)

    state = _state(claude)
    assert "<<<<<<< " in (claude / "rules" / "conflict.md").read_text(encoding="utf-8")
    assert state["last_synced_base_sha"] == base
    assert state["pending_base_sha"] == head


def test_resolve_done_refuses_while_markers_remain(tmp_path, capsys):
    _, _, claude, base, head = _conflict_round(tmp_path)
    capsys.readouterr()

    rc = pull.resolve_done(claude)

    err = capsys.readouterr().err
    assert rc == 1
    assert "rules/conflict.md" in err
    assert _state(claude)["last_synced_base_sha"] == base
    assert _state(claude)["pending_base_sha"] == head


def test_resolve_done_promotes_pending_and_next_pull_does_not_rereport(tmp_path):
    """解完衝突 → --resolve-done 推進 base → 下一輪以新 base 合併，已解衝突不重報。"""
    upstream, project_root, claude, _, head = _conflict_round(tmp_path)
    (claude / "rules" / "conflict.md").write_text("a\nRESOLVED\nc\n", encoding="utf-8")

    assert pull.resolve_done(claude) == 0
    assert _state(claude)["last_synced_base_sha"] == head
    assert "pending_base_sha" not in _state(claude)

    head2 = _second_upstream_round(upstream, project_root)

    assert (claude / "rules" / "conflict.md").read_text(encoding="utf-8") == "a\nRESOLVED\nc\n"
    assert _state(claude)["last_synced_base_sha"] == head2
    assert "pending_base_sha" not in _state(claude)


def test_without_resolve_done_next_pull_rereports_resolved_conflict(tmp_path):
    """對照組：不執行 --resolve-done，下一輪仍以舊 base 合併，已解的衝突重新出現。"""
    upstream, project_root, claude, base, _ = _conflict_round(tmp_path)
    (claude / "rules" / "conflict.md").write_text("a\nRESOLVED\nc\n", encoding="utf-8")

    _second_upstream_round(upstream, project_root)

    assert "<<<<<<< " in (claude / "rules" / "conflict.md").read_text(encoding="utf-8")
    assert _state(claude)["last_synced_base_sha"] == base


def test_resolve_done_without_pending_is_noop(tmp_path):
    claude = tmp_path / ".claude"
    claude.mkdir()
    (claude / ".sync-state.json").write_text(
        json.dumps({"last_synced_base_sha": "abc"}), encoding="utf-8"
    )

    assert pull.resolve_done(claude) == 0
    assert _state(claude) == {"last_synced_base_sha": "abc"}


def test_warn_pending_base_hints_only_when_pending(tmp_path, capsys):
    claude = tmp_path / ".claude"
    claude.mkdir()
    (claude / ".sync-state.json").write_text("{}", encoding="utf-8")
    assert pull.warn_pending_base(claude) is None
    assert "--resolve-done" not in capsys.readouterr().out

    pull.write_pending_base_sha(claude, "f" * 40)
    assert pull.warn_pending_base(claude) == "f" * 40
    assert "--resolve-done" in capsys.readouterr().out


def test_parse_args_rejects_resolve_done_with_audit_or_bump():
    assert pull.parse_args(["--resolve-done"]).resolve_done is True
    for extra in (["--audit"], ["--bump"]):
        try:
            pull.parse_args(["--resolve-done", *extra])
        except SystemExit as exc:
            assert exc.code == 2
        else:
            raise AssertionError(f"--resolve-done 與 {extra} 併用應被拒絕")
