"""E2：hook 讀取 git 路徑清單須以 -z 取原始路徑（真實 git repo，不 mock subprocess）。

紅燈路徑：檔名含雙引號的 CJK 路徑。core.quotepath=false 只免除非 ASCII 跳脫，
含 `"` 的路徑仍會被加引號與反斜線跳脫，只有 -z 能取回原始路徑。
對照組：純 ASCII 與純 CJK 路徑（不退化）。
"""

import importlib.util
import logging
import subprocess
import sys
from pathlib import Path
from typing import List

import pytest

HOOKS_DIR = Path(__file__).parent.parent
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))
    sys.path.insert(0, str(HOOKS_DIR.parent))

QUOTED_CJK_NAME = '文件"甲.md'
PLAIN_CJK_NAME = "文件乙.md"
ASCII_NAME = "plain.md"


def _load(filename: str, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, HOOKS_DIR / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=str(repo), check=True, capture_output=True,
    )


@pytest.fixture
def logger():
    log = logging.getLogger("test-git-z-path-reading-e2")
    log.addHandler(logging.NullHandler())
    return log


@pytest.fixture
def repo(tmp_path):
    _git(tmp_path, "init", "-q")
    (tmp_path / "seed.txt").write_text("seed", encoding="utf-8")
    _git(tmp_path, "add", "seed.txt")
    _git(tmp_path, "commit", "-q", "-m", "seed")
    return tmp_path


def _commit_files(repo: Path, rel_paths: List[str]) -> None:
    for rel in rel_paths:
        target = repo / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("x", encoding="utf-8")
    _git(repo, "add", "--", *rel_paths)
    _git(repo, "commit", "-q", "-m", "add")


NAMES = [ASCII_NAME, PLAIN_CJK_NAME, QUOTED_CJK_NAME]


def test_parallel_dispatch_verification_diff_head_reads_raw_paths(repo, logger):
    hook = _load("parallel-dispatch-verification-hook.py", "pdv_hook_e2")
    _commit_files(repo, [f"docs/{n}" for n in NAMES])
    for n in NAMES:
        (repo / "docs" / n).write_text("changed", encoding="utf-8")

    changed = hook.get_git_changed_files(repo, logger)

    for n in NAMES:
        assert hook.normalize_path(f"docs/{n}") in changed


@pytest.mark.parametrize("module_file,module_name", [
    ("skill-cli-sync-check-hook.py", "scs_hook_e2"),
    ("variable-count-literal-guard-hook.py", "vcl_hook_e2"),
])
def test_get_commit_files_reads_raw_paths(repo, logger, module_file, module_name):
    hook = _load(module_file, module_name)
    rels = [f".claude/rules/{n}" for n in NAMES]
    _commit_files(repo, rels)

    files = hook.get_commit_files(repo, logger)

    assert sorted(files) == sorted(rels)


def test_gitignore_check_ls_files_reads_raw_paths(repo, logger):
    hook = _load("session-start-gitignore-check-hook.py", "gic_hook_e2")
    rels = [f".claude/state/{n}" for n in NAMES]
    _commit_files(repo, rels)

    tracked = hook.check_tracked_runtime_state(repo, logger)

    assert sorted(tracked) == sorted(rels)


def test_experiment_artifact_untracked_status_reads_raw_paths(repo, logger):
    from acceptance_checkers import experiment_artifact_checker as checker

    rels = [f"docs/{n}" for n in NAMES]
    for rel in rels:
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text("x", encoding="utf-8")

    untracked = checker._run_git_status_untracked(repo, logger)

    assert sorted(untracked) == sorted(rels)


def test_experiment_artifact_status_skips_rename_source_path(repo, logger):
    """status -z 的 rename 條目多帶一段舊路徑，不可被當成 untracked 項目。"""
    from acceptance_checkers import experiment_artifact_checker as checker

    _commit_files(repo, [f"docs/{QUOTED_CJK_NAME}"])
    _git(repo, "mv", f"docs/{QUOTED_CJK_NAME}", f"docs/{PLAIN_CJK_NAME}")
    (repo / "docs" / ASCII_NAME).write_text("x", encoding="utf-8")

    untracked = checker._run_git_status_untracked(repo, logger)

    assert untracked == [f"docs/{ASCII_NAME}"]


def test_commit_msg_layer2_changed_files_reads_raw_paths(repo, logger):
    hook = _load("commit-msg-layer2-marker-check-hook.py", "l2_hook_e2")
    rels = [f"docs/{n}" for n in NAMES]
    _commit_files(repo, rels)

    files = hook._get_changed_files(repo, logger)

    assert sorted(files) == sorted(rels)
