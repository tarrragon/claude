"""Tests for reference-stability-rule8-guard-hook.py 全禁偵測 + 存量凍結（0.2.1-W3-315）

背景：舊版守衛僅在 ticket ID 前 15 字元鄰近視窗內含跳轉引導詞
（詳見/參見/參閱/參考/依據/根據/來源是/相關文件）時觸發 WARNING，與
reference-stability-rules.md 規則 8「引用性質判準：全禁原則與五類分類」
已改採全禁的判準脫節（0.2.1-W3-306 / W3-308 新增 16 處無跳轉詞違規全程未
攔截）。本次改寫：
  - find_ticket_id_hits 成為全量偵測（不再分依賴型/歷史錨點型）
  - 新增第 4 類白名單（is_class4_whitelisted）與第 5 類測試路徑
    （is_class5_test_path）機械可判定豁免
  - 新增「編輯前後淨增量比對」存量凍結機制（reconstruct_pre_post_text +
    diff_new_hits）：檔案既有 ticket ID 天然落在 pre_text 而不重複觸發，
    僅本次操作淨增的 ticket ID 觸發 WARNING

測試覆蓋：
| 測試 | 場景 | 驗證 |
|------|------|------|
| test_full_ban_no_jump_word_detected | 0.2.1-W3-308 形態無跳轉詞裸引用 | 觸發 WARNING（acceptance 1） |
| test_full_ban_with_jump_word_still_detected | 舊版依賴型（含跳轉詞） | 仍觸發 WARNING（回歸） |
| test_class4_whitelist_path_exempt | ticket-id-conventions.md | 豁免，不觸發（acceptance 2） |
| test_class5_test_dir_path_exempt | .claude/hooks/tests/ 下檔案 | 豁免，不觸發（acceptance 2） |
| test_class5_test_filename_pattern_exempt | *_test.py 檔名 | 豁免，不觸發（acceptance 2） |
| test_frozen_existing_hit_not_rewarned | 既有 ticket ID 原樣保留（純重排） | 不觸發（存量凍結，acceptance 3） |
| test_new_hit_in_already_violating_file_still_warned | 已有存量違規的檔案新增另一 ticket ID | 仍觸發，且只回報新增項（acceptance 3 關鍵情境） |
| test_new_file_write_with_ticket_id_warned | Write 建立全新檔案含 ticket ID | 觸發（無存量基準時 pre_text 視為空） |
| test_non_scanned_path_silent | 路徑不在 .claude/ 下 | 不觸發 |
| test_handoff_archive_exempt | .claude/handoff/archive/ | 不觸發（既有豁免回歸） |
| test_code_fence_content_not_flagged | code fence 內容 | 不觸發（既有豁免回歸） |
| test_date_and_framework_id_not_flagged | 日期 / PC-xxx / CC 版本 | 不觸發（既有豁免回歸） |

策略：
- importlib 動態載入（檔名含 hyphen）
- 以真實 tmp_path 檔案模擬「編輯前磁碟內容」，驗證存量凍結的淨增量比對
- monkeypatch sys.stdin 餵入 stdin JSON，呼叫 main() 驗證端到端行為
- capsys 捕獲 stderr WARNING 訊息
"""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest


HOOK_PATH = Path(__file__).parent.parent / "reference-stability-rule8-guard-hook.py"


def _load_hook_module():
    spec = importlib.util.spec_from_file_location(
        "reference_stability_rule8_guard_hook", HOOK_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def hook_mod():
    return _load_hook_module()


def _stdin_json(payload: dict) -> io.StringIO:
    return io.StringIO(json.dumps(payload))


def _run_main(hook_mod, monkeypatch, payload: dict) -> int:
    monkeypatch.setattr(sys, "stdin", _stdin_json(payload))
    return hook_mod.main()


def _claude_path(tmp_path: Path, *parts: str) -> Path:
    """在 tmp_path 下建立含 .claude/ 片段的路徑（守衛以子字串比對掃描範圍）。"""
    p = tmp_path.joinpath(".claude", *parts)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


# ---------------------------------------------------------------------------
# 全禁偵測（acceptance 1）：無跳轉詞裸引用亦能偵測
# ---------------------------------------------------------------------------


class TestFullBanDetection:
    def test_full_ban_no_jump_word_detected(self, hook_mod, monkeypatch, tmp_path, capsys):
        target = _claude_path(tmp_path, "skills", "ticket", "hooks", "example-hook.py")
        target.write_text("既有內容行\n無關的一行\n", encoding="utf-8")

        payload = {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": str(target),
                "old_string": "無關的一行",
                "new_string": "無關的一行\n# from 0.2.1-W3-308",
            },
        }
        rc = _run_main(hook_mod, monkeypatch, payload)
        err = capsys.readouterr().err

        assert rc == 0
        assert "0.2.1-W3-308" in err
        assert "WARNING" in err

    def test_full_ban_with_jump_word_still_detected(self, hook_mod, monkeypatch, tmp_path, capsys):
        target = _claude_path(tmp_path, "rules", "core", "example.md")
        target.write_text("原始內容\n", encoding="utf-8")

        payload = {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": str(target),
                "old_string": "原始內容",
                "new_string": "原始內容\n詳見 0.2.1-W3-999 的分析結論。",
            },
        }
        rc = _run_main(hook_mod, monkeypatch, payload)
        err = capsys.readouterr().err

        assert rc == 0
        assert "0.2.1-W3-999" in err


# ---------------------------------------------------------------------------
# 第 4 / 5 類機械可判定豁免（acceptance 2）
# ---------------------------------------------------------------------------


class TestMechanicalExemptions:
    def test_class4_whitelist_path_exempt(self, hook_mod, monkeypatch, tmp_path, capsys):
        target = _claude_path(tmp_path, "references", "ticket-id-conventions.md")
        target.write_text("格式規範文件\n", encoding="utf-8")

        payload = {
            "tool_name": "Write",
            "tool_input": {
                "file_path": str(target),
                "content": "格式範例：0.1.0-W3-001（被說明對象）",
            },
        }
        rc = _run_main(hook_mod, monkeypatch, payload)
        err = capsys.readouterr().err

        assert rc == 0
        assert err == ""

    def test_class5_test_dir_path_exempt(self, hook_mod, monkeypatch, tmp_path, capsys):
        target = _claude_path(tmp_path, "hooks", "tests", "test_example_hook.py")
        target.write_text("", encoding="utf-8")

        payload = {
            "tool_name": "Write",
            "tool_input": {
                "file_path": str(target),
                "content": "assert parse('0.1.0-W3-001') == True",
            },
        }
        rc = _run_main(hook_mod, monkeypatch, payload)
        err = capsys.readouterr().err

        assert rc == 0
        assert err == ""

    def test_class5_test_filename_pattern_exempt(self, hook_mod, monkeypatch, tmp_path, capsys):
        target = _claude_path(tmp_path, "scripts", "parser_test.py")
        target.write_text("", encoding="utf-8")

        payload = {
            "tool_name": "Write",
            "tool_input": {
                "file_path": str(target),
                "content": "assert parse('W3-001') == True",
            },
        }
        rc = _run_main(hook_mod, monkeypatch, payload)
        err = capsys.readouterr().err

        assert rc == 0
        assert err == ""

    def test_non_exempt_path_with_same_style_id_still_warned(
        self, hook_mod, monkeypatch, tmp_path, capsys
    ):
        """確認第 4/5 類豁免僅限指定路徑，非白名單路徑的同類引用仍應告警。"""
        target = _claude_path(tmp_path, "methodologies", "example-methodology.md")
        target.write_text("原始內容\n", encoding="utf-8")

        payload = {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": str(target),
                "old_string": "原始內容",
                "new_string": "原始內容\n格式範例：0.1.0-W3-001",
            },
        }
        rc = _run_main(hook_mod, monkeypatch, payload)
        err = capsys.readouterr().err

        assert rc == 0
        assert "0.1.0-W3-001" in err


# ---------------------------------------------------------------------------
# 存量凍結機制（acceptance 3）：編輯前後淨增量比對
# ---------------------------------------------------------------------------


class TestFreezeMechanism:
    def test_frozen_existing_hit_not_rewarned(self, hook_mod, monkeypatch, tmp_path, capsys):
        target = _claude_path(tmp_path, "pm-rules", "example.md")
        target.write_text(
            "既有內容第一行\n舊引用（0.2.1-W3-100 教訓）\n既有內容第三行\n",
            encoding="utf-8",
        )

        payload = {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": str(target),
                "old_string": "既有內容第三行",
                "new_string": "既有內容第三行（微調文字，仍含 0.2.1-W3-100）",
            },
        }
        rc = _run_main(hook_mod, monkeypatch, payload)
        err = capsys.readouterr().err

        assert rc == 0
        assert err == ""

    def test_new_hit_in_already_violating_file_still_warned(
        self, hook_mod, monkeypatch, tmp_path, capsys
    ):
        """凍結範圍內新增命中仍告警：關鍵情境，防止整檔豁免漏洞。"""
        target = _claude_path(tmp_path, "pm-rules", "example2.md")
        target.write_text(
            "既有內容第一行\n舊引用（0.2.1-W3-100 教訓）\n既有內容第三行\n",
            encoding="utf-8",
        )

        payload = {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": str(target),
                "old_string": "既有內容第一行",
                "new_string": "既有內容第一行\n新增引用（0.2.1-W3-999 教訓）",
            },
        }
        rc = _run_main(hook_mod, monkeypatch, payload)
        err = capsys.readouterr().err

        assert rc == 0
        assert "0.2.1-W3-999" in err
        # 既有存量（0.2.1-W3-100）不應出現在「新增命中」清單中
        assert "0.2.1-W3-100" not in err

    def test_new_file_write_with_ticket_id_warned(self, hook_mod, monkeypatch, tmp_path, capsys):
        target = _claude_path(tmp_path, "references", "brand-new.md")
        # 檔案尚未存在（不預先寫入），模擬 Write 建立全新檔案

        payload = {
            "tool_name": "Write",
            "tool_input": {
                "file_path": str(target),
                "content": "全新檔案，直接 # from 0.2.1-W3-308 無跳轉詞",
            },
        }
        rc = _run_main(hook_mod, monkeypatch, payload)
        err = capsys.readouterr().err

        assert rc == 0
        assert "0.2.1-W3-308" in err

    def test_multiedit_freeze_and_new_hit(self, hook_mod, monkeypatch, tmp_path, capsys):
        target = _claude_path(tmp_path, "pm-rules", "example3.md")
        target.write_text(
            "第一段（0.2.1-W3-100）\n第二段內容\n第三段內容\n",
            encoding="utf-8",
        )

        payload = {
            "tool_name": "MultiEdit",
            "tool_input": {
                "file_path": str(target),
                "edits": [
                    {
                        "old_string": "第二段內容",
                        "new_string": "第二段內容（仍含 0.2.1-W3-100）",
                    },
                    {
                        "old_string": "第三段內容",
                        "new_string": "第三段內容（新增 0.2.1-W3-777）",
                    },
                ],
            },
        }
        rc = _run_main(hook_mod, monkeypatch, payload)
        err = capsys.readouterr().err

        assert rc == 0
        assert "0.2.1-W3-777" in err
        assert "0.2.1-W3-100" not in err


# ---------------------------------------------------------------------------
# 既有放行例外回歸測試
# ---------------------------------------------------------------------------


class TestExistingExemptionsRegression:
    def test_non_scanned_path_silent(self, hook_mod, monkeypatch, tmp_path, capsys):
        target = tmp_path / "docs" / "work-logs" / "example.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("", encoding="utf-8")

        payload = {
            "tool_name": "Write",
            "tool_input": {
                "file_path": str(target),
                "content": "詳見 0.2.1-W3-308 的分析結論。",
            },
        }
        rc = _run_main(hook_mod, monkeypatch, payload)
        err = capsys.readouterr().err

        assert rc == 0
        assert err == ""

    def test_handoff_archive_exempt(self, hook_mod, monkeypatch, tmp_path, capsys):
        target = _claude_path(tmp_path, "handoff", "archive", "2026-01-01.md")
        target.write_text("", encoding="utf-8")

        payload = {
            "tool_name": "Write",
            "tool_input": {
                "file_path": str(target),
                "content": "詳見 0.2.1-W3-308 的分析結論。",
            },
        }
        rc = _run_main(hook_mod, monkeypatch, payload)
        err = capsys.readouterr().err

        assert rc == 0
        assert err == ""

    def test_code_fence_content_not_flagged(self, hook_mod, monkeypatch, tmp_path, capsys):
        target = _claude_path(tmp_path, "references", "example-doc.md")
        target.write_text("原始內容\n", encoding="utf-8")

        payload = {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": str(target),
                "old_string": "原始內容",
                "new_string": "原始內容\n```\n詳見 0.2.1-W3-308 的分析結論\n```\n",
            },
        }
        rc = _run_main(hook_mod, monkeypatch, payload)
        err = capsys.readouterr().err

        assert rc == 0
        assert err == ""

    def test_date_and_framework_id_not_flagged(self, hook_mod, monkeypatch, tmp_path, capsys):
        target = _claude_path(tmp_path, "error-patterns", "example.md")
        target.write_text("原始內容\n", encoding="utf-8")

        payload = {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": str(target),
                "old_string": "原始內容",
                "new_string": (
                    "原始內容\n此變更於 2026-07-08 完成，已知案例：PC-050、IMP-003。"
                    "CC 2.1.97 新增能力。"
                ),
            },
        }
        rc = _run_main(hook_mod, monkeypatch, payload)
        err = capsys.readouterr().err

        assert rc == 0
        assert err == ""


# ---------------------------------------------------------------------------
# 單元函式測試（守衛與規則文件判準一致性，acceptance 4）
# ---------------------------------------------------------------------------


class TestUnitFunctions:
    def test_find_ticket_id_hits_full_ban_no_classification(self, hook_mod):
        """find_ticket_id_hits 為全量偵測，不再區分依賴型/歷史錨點型。"""
        hits = hook_mod.find_ticket_id_hits("裸引用（0.2.1-W3-100 教訓），無跳轉詞。")
        assert "0.2.1-W3-100" in hits

    def test_is_class4_whitelisted_exact_path_only(self, hook_mod):
        assert hook_mod.is_class4_whitelisted(
            ".claude/references/ticket-id-conventions.md"
        )
        assert not hook_mod.is_class4_whitelisted(".claude/references/other-doc.md")

    def test_is_class5_test_path_covers_dir_and_filename(self, hook_mod):
        assert hook_mod.is_class5_test_path(".claude/hooks/tests/test_foo_hook.py")
        assert hook_mod.is_class5_test_path(".claude/scripts/foo_test.py")
        assert not hook_mod.is_class5_test_path(".claude/hooks/foo-hook.py")

    def test_whitelist_member_count_within_limit(self, hook_mod):
        """規則文件明訂第 4 類白名單成員上限 3。"""
        assert len(hook_mod.WHITELIST_PATHS) <= 3

    def test_diff_new_hits_excludes_pre_existing(self, hook_mod):
        pre = "既有引用（0.2.1-W3-100）"
        post = "既有引用（0.2.1-W3-100）新增引用（0.2.1-W3-200）"
        new_hits = hook_mod.diff_new_hits(pre, post)
        assert "0.2.1-W3-200" in new_hits
        assert "0.2.1-W3-100" not in new_hits

    def test_reconstruct_pre_post_text_edit_reads_disk(self, hook_mod, tmp_path):
        target = tmp_path / "sample.md"
        target.write_text("原始內容\n", encoding="utf-8")

        pre, post = hook_mod.reconstruct_pre_post_text(
            "Edit",
            {"file_path": str(target), "old_string": "原始內容", "new_string": "改寫內容"},
            str(target),
        )
        assert pre == "原始內容\n"
        assert post == "改寫內容\n"
