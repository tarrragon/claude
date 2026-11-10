"""Tests for agent-commit-verification-hook.py 自激迴圈防護（1.0.0-W1-055.1）.

背景：W1-055 ANA 確認兩個 SubagentStop hook 無 stop_hook_active 檢查、hook error
摘要無去重，疊加 additionalContext 自激迴圈造成同一筆 ERROR 在 5 分鐘視窗內
重複播報（W1-074/075/076 觀測症狀）。

測試覆蓋：
| 測試 | 場景 | 驗證 |
|------|------|------|
| test_stop_hook_active_silent | stop_hook_active=true | 靜默 exit 0，不掃描、不輸出 |
| test_stop_hook_active_false_normal_flow | stop_hook_active=false | 照常輸出警告 |
| test_hook_error_fingerprint_dedup | 相同錯誤集合二次事件 | 第二次不播報 hook error 摘要 |
| test_hook_error_fingerprint_changes_rebroadcast | 錯誤集合變化 | fingerprint 變化即重新播報 |
| test_build_error_fingerprint_* | fingerprint 函式 | 排序穩定性、內容敏感性 |

策略：
- importlib 動態載入（檔名含 hyphen）
- monkeypatch 取代 git query / scan 函式以隔離真實 repo 狀態
- monkeypatch _get_error_dedup_state_file 指向 tmp_path（避免污染真實 repo）
- capsys 捕獲 stdout JSON
"""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest


HOOK_PATH = (
    Path(__file__).parent.parent / "agent-commit-verification-hook.py"
)


def _load_hook_module():
    spec = importlib.util.spec_from_file_location(
        "agent_commit_verification_hook", HOOK_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def hook_mod():
    return _load_hook_module()


def _stdin(payload: dict) -> io.StringIO:
    return io.StringIO(json.dumps(payload))


def _patch_clean(hook_mod, monkeypatch, tmp_path):
    """Patch git/scan helpers 為乾淨狀態，dedup state 導向 tmp_path。"""
    monkeypatch.setattr(hook_mod, "_lookup_agent_info", lambda *a, **kw: ("agent-X", False))
    monkeypatch.setattr(hook_mod, "get_uncommitted_files", lambda *a, **kw: [])
    monkeypatch.setattr(hook_mod, "get_unmerged_worktrees", lambda *a, **kw: [])
    monkeypatch.setattr(hook_mod, "get_unmerged_feature_branches", lambda *a, **kw: [])
    monkeypatch.setattr(hook_mod, "scan_hook_errors", lambda *a, **kw: [])
    monkeypatch.setattr(hook_mod, "get_project_root", lambda: tmp_path)
    monkeypatch.setattr(
        hook_mod, "_get_error_dedup_state_file",
        lambda root: tmp_path / "hook-error-broadcast-dedup.json",
    )


class TestStopHookActiveCircuitBreaker:
    """1.0.0-W1-055.1 修復 1：stop_hook_active=true 靜默退出（自激迴圈斷路器）。"""

    def test_stop_hook_active_silent(self, hook_mod, monkeypatch, capsys, tmp_path):
        """stop_hook_active=true 時靜默 exit 0，不執行掃描、不輸出任何 JSON。"""
        calls = {"scan": 0}

        def _record_scan(*a, **kw):
            calls["scan"] += 1
            return []

        _patch_clean(hook_mod, monkeypatch, tmp_path)
        monkeypatch.setattr(hook_mod, "get_uncommitted_files", _record_scan)
        monkeypatch.setattr(
            sys, "stdin",
            _stdin({"agent_id": "agent-xyz", "stop_hook_active": True}),
        )

        with pytest.raises(SystemExit) as exc:
            hook_mod.main()
        assert exc.value.code == 0

        captured = capsys.readouterr()
        assert captured.out == "", "stop_hook_active=true 不應輸出（避免再注入）"
        assert calls["scan"] == 0, "stop_hook_active=true 不應執行 git 掃描"

    def test_stop_hook_active_false_normal_flow(
        self, hook_mod, monkeypatch, capsys, tmp_path
    ):
        """stop_hook_active=false 時照常輸出警告（不誤傷正常事件）。"""
        _patch_clean(hook_mod, monkeypatch, tmp_path)
        monkeypatch.setattr(
            hook_mod, "get_uncommitted_files", lambda *a, **kw: ["src/foo.py"]
        )
        monkeypatch.setattr(
            sys, "stdin",
            _stdin({"agent_id": "agent-xyz", "stop_hook_active": False}),
        )

        with pytest.raises(SystemExit) as exc:
            hook_mod.main()
        assert exc.value.code == 0

        payload = json.loads(capsys.readouterr().out)
        assert "src/foo.py" in payload["systemMessage"]


class TestHookErrorFingerprintDedup:
    """1.0.0-W1-055.1 修復 2：hook error 摘要以 fingerprint 做 TTL 去重。"""

    ERRORS = [("ticket-quality-gate", 3), ("some-other-hook", 1)]

    def _run_event(self, hook_mod, monkeypatch, capsys, tmp_path, errors):
        _patch_clean(hook_mod, monkeypatch, tmp_path)
        monkeypatch.setattr(hook_mod, "scan_hook_errors", lambda *a, **kw: errors)
        monkeypatch.setattr(sys, "stdin", _stdin({"agent_id": "agent-xyz"}))

        with pytest.raises(SystemExit) as exc:
            hook_mod.main()
        assert exc.value.code == 0
        return capsys.readouterr().out

    def test_hook_error_fingerprint_dedup(
        self, hook_mod, monkeypatch, capsys, tmp_path
    ):
        """相同錯誤集合的第二次事件：摘要被去重，stdout 靜默。

        重現 W1-074/075/076 症狀：同一筆 ERROR 記錄在 5 分鐘掃描視窗內
        隨每次 SubagentStop 事件重複播報。
        """
        first = self._run_event(hook_mod, monkeypatch, capsys, tmp_path, self.ERRORS)
        msg = json.loads(first)["systemMessage"]
        assert "ticket-quality-gate" in msg
        assert "3 個錯誤記錄" in msg

        second = self._run_event(hook_mod, monkeypatch, capsys, tmp_path, self.ERRORS)
        assert second == "", "TTL 內相同 fingerprint 的摘要應被去重（無其他訊息時靜默）"

    def test_hook_error_fingerprint_changes_rebroadcast(
        self, hook_mod, monkeypatch, capsys, tmp_path
    ):
        """錯誤集合變化（新錯誤或計數成長）→ fingerprint 變化 → 立即重新播報。"""
        self._run_event(hook_mod, monkeypatch, capsys, tmp_path, self.ERRORS)

        grown = [("ticket-quality-gate", 4), ("some-other-hook", 1)]
        out = self._run_event(hook_mod, monkeypatch, capsys, tmp_path, grown)
        msg = json.loads(out)["systemMessage"]
        assert "4 個錯誤記錄" in msg, "新錯誤不應被舊播報的 dedup 遮蔽"

    def test_dedup_ttl_expiry(self, hook_mod, tmp_path):
        """TTL 過期後相同 fingerprint 重新播報。"""
        import logging

        logger = logging.getLogger("test-acv-dedup-ttl")
        state_file = tmp_path / "dedup.json"
        ttl = hook_mod.HOOK_ERROR_DEDUP_TTL_SECONDS

        t0 = 1_000_000.0
        fp = hook_mod.build_error_fingerprint(self.ERRORS)
        assert hook_mod.check_and_record_broadcast(
            state_file, fp, ttl, logger, now=t0
        ) is False
        assert hook_mod.check_and_record_broadcast(
            state_file, fp, ttl, logger, now=t0 + ttl - 1
        ) is True
        assert hook_mod.check_and_record_broadcast(
            state_file, fp, ttl, logger, now=t0 + ttl + 1
        ) is False


class TestBuildErrorFingerprint:

    def test_fingerprint_order_insensitive(self, hook_mod):
        """錯誤清單順序不影響 fingerprint（canonical 排序）。"""
        a = hook_mod.build_error_fingerprint([("hook-a", 1), ("hook-b", 2)])
        b = hook_mod.build_error_fingerprint([("hook-b", 2), ("hook-a", 1)])
        assert a == b

    def test_fingerprint_content_sensitive(self, hook_mod):
        """錯誤名稱或計數任一變化都產生不同 fingerprint。"""
        base = hook_mod.build_error_fingerprint([("hook-a", 1)])
        assert base != hook_mod.build_error_fingerprint([("hook-a", 2)])
        assert base != hook_mod.build_error_fingerprint([("hook-c", 1)])
