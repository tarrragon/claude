#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hook-liveness-summary-hook.py 測試

驗證彙整入口正確區分「已載入 / 本 session 從未觸發 / 未涵蓋（無探針）」
三類清單，且不誤把當前（剛啟動、尚無實質資料的）session 自己的檔案
當作比對基準。
"""

import importlib.util
import json
import logging
import subprocess
from pathlib import Path

import pytest

_HOOK_DIR = Path(__file__).resolve().parent.parent
_HOOK_PATH = _HOOK_DIR / "hook-liveness-summary-hook.py"

_spec = importlib.util.spec_from_file_location("hook_liveness_summary", _HOOK_PATH)
summary_hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(summary_hook)

_test_logger = logging.getLogger("test-hook-liveness-summary")


def _write_settings(root: Path, hook_files):
    settings_dir = root / ".claude"
    settings_dir.mkdir(parents=True, exist_ok=True)
    hooks_entries = [
        {"command": "$CLAUDE_PROJECT_DIR/.claude/hooks/{}.py".format(name)}
        for name in hook_files
    ]
    settings = {"hooks": {"SessionStart": [{"hooks": hooks_entries}]}}
    (settings_dir / "settings.json").write_text(
        json.dumps(settings), encoding="utf-8"
    )


def _write_hook_file(root: Path, name: str, covered: bool):
    hooks_dir = root / ".claude" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    body = "run_hook_safely(main, '{}')\n".format(name) if covered else "pass\n"
    (hooks_dir / "{}.py".format(name)).write_text(body, encoding="utf-8")


def _write_liveness_file(root: Path, session_id: str, hook_names):
    liveness_dir = root / ".claude" / "hook-logs" / "_liveness"
    liveness_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps({"hook": name, "session_id": session_id, "pid": 1, "ts": "t"})
        for name in hook_names
    ]
    (liveness_dir / "{}.jsonl".format(session_id)).write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


class TestRegisteredHookNames:
    def test_extracts_hooks_dir_py_files_only(self):
        settings = {
            "hooks": {
                "SessionStart": [
                    {
                        "hooks": [
                            {"command": "$CLAUDE_PROJECT_DIR/.claude/hooks/foo.py"},
                            {
                                "command": "$CLAUDE_PROJECT_DIR/.claude/skills/x/hooks/bar.py"
                            },
                            {"command": "uv run $CLAUDE_PROJECT_DIR/.claude/hooks/baz.py"},
                        ]
                    }
                ]
            }
        }
        names = summary_hook._registered_hook_names(settings)
        assert "foo" in names
        assert "baz" in names
        assert "bar" not in names


class TestCoveredByRunHookSafely:
    def test_distinguishes_covered_and_uncovered(self, tmp_path):
        _write_hook_file(tmp_path, "covered-hook", covered=True)
        _write_hook_file(tmp_path, "uncovered-hook", covered=False)

        covered = summary_hook._covered_by_run_hook_safely(
            tmp_path, {"covered-hook", "uncovered-hook", "missing-hook"}
        )

        assert covered == {"covered-hook"}


class TestMostRecentCompletedLivenessFile:
    def test_excludes_current_session_file(self, tmp_path):
        _write_liveness_file(tmp_path, "prev-session", ["hook-a"])
        _write_liveness_file(tmp_path, "current-session", ["hook-liveness-summary"])

        result = summary_hook._most_recent_completed_liveness_file(
            tmp_path, exclude_session_id="current-session"
        )

        assert result.stem == "prev-session"

    def test_returns_none_when_no_liveness_dir(self, tmp_path):
        result = summary_hook._most_recent_completed_liveness_file(
            tmp_path, exclude_session_id="anything"
        )
        assert result is None


class TestInvokedHookNames:
    def test_parses_jsonl_lines(self, tmp_path):
        _write_liveness_file(tmp_path, "s1", ["hook-a", "hook-b"])
        liveness_file = tmp_path / ".claude" / "hook-logs" / "_liveness" / "s1.jsonl"

        invoked = summary_hook._invoked_hook_names(liveness_file)

        assert invoked == {"hook-a", "hook-b"}

    def test_skips_malformed_lines(self, tmp_path):
        liveness_dir = tmp_path / ".claude" / "hook-logs" / "_liveness"
        liveness_dir.mkdir(parents=True)
        f = liveness_dir / "s2.jsonl"
        f.write_text('not-json\n{"hook": "ok-hook"}\n', encoding="utf-8")

        invoked = summary_hook._invoked_hook_names(f)

        assert invoked == {"ok-hook"}


class TestMainEndToEnd:
    def test_main_reports_three_categories(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            summary_hook, "get_project_root", lambda: tmp_path
        )
        monkeypatch.setenv(summary_hook.ENV_SESSION_ID, "current-session")
        monkeypatch.setattr(
            "sys.stdin", __import__("io").StringIO("")
        )

        _write_settings(tmp_path, ["loaded-hook", "silent-hook", "stub-hook"])
        _write_hook_file(tmp_path, "loaded-hook", covered=True)
        _write_hook_file(tmp_path, "silent-hook", covered=True)
        _write_hook_file(tmp_path, "stub-hook", covered=False)
        _write_liveness_file(tmp_path, "prev-session", ["loaded-hook"])

        exit_code = summary_hook.main()

        assert exit_code == 0

    def test_main_handles_missing_settings_gracefully(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            summary_hook, "get_project_root", lambda: tmp_path
        )
        monkeypatch.setattr(
            "sys.stdin", __import__("io").StringIO("")
        )

        exit_code = summary_hook.main()

        assert exit_code == 0


# ============================================================================
# SessionStart 主動崩潰偵測（方案 A）測試
# ============================================================================

_CLAUDE_DIR = _HOOK_DIR.parent


def _write_uv_settings(root: Path, uv_hook_files, plain_hook_files=()):
    """比照 _write_settings，但區分 uv run 登記與 python3 登記兩種型態，
    供 `_uv_registered_hook_names` 篩選邏輯測試使用。"""
    settings_dir = root / ".claude"
    settings_dir.mkdir(parents=True, exist_ok=True)
    hooks_entries = [
        {"command": "uv run --quiet $CLAUDE_PROJECT_DIR/.claude/hooks/{}.py".format(name)}
        for name in uv_hook_files
    ] + [
        {"command": "python3 $CLAUDE_PROJECT_DIR/.claude/hooks/{}.py".format(name)}
        for name in plain_hook_files
    ]
    settings = {"hooks": {"SessionStart": [{"hooks": hooks_entries}]}}
    (settings_dir / "settings.json").write_text(json.dumps(settings), encoding="utf-8")


def _write_pep723_hook_file(root: Path, name: str, deps, extra_import: str = ""):
    """寫入一個真實可用 uv run 執行的最小 hook 檔案，sys.path 指向真實
    `.claude/`（重用既有 `lib` 套件，不在 tmp_path 下複製一份）。

    Args:
        deps: PEP 723 dependencies 列表（空列表代表無依賴宣告風險）
        extra_import: 額外插入 module-level 的 import 陳述式，用於模擬
            未宣告依賴導致的 import 階段崩潰（傳入不存在的模組名稱）
    """
    hooks_dir = root / ".claude" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    deps_literal = json.dumps(deps)
    content = (
        "#!/usr/bin/env python3\n"
        "# /// script\n"
        '# requires-python = ">=3.9"\n'
        "# dependencies = {deps}\n"
        "# ///\n"
        "import sys\n"
        "sys.path.insert(0, r'{claude_dir}')\n"
        "{extra_import}\n"
        "from lib import setup_hook_logging, run_hook_safely, read_json_from_stdin\n"
        "\n"
        "def main():\n"
        "    logger = setup_hook_logging('test-smoke-{name}')\n"
        "    read_json_from_stdin(logger)\n"
        "    return 0\n"
        "\n"
        "if __name__ == '__main__':\n"
        "    sys.exit(run_hook_safely(main, 'test-smoke-{name}'))\n"
    ).format(
        deps=deps_literal,
        claude_dir=str(_CLAUDE_DIR),
        extra_import=extra_import,
        name=name,
    )
    (hooks_dir / "{}.py".format(name)).write_text(content, encoding="utf-8")


class TestResolveUsesUv:
    """判準單元測試：settings.json 呼叫前綴優先，僅裸路徑回退 shebang
    （與 hook-dependency-isolation-check-hook.py 的 _resolve_uses_uv 對齊，
    0.2.1-W3-1084 協調結論）。"""

    def test_explicit_uv_prefix_wins_regardless_of_shebang(self):
        assert summary_hook._resolve_uses_uv(
            "#!/usr/bin/env python3\n", {"uv run --quiet"}
        ) is True

    def test_explicit_other_interpreter_wins_even_if_shebang_says_uv(self):
        assert summary_hook._resolve_uses_uv(
            "#!/usr/bin/env -S uv run --quiet --script\n", {"python3"}
        ) is False

    def test_bare_path_registration_falls_back_to_shebang_true(self):
        assert summary_hook._resolve_uses_uv(
            "#!/usr/bin/env -S uv run --quiet --script\n", {""}
        ) is True

    def test_bare_path_registration_falls_back_to_shebang_false(self):
        assert summary_hook._resolve_uses_uv("#!/usr/bin/env python3\n", {""}) is False

    def test_mixed_prefixes_uv_wins_if_any_present(self):
        assert summary_hook._resolve_uses_uv(
            "#!/usr/bin/env python3\n", {"python3", "uv run --quiet"}
        ) is True

    def test_no_command_prefixes_falls_back_to_shebang(self):
        assert summary_hook._resolve_uses_uv("#!/usr/bin/env -S uv run\n", set()) is True


class TestUvRegisteredHookNames:
    def test_filters_by_uv_run_command_prefix(self, tmp_path):
        _write_uv_settings(tmp_path, uv_hook_files=["uv-hook"], plain_hook_files=["plain-hook"])
        _write_pep723_hook_file(tmp_path, "uv-hook", deps=[])
        _write_pep723_hook_file(tmp_path, "plain-hook", deps=[])
        settings = json.loads((tmp_path / ".claude" / "settings.json").read_text())

        names = summary_hook._uv_registered_hook_names(tmp_path, settings)

        assert names == {"uv-hook"}

    def test_uv_registration_independent_of_file_shebang(self, tmp_path):
        """settings.json 以 uv run 登記時視為隔離環境生效，即使檔案自身
        shebang 非 uv run（0.2.1-W3-1084 揭示的落差：動機案例
        active-dispatch-tracker-hook.py 即屬此類）。settings.json 為明確
        前綴（非裸路徑）時不需回退讀 shebang，即可判定為 True。"""
        _write_uv_settings(tmp_path, uv_hook_files=["tracker-like"])
        hooks_dir = tmp_path / ".claude" / "hooks"
        hooks_dir.mkdir(parents=True, exist_ok=True)
        (hooks_dir / "tracker-like.py").write_text(
            "#!/usr/bin/env python3\n", encoding="utf-8"
        )
        settings = json.loads((tmp_path / ".claude" / "settings.json").read_text())

        names = summary_hook._uv_registered_hook_names(tmp_path, settings)

        assert "tracker-like" in names

    def test_bare_path_registration_uses_own_shebang(self, tmp_path):
        """裸路徑登記（無直譯器前綴）時，隔離與否回退讀檔案自身 shebang
        （0.2.1-W3-1084 協調結論：本專案目前無此類登記，但判準邏輯仍須
        正確處理，避免未來出現時誤判）。"""
        settings_dir = tmp_path / ".claude"
        settings_dir.mkdir(parents=True, exist_ok=True)
        settings = {
            "hooks": {
                "SessionStart": [
                    {
                        "hooks": [
                            {"command": "$CLAUDE_PROJECT_DIR/.claude/hooks/bare-uv-hook.py"},
                            {"command": "$CLAUDE_PROJECT_DIR/.claude/hooks/bare-plain-hook.py"},
                        ]
                    }
                ]
            }
        }
        (settings_dir / "settings.json").write_text(json.dumps(settings), encoding="utf-8")
        hooks_dir = settings_dir / "hooks"
        hooks_dir.mkdir(parents=True, exist_ok=True)
        (hooks_dir / "bare-uv-hook.py").write_text(
            "#!/usr/bin/env -S uv run --quiet --script\n", encoding="utf-8"
        )
        (hooks_dir / "bare-plain-hook.py").write_text(
            "#!/usr/bin/env python3\n", encoding="utf-8"
        )

        names = summary_hook._uv_registered_hook_names(tmp_path, settings)

        assert names == {"bare-uv-hook"}


class TestHasNonEmptyPep723Deps:
    def test_true_when_deps_non_empty(self):
        content = (
            "#!/usr/bin/env python3\n"
            "# /// script\n"
            '# dependencies = ["pyyaml"]\n'
            "# ///\n"
        )
        assert summary_hook._has_non_empty_pep723_deps(content) is True

    def test_false_when_no_pep723_block(self):
        content = "#!/usr/bin/env python3\nimport os\n"
        assert summary_hook._has_non_empty_pep723_deps(content) is False

    def test_false_when_deps_empty(self):
        content = (
            "#!/usr/bin/env python3\n"
            "# /// script\n"
            "# dependencies = []\n"
            "# ///\n"
        )
        assert summary_hook._has_non_empty_pep723_deps(content) is False


class TestSmokeTestCandidates:
    def test_selects_uv_registered_with_non_empty_deps_only(self, tmp_path):
        _write_uv_settings(
            tmp_path,
            uv_hook_files=["risky-hook", "safe-hook"],
            plain_hook_files=["non-uv-hook"],
        )
        _write_pep723_hook_file(tmp_path, "risky-hook", deps=["pyyaml"])
        _write_pep723_hook_file(tmp_path, "safe-hook", deps=[])
        _write_pep723_hook_file(tmp_path, "non-uv-hook", deps=["pyyaml"])

        settings = json.loads((tmp_path / ".claude" / "settings.json").read_text())
        candidates = summary_hook._smoke_test_candidates(tmp_path, settings)

        assert candidates == {"risky-hook"}

    def test_excludes_hooks_not_covered_by_run_hook_safely(self, tmp_path):
        """實機驗證撈到的真實案例：直接 sys.exit(main())、不經
        run_hook_safely 的 hook 即使正常執行成功也不會寫入 liveness
        條目，若不排除會被永遠誤判為崩潰（見 _smoke_test_candidates
        docstring）。"""
        _write_uv_settings(tmp_path, uv_hook_files=["legacy-hook"])
        hooks_dir = tmp_path / ".claude" / "hooks"
        hooks_dir.mkdir(parents=True, exist_ok=True)
        (hooks_dir / "legacy-hook.py").write_text(
            "#!/usr/bin/env python3\n"
            "# /// script\n"
            '# dependencies = ["pyyaml"]\n'
            "# ///\n"
            "import sys\n"
            "def main():\n"
            "    return 0\n"
            "if __name__ == '__main__':\n"
            "    sys.exit(main())\n",
            encoding="utf-8",
        )

        settings = json.loads((tmp_path / ".claude" / "settings.json").read_text())
        candidates = summary_hook._smoke_test_candidates(tmp_path, settings)

        assert candidates == set()


class TestSmokeTestCacheRoundtrip:
    def test_save_then_load_returns_same_data(self, tmp_path):
        cache = {"foo-hook": {"mtime": 123.0, "status": "ok", "summary": ""}}
        summary_hook._save_smoke_test_cache(tmp_path, cache, _test_logger)

        loaded = summary_hook._load_smoke_test_cache(tmp_path)

        assert loaded == cache

    def test_load_returns_empty_dict_when_missing(self, tmp_path):
        assert summary_hook._load_smoke_test_cache(tmp_path) == {}

    def test_load_returns_empty_dict_when_malformed(self, tmp_path):
        path = summary_hook._smoke_test_cache_path(tmp_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("not-json", encoding="utf-8")

        assert summary_hook._load_smoke_test_cache(tmp_path) == {}


class TestSmokeTestLock:
    def test_second_acquire_fails_while_held(self, tmp_path):
        assert summary_hook._acquire_smoke_test_lock(tmp_path) is True
        assert summary_hook._acquire_smoke_test_lock(tmp_path) is False

    def test_acquire_succeeds_after_release(self, tmp_path):
        assert summary_hook._acquire_smoke_test_lock(tmp_path) is True
        summary_hook._release_smoke_test_lock(tmp_path)
        assert summary_hook._acquire_smoke_test_lock(tmp_path) is True

    def test_stale_lock_is_cleared_and_reacquired(self, tmp_path, monkeypatch):
        lock_path = summary_hook._smoke_test_lock_path(tmp_path)
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.write_text("", encoding="utf-8")
        stale_mtime = __import__("time").time() - (
            summary_hook.SMOKE_TEST_LOCK_STALE_SECONDS + 10
        )
        __import__("os").utime(str(lock_path), (stale_mtime, stale_mtime))

        assert summary_hook._acquire_smoke_test_lock(tmp_path) is True


class TestRunSingleSmokeTest:
    """真實透過 uv run 呼叫子行程，驗證 liveness 條目有無的崩潰判準。"""

    def test_healthy_hook_not_flagged_as_crashed(self, tmp_path):
        _write_pep723_hook_file(tmp_path, "healthy-hook", deps=[])
        sentinel_file = (
            tmp_path / ".claude" / "hook-logs" / summary_hook.LIVENESS_SUBDIR
            / "{}.jsonl".format(summary_hook.SMOKE_TEST_SENTINEL_SESSION_ID)
        )

        status, summary = summary_hook._run_single_smoke_test(
            tmp_path, "healthy-hook", sentinel_file
        )

        assert status == "ok"
        assert summary == ""

    def test_pins_project_dir_env_to_root(self, tmp_path, monkeypatch):
        """實機驗證撈到的真實案例：子行程若繼承呼叫端（本 hook 自身）
        的 CLAUDE_PROJECT_DIR 環境變數，`get_project_root()` 判準優先序
        會讓子行程解析到錯誤的專案根目錄（優先於 cwd），使 liveness
        索引寫入呼叫端所指的專案而非本次測試的 tmp_path，造成健康 hook
        被誤判為崩潰（根因非系統負載，見 SMOKE_TEST 常數與本函式
        docstring 的更正說明）。此測試模擬呼叫端環境變數指向「別的專案」
        的情境，驗證子行程仍正確寫入 tmp_path 而非該別的專案路徑。"""
        other_project = tmp_path / "unrelated-other-project"
        other_project.mkdir()
        (other_project / ".claude").mkdir()
        monkeypatch.setenv(summary_hook.ENV_PROJECT_DIR, str(other_project))

        real_root = tmp_path / "real-root"
        _write_pep723_hook_file(real_root, "healthy-hook", deps=[])
        sentinel_file = (
            real_root / ".claude" / "hook-logs" / summary_hook.LIVENESS_SUBDIR
            / "{}.jsonl".format(summary_hook.SMOKE_TEST_SENTINEL_SESSION_ID)
        )

        status, summary = summary_hook._run_single_smoke_test(
            real_root, "healthy-hook", sentinel_file
        )

        assert status == "ok"
        other_sentinel = (
            other_project / ".claude" / "hook-logs" / summary_hook.LIVENESS_SUBDIR
            / "{}.jsonl".format(summary_hook.SMOKE_TEST_SENTINEL_SESSION_ID)
        )
        assert not other_sentinel.exists()

    def test_import_crash_is_flagged(self, tmp_path):
        _write_pep723_hook_file(
            tmp_path,
            "crashing-hook",
            deps=[],
            extra_import="import definitely_not_a_real_package_xyz123\n",
        )
        sentinel_file = (
            tmp_path / ".claude" / "hook-logs" / summary_hook.LIVENESS_SUBDIR
            / "{}.jsonl".format(summary_hook.SMOKE_TEST_SENTINEL_SESSION_ID)
        )

        status, summary = summary_hook._run_single_smoke_test(
            tmp_path, "crashing-hook", sentinel_file
        )

        assert status == "crashed"
        assert "definitely_not_a_real_package_xyz123" in summary or "ModuleNotFoundError" in summary

    def test_timeout_not_flagged_as_crashed(self, tmp_path, monkeypatch):
        """逾時（可能為系統負載）不應被判定為崩潰，見 _run_single_smoke_test
        docstring 的三態設計（實機驗證撈到的真實案例：健康 hook 在系統
        負載較高時偶爾逾時，若判為 crashed 會產生假陽性）。"""
        _write_pep723_hook_file(tmp_path, "slow-hook", deps=[])
        sentinel_file = (
            tmp_path / ".claude" / "hook-logs" / summary_hook.LIVENESS_SUBDIR
            / "{}.jsonl".format(summary_hook.SMOKE_TEST_SENTINEL_SESSION_ID)
        )

        def _raise_timeout(*args, **kwargs):
            raise subprocess.TimeoutExpired(cmd="uv run", timeout=0.01)

        monkeypatch.setattr(summary_hook.subprocess, "run", _raise_timeout)

        status, summary = summary_hook._run_single_smoke_test(
            tmp_path, "slow-hook", sentinel_file
        )

        assert status == "timeout"
        assert "逾時" in summary


class TestSmokeTestRegisteredHooksOrchestration:
    def test_unchanged_mtime_skips_retest(self, tmp_path, monkeypatch):
        """快取命中（mtime 未變）時不應重新呼叫 _run_single_smoke_test。"""
        _write_uv_settings(tmp_path, uv_hook_files=["cached-hook"])
        _write_pep723_hook_file(tmp_path, "cached-hook", deps=["pyyaml"])
        settings = json.loads((tmp_path / ".claude" / "settings.json").read_text())

        call_count = {"n": 0}

        def _fake_run(root, name, sentinel):
            call_count["n"] += 1
            return "ok", ""

        monkeypatch.setattr(summary_hook, "_run_single_smoke_test", _fake_run)

        first = summary_hook._smoke_test_registered_hooks(tmp_path, settings, _test_logger)
        assert call_count["n"] == 1
        assert first == []

        second = summary_hook._smoke_test_registered_hooks(tmp_path, settings, _test_logger)
        assert call_count["n"] == 1  # 快取命中，未重新呼叫
        assert second == []

    def test_reports_cached_crash_even_without_retest(self, tmp_path, monkeypatch):
        _write_uv_settings(tmp_path, uv_hook_files=["broken-hook"])
        _write_pep723_hook_file(tmp_path, "broken-hook", deps=["pyyaml"])
        settings = json.loads((tmp_path / ".claude" / "settings.json").read_text())

        monkeypatch.setattr(
            summary_hook, "_run_single_smoke_test",
            lambda root, name, sentinel: ("crashed", "ModuleNotFoundError: no module"),
        )

        first = summary_hook._smoke_test_registered_hooks(tmp_path, settings, _test_logger)
        assert first == [("broken-hook", "ModuleNotFoundError: no module")]

        # mtime 未變、快取命中，仍應持續回報崩潰狀態（不因未重測而消失）
        second = summary_hook._smoke_test_registered_hooks(tmp_path, settings, _test_logger)
        assert second == [("broken-hook", "ModuleNotFoundError: no module")]

    def test_time_budget_defers_remaining_candidates(self, tmp_path, monkeypatch):
        _write_uv_settings(tmp_path, uv_hook_files=["hook-a", "hook-b"])
        _write_pep723_hook_file(tmp_path, "hook-a", deps=["pyyaml"])
        _write_pep723_hook_file(tmp_path, "hook-b", deps=["pyyaml"])
        settings = json.loads((tmp_path / ".claude" / "settings.json").read_text())

        monkeypatch.setattr(summary_hook, "SMOKE_TEST_TIME_BUDGET_SECONDS", 0.0)
        call_count = {"n": 0}

        def _fake_run(root, name, sentinel):
            call_count["n"] += 1
            return "ok", ""

        monkeypatch.setattr(summary_hook, "_run_single_smoke_test", _fake_run)

        result = summary_hook._smoke_test_registered_hooks(tmp_path, settings, _test_logger)

        assert result == []
        assert call_count["n"] == 0  # 預算為 0，第一個候選前就已超出預算

    def test_timeout_status_not_cached_and_not_reported_as_crash(self, tmp_path, monkeypatch):
        """timeout 狀態不確定，不應快取也不應出現在崩潰回報中；候選應
        留在佇列供下次 SessionStart 重試（見三態設計 Why）。"""
        _write_uv_settings(tmp_path, uv_hook_files=["flaky-hook"])
        _write_pep723_hook_file(tmp_path, "flaky-hook", deps=["pyyaml"])
        settings = json.loads((tmp_path / ".claude" / "settings.json").read_text())

        monkeypatch.setattr(
            summary_hook, "_run_single_smoke_test",
            lambda root, name, sentinel: ("timeout", "smoke test 逾時"),
        )

        result = summary_hook._smoke_test_registered_hooks(tmp_path, settings, _test_logger)

        assert result == []
        cache = summary_hook._load_smoke_test_cache(tmp_path)
        assert "flaky-hook" not in cache


class TestReportSmokeTestCrashes:
    def test_emits_additional_context_when_crashed(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(
            summary_hook, "_smoke_test_registered_hooks",
            lambda root, settings, logger: [("broken-hook", "ModuleNotFoundError")],
        )

        summary_hook._report_smoke_test_crashes(tmp_path, {}, _test_logger, None)

        captured = capsys.readouterr()
        assert "broken-hook" in captured.out
        assert "additionalContext" in captured.out or "hookSpecificOutput" in captured.out

    def test_silent_when_no_crash(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(
            summary_hook, "_smoke_test_registered_hooks",
            lambda root, settings, logger: [],
        )

        summary_hook._report_smoke_test_crashes(tmp_path, {}, _test_logger, None)

        captured = capsys.readouterr()
        assert captured.out == ""

    def test_skips_when_lock_held(self, tmp_path, monkeypatch):
        summary_hook._acquire_smoke_test_lock(tmp_path)
        call_count = {"n": 0}
        monkeypatch.setattr(
            summary_hook, "_smoke_test_registered_hooks",
            lambda root, settings, logger: call_count.update(n=call_count["n"] + 1) or [],
        )

        summary_hook._report_smoke_test_crashes(tmp_path, {}, _test_logger, None)

        assert call_count["n"] == 0
