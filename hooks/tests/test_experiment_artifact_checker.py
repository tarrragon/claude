"""
Experiment Artifact Checker Tests

對應 Ticket 0.2.1-W3-676：complete 前實驗器材殘留掃描 checker。

驗證範圍：
- 已登記已處置（kept + successor）：不阻擋
- 已登記未處置（status=active）：阻擋
- 未登記殘留（git status 有檔案但無登記）：阻擋
- 已登記 removed 但檔案仍在工作區（登記與實況不一致）：阻擋
- 無候選檔案時短路，不呼叫 list-artifacts（效能與 CLI 依賴最小化）
- git status / list-artifacts 子行程失敗時 fail-open（不阻擋，非本檢查職責的
  基礎設施故障不應連帶擋下 complete）
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_hooks_dir = Path(__file__).parent.parent
if str(_hooks_dir) not in sys.path:
    sys.path.insert(0, str(_hooks_dir))

from acceptance_checkers.experiment_artifact_checker import (  # noqa: E402
    check_experiment_artifact_residual,
)


@pytest.fixture
def logger():
    log = logging.getLogger("test-experiment-artifact-checker")
    log.addHandler(logging.NullHandler())
    log.setLevel(logging.CRITICAL)
    return log


TICKET_ID = "0.2.1-W3-999"


def _git_status_result(untracked_paths: list) -> MagicMock:
    """組出 git status --porcelain --untracked-files=all 的 subprocess 結果。"""
    lines = [f"?? {p}" for p in untracked_paths]
    result = MagicMock()
    result.returncode = 0
    result.stdout = "\n".join(lines)
    result.stderr = ""
    return result


def _list_artifacts_result(entries: list) -> MagicMock:
    result = MagicMock()
    result.returncode = 0
    result.stdout = json.dumps(entries)
    result.stderr = ""
    return result


def _dispatch_mock(git_status_stdout_paths, artifacts_entries):
    """依命令首字判斷回傳 git status 或 list-artifacts 的 mock 結果。"""

    def _side_effect(cmd, **kwargs):
        if cmd[:2] == ["git", "--no-optional-locks"]:
            return _git_status_result(git_status_stdout_paths)
        if cmd[:3] == ["ticket", "track", "list-artifacts"]:
            return _list_artifacts_result(artifacts_entries)
        raise AssertionError(f"未預期的命令: {cmd}")

    return _side_effect


def _patch_subprocess(side_effect):
    from acceptance_checkers import experiment_artifact_checker as _mod

    return patch.object(_mod.subprocess, "run", side_effect=side_effect)


# ----------------------------------------------------------------------------
# 情境 1：無候選檔案（短路，不呼叫 list-artifacts）
# ----------------------------------------------------------------------------

def test_no_candidate_files_passes_without_calling_list_artifacts(logger):
    call_log = []

    def _side_effect(cmd, **kwargs):
        call_log.append(cmd)
        if cmd[:2] == ["git", "--no-optional-locks"]:
            return _git_status_result(["docs/unrelated.md"])
        raise AssertionError("不應呼叫 list-artifacts（無候選檔案時應短路）")

    with _patch_subprocess(_side_effect):
        should_block, msg = check_experiment_artifact_residual(
            TICKET_ID, Path("/fake/project"), logger
        )

    assert should_block is False
    assert msg is None
    assert len(call_log) == 1  # 只呼叫 git status，未呼叫 list-artifacts


# ----------------------------------------------------------------------------
# 情境 2：已登記已處置（kept + successor）：不阻擋
# ----------------------------------------------------------------------------

def test_registered_kept_with_successor_passes(logger):
    path = f"experiment-{TICKET_ID}-sentinel.md"
    entries = [
        {
            "label": "EXP-1",
            "timestamp": "2026-08-20 10:00",
            "path": path,
            "purpose": "測試",
            "expiry": "本票收尾",
            "type": "明示",
            "status": "kept（接手：0.2.1-W3-998）",
        }
    ]
    with _patch_subprocess(_dispatch_mock([path], entries)):
        should_block, msg = check_experiment_artifact_residual(
            TICKET_ID, Path("/fake/project"), logger
        )

    assert should_block is False
    assert msg is None


# ----------------------------------------------------------------------------
# 情境 3：已登記未處置（status=active）：阻擋
# ----------------------------------------------------------------------------

def test_registered_active_blocks(logger):
    path = f"experiment-{TICKET_ID}-sentinel.md"
    entries = [
        {
            "label": "EXP-1",
            "timestamp": "2026-08-20 10:00",
            "path": path,
            "purpose": "測試",
            "expiry": "本票收尾",
            "type": "明示",
            "status": "active",
        }
    ]
    with _patch_subprocess(_dispatch_mock([path], entries)):
        should_block, msg = check_experiment_artifact_residual(
            TICKET_ID, Path("/fake/project"), logger
        )

    assert should_block is True
    assert "EXP-1" in msg
    assert path in msg
    assert "resolve-artifact" in msg


# ----------------------------------------------------------------------------
# 情境 4：未登記殘留：阻擋，且不依賴票面登記完整性（entries 為空）
# ----------------------------------------------------------------------------

def test_unregistered_residual_blocks(logger):
    path = f"experiment-{TICKET_ID}-orphan.log"
    with _patch_subprocess(_dispatch_mock([path], [])):
        should_block, msg = check_experiment_artifact_residual(
            TICKET_ID, Path("/fake/project"), logger
        )

    assert should_block is True
    assert path in msg
    assert "未登記" in msg


# ----------------------------------------------------------------------------
# 情境 5：已登記為 removed 但檔案仍在工作區（登記與實況不一致）：阻擋
# ----------------------------------------------------------------------------

def test_registered_removed_but_file_still_present_blocks(logger):
    path = f"experiment-{TICKET_ID}-sentinel.md"
    entries = [
        {
            "label": "EXP-1",
            "timestamp": "2026-08-20 10:00",
            "path": path,
            "purpose": "測試",
            "expiry": "本票收尾",
            "type": "明示",
            "status": "removed",
        }
    ]
    with _patch_subprocess(_dispatch_mock([path], entries)):
        should_block, msg = check_experiment_artifact_residual(
            TICKET_ID, Path("/fake/project"), logger
        )

    assert should_block is True
    assert "EXP-1" in msg
    assert "removed" in msg


# ----------------------------------------------------------------------------
# 情境 6：僅比對本票 ID 前綴，其他票的 experiment- 檔案不在掃描範圍
# ----------------------------------------------------------------------------

def test_other_ticket_experiment_file_is_out_of_scope(logger):
    other_ticket_path = "experiment-0.2.1-W3-111-something.log"
    with _patch_subprocess(_dispatch_mock([other_ticket_path], [])):
        should_block, msg = check_experiment_artifact_residual(
            TICKET_ID, Path("/fake/project"), logger
        )

    assert should_block is False
    assert msg is None


# ----------------------------------------------------------------------------
# 情境 7：git status 子行程失敗 -> fail-open（不阻擋）
# ----------------------------------------------------------------------------

def test_git_status_failure_fails_open(logger):
    def _side_effect(cmd, **kwargs):
        raise FileNotFoundError("git not found")

    with _patch_subprocess(_side_effect):
        should_block, msg = check_experiment_artifact_residual(
            TICKET_ID, Path("/fake/project"), logger
        )

    assert should_block is False
    assert msg is None


# ----------------------------------------------------------------------------
# 情境 8：list-artifacts 子行程失敗 -> fail-open（不阻擋；候選檔案仍存在但
# 無法確認登記狀態時，不因基礎設施故障連帶擋下 complete）
# ----------------------------------------------------------------------------

def test_list_artifacts_failure_fails_open(logger):
    path = f"experiment-{TICKET_ID}-sentinel.md"

    def _side_effect(cmd, **kwargs):
        if cmd[:2] == ["git", "--no-optional-locks"]:
            return _git_status_result([path])
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=15)

    with _patch_subprocess(_side_effect):
        should_block, msg = check_experiment_artifact_residual(
            TICKET_ID, Path("/fake/project"), logger
        )

    assert should_block is False
    assert msg is None


# ----------------------------------------------------------------------------
# 情境 9：登記路徑書寫方式不同（前導 "./"）仍可正確比對
# ----------------------------------------------------------------------------

def test_path_normalization_matches_leading_dot_slash(logger):
    git_path = f"experiment-{TICKET_ID}-sentinel.md"
    registered_path = f"./experiment-{TICKET_ID}-sentinel.md"
    entries = [
        {
            "label": "EXP-1",
            "timestamp": "2026-08-20 10:00",
            "path": registered_path,
            "purpose": "測試",
            "expiry": "本票收尾",
            "type": "明示",
            "status": "kept（接手：0.2.1-W3-998）",
        }
    ]
    with _patch_subprocess(_dispatch_mock([git_path], entries)):
        should_block, msg = check_experiment_artifact_residual(
            TICKET_ID, Path("/fake/project"), logger
        )

    assert should_block is False
    assert msg is None
