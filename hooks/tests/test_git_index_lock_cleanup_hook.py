"""
Unit tests for git-index-lock-cleanup-hook.

Source: 0.18.0-W17-194 — 強化 lock 殘留警告訊息加入 GUI app 外部進程偵測
Related: PC-139 (git-index-lock-source-misattribution-gui-app-fork)
"""

import importlib.util
import os
import re
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest


HOOK_PATH = Path(__file__).resolve().parent.parent / "git-index-lock-cleanup-hook.py"


@pytest.fixture(scope="module")
def hook_module():
    sys.path.insert(0, str(HOOK_PATH.parent))
    sys.path.insert(0, str(HOOK_PATH.parent.parent / "lib"))
    spec = importlib.util.spec_from_file_location(
        "git_index_lock_cleanup_hook", HOOK_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def fresh_lock(tmp_path):
    """建立一個 .git/index.lock 模擬剛產生的 lock（lock_age < threshold）。"""
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    lock = git_dir / "index.lock"
    lock.write_text("")
    return tmp_path, lock


def test_fresh_lock_message_contains_gui_app_names(hook_module, fresh_lock):
    """訊息必須包含 4 個 GUI app 名稱（Fork / GitKraken / SourceTree / VS Code）。"""
    project_root, _ = fresh_lock
    with patch.object(hook_module, "get_project_root", return_value=str(project_root)):
        import logging
        logger = logging.getLogger("test")
        msg = hook_module.check_and_cleanup_index_lock(logger)

    assert msg is not None
    for name in ("Fork", "GitKraken", "SourceTree", "VS Code"):
        assert name in msg, f"訊息缺少 GUI app 名稱: {name}"


def test_fresh_lock_message_contains_ps_aux_detection(hook_module, fresh_lock):
    """訊息必須包含 ps aux 外部進程偵測指令範例。"""
    project_root, _ = fresh_lock
    with patch.object(hook_module, "get_project_root", return_value=str(project_root)):
        import logging
        logger = logging.getLogger("test")
        msg = hook_module.check_and_cleanup_index_lock(logger)

    assert msg is not None
    # regex match: ps aux | grep ... Fork|GitKraken|SourceTree
    assert re.search(r"ps\s+aux\s*\|\s*grep", msg), "訊息缺少 ps aux | grep 偵測指令"
    assert re.search(r"Fork\|GitKraken\|SourceTree", msg), "訊息缺少 GUI app pattern"


def test_fresh_lock_message_contains_pc139_reference(hook_module, fresh_lock):
    """訊息必須 cross-link 至 PC-139 error-pattern。"""
    project_root, _ = fresh_lock
    with patch.object(hook_module, "get_project_root", return_value=str(project_root)):
        import logging
        logger = logging.getLogger("test")
        msg = hook_module.check_and_cleanup_index_lock(logger)

    assert msg is not None
    assert "PC-139" in msg, "訊息缺少 PC-139 引用"
    assert (
        "PC-139-git-index-lock-source-misattribution-gui-app-fork" in msg
    ), "訊息缺少 PC-139 完整檔案名引用"


def test_no_lock_returns_none(hook_module, tmp_path):
    """無 lock 檔時應回傳 None。"""
    (tmp_path / ".git").mkdir()
    with patch.object(hook_module, "get_project_root", return_value=str(tmp_path)):
        import logging
        logger = logging.getLogger("test")
        msg = hook_module.check_and_cleanup_index_lock(logger)
    assert msg is None


def test_stale_lock_auto_removed(hook_module, tmp_path):
    """過期 lock 自動移除，訊息含 IMP-046 標記。"""
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    lock = git_dir / "index.lock"
    lock.write_text("")
    # 將 mtime 設為遠超過 STALE_THRESHOLD_SECONDS
    old_time = time.time() - (hook_module.STALE_THRESHOLD_SECONDS + 60)
    os.utime(lock, (old_time, old_time))

    with patch.object(hook_module, "get_project_root", return_value=str(tmp_path)):
        import logging
        logger = logging.getLogger("test")
        msg = hook_module.check_and_cleanup_index_lock(logger)

    assert msg is not None
    assert "IMP-046" in msg
    assert not lock.exists(), "過期 lock 應被自動移除"
