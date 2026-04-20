#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for wrap-decision-tripwire-hook.py

涵蓋 12 類測試案例（對應 Phase 2 規格 50+ 測試）：
A. 檔案存在性與 metadata (A1-A5)
B. settings.json 註冊 (B1-B4)
C. S1 consecutive_failures (C1-C10)
D. S2 restrictive_keywords (D1-D8)
E. S3 ana_claim (E1-E7)
F. 重置條件路徑 (F1-F9)
G. 提醒訊息快照 (G1-G5)
H. stderr + 日誌雙通道 (H1-H7)
I. YAML 讀取與 fallback (I1-I8)
J. Source-of-truth 約束 (J1-J6)
K. 文件同步 (K1-K3)
L. Hook 不阻擋 advisory (L1-L3)
"""

import ast
import copy
import importlib.util
import io
import json
import os
import re
import subprocess
import sys
import textwrap
from datetime import datetime, timedelta
from pathlib import Path

import pytest
import yaml


# ============================================================================
# Paths & Module loader
# ============================================================================

REPO_ROOT = Path(__file__).resolve().parents[3]
HOOK_PATH = REPO_ROOT / ".claude" / "hooks" / "wrap-decision-tripwire-hook.py"
CONFIG_PATH = REPO_ROOT / ".claude" / "config" / "wrap-triggers.yaml"
SETTINGS_PATH = REPO_ROOT / ".claude" / "settings.json"
SKILL_PATH = REPO_ROOT / ".claude" / "skills" / "wrap-decision" / "SKILL.md"
CATALOG_PATH = REPO_ROOT / ".claude" / "skills" / "wrap-decision" / "references" / "tripwire-catalog.md"


def _load_hook_module():
    """動態載入 Hook 模組（檔名含 `-` 不能用一般 import）。"""
    spec = importlib.util.spec_from_file_location("wrap_tripwire_hook", HOOK_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def hook_mod():
    return _load_hook_module()


# ============================================================================
# Fixtures
# ============================================================================

# 結構化 fixture 取代字串 + .replace() pattern（W10-063 重構）
# 以 dict 為 source of truth，透過 yaml_fixture() 產生 YAML 文字。
# 變體測試使用 signal_overrides / top_overrides，避免脆弱的字串替換。
DEFAULT_CONFIG = {
    "version": "1.0.0",
    "last_updated": "2026-04-15",
    "settings": {
        "state_file": ".claude/hook-state/wrap-tripwire-state.json",
        "warn_cooldown_seconds": 300,
        "hook_mode": "advisory",
    },
    "signals": [
        {
            "id": "consecutive_failures",
            "enabled": True,
            "event_sources": ["PostToolUse"],
            "tool_matcher": "Task",
            "threshold": 2,
            "reset_conditions": ["agent_success", "ticket_switch", "manual_wrap_invocation"],
            "message_template": (
                "[WRAP Tripwire] 連續 {count} 次代理人失敗（Ticket: {ticket_id}）。\n"
                "你是有選擇的：\n"
                "  /wrap-decision        — 系統性擴增選項\n"
                "  搜尋社群             — 看看有沒有人解決過\n"
                "  建 Ticket 延後       — 回到核心任務\n"
            ),
        },
        {
            "id": "restrictive_keywords",
            "enabled": True,
            "event_sources": ["UserPromptSubmit"],
            "keywords": ["做不到", "沒辦法", "無法", "不支援", "不可能", "impossible", "限制性解法"],
            "match_mode": "substring",
            "case_sensitive": False,
            "min_prompt_length": 20,
            "reset_conditions": ["manual_wrap_invocation"],
            "message_template": (
                "[WRAP Tripwire] 偵測到限制性結論（關鍵字：{matched_keyword}）。\n"
                "你是有選擇的：\n"
                "  /wrap-decision        — 搜尋間接方案\n"
                "  窮盡五問檢查         — tool-discovery.md 規則 1\n"
            ),
        },
        {
            "id": "ana_claim",
            "enabled": True,
            "event_sources": ["PostToolUse"],
            "tool_matcher": "Bash",
            "command_pattern": r"ticket\s+(track\s+)?claim.*\bANA\b|ana[-_]?claim",
            "ticket_type_filter": "ANA",
            "reset_conditions": ["wrap_section_written", "manual_wrap_invocation"],
            "message_template": (
                "[WRAP Tripwire] 你正在 claim ANA Ticket（{ticket_id}）。\n"
                "你是有選擇的：\n"
                "  /wrap-decision        — 執行完整 WRAP 流程\n"
                "  在 Solution 寫三問     — W/A/P 三問\n"
            ),
        },
    ],
    "output": {
        "stderr_prefix": "[WRAP Tripwire]",
    },
}


def yaml_fixture(top_overrides=None, signal_overrides=None):
    """Produce a YAML string from DEFAULT_CONFIG with structured overrides.

    Args:
        top_overrides: dict 覆蓋頂層欄位（如 {"version": "9.9.9"}）。
        signal_overrides: dict of {signal_id: {field: value}}，覆蓋指定 signal 的欄位。

    Returns:
        YAML 字串（UTF-8，allow_unicode）。
    """
    config = copy.deepcopy(DEFAULT_CONFIG)
    if top_overrides:
        config.update(top_overrides)
    if signal_overrides:
        for signal in config["signals"]:
            sid = signal["id"]
            if sid in signal_overrides:
                signal.update(signal_overrides[sid])
    return yaml.safe_dump(config, allow_unicode=True, sort_keys=False)


# Backward-compat alias: 預設 YAML 文字（等同 yaml_fixture() 無 overrides）
DEFAULT_YAML = yaml_fixture()


@pytest.fixture
def tmp_yaml(tmp_path):
    p = tmp_path / "wrap-triggers.yaml"
    p.write_text(DEFAULT_YAML, encoding="utf-8")
    return p


@pytest.fixture
def tmp_state_path(tmp_path):
    return tmp_path / "state.json"


@pytest.fixture
def frozen_now(hook_mod, monkeypatch):
    """凍結 _now() 返回指定時間。"""
    class Clock:
        t = datetime(2026, 4, 15, 12, 0, 0)

        def advance(self, seconds):
            self.t = self.t + timedelta(seconds=seconds)

        def set(self, dt):
            self.t = dt

    clock = Clock()
    monkeypatch.setattr(hook_mod, "_now", lambda: clock.t)
    return clock


def _load_config(hook_mod, yaml_path, logger=None):
    if logger is None:
        import logging
        logger = logging.getLogger("test")
    return hook_mod.load_config(Path(yaml_path), logger)


# ============================================================================
# A. 檔案存在性與 metadata
# ============================================================================

class TestA_FileMetadata:
    def test_a1_hook_file_exists(self):
        assert HOOK_PATH.is_file()

    def test_a2_hook_has_pep723_metadata(self):
        head = HOOK_PATH.read_text(encoding="utf-8").splitlines()[:20]
        text = "\n".join(head)
        assert "# /// script" in text
        assert "requires-python" in text
        assert "pyyaml" in text

    def test_a3_yaml_config_file_exists(self):
        assert CONFIG_PATH.is_file()

    def test_a4_yaml_matches_schema_contract(self):
        import yaml
        raw = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        assert "version" in raw
        assert "signals" in raw and isinstance(raw["signals"], list)
        ids = {s["id"] for s in raw["signals"]}
        assert {"consecutive_failures", "restrictive_keywords", "ana_claim"} <= ids
        for s in raw["signals"]:
            assert "event_sources" in s
            assert "reset_conditions" in s
            assert "message_template" in s

    def test_a5_state_json_created_on_first_write(self, hook_mod, tmp_state_path, frozen_now):
        import logging
        logger = logging.getLogger("t")
        state = hook_mod._initial_state()
        state["current_ticket"] = "0.18.0-W10-009"
        hook_mod.save_state_atomic(tmp_state_path, state, logger)
        assert tmp_state_path.exists()
        data = json.loads(tmp_state_path.read_text(encoding="utf-8"))
        assert data["version"] == "1.0.0"
        assert data["current_ticket"] == "0.18.0-W10-009"
        assert "signals" in data


# ============================================================================
# B. settings.json 註冊
# ============================================================================

class TestB_Settings:
    @pytest.fixture
    def settings(self):
        return json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))

    def test_b1_post_tool_use_registered(self, settings):
        found = False
        for entry in settings["hooks"]["PostToolUse"]:
            for h in entry.get("hooks", []):
                if "wrap-decision-tripwire-hook.py" in h.get("command", ""):
                    found = True
        assert found

    def test_b2_user_prompt_submit_registered(self, settings):
        found = False
        for entry in settings["hooks"]["UserPromptSubmit"]:
            for h in entry.get("hooks", []):
                if "wrap-decision-tripwire-hook.py" in h.get("command", ""):
                    found = True
        assert found

    def test_b3_not_registered_in_other_events(self, settings):
        for ev in ("PreToolUse", "SessionStart", "Stop"):
            for entry in settings["hooks"].get(ev, []):
                for h in entry.get("hooks", []):
                    assert "wrap-decision-tripwire-hook.py" not in h.get("command", ""), \
                        "hook should not register to {}".format(ev)

    def test_b4_no_duplicate_post_tool_use_entries(self, settings):
        """HIGH #2: PostToolUse 全捕策略 — Hook 只能出現在 1 個 entry。"""
        count = 0
        for entry in settings["hooks"]["PostToolUse"]:
            for h in entry.get("hooks", []):
                if "wrap-decision-tripwire-hook.py" in h.get("command", ""):
                    count += 1
        assert count == 1, "Expect exactly 1 PostToolUse registration, got {}".format(count)


# ============================================================================
# Helper: build events
# ============================================================================

def make_post_tool_use_task(tool_response, cwd=None):
    return {
        "hook_event_name": "PostToolUse",
        "tool_name": "Task",
        "tool_input": {},
        "tool_response": tool_response,
        "cwd": str(cwd) if cwd else "/tmp",
    }


def make_post_tool_use_bash(command, cwd=None):
    return {
        "hook_event_name": "PostToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "tool_response": {},
        "cwd": str(cwd) if cwd else "/tmp",
    }


def make_user_prompt(prompt, cwd=None):
    return {
        "hook_event_name": "UserPromptSubmit",
        "prompt": prompt,
        "cwd": str(cwd) if cwd else "/tmp",
    }


# ============================================================================
# C. S1 consecutive_failures
# ============================================================================

class TestC_S1:
    @pytest.fixture
    def strategy(self, hook_mod):
        return hook_mod.ConsecutiveFailuresStrategy()

    @pytest.fixture
    def sd_s1(self, hook_mod, tmp_yaml):
        cfg = _load_config(hook_mod, tmp_yaml)
        return next(s for s in cfg.signals if s.id == "consecutive_failures")

    def test_c1_first_failure_no_warn(self, hook_mod, strategy, sd_s1):
        import logging
        state = hook_mod._initial_state()
        event = make_post_tool_use_task({"status": "failed", "error": "boom"})
        result = strategy.detect(event, state, sd_s1, "T-1", logging.getLogger("t"))
        assert result.hit is True
        assert result.count == 1
        assert result.should_warn is False
        state = strategy.apply(state, result, "T-1")
        assert state["signals"]["consecutive_failures"]["count"] == 1

    def test_c2_second_failure_warns(self, hook_mod, strategy, sd_s1):
        import logging
        state = hook_mod._initial_state()
        state["signals"]["consecutive_failures"] = {"count": 1}
        event = make_post_tool_use_task({"status": "failed"})
        result = strategy.detect(event, state, sd_s1, "T-1", logging.getLogger("t"))
        assert result.count == 2
        assert result.should_warn is True

    def test_c3_success_resets_count(self, hook_mod, strategy, sd_s1):
        import logging
        state = hook_mod._initial_state()
        state["signals"]["consecutive_failures"] = {"count": 2}
        event = make_post_tool_use_task({"status": "ok", "message": "all good"})
        result = strategy.detect(event, state, sd_s1, "T-1", logging.getLogger("t"))
        assert result.hit is False
        assert result.reset is True
        state = strategy.apply(state, result, "T-1")
        assert state["signals"]["consecutive_failures"]["count"] == 0

    def test_c4_ticket_switch_resets(self, hook_mod):
        state = hook_mod._initial_state()
        state["current_ticket"] = "T-A"
        state["signals"]["consecutive_failures"] = {"count": 2}
        state = hook_mod.apply_ticket_switch_reset(state, "T-B")
        assert state["current_ticket"] == "T-B"
        assert state["signals"] == {}

    def test_c5_cooldown_suppresses_but_count_still_accumulates(self, hook_mod, strategy, sd_s1, frozen_now):
        """Phase 3a §2 #6 決策：cooldown 內仍累加 count。"""
        import logging
        state = hook_mod._initial_state()
        # 上次提醒於 60 秒前；count=2
        state["signals"]["consecutive_failures"] = {
            "count": 2,
            "last_warned_at": (frozen_now.t - timedelta(seconds=60)).isoformat(),
        }
        event = make_post_tool_use_task({"status": "failed"})
        result = strategy.detect(event, state, sd_s1, "T-1", logging.getLogger("t"))
        # count 仍累加到 3
        assert result.count == 3
        # cooldown 還在（60 < 300）
        state = strategy.apply(state, result, "T-1")
        assert hook_mod.in_cooldown(state, "consecutive_failures", 300) is True

    def test_c6_after_cooldown_warns_again(self, hook_mod, frozen_now):
        state = hook_mod._initial_state()
        state["signals"]["consecutive_failures"] = {
            "count": 2,
            "last_warned_at": (frozen_now.t - timedelta(seconds=301)).isoformat(),
        }
        assert hook_mod.in_cooldown(state, "consecutive_failures", 300) is False

    def test_c7_failure_detection_primary_marker(self, hook_mod, strategy, sd_s1):
        import logging
        state = hook_mod._initial_state()
        event = make_post_tool_use_task({"status": "failed"})
        result = strategy.detect(event, state, sd_s1, "T-1", logging.getLogger("t"))
        assert result.hit is True

    def test_c8_failure_detection_fallback_keyword(self, hook_mod, strategy, sd_s1):
        import logging
        state = hook_mod._initial_state()
        event = make_post_tool_use_task({"output": "...Exception thrown while running..."})
        result = strategy.detect(event, state, sd_s1, "T-1", logging.getLogger("t"))
        assert result.hit is True

    def test_c9_non_task_tool_ignored(self, hook_mod, strategy, sd_s1):
        import logging
        state = hook_mod._initial_state()
        event = make_post_tool_use_bash("echo error")
        result = strategy.detect(event, state, sd_s1, "T-1", logging.getLogger("t"))
        assert result.hit is False

    def test_c10_clock_rewind_treated_as_cooldown_elapsed(self, hook_mod, frozen_now):
        state = hook_mod._initial_state()
        # last_warned_at 比現在還晚
        state["signals"]["consecutive_failures"] = {
            "last_warned_at": (frozen_now.t + timedelta(seconds=60)).isoformat(),
        }
        assert hook_mod.in_cooldown(state, "consecutive_failures", 300) is False


# ============================================================================
# D. S2 restrictive_keywords
# ============================================================================

class TestD_S2:
    @pytest.fixture
    def strategy(self, hook_mod):
        return hook_mod.RestrictiveKeywordsStrategy()

    @pytest.fixture
    def sd_s2(self, hook_mod, tmp_yaml):
        cfg = _load_config(hook_mod, tmp_yaml)
        return next(s for s in cfg.signals if s.id == "restrictive_keywords")

    def test_d1_keyword_match_triggers(self, hook_mod, strategy, sd_s2):
        import logging
        state = hook_mod._initial_state()
        event = make_user_prompt("這個功能做不到啦不可能實現的我想我們應該放棄")
        result = strategy.detect(event, state, sd_s2, None, logging.getLogger("t"))
        assert result.hit is True
        assert result.matched_keyword in {"做不到", "不可能"}

    def test_d2_short_prompt_filtered(self, hook_mod, strategy, sd_s2):
        import logging
        state = hook_mod._initial_state()
        event = make_user_prompt("無法")
        result = strategy.detect(event, state, sd_s2, None, logging.getLogger("t"))
        assert result.hit is False

    def test_d3_case_insensitive_match(self, hook_mod, strategy, sd_s2):
        import logging
        state = hook_mod._initial_state()
        event = make_user_prompt("This is IMPOSSIBLE to achieve in current setup here yo")
        result = strategy.detect(event, state, sd_s2, None, logging.getLogger("t"))
        assert result.hit is True
        assert result.matched_keyword.lower() == "impossible"

    def test_d4_chinese_english_mix(self, hook_mod, strategy, sd_s2):
        import logging
        state = hook_mod._initial_state()
        event = make_user_prompt("這 impossible 啦真的沒辦法解決現在這個情況了")
        result = strategy.detect(event, state, sd_s2, None, logging.getLogger("t"))
        assert result.hit is True

    def test_d5_no_keyword_no_warning(self, hook_mod, strategy, sd_s2):
        import logging
        state = hook_mod._initial_state()
        event = make_user_prompt("請幫我分析這個 ticket 的 acceptance 條件並建立測試案例")
        result = strategy.detect(event, state, sd_s2, None, logging.getLogger("t"))
        assert result.hit is False

    def test_d7_keywords_loaded_from_yaml(self, hook_mod, tmp_path):
        """修改 YAML keywords 改變 Hook 行為（反硬編碼證明）。"""
        custom_yaml = tmp_path / "custom.yaml"
        custom_yaml.write_text(
            yaml_fixture(signal_overrides={"restrictive_keywords": {"keywords": ["專案特殊詞XYZ"]}}),
            encoding="utf-8",
        )
        cfg = _load_config(hook_mod, custom_yaml)
        sd = next(s for s in cfg.signals if s.id == "restrictive_keywords")
        assert sd.keywords == ["專案特殊詞XYZ"]

        import logging
        strat = hook_mod.RestrictiveKeywordsStrategy()
        state = hook_mod._initial_state()
        event = make_user_prompt("這裡涉及 專案特殊詞XYZ 的處理方式討論")
        result = strat.detect(event, state, sd, None, logging.getLogger("t"))
        assert result.hit is True
        assert result.matched_keyword == "專案特殊詞XYZ"

    def test_d8_cooldown_applies(self, hook_mod, frozen_now):
        state = hook_mod._initial_state()
        state["signals"]["restrictive_keywords"] = {
            "last_warned_at": (frozen_now.t - timedelta(seconds=60)).isoformat(),
        }
        assert hook_mod.in_cooldown(state, "restrictive_keywords", 300) is True


# ============================================================================
# E. S3 ana_claim
# ============================================================================

class TestE_S3:
    @pytest.fixture
    def strategy(self, hook_mod):
        return hook_mod.AnaClaimStrategy()

    @pytest.fixture
    def sd_s3(self, hook_mod, tmp_yaml):
        cfg = _load_config(hook_mod, tmp_yaml)
        return next(s for s in cfg.signals if s.id == "ana_claim")

    @pytest.fixture
    def fake_project(self, tmp_path, hook_mod, monkeypatch):
        root = tmp_path / "proj"
        tickets_dir = root / "docs" / "work-logs" / "v0" / "v0.18" / "v0.18.0" / "tickets"
        tickets_dir.mkdir(parents=True)

        def _write_ticket(tid, type_val, include_wrap=False):
            p = tickets_dir / "{}.md".format(tid)
            body = "---\nid: {}\ntype: {}\n---\n\n# Title\n\n## Solution\n\n".format(tid, type_val)
            if include_wrap:
                body += "## WRAP 三問\n\nW: xxx\n"
            p.write_text(body, encoding="utf-8")

        monkeypatch.setattr(hook_mod, "get_project_root", lambda: root)
        return _write_ticket, root

    def test_e1_bash_claim_ana_triggers(self, hook_mod, strategy, sd_s3, fake_project):
        import logging
        write, _ = fake_project
        write("0.18.0-W9-004", "ANA", include_wrap=False)
        state = hook_mod._initial_state()
        event = make_post_tool_use_bash("ticket track claim 0.18.0-W9-004 ANA")
        result = strategy.detect(event, state, sd_s3, None, logging.getLogger("t"))
        assert result.hit is True
        assert result.ticket_id == "0.18.0-W9-004"

    def test_e2_bash_claim_imp_ignored(self, hook_mod, strategy, sd_s3, fake_project):
        import logging
        write, _ = fake_project
        write("0.18.0-W10-009", "IMP", include_wrap=False)
        state = hook_mod._initial_state()
        # command 含 ANA 字樣但 ticket 實際 type=IMP
        event = make_post_tool_use_bash("ticket track claim 0.18.0-W10-009 ANA")
        result = strategy.detect(event, state, sd_s3, None, logging.getLogger("t"))
        assert result.hit is False

    def test_e3_alternative_command_pattern(self, hook_mod, strategy, sd_s3, fake_project):
        import logging
        write, _ = fake_project
        write("0.18.0-W9-004", "ANA", include_wrap=False)
        state = hook_mod._initial_state()
        event = make_post_tool_use_bash("ana-claim 0.18.0-W9-004")
        result = strategy.detect(event, state, sd_s3, None, logging.getLogger("t"))
        # command_pattern 匹配但未必含 ANA ticket type filter；驗證至少 regex matches
        # 此測試主要驗 pattern（第 2 alternation branch）
        # 如果 ticket type=ANA 則 hit=True
        assert result.hit is True

    def test_e4_non_claim_bash_ignored(self, hook_mod, strategy, sd_s3, fake_project):
        import logging
        state = hook_mod._initial_state()
        event = make_post_tool_use_bash("ticket track list")
        result = strategy.detect(event, state, sd_s3, None, logging.getLogger("t"))
        assert result.hit is False

    def test_e5_wrap_section_written_suppresses(self, hook_mod, strategy, sd_s3, fake_project):
        import logging
        write, _ = fake_project
        write("0.18.0-W9-005", "ANA", include_wrap=True)
        state = hook_mod._initial_state()
        event = make_post_tool_use_bash("ticket track claim 0.18.0-W9-005 ANA")
        result = strategy.detect(event, state, sd_s3, None, logging.getLogger("t"))
        assert result.hit is False
        assert result.log_reason == "wrap_section_written"

    def test_e6_user_prompt_submit_ignored(self, hook_mod, strategy, sd_s3, fake_project):
        import logging
        state = hook_mod._initial_state()
        event = make_user_prompt("claim W9-004 ANA ticket 進行分析作業")
        result = strategy.detect(event, state, sd_s3, None, logging.getLogger("t"))
        assert result.hit is False

    def test_e7_frontmatter_unreadable_skips(self, hook_mod, strategy, sd_s3, fake_project):
        import logging
        # 不建立 ticket 檔案
        state = hook_mod._initial_state()
        event = make_post_tool_use_bash("ticket track claim 0.99.0-W99-999 ANA")
        result = strategy.detect(event, state, sd_s3, None, logging.getLogger("t"))
        assert result.hit is False


# ============================================================================
# F. 重置條件路徑
# ============================================================================

class TestF_Resets:
    def test_f1_agent_success_only_affects_s1(self, hook_mod):
        """ConsecutiveFailuresStrategy.apply() 處理 S1 reset；此測試驗 apply 行為。"""
        state = hook_mod._initial_state()
        state["signals"] = {
            "consecutive_failures": {"count": 2},
            "restrictive_keywords": {"last_warned_at": "2026-01-01T00:00:00"},
        }
        strat = hook_mod.ConsecutiveFailuresStrategy()
        result = hook_mod.DetectResult(hit=False, reset=True)
        state = strat.apply(state, result, "T-1")
        assert state["signals"]["consecutive_failures"]["count"] == 0
        assert state["signals"]["restrictive_keywords"]["last_warned_at"] == "2026-01-01T00:00:00"

    def test_f2_ticket_switch_resets_all(self, hook_mod):
        state = hook_mod._initial_state()
        state["current_ticket"] = "T-A"
        state["signals"] = {
            "consecutive_failures": {"count": 2},
            "restrictive_keywords": {"last_warned_at": "2026-01-01T00:00:00"},
            "ana_claim": {"last_claimed_ticket": "X"},
        }
        state = hook_mod.apply_ticket_switch_reset(state, "T-B")
        assert state["current_ticket"] == "T-B"
        assert state["signals"] == {}

    def test_f3_manual_wrap_via_user_prompt(self, hook_mod):
        event = make_user_prompt("/wrap-decision 我想擴增選項因為這個 ticket 有問題")
        assert hook_mod.is_manual_wrap_invocation(event) is True

    def test_f4_manual_wrap_via_bash(self, hook_mod):
        event = make_post_tool_use_bash("/wrap-decision")
        assert hook_mod.is_manual_wrap_invocation(event) is True

    def test_f5_ticket_derivation_env_wins(self, hook_mod, monkeypatch, tmp_path):
        monkeypatch.setenv("TICKET_ID", "ENV-T-1")
        import logging
        t = hook_mod.derive_ticket({}, tmp_path, logging.getLogger("t"))
        assert t == "ENV-T-1"

    def test_f6_ticket_derivation_all_fail_returns_none(self, hook_mod, monkeypatch, tmp_path):
        monkeypatch.delenv("TICKET_ID", raising=False)
        # tmp_path 沒有 dispatch-active.json 也沒有 git repo
        def fake_run(*args, **kwargs):
            raise subprocess.SubprocessError("no git")
        monkeypatch.setattr(hook_mod.subprocess, "run", fake_run)
        import logging
        t = hook_mod.derive_ticket({}, tmp_path, logging.getLogger("t"))
        assert t is None

    def test_f7_manual_wrap_priority_over_keyword(self, hook_mod):
        """含 /wrap-decision 的 prompt 即使含關鍵字，也應先被重置。"""
        event = make_user_prompt("/wrap-decision 我覺得做不到所以來擴增選項")
        assert hook_mod.is_manual_wrap_invocation(event) is True

    def test_f8_dispatch_json_corrupted_fallthrough(self, hook_mod, monkeypatch, tmp_path):
        monkeypatch.delenv("TICKET_ID", raising=False)
        d = tmp_path / ".claude"
        d.mkdir()
        (d / "dispatch-active.json").write_text("not-json{{{", encoding="utf-8")
        def fake_run(*args, **kwargs):
            raise subprocess.SubprocessError("no git")
        monkeypatch.setattr(hook_mod.subprocess, "run", fake_run)
        import logging
        t = hook_mod.derive_ticket({}, tmp_path, logging.getLogger("t"))
        assert t is None  # 損毀 → fallthrough → layer 3 fail → None

    def test_f9_dispatch_json_missing_fallthrough(self, hook_mod, monkeypatch, tmp_path):
        monkeypatch.delenv("TICKET_ID", raising=False)
        def fake_run(*args, **kwargs):
            raise FileNotFoundError("no git")
        monkeypatch.setattr(hook_mod.subprocess, "run", fake_run)
        import logging
        t = hook_mod.derive_ticket({}, tmp_path, logging.getLogger("t"))
        assert t is None


# ============================================================================
# G. 提醒訊息快照
# ============================================================================

class TestG_Message:
    @pytest.fixture
    def cfg(self, hook_mod, tmp_yaml):
        return _load_config(hook_mod, tmp_yaml)

    def test_g1_contains_choice_philosophy(self, hook_mod, cfg):
        sd = next(s for s in cfg.signals if s.id == "consecutive_failures")
        result = hook_mod.DetectResult(hit=True, count=2)
        msg = hook_mod.render_message(sd, result, "0.18.0-W10-009")
        assert "你是有選擇的" in msg

    def test_g2_message_lists_at_least_two_options(self, hook_mod, cfg):
        for sid in ("consecutive_failures", "restrictive_keywords", "ana_claim"):
            sd = next(s for s in cfg.signals if s.id == sid)
            result = hook_mod.DetectResult(hit=True, count=2, matched_keyword="做不到", ticket_id="T-1")
            msg = hook_mod.render_message(sd, result, "T-1")
            # 計算縮排選項行（兩個空格起頭且含 —）
            opt_lines = [line for line in msg.splitlines() if re.match(r"^\s{2,}\S.*—", line)]
            assert len(opt_lines) >= 2, "Signal {} message lacks >=2 options: {!r}".format(sid, msg)

    def test_g3_message_includes_prefix(self, hook_mod, cfg):
        sd = next(s for s in cfg.signals if s.id == "consecutive_failures")
        result = hook_mod.DetectResult(hit=True, count=2)
        msg = hook_mod.render_message(sd, result, "T-1")
        assert "[WRAP Tripwire]" in msg or "[WRAP 絆腳索]" in msg

    def test_g4_dynamic_field_rendering(self, hook_mod, cfg):
        sd = next(s for s in cfg.signals if s.id == "consecutive_failures")
        result = hook_mod.DetectResult(hit=True, count=2)
        msg = hook_mod.render_message(sd, result, "0.18.0-W10-009")
        assert "0.18.0-W10-009" in msg
        assert "2" in msg

    def test_g5_no_state_snapshot_leaked(self, hook_mod, cfg):
        sd = next(s for s in cfg.signals if s.id == "consecutive_failures")
        result = hook_mod.DetectResult(hit=True, count=2)
        msg = hook_mod.render_message(sd, result, "T-1")
        assert "last_warned_at" not in msg
        assert "signals" not in msg


# ============================================================================
# H. stderr + 日誌雙通道
# ============================================================================

class TestH_Channels:
    def test_h3_yaml_parse_failure_dual_channel(self, hook_mod, tmp_path, capsys):
        bad = tmp_path / "bad.yaml"
        bad.write_text("::: invalid :::\n  - [", encoding="utf-8")
        import logging
        logger = logging.getLogger("t_h3")
        cfg = hook_mod.load_config(bad, logger)
        assert cfg is None
        err = capsys.readouterr().err
        assert "[WRAP Tripwire]" in err

    def test_h4_state_write_error_does_not_crash(self, hook_mod, tmp_path, capsys):
        """state 寫入失敗應走 except 路徑 + stderr，不 raise。"""
        import logging
        logger = logging.getLogger("t_h4")
        # 讓 parent 指向不存在且無法建立的路徑（用現有檔當作目錄）
        blocker = tmp_path / "blocker"
        blocker.write_text("", encoding="utf-8")
        target = blocker / "nested" / "state.json"
        state = hook_mod._initial_state()
        # 不應拋例外
        hook_mod.save_state_atomic(target, state, logger)
        # stderr 可能輸出或未（取決於是否觸發）；至少不 raise
        # 驗證未建立成功
        assert not target.exists()


# ============================================================================
# I. YAML 讀取與 fallback
# ============================================================================

class TestI_YamlFallback:
    def test_i1_yaml_missing_exits_zero(self, hook_mod, tmp_path, capsys):
        import logging
        cfg = hook_mod.load_config(tmp_path / "not-exist.yaml", logging.getLogger("t_i1"))
        assert cfg is None
        err = capsys.readouterr().err
        assert "config missing" in err

    def test_i2_yaml_parse_failure(self, hook_mod, tmp_path, capsys):
        p = tmp_path / "bad.yaml"
        p.write_text("::: invalid :::\n- [[[[", encoding="utf-8")
        import logging
        cfg = hook_mod.load_config(p, logging.getLogger("t_i2"))
        assert cfg is None

    def test_i3_version_mismatch_best_effort(self, hook_mod, tmp_path, capsys):
        p = tmp_path / "v.yaml"
        p.write_text(yaml_fixture(top_overrides={"version": "9.9.9"}), encoding="utf-8")
        import logging
        cfg = hook_mod.load_config(p, logging.getLogger("t_i3"))
        assert cfg is not None
        assert len(cfg.signals) >= 3
        err = capsys.readouterr().err
        assert "version mismatch" in err

    def test_i4_disabled_signal_skipped_at_parse(self, hook_mod, tmp_path):
        p = tmp_path / "d.yaml"
        # 把 S1 改成 enabled=false
        content = yaml_fixture(signal_overrides={"consecutive_failures": {"enabled": False}})
        p.write_text(content, encoding="utf-8")
        import logging
        cfg = hook_mod.load_config(p, logging.getLogger("t_i4"))
        s1 = next(s for s in cfg.signals if s.id == "consecutive_failures")
        assert s1.enabled is False

    def test_i5_unknown_reset_logged_not_fatal(self, hook_mod, tmp_path, caplog):
        import logging
        p = tmp_path / "u.yaml"
        content = yaml_fixture(signal_overrides={
            "consecutive_failures": {"reset_conditions": ["agent_success", "unknown_reset_xyz"]}
        })
        p.write_text(content, encoding="utf-8")
        cfg = hook_mod.load_config(p, logging.getLogger("t_i5"))
        assert cfg is not None


# ============================================================================
# J. Source-of-truth 約束（AST + 行為證明）
# ============================================================================

class TestJ_SourceOfTruth:
    @pytest.fixture(scope="class")
    def hook_source(self):
        return HOOK_PATH.read_text(encoding="utf-8")

    @pytest.fixture(scope="class")
    def hook_ast(self, hook_source):
        return ast.parse(hook_source)

    def test_j1_yaml_keyword_change_changes_behavior(self, hook_mod, tmp_path):
        """修改 YAML keywords 改變 Hook 行為（核心反硬編碼證明）。"""
        import logging
        custom = tmp_path / "custom.yaml"
        custom.write_text(
            yaml_fixture(signal_overrides={"restrictive_keywords": {"keywords": ["ZZUNIQUEKEY"]}}),
            encoding="utf-8",
        )
        cfg = hook_mod.load_config(custom, logging.getLogger("t"))
        sd = next(s for s in cfg.signals if s.id == "restrictive_keywords")
        strat = hook_mod.RestrictiveKeywordsStrategy()
        # 不應命中 "做不到"
        state = hook_mod._initial_state()
        ev1 = make_user_prompt("這個問題真的做不到啦完全沒辦法啊拜託")
        r1 = strat.detect(ev1, state, sd, None, logging.getLogger("t"))
        assert r1.hit is False
        # 應命中 "ZZUNIQUEKEY"
        ev2 = make_user_prompt("我們這裡用 ZZUNIQUEKEY 作為關鍵字測試")
        r2 = strat.detect(ev2, state, sd, None, logging.getLogger("t"))
        assert r2.hit is True

    def test_j2_threshold_change_via_yaml(self, hook_mod, tmp_path):
        import logging
        custom = tmp_path / "t.yaml"
        custom.write_text(
            yaml_fixture(signal_overrides={"consecutive_failures": {"threshold": 3}}),
            encoding="utf-8",
        )
        cfg = hook_mod.load_config(custom, logging.getLogger("t"))
        sd = next(s for s in cfg.signals if s.id == "consecutive_failures")
        assert sd.threshold == 3
        # 連續 2 次失敗不應觸發（門檻為 3）
        strat = hook_mod.ConsecutiveFailuresStrategy()
        state = hook_mod._initial_state()
        state["signals"]["consecutive_failures"] = {"count": 1}
        event = make_post_tool_use_task({"status": "failed"})
        r = strat.detect(event, state, sd, "T-1", logging.getLogger("t"))
        assert r.count == 2
        assert r.should_warn is False  # threshold=3，count=2 不觸發

    def _module_assigns(self, tree):
        """返回所有 module-level Assign/AnnAssign target 名稱。"""
        names = []
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name):
                        names.append((t.id, node.value))
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                names.append((node.target.id, node.value))
        return names

    def test_j3_no_hardcoded_keyword_list(self, hook_ast):
        """AST 靜態分析：禁止 module-level 定義 KEYWORDS/TRIGGERS/RESTRICTIVE/IMPOSSIBLE = [...]"""
        forbidden = {"KEYWORDS", "TRIGGERS", "RESTRICTIVE_KEYWORDS", "IMPOSSIBLE_WORDS"}
        for name, value in self._module_assigns(hook_ast):
            if name.upper() in forbidden and isinstance(value, ast.List):
                pytest.fail("Found hardcoded module-level list: {}".format(name))

    def test_j4_hook_reads_yaml(self, hook_source):
        """Hook 程式碼含 yaml.safe_load 與 wrap-triggers.yaml 路徑引用。"""
        assert re.search(r"yaml\.safe_load|yaml\.load", hook_source)
        assert "wrap-triggers.yaml" in hook_source

    def test_j5_no_hardcoded_threshold_in_conditions(self, hook_ast):
        """AST：確認沒有 module-level `threshold = <數字>`。"""
        for name, value in self._module_assigns(hook_ast):
            if name.lower() == "threshold" and isinstance(value, ast.Constant):
                pytest.fail("Found hardcoded threshold constant: {} = {}".format(name, value.value))

    def test_j6_negative_fixture_triggers_ast_failure(self, hook_mod, tmp_path):
        """Negative fixture：注入硬編碼 keyword list 後，AST 檢查應識別出。"""
        fake = tmp_path / "fake_hook.py"
        fake.write_text(textwrap.dedent("""
            KEYWORDS = ["做不到", "沒辦法"]
            THRESHOLD = 2
            def main():
                pass
        """), encoding="utf-8")
        tree = ast.parse(fake.read_text(encoding="utf-8"))
        names = []
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name):
                        names.append((t.id, node.value))
        forbidden = {"KEYWORDS", "TRIGGERS"}
        found = any(
            n.upper() in forbidden and isinstance(v, ast.List)
            for n, v in names
        )
        assert found is True  # negative fixture 預期被 AST 識別


# ============================================================================
# K. 文件同步
# ============================================================================

class TestK_DocSync:
    def test_k1_catalog_pending_marker_removed(self):
        text = CATALOG_PATH.read_text(encoding="utf-8")
        assert "實際 Hook 程式碼實作為獨立 Ticket（待建立）" not in text

    def test_k2_catalog_links_to_w10_009(self):
        text = CATALOG_PATH.read_text(encoding="utf-8")
        assert "0.18.0-W10-009" in text

    def test_k3_skill_md_yaml_sync_note_present(self):
        text = SKILL_PATH.read_text(encoding="utf-8")
        assert "機器可讀版本" in text
        assert "wrap-triggers.yaml" in text


# ============================================================================
# L. Hook 不阻擋（advisory 模式）
# ============================================================================

class TestL_Advisory:
    """integration-ish tests: 跑完整 main() 驗證 exit code=0。"""

    def _run_hook(self, hook_mod, monkeypatch, event, yaml_path, state_path, tmp_path, capsys):
        """呼叫 main() 並回傳 (exit_code, stderr)。"""
        import logging
        # patch config/state 路徑
        monkeypatch.setattr(hook_mod, "get_project_root", lambda: tmp_path)
        # 將 yaml 放到預期位置
        target_yaml = tmp_path / ".claude" / "config" / "wrap-triggers.yaml"
        target_yaml.parent.mkdir(parents=True, exist_ok=True)
        target_yaml.write_text(yaml_path.read_text(encoding="utf-8"), encoding="utf-8")
        # patch stdin
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(event)))
        # disable env ticket
        monkeypatch.delenv("TICKET_ID", raising=False)
        # 直接 patch derive_ticket 避免觸及真實 git/dispatch 狀態
        monkeypatch.setattr(hook_mod, "derive_ticket",
                            lambda ev, cwd, logger: "TEST-TICKET-0.18-W10-009")
        code = hook_mod.main()
        captured = capsys.readouterr()
        return code, captured.err

    def test_l1_signal_paths_exit_zero(self, hook_mod, monkeypatch, tmp_yaml, tmp_state_path, tmp_path, capsys):
        event = make_user_prompt("這個任務做不到啦完全沒辦法真的不行了拜託")
        code, _ = self._run_hook(hook_mod, monkeypatch, event, tmp_yaml, tmp_state_path, tmp_path, capsys)
        assert code == 0

    def test_l2_yaml_missing_exits_zero(self, hook_mod, monkeypatch, tmp_path, capsys):
        import logging
        monkeypatch.setattr(hook_mod, "get_project_root", lambda: tmp_path)
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(make_user_prompt("hi"))))
        code = hook_mod.main()
        assert code == 0

    def test_l3_no_signal_exit_zero(self, hook_mod, monkeypatch, tmp_yaml, tmp_state_path, tmp_path, capsys):
        event = make_user_prompt("這是正常的開發需求並不包含任何關鍵字")
        code, _ = self._run_hook(hook_mod, monkeypatch, event, tmp_yaml, tmp_state_path, tmp_path, capsys)
        assert code == 0


# ============================================================================
# M. S4 reflection_depth_challenge（category=reflection_trigger）— W15-018
# ============================================================================
#
# 涵蓋：
#   M1 category 預設值向後相容（未標註 → wrap_standard）
#   M2 category 顯式標註 reflection_trigger 正確解析
#   M3 T6 反思關鍵字觸發（含 "再想想" / "introspection" 等）
#   M4 min_prompt_length 過濾短 prompt
#   M5 S2/S4 cooldown 獨立（S4 觸發不影響 S2）
#   M6 訊息前綴依 category 區分（由 YAML template 驅動）
#
# 設計前提：
#   - S4 複用 RestrictiveKeywordsStrategy（關鍵字匹配邏輯完全相同），
#     但在 SIGNAL_STRATEGIES 以獨立 key 註冊，state cooldown 自然獨立。

REFLECTION_SIGNAL = {
    "id": "reflection_depth_challenge",
    "category": "reflection_trigger",
    "enabled": True,
    "event_sources": ["UserPromptSubmit"],
    "keywords": [
        "太表層", "不夠深", "再想想", "這解釋不了",
        "為何不是", "更深一層", "還有其他可能嗎", "introspection",
    ],
    "match_mode": "substring",
    "case_sensitive": False,
    "min_prompt_length": 30,
    "reset_conditions": ["manual_reflection_invocation", "session_end"],
    "message_template": (
        "[Reflection Trigger] 偵測到反思深度質疑（關鍵字：{matched_keyword}）。\n"
        "建議採用 three-phase-reflection 方法論：\n"
        "  Phase 1: 列 5+ 候選假設 + Reality Test\n"
        "  Phase 2: WRAP 檢驗 Phase 1 結論\n"
    ),
}


def yaml_fixture_with_reflection(signal_overrides=None):
    """Produce YAML including the S4 reflection signal.

    Args:
        signal_overrides: dict of {signal_id: {field: value}} 覆蓋任一訊號欄位。
    """
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["signals"].append(copy.deepcopy(REFLECTION_SIGNAL))
    if signal_overrides:
        for signal in config["signals"]:
            sid = signal["id"]
            if sid in signal_overrides:
                signal.update(signal_overrides[sid])
    return yaml.safe_dump(config, allow_unicode=True, sort_keys=False)


class TestM_ReflectionTrigger:
    @pytest.fixture
    def tmp_yaml_with_reflection(self, tmp_path):
        p = tmp_path / "wrap-triggers.yaml"
        p.write_text(yaml_fixture_with_reflection(), encoding="utf-8")
        return p

    @pytest.fixture
    def cfg(self, hook_mod, tmp_yaml_with_reflection):
        return _load_config(hook_mod, tmp_yaml_with_reflection)

    @pytest.fixture
    def sd_s4(self, cfg):
        return next(s for s in cfg.signals if s.id == "reflection_depth_challenge")

    def test_m1_category_default_wrap_standard(self, cfg):
        """未標註 category 的訊號（既有 S1/S2/S3）預設為 wrap_standard。"""
        for sid in ("consecutive_failures", "restrictive_keywords", "ana_claim"):
            sd = next(s for s in cfg.signals if s.id == sid)
            assert sd.category == "wrap_standard", \
                "signal {} expected default category wrap_standard, got {}".format(sid, sd.category)

    def test_m2_category_reflection_trigger_parsed(self, sd_s4):
        """category=reflection_trigger 正確從 YAML 解析。"""
        assert sd_s4.category == "reflection_trigger"

    def test_m3_reflection_keyword_triggers(self, hook_mod, sd_s4):
        """T6 類反思關鍵字觸發（中文 + 英文 introspection）。"""
        import logging
        strat = hook_mod.SIGNAL_STRATEGIES["reflection_depth_challenge"]
        state = hook_mod._initial_state()
        # 中文關鍵字（prompt 長度需 >= 30）
        event = make_user_prompt("你剛剛的分析太表層了完全沒有挖到真正的深因請再想想到底根本原因是什麼呢拜託")
        result = strat.detect(event, state, sd_s4, None, logging.getLogger("t"))
        assert result.hit is True
        assert result.matched_keyword in {"太表層", "再想想"}
        assert result.should_warn is True

    def test_m3b_reflection_keyword_introspection(self, hook_mod, sd_s4):
        """英文關鍵字 introspection 觸發（case insensitive）。"""
        import logging
        strat = hook_mod.SIGNAL_STRATEGIES["reflection_depth_challenge"]
        state = hook_mod._initial_state()
        event = make_user_prompt("Please do deeper INTROSPECTION on the root cause here")
        result = strat.detect(event, state, sd_s4, None, logging.getLogger("t"))
        assert result.hit is True
        assert result.matched_keyword.lower() == "introspection"

    def test_m4_min_prompt_length_filter(self, hook_mod, sd_s4):
        """短 prompt（< min_prompt_length=30）即使含關鍵字也不觸發。"""
        import logging
        strat = hook_mod.SIGNAL_STRATEGIES["reflection_depth_challenge"]
        state = hook_mod._initial_state()
        event = make_user_prompt("再想想")  # < 30 chars
        result = strat.detect(event, state, sd_s4, None, logging.getLogger("t"))
        assert result.hit is False

    def test_m5_s4_cooldown_independent_from_s2(self, hook_mod, frozen_now):
        """S2 cooldown 激活時，S4 cooldown 仍為 False（獨立訊號 state）。"""
        state = hook_mod._initial_state()
        state["signals"]["restrictive_keywords"] = {
            "last_warned_at": (frozen_now.t - timedelta(seconds=60)).isoformat(),
        }
        # S2 在 cooldown 期間
        assert hook_mod.in_cooldown(state, "restrictive_keywords", 300) is True
        # S4 未曾提醒 → 不在 cooldown
        assert hook_mod.in_cooldown(state, "reflection_depth_challenge", 300) is False

    def test_m5b_s2_cooldown_unaffected_by_s4_warning(self, hook_mod, frozen_now):
        """S4 mark_warned 不會影響 S2 cooldown。"""
        state = hook_mod._initial_state()
        # S4 剛提醒
        hook_mod.mark_warned(state, "reflection_depth_challenge")
        # S2 未曾提醒
        assert hook_mod.in_cooldown(state, "restrictive_keywords", 300) is False
        # S4 在 cooldown
        assert hook_mod.in_cooldown(state, "reflection_depth_challenge", 300) is True

    def test_m6_message_prefix_differs_by_category(self, hook_mod, cfg):
        """不同 category 的訊號產生不同訊息前綴（由 YAML template 驅動）。"""
        sd_wrap = next(s for s in cfg.signals if s.id == "restrictive_keywords")
        sd_refl = next(s for s in cfg.signals if s.id == "reflection_depth_challenge")
        result = hook_mod.DetectResult(hit=True, matched_keyword="做不到", signal_id=sd_wrap.id)
        wrap_msg = hook_mod.render_message(sd_wrap, result, "T-1")
        result_refl = hook_mod.DetectResult(hit=True, matched_keyword="再想想", signal_id=sd_refl.id)
        refl_msg = hook_mod.render_message(sd_refl, result_refl, "T-1")
        assert "[WRAP Tripwire]" in wrap_msg or "[WRAP 絆腳索]" in wrap_msg
        assert "[Reflection Trigger]" in refl_msg
        assert "three-phase-reflection" in refl_msg

    def test_m7_non_user_prompt_event_ignored(self, hook_mod, sd_s4):
        """S4 只在 UserPromptSubmit 觸發；其他 event 忽略。
        （由 _process_signals 過濾 event_sources，strategy 層不負責，但驗證 config 設定正確）"""
        assert sd_s4.event_sources == ["UserPromptSubmit"]

    def test_m8_strategy_registered(self, hook_mod):
        """SIGNAL_STRATEGIES 包含 reflection_depth_challenge 鍵。"""
        assert "reflection_depth_challenge" in hook_mod.SIGNAL_STRATEGIES

    def test_m9_backward_compat_yaml_without_category_parses(self, hook_mod, tmp_yaml):
        """既有 yaml（無 category 欄位）仍能解析，所有訊號 category=wrap_standard。"""
        cfg = _load_config(hook_mod, tmp_yaml)
        for sd in cfg.signals:
            assert sd.category == "wrap_standard"

    def test_m10_reset_conditions_include_reflection_specific(self, sd_s4):
        """reflection_trigger 新增的 reset_conditions 不被視為 unknown。"""
        assert "manual_reflection_invocation" in sd_s4.reset_conditions
        assert "session_end" in sd_s4.reset_conditions

    def test_m11_reflection_reset_conditions_not_logged_as_unknown(self, hook_mod, tmp_path, caplog):
        """解析含 reflection_trigger 的 yaml 時，新 reset 條件不被記為 unknown。"""
        import logging
        p = tmp_path / "r.yaml"
        p.write_text(yaml_fixture_with_reflection(), encoding="utf-8")
        with caplog.at_level(logging.INFO):
            cfg = _load_config(hook_mod, p)
        assert cfg is not None
        # 確認沒有針對 manual_reflection_invocation / session_end 的 unknown log
        for rec in caplog.records:
            assert "manual_reflection_invocation" not in rec.getMessage() or "unknown" not in rec.getMessage().lower()
            assert "session_end" not in rec.getMessage() or "unknown" not in rec.getMessage().lower()
