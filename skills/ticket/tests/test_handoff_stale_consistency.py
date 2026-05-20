"""
三方 handoff stale 判斷一致性整合測試（W17-095.4）

固化「handoff_utils / stop-hook / reminder-hook 三方對同一 handoff record
的 stale 判斷必一致」的約束，避免 W17-095.1/.2/.3 落地後再分歧。

3 情境 × 3 入口 = 9 case 矩陣：

| Case | 情境                         | 入口                               | 預期                       |
|------|------------------------------|------------------------------------|----------------------------|
| 1    | S1 任務鏈目標已啟動          | utils.is_handoff_stale             | (True, "目標 ... 已 ...")  |
| 2    | S1                           | stop-hook.should_preserve          | False                      |
| 3    | S1                           | reminder-hook.scan                 | tasks==0, stale_count==1   |
| 4    | S2 非任務鏈來源 completed    | utils.is_handoff_stale             | (True, "...completed")     |
| 5    | S2                           | stop-hook.should_preserve          | False                      |
| 6    | S2                           | reminder-hook.scan                 | tasks==0, stale_count==1   |
| 7    | S3 未完成                    | utils.is_handoff_stale             | (False, "")                |
| 8    | S3                           | stop-hook.should_preserve          | True                       |
| 9    | S3                           | reminder-hook.scan                 | tasks==1, stale_count==0   |

語義一致性：
    utils.is_handoff_stale == True
    ⇔ stop-hook.should_preserve_pending_json == False
    ⇔ reminder-hook 將該筆計入 stale_count（不進 tasks）

設計：
- 共用 fixture 提供 3 個 record（S1/S2/S3）
- 共用 stub 替換 handoff_utils 的 ticket status 探測函式（避開實際 ticket fs）
- stop-hook / reminder-hook 透過 importlib 載入；兩 hook 內 import 的
  `is_handoff_stale` 仍指向 handoff_utils 模組的同一函式物件，stub 一次三方共用
"""

import importlib
import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[4]
HOOKS_DIR = PROJECT_ROOT / ".claude" / "hooks"
# W10-092: handoff-auto-resume-stop-hook 與 handoff-reminder-hook 已遷至 .claude/skills/ticket/hooks/
TICKET_SKILL_HOOKS_DIR = PROJECT_ROOT / ".claude" / "skills" / "ticket" / "hooks"
STOP_HOOK_PATH = TICKET_SKILL_HOOKS_DIR / "handoff-auto-resume-stop-hook.py"
REMINDER_HOOK_PATH = TICKET_SKILL_HOOKS_DIR / "handoff-reminder-hook.py"


# ---------------------------------------------------------------------------
# Hook 模組載入（hyphen 檔名需 importlib + sys.path 補丁）
# ---------------------------------------------------------------------------

def _load_hook_module(name: str, path: Path):
    """載入 .py hook 為模組。

    hook 內部會 `sys.path.insert` 加入 hook_utils 與 ticket_system lib 路徑，
    並 `from handoff_utils import is_handoff_stale`。
    """
    # 確保 hook_utils 可被找到
    hooks_dir_str = str(HOOKS_DIR)
    if hooks_dir_str not in sys.path:
        sys.path.insert(0, hooks_dir_str)

    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def stop_hook():
    return _load_hook_module("handoff_auto_resume_stop_hook", STOP_HOOK_PATH)


@pytest.fixture(scope="module")
def reminder_hook():
    return _load_hook_module("handoff_reminder_hook", REMINDER_HOOK_PATH)


@pytest.fixture
def utils_module():
    """重新 import handoff_utils 確保拿到最新 module 物件。"""
    from ticket_system.lib import handoff_utils
    importlib.reload(handoff_utils)
    return handoff_utils


# ---------------------------------------------------------------------------
# 共用 record fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def s1_task_chain_target_started_record():
    """S1: 任務鏈方向，目標 ticket 已啟動（in_progress）。"""
    return {
        "ticket_id": "0.18.0-W17-001",
        "from_ticket": "0.18.0-W17-001",
        "to_ticket": "0.18.0-W17-002",
        "title": "S1 任務鏈來源",
        "direction": "to-sibling:0.18.0-W17-002",
        "from_status": "completed",
        "timestamp": "2026-05-02T10:00:00",
        "what": "S1 fixture",
        "chain": {},
        "resumed_at": None,
    }


@pytest.fixture
def s2_non_chain_source_completed_record():
    """S2: 非任務鏈方向，來源 ticket 已 completed。"""
    return {
        "ticket_id": "0.18.0-W17-010",
        "from_ticket": "0.18.0-W17-010",
        "title": "S2 context-refresh",
        "direction": "context-refresh",
        "from_status": "in_progress",  # from_status 故意非 completed，
                                       # 讓 stale 來自「來源 ticket 已 completed」分支
        "timestamp": "2026-05-02T10:01:00",
        "what": "S2 fixture",
        "chain": {},
        "resumed_at": None,
    }


@pytest.fixture
def s3_not_completed_record():
    """S3: 非任務鏈方向，來源 ticket 仍 pending／in_progress。"""
    return {
        "ticket_id": "0.18.0-W17-020",
        "from_ticket": "0.18.0-W17-020",
        "title": "S3 仍進行中",
        "direction": "context-refresh",
        "from_status": "in_progress",
        "timestamp": "2026-05-02T10:02:00",
        "what": "S3 fixture",
        "chain": {},
        "resumed_at": None,
    }


# ---------------------------------------------------------------------------
# Stub helpers：替換 handoff_utils 內部的 ticket 狀態探測，避開真實 fs
# ---------------------------------------------------------------------------

class _ScenarioStub:
    """共用 stub，三方入口共享同一份 ticket status 認知。"""

    def __init__(self, scenario: str):
        self.scenario = scenario  # "S1" | "S2" | "S3"

    # ---- handoff_utils 探測函式 stubs ----
    # W17-181.1: 改為新簽章（接受 optional project_root）
    def is_ticket_in_progress_or_completed(self, ticket_id: str, project_root=None) -> bool:
        # 只有 S1 的 target 視為已啟動
        return self.scenario == "S1" and ticket_id == "0.18.0-W17-002"

    def is_ticket_completed(self, ticket_id: str, project_root=None) -> bool:
        # 只有 S2 的 source 視為已 completed
        return self.scenario == "S2" and ticket_id == "0.18.0-W17-010"

    def load_ticket_status(self, ticket_id: str, project_root=None):
        """W17-181.1：替換原 extract_version + load_and_validate_ticket 的雙函式 stub。
        僅 S1 reason 組裝會走到這裡（取得 target status 填入訊息）。
        """
        if self.scenario == "S1" and ticket_id == "0.18.0-W17-002":
            return "in_progress"
        return "pending"


def _patch_utils(utils_module, stub: _ScenarioStub):
    """patch handoff_utils 的 3 個底層函式（W17-181.1 簽章變更）。回傳 patcher list 供 caller stop。"""
    patches = [
        patch.object(utils_module, "is_ticket_in_progress_or_completed",
                     side_effect=stub.is_ticket_in_progress_or_completed),
        patch.object(utils_module, "is_ticket_completed",
                     side_effect=stub.is_ticket_completed),
        patch.object(utils_module, "_load_ticket_status",
                     side_effect=stub.load_ticket_status),
    ]
    for p in patches:
        p.start()
    return patches


def _stop_patches(patches):
    for p in patches:
        p.stop()


# ---------------------------------------------------------------------------
# 入口呼叫 helpers
# ---------------------------------------------------------------------------

def _call_utils(utils_module, record):
    return utils_module.is_handoff_stale(record)


def _call_stop_hook(stop_hook, utils_module, record):
    """確保 stop_hook 內 import 的 is_handoff_stale 指向最新 utils 模組。"""
    # stop_hook 在 import 時已綁定 is_handoff_stale 函式物件，
    # 由於 utils_module 經過 reload，需重新指派。
    stop_hook.is_handoff_stale = utils_module.is_handoff_stale
    return stop_hook.should_preserve_pending_json(record, MagicMock())


def _call_reminder_hook(reminder_hook, utils_module, tmp_path: Path, record):
    """寫入 record 到 tmp pending 目錄後呼叫 scan。

    project_root 結構：tmp_path/.claude/handoff/pending/<ticket_id>.json
    """
    reminder_hook.is_handoff_stale = utils_module.is_handoff_stale

    pending_dir = tmp_path / ".claude" / "handoff" / "pending"
    pending_dir.mkdir(parents=True, exist_ok=True)
    name = record.get("ticket_id", "unknown")
    (pending_dir / f"{name}.json").write_text(
        json.dumps(record, ensure_ascii=False), encoding="utf-8"
    )
    tasks, stale_count = reminder_hook.scan_handoff_pending_directory(
        tmp_path, MagicMock()
    )
    return tasks, stale_count


# ---------------------------------------------------------------------------
# 9 case：3 情境 × 3 入口
# ---------------------------------------------------------------------------

class TestS1TaskChainTargetStarted:
    """S1: direction 為任務鏈、target ticket 已 in_progress → stale。"""

    def test_case1_utils_marks_stale(self, utils_module,
                                     s1_task_chain_target_started_record):
        patches = _patch_utils(utils_module, _ScenarioStub("S1"))
        try:
            is_stale, reason = _call_utils(
                utils_module, s1_task_chain_target_started_record
            )
        finally:
            _stop_patches(patches)
        assert is_stale is True
        assert "0.18.0-W17-002" in reason
        assert "in_progress" in reason or "completed" in reason

    def test_case2_stop_hook_does_not_preserve(self, utils_module, stop_hook,
                                               s1_task_chain_target_started_record):
        patches = _patch_utils(utils_module, _ScenarioStub("S1"))
        try:
            preserve = _call_stop_hook(
                stop_hook, utils_module, s1_task_chain_target_started_record
            )
        finally:
            _stop_patches(patches)
        assert preserve is False

    def test_case3_reminder_hook_filters_as_stale(
        self, utils_module, reminder_hook, tmp_path,
        s1_task_chain_target_started_record
    ):
        patches = _patch_utils(utils_module, _ScenarioStub("S1"))
        try:
            tasks, stale_count = _call_reminder_hook(
                reminder_hook, utils_module, tmp_path,
                s1_task_chain_target_started_record,
            )
        finally:
            _stop_patches(patches)
        assert len(tasks) == 0
        assert stale_count == 1


class TestS2NonChainSourceCompleted:
    """S2: 非任務鏈方向，來源 ticket 已 completed → stale。"""

    def test_case4_utils_marks_stale(self, utils_module,
                                     s2_non_chain_source_completed_record):
        patches = _patch_utils(utils_module, _ScenarioStub("S2"))
        try:
            is_stale, reason = _call_utils(
                utils_module, s2_non_chain_source_completed_record
            )
        finally:
            _stop_patches(patches)
        assert is_stale is True
        assert "completed" in reason
        assert "0.18.0-W17-010" in reason

    def test_case5_stop_hook_does_not_preserve(self, utils_module, stop_hook,
                                               s2_non_chain_source_completed_record):
        patches = _patch_utils(utils_module, _ScenarioStub("S2"))
        try:
            preserve = _call_stop_hook(
                stop_hook, utils_module, s2_non_chain_source_completed_record
            )
        finally:
            _stop_patches(patches)
        assert preserve is False

    def test_case6_reminder_hook_filters_as_stale(
        self, utils_module, reminder_hook, tmp_path,
        s2_non_chain_source_completed_record
    ):
        patches = _patch_utils(utils_module, _ScenarioStub("S2"))
        try:
            tasks, stale_count = _call_reminder_hook(
                reminder_hook, utils_module, tmp_path,
                s2_non_chain_source_completed_record,
            )
        finally:
            _stop_patches(patches)
        assert len(tasks) == 0
        assert stale_count == 1


class TestS3NotCompleted:
    """S3: 非任務鏈方向，來源仍 pending → 非 stale。"""

    def test_case7_utils_marks_non_stale(self, utils_module,
                                         s3_not_completed_record):
        patches = _patch_utils(utils_module, _ScenarioStub("S3"))
        try:
            is_stale, reason = _call_utils(
                utils_module, s3_not_completed_record
            )
        finally:
            _stop_patches(patches)
        assert is_stale is False
        assert reason == ""

    def test_case8_stop_hook_preserves(self, utils_module, stop_hook,
                                       s3_not_completed_record):
        patches = _patch_utils(utils_module, _ScenarioStub("S3"))
        try:
            preserve = _call_stop_hook(
                stop_hook, utils_module, s3_not_completed_record
            )
        finally:
            _stop_patches(patches)
        assert preserve is True

    def test_case9_reminder_hook_keeps_in_tasks(
        self, utils_module, reminder_hook, tmp_path,
        s3_not_completed_record
    ):
        patches = _patch_utils(utils_module, _ScenarioStub("S3"))
        try:
            tasks, stale_count = _call_reminder_hook(
                reminder_hook, utils_module, tmp_path,
                s3_not_completed_record,
            )
        finally:
            _stop_patches(patches)
        assert len(tasks) == 1
        assert stale_count == 0
        assert tasks[0]["ticket_id"] == "0.18.0-W17-020"


# ---------------------------------------------------------------------------
# 跨入口一致性彙總（提示性檢查；非 9 case 之外的新斷言）
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "scenario,record_fixture,expect_stale",
    [
        ("S1", "s1_task_chain_target_started_record", True),
        ("S2", "s2_non_chain_source_completed_record", True),
        ("S3", "s3_not_completed_record", False),
    ],
)
def test_three_consumers_agree(
    request, utils_module, stop_hook, reminder_hook, tmp_path,
    scenario, record_fixture, expect_stale,
):
    """同一 record 餵三方入口，三方對 stale 結論必一致。"""
    record = request.getfixturevalue(record_fixture)
    patches = _patch_utils(utils_module, _ScenarioStub(scenario))
    try:
        is_stale, _ = _call_utils(utils_module, record)
        preserve = _call_stop_hook(stop_hook, utils_module, record)
        tasks, stale_count = _call_reminder_hook(
            reminder_hook, utils_module, tmp_path, record
        )
    finally:
        _stop_patches(patches)

    assert is_stale is expect_stale
    # 反向語義：preserve == not is_stale
    assert preserve is (not expect_stale)
    if expect_stale:
        assert stale_count == 1 and len(tasks) == 0
    else:
        assert stale_count == 0 and len(tasks) == 1
