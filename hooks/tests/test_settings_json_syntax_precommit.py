"""settings.json 語法閘門（pre-commit）與其安裝的端對端測試（tarrragon/claude#97）。

在暫存 git repo 實際執行安裝器與 git commit：
- 正向對照：staged 的 settings.json 語法錯誤 -> commit 被擋，訊息含行列
- 反向對照：語法正確、未 staged、或只改其他檔 -> commit 成功
- 既有使用者 pre-commit 改名為 pre-commit.local 並被串接呼叫，內容不變
- 安裝冪等；core.hooksPath 有設定時跳過；閘門腳本啟動失敗時放行但可見
"""
from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
INSTALLER = HOOKS_DIR / "git-ref-transaction-guard-install-hook.py"
GATE_SCRIPT = HOOKS_DIR / "settings-json-syntax-precommit.py"

_spec = importlib.util.spec_from_file_location("settings_json_syntax_precommit", GATE_SCRIPT)
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)

VALID = '{\n  "hooks": {}\n}\n'
INVALID = '{\n  "hooks": {},\n}\n'  # 尾逗號：第 3 行第 1 列
GIT_ENV = {
    "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t.t",
    "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t.t",
}


def _git(repo: Path, *args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=str(repo), capture_output=True, text=True,
        env={**os.environ, **GIT_ENV, **(env or {})},
    )


def _install(repo: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(INSTALLER)], cwd=str(repo), capture_output=True, text=True,
        env={**os.environ, "CLAUDE_PROJECT_DIR": str(repo)},
    )


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    hooks = root / ".claude" / "hooks"
    hooks.mkdir(parents=True)
    shutil.copy2(GATE_SCRIPT, hooks / GATE_SCRIPT.name)
    (root / ".claude" / "settings.json").write_text(VALID, encoding="utf-8")
    _git(root, "add", "-A")
    assert _git(root, "commit", "-q", "-m", "init").returncode == 0
    return root


def _hooks_dir(repo: Path) -> Path:
    return repo / ".git" / "hooks"


def _head(repo: Path) -> str:
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


def _stage_settings(repo: Path, text: str) -> None:
    (repo / ".claude" / "settings.json").write_text(text, encoding="utf-8")
    _git(repo, "add", ".claude/settings.json")


# ---- 判定函式 ----

def test_find_syntax_error_reports_line_and_column():
    assert gate.find_syntax_error(VALID) is None
    assert gate.find_syntax_error(INVALID).startswith("第 3 行第 1 列")


# ---- 端對端：commit 的阻擋與放行 ----

def test_invalid_staged_settings_blocks_commit(repo):
    assert _install(repo).returncode == 0
    before = _head(repo)
    _stage_settings(repo, INVALID)

    result = _git(repo, "commit", "-m", "broken")

    assert result.returncode != 0
    assert "第 3 行第 1 列" in result.stderr
    assert _head(repo) == before


def test_valid_staged_settings_commits(repo):
    _install(repo)
    _stage_settings(repo, '{\n  "hooks": {"Stop": []}\n}\n')

    result = _git(repo, "commit", "-m", "ok")

    assert result.returncode == 0, result.stderr


def test_unstaged_broken_settings_does_not_block_other_commit(repo):
    _install(repo)
    (repo / ".claude" / "settings.json").write_text(INVALID, encoding="utf-8")  # 未 add
    (repo / "README.md").write_text("x\n", encoding="utf-8")
    _git(repo, "add", "README.md")

    assert _git(repo, "commit", "-m", "readme").returncode == 0


def test_reads_index_not_worktree(repo):
    """staged 的是壞版本、工作區已修好但未重新 add -> 仍阻擋。"""
    _install(repo)
    _stage_settings(repo, INVALID)
    (repo / ".claude" / "settings.json").write_text(VALID, encoding="utf-8")

    assert _git(repo, "commit", "-m", "still-broken-in-index").returncode != 0


def test_gate_startup_failure_allows_commit_visibly(repo, tmp_path):
    """閘門腳本啟動失敗（非 87 的非 0 結束碼）-> 放行並寫 stderr。"""
    _install(repo)
    fake_bin = tmp_path / "fakebin"
    fake_bin.mkdir()
    fake_python = fake_bin / "python3"
    fake_python.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    fake_python.chmod(0o755)
    _stage_settings(repo, INVALID)

    result = _git(repo, "commit", "-m", "x", env={"PATH": f"{fake_bin}:{os.environ['PATH']}"})

    assert result.returncode == 0
    assert "啟動失敗" in result.stderr


# ---- 涵蓋範圍（對應 hook-architect-technical-reference〈git 原生 hook 的安裝與移除〉）----

def _diverge_on_settings(repo: Path) -> None:
    """main 與 side 兩分支對 settings.json 做衝突修改。"""
    _git(repo, "checkout", "-q", "-b", "side")
    _stage_settings(repo, '{"side": 1}\n')
    assert _git(repo, "commit", "-q", "-m", "side").returncode == 0
    _git(repo, "checkout", "-q", "-")
    _stage_settings(repo, '{"main": 1}\n')
    assert _git(repo, "commit", "-q", "-m", "main").returncode == 0


def test_merge_continue_with_broken_settings_is_blocked(repo):
    """解完衝突後以 merge --continue 完成的合併提交會經過 pre-commit。"""
    _install(repo)
    _diverge_on_settings(repo)
    assert _git(repo, "merge", "side").returncode != 0  # 衝突
    _stage_settings(repo, INVALID)

    result = _git(repo, "merge", "--continue", env={"GIT_EDITOR": "true"})

    assert result.returncode != 0
    assert "第 3 行第 1 列" in result.stderr


def test_cherry_pick_is_not_covered(repo):
    """cherry-pick 不觸發 pre-commit（文件列為不涵蓋，此測試釘住該邊界）。"""
    _install(repo)
    _git(repo, "checkout", "-q", "-b", "broken")
    _stage_settings(repo, INVALID)
    assert _git(repo, "commit", "-q", "--no-verify", "-m", "broken").returncode == 0
    _git(repo, "checkout", "-q", "-")

    assert _git(repo, "cherry-pick", "broken").returncode == 0


# ---- 安裝：串接、冪等、hooksPath ----

def test_existing_user_precommit_is_chained_not_overwritten(repo):
    user_hook = _hooks_dir(repo) / "pre-commit"
    user_hook.parent.mkdir(parents=True, exist_ok=True)
    user_body = '#!/bin/sh\necho ran > "$(git rev-parse --show-toplevel)/user-hook-ran"\nexit 0\n'
    user_hook.write_text(user_body, encoding="utf-8")
    user_hook.chmod(0o755)

    result = _install(repo)

    chained = _hooks_dir(repo) / "pre-commit.local"
    assert chained.read_text(encoding="utf-8") == user_body
    assert "pre-commit.local" in result.stderr
    _stage_settings(repo, '{"a": 1}\n')
    assert _git(repo, "commit", "-m", "chained").returncode == 0
    assert (repo / "user-hook-ran").exists()


def test_chained_user_hook_failure_still_blocks(repo):
    user_hook = _hooks_dir(repo) / "pre-commit"
    user_hook.parent.mkdir(parents=True, exist_ok=True)
    user_hook.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    user_hook.chmod(0o755)
    _install(repo)
    _stage_settings(repo, '{"a": 2}\n')

    assert _git(repo, "commit", "-m", "user-blocks").returncode != 0


def test_install_is_idempotent(repo):
    _install(repo)
    first = (_hooks_dir(repo) / "pre-commit").read_text(encoding="utf-8")

    result = _install(repo)

    assert (_hooks_dir(repo) / "pre-commit").read_text(encoding="utf-8") == first
    assert not (_hooks_dir(repo) / "pre-commit.local").exists()
    assert "pre-commit" not in result.stderr


def test_skips_when_both_precommit_and_local_exist(repo):
    hooks = _hooks_dir(repo)
    hooks.mkdir(parents=True, exist_ok=True)
    (hooks / "pre-commit").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    (hooks / "pre-commit.local").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")

    result = _install(repo)

    assert "無法串接" in result.stderr
    assert (hooks / "pre-commit").read_text(encoding="utf-8") == "#!/bin/sh\nexit 0\n"


def test_skips_when_core_hooks_path_set(repo):
    _git(repo, "config", "core.hooksPath", ".husky")

    result = _install(repo)

    assert "core.hooksPath" in result.stderr
    assert not (_hooks_dir(repo) / "pre-commit").exists()
