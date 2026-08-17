"""
回歸測試：ticket-file-access-guard-hook 兩個實測破口的修復。

破口一（絕對路徑不匹配）：normalize_path() 原本只處理反斜線與 ./ 前綴，不將
絕對路徑轉換為專案相對路徑，而 TICKET_PATH_PATTERNS 以 ^docs/ 或 ^\\.claude/
錨定。harness 系統指令要求 subagent 一律使用絕對路徑，故 is_ticket_file()
對絕對路徑一律回傳 False，讓守衛完全繞過。

破口二（handoff 恢復模式全域放行）：is_handoff_recovery_mode() 只檢查
.claude/handoff/pending/ 有無任何 json，命中即對所有 ticket 全域放行 Read，
但未恢復的 handoff 是常態非例外，導致守衛長期對所有 ticket 停用。修復後改為
只放行該 handoff 記錄實際指向的 ticket（ticket_id 或 target_ticket_id）。

涵蓋四類情境：絕對路徑攔截、相對路徑攔截、handoff 模式下的預期行為（含限定
範圍生效與失效兩面）、既有非 ticket 檔案放行情境不被破壞。
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


def _load_hook_module():
    """動態 import hook（檔名含 dash，無法用一般 import）。"""
    hook_path = (
        Path(__file__).resolve().parents[1]
        / "hooks"
        / "ticket-file-access-guard-hook.py"
    )
    spec = importlib.util.spec_from_file_location(
        "ticket_file_access_guard_hook_path_and_handoff_scope", hook_path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


TICKET_RELPATH = "docs/work-logs/v0/v0.2/v0.2.1/tickets/{id}.md"


def _make_project(tmp_path: Path, *, handoff_records=None):
    """建立最小專案結構：ticket md 檔 + 選填 handoff pending 記錄。"""
    for ticket_id in ("0.2.1-W3-549", "0.2.1-W3-500", "0.2.1-W3-520"):
        rel = TICKET_RELPATH.format(id=ticket_id)
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("dummy ticket content\n", encoding="utf-8")

    if handoff_records:
        pending_dir = tmp_path / ".claude" / "handoff" / "pending"
        pending_dir.mkdir(parents=True, exist_ok=True)
        for filename, record in handoff_records.items():
            (pending_dir / filename).write_text(
                json.dumps(record, ensure_ascii=False), encoding="utf-8"
            )

    return tmp_path


@pytest.fixture
def module_and_root(tmp_path, monkeypatch):
    module = _load_hook_module()
    project_root = _make_project(tmp_path)
    monkeypatch.setattr(module, "get_project_root", lambda: project_root)
    logger = module.setup_hook_logging("test")
    return module, project_root, logger


class TestAbsolutePathInterception:
    """破口一：絕對路徑形式的 ticket md 讀取必須被正確攔截。"""

    def test_absolute_path_without_handoff_is_blocked(self, module_and_root):
        module, project_root, logger = module_and_root
        abs_path = str(project_root / TICKET_RELPATH.format(id="0.2.1-W3-549"))

        is_allowed, reason = module.check_read_permission(abs_path, logger)

        assert is_allowed is False
        assert "禁止直接讀取 ticket 檔案" in reason

    def test_absolute_path_recognized_as_ticket_file(self, module_and_root):
        """normalize_path 必須將絕對路徑轉為專案相對路徑後才比對 pattern。"""
        module, project_root, _logger = module_and_root
        abs_path = str(project_root / TICKET_RELPATH.format(id="0.2.1-W3-549"))

        assert module.is_ticket_file(abs_path) is True

    def test_normalize_path_preserves_relative_path_behavior(self, module_and_root):
        """既有相對路徑（含 ./ 前綴）行為不可破。"""
        module, _project_root, _logger = module_and_root
        rel = TICKET_RELPATH.format(id="0.2.1-W3-549")

        assert module.normalize_path(rel) == rel
        assert module.normalize_path(f"./{rel}") == rel


class TestRelativePathInterception:
    """既有相對路徑攔截行為維持不變（回歸基準線）。"""

    def test_relative_path_without_handoff_is_blocked(self, module_and_root):
        module, _project_root, logger = module_and_root
        rel_path = TICKET_RELPATH.format(id="0.2.1-W3-549")

        is_allowed, reason = module.check_read_permission(rel_path, logger)

        assert is_allowed is False
        assert "禁止直接讀取 ticket 檔案" in reason


class TestHandoffRecoveryModeScoped:
    """破口二：handoff 恢復模式只放行該 handoff 實際指向的 ticket。"""

    def test_unrelated_ticket_still_blocked_despite_pending_handoff(self, tmp_path, monkeypatch):
        """核心回歸案例：0.2.1-W3-500 的 handoff 存在時，讀取無關的
        0.2.1-W3-549 仍必須被攔截（修復前為全域放行）。"""
        module = _load_hook_module()
        project_root = _make_project(
            tmp_path,
            handoff_records={
                "0.2.1-W3-500.json": {
                    "ticket_id": "0.2.1-W3-500",
                    "target_ticket_id": "0.2.1-W3-520",
                }
            },
        )
        monkeypatch.setattr(module, "get_project_root", lambda: project_root)
        logger = module.setup_hook_logging("test")
        rel_path = TICKET_RELPATH.format(id="0.2.1-W3-549")

        is_allowed, reason = module.check_read_permission(rel_path, logger)

        assert is_allowed is False
        assert "禁止直接讀取 ticket 檔案" in reason

    def test_source_ticket_id_allowed_via_relative_path(self, tmp_path, monkeypatch):
        module = _load_hook_module()
        project_root = _make_project(
            tmp_path,
            handoff_records={
                "0.2.1-W3-500.json": {
                    "ticket_id": "0.2.1-W3-500",
                    "target_ticket_id": "0.2.1-W3-520",
                }
            },
        )
        monkeypatch.setattr(module, "get_project_root", lambda: project_root)
        logger = module.setup_hook_logging("test")
        rel_path = TICKET_RELPATH.format(id="0.2.1-W3-500")

        is_allowed, reason = module.check_read_permission(rel_path, logger)

        assert is_allowed is True
        assert "Handoff 恢復模式允許" in reason

    def test_target_ticket_id_allowed_via_absolute_path(self, tmp_path, monkeypatch):
        """target_ticket_id 也屬合法恢復範圍，且與絕對路徑修復疊加驗證。"""
        module = _load_hook_module()
        project_root = _make_project(
            tmp_path,
            handoff_records={
                "0.2.1-W3-500.json": {
                    "ticket_id": "0.2.1-W3-500",
                    "target_ticket_id": "0.2.1-W3-520",
                }
            },
        )
        monkeypatch.setattr(module, "get_project_root", lambda: project_root)
        logger = module.setup_hook_logging("test")
        abs_path = str(project_root / TICKET_RELPATH.format(id="0.2.1-W3-520"))

        is_allowed, reason = module.check_read_permission(abs_path, logger)

        assert is_allowed is True
        assert "Handoff 恢復模式允許" in reason

    def test_no_pending_handoff_directory_denies_all_ticket_reads(self, module_and_root):
        """無任何 pending handoff 時（module_and_root fixture 未建立該目錄），
        讀取 ticket 一律走一般攔截路徑。"""
        module, _project_root, logger = module_and_root
        rel_path = TICKET_RELPATH.format(id="0.2.1-W3-549")

        is_allowed, _reason = module.check_read_permission(rel_path, logger)

        assert is_allowed is False

    def test_malformed_handoff_json_does_not_crash_and_is_skipped(self, tmp_path, monkeypatch):
        """損壞的 handoff json 只應被略過記錄警告，不應讓 hook 拋例外。"""
        module = _load_hook_module()
        project_root = _make_project(tmp_path)
        pending_dir = project_root / ".claude" / "handoff" / "pending"
        pending_dir.mkdir(parents=True, exist_ok=True)
        (pending_dir / "broken.json").write_text("{not valid json", encoding="utf-8")
        monkeypatch.setattr(module, "get_project_root", lambda: project_root)
        logger = module.setup_hook_logging("test")
        rel_path = TICKET_RELPATH.format(id="0.2.1-W3-549")

        is_allowed, _reason = module.check_read_permission(rel_path, logger)

        assert is_allowed is False


class TestExistingPassthroughUnaffected:
    """既有放行情境（非 ticket 檔案）不被本次修復破壞。"""

    def test_non_ticket_relative_path_allowed(self, module_and_root):
        module, _project_root, logger = module_and_root

        is_allowed, reason = module.check_read_permission("lib/main.dart", logger)

        assert is_allowed is True
        assert "非 ticket 檔案" in reason

    def test_non_ticket_absolute_path_allowed(self, module_and_root):
        module, project_root, logger = module_and_root
        abs_path = str(project_root / "lib" / "main.dart")

        is_allowed, reason = module.check_read_permission(abs_path, logger)

        assert is_allowed is True
        assert "非 ticket 檔案" in reason

    def test_internal_call_bypasses_all_checks(self, module_and_root, monkeypatch):
        module, _project_root, logger = module_and_root
        monkeypatch.setenv("TICKET_TRACKER_INTERNAL", "1")
        rel_path = TICKET_RELPATH.format(id="0.2.1-W3-549")

        is_allowed, reason = module.check_read_permission(rel_path, logger)

        assert is_allowed is True
        assert "內部呼叫允許" in reason
