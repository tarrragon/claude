"""Tests for sync-claude-push.py 安全強化（0.32.0-W1-008）.

兩個 push 端安全缺口（v1.48.6 誤推實證）：

防護 (a) push honor preserve:
  push 用 git archive HEAD 全樹 overlay，過濾僅靠 should_exclude（manifest），
  不讀 sync-preserve.yaml，致 APP 專案特化檔（skills/wrap-decision/references/
  project-integration/* 等）被推上共享框架。本組測試證明 preserve-listed 檔不在
  copy_filtered_from_staging 過濾後的集合中（與 pull 對稱）。

防護 (b) argparse 攔截:
  舊版把任何位置參數當 commit 訊息，--help / 未知旗標會觸發真實不可逆推送
  （PC-V1-001 再犯）。本組測試證明 parse_args 對 --help exit 0、未知旗標 exit
  非 0，且解析階段不觸發任何網路 push（純函式，不 clone / 不 push）。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parent.parent / "sync-claude-push.py"
_spec = importlib.util.spec_from_file_location("sync_claude_push", _SCRIPT)
assert _spec and _spec.loader
sync_mod = importlib.util.module_from_spec(_spec)
sys.modules["sync_claude_push"] = sync_mod
_spec.loader.exec_module(sync_mod)  # type: ignore[union-attr]


def _write(base: Path, rel: str, content: str = "x\n") -> None:
    p = base / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


# =====================================================================
# 防護 (a)：push honor preserve
# =====================================================================

def _write_preserve(claude_dir: Path, paths: list[str]) -> None:
    lines = ["preserve:"]
    lines += [f"  - {p}" for p in paths]
    (claude_dir / "sync-preserve.yaml").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def test_load_preserve_list_reads_paths(tmp_path: Path):
    """load_preserve_list 讀出 sync-preserve.yaml 的相對路徑集合。"""
    _write_preserve(
        tmp_path,
        [
            "skills/wrap-decision/references/project-integration/README.md",
            "error-patterns/process-compliance/PC-177-x.md",
        ],
    )
    result = sync_mod.load_preserve_list(tmp_path)
    assert result == {
        "skills/wrap-decision/references/project-integration/README.md",
        "error-patterns/process-compliance/PC-177-x.md",
    }


def test_load_preserve_list_missing_file_returns_empty(tmp_path: Path):
    """無 sync-preserve.yaml 時回傳空集合（合法：專案未定義 preserve）。"""
    assert sync_mod.load_preserve_list(tmp_path) == set()


def test_copy_filtered_excludes_preserve_listed(tmp_path: Path):
    """preserve-listed 檔不在 copy_filtered_from_staging 過濾後的遠端集合中。"""
    src = tmp_path / "staging"
    dst = tmp_path / "remote"
    src.mkdir()
    dst.mkdir()
    preserved_rel = "skills/wrap-decision/references/project-integration/README.md"
    _write(src, preserved_rel)
    _write(src, "rules/core/quality-baseline.md")

    preserve = {preserved_rel}
    count = sync_mod.copy_filtered_from_staging(src, dst, preserve)

    # preserve 檔不複製到遠端；框架檔正常複製
    assert not (dst / preserved_rel).exists()
    assert (dst / "rules/core/quality-baseline.md").exists()
    assert count == 1


def test_copy_filtered_without_preserve_copies_all(tmp_path: Path):
    """preserve 為空（向後相容）時所有非 should_exclude 檔照常複製。"""
    src = tmp_path / "staging"
    dst = tmp_path / "remote"
    src.mkdir()
    dst.mkdir()
    _write(src, "a/b.md")
    _write(src, "c.md")

    count = sync_mod.copy_filtered_from_staging(src, dst, set())

    assert (dst / "a/b.md").exists()
    assert (dst / "c.md").exists()
    assert count == 2


def test_detect_uncleaned_deletions_skips_preserve(tmp_path: Path):
    """遠端存在的 preserve 檔不應被當成本地刪除的孤兒（與 clean 對齊）。"""
    temp_dir = tmp_path / "remote_clone"
    staging = tmp_path / "staging"
    temp_dir.mkdir()
    staging.mkdir()
    preserved_rel = "skills/wrap-decision/references/project-integration/README.md"
    # 遠端有 preserve 檔，本地 staging 無（因 push 端不推 preserve）→ 不算孤兒
    _write(temp_dir, preserved_rel)
    # 真正孤兒
    _write(temp_dir, "hooks/obsolete.py")

    orphans = sync_mod.detect_uncleaned_deletions(
        temp_dir, staging, preserve={preserved_rel}
    )

    assert orphans == ["hooks/obsolete.py"]


def test_clean_stale_files_skips_preserve(tmp_path: Path):
    """--clean 不刪除遠端的 preserve 檔（可能屬他專案特化內容）。"""
    temp_dir = tmp_path / "remote_clone"
    staging = tmp_path / "staging"
    temp_dir.mkdir()
    staging.mkdir()
    preserved_rel = "skills/wrap-decision/references/project-integration/README.md"
    _write(temp_dir, preserved_rel)
    _write(temp_dir, "hooks/obsolete.py")

    deleted = sync_mod.clean_stale_files(temp_dir, staging, preserve={preserved_rel})

    # preserve 檔保留；真孤兒被刪（deleted 計入檔 + 隨之清空的目錄）
    assert (temp_dir / preserved_rel).exists()
    assert not (temp_dir / "hooks/obsolete.py").exists()
    assert deleted >= 1


# =====================================================================
# 防護 (b)：argparse 攔截（不觸發推送）
# =====================================================================

def test_parse_args_help_exits_zero(capsys):
    """--help 顯示用法並 exit 0，不觸發推送。"""
    with pytest.raises(SystemExit) as exc:
        sync_mod.parse_args(["--help"])
    assert exc.value.code == 0


def test_parse_args_unknown_flag_exits_nonzero(capsys):
    """未知旗標 exit 非 0，不當作 commit 訊息觸發推送（PC-V1-001 防護）。"""
    with pytest.raises(SystemExit) as exc:
        sync_mod.parse_args(["--unknown-flag"])
    assert exc.value.code != 0


def test_parse_args_short_help_exits_zero():
    """-h 同 --help，exit 0。"""
    with pytest.raises(SystemExit) as exc:
        sync_mod.parse_args(["-h"])
    assert exc.value.code == 0


def test_parse_args_positional_message_accepted():
    """位置參數 commit message 正常接受（向後相容）。"""
    args = sync_mod.parse_args(["my commit message"])
    assert args.message == "my commit message"
    assert args.clean is False
    assert args.force is False
    assert args.dry_run is False


def test_parse_args_known_flags_parsed():
    """--clean / --force / --dry-run 正常解析。"""
    args = sync_mod.parse_args(["--clean", "--force", "--dry-run"])
    assert args.clean is True
    assert args.force is True
    assert args.dry_run is True
    assert args.message is None


def test_parse_args_no_args_message_none():
    """無參數時 message 為 None（auto-generated 路徑）。"""
    args = sync_mod.parse_args([])
    assert args.message is None
