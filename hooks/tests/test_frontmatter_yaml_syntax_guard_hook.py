"""Tests for frontmatter-yaml-syntax-guard-hook.py（0.2.1-W3-710）

背景：PyYAML frontmatter 解析為全有全無——單一未跳脫冒號或 flow-style
字元即整份靜默回傳空字典，既有呼叫端無法區分「解析失敗」與「本來就沒有
frontmatter」。本 hook 在 PostToolUse（Edit/Write 完成後）讀回檔案並嘗試
解析 frontmatter，語法錯誤時阻擋（exit 2）並回報可定位的行號；檔案任意
位置有 `<!-- yaml-frontmatter-exempt: <理由> -->` marker 時降級為警告
不阻擋。

三個現成命中語料（皆為專案 dogfooding 掃描時的真實內容片段，本測試檔
以字面重現其 YAML 錯誤形態，不依賴外部檔案存在）：
- basil-writing-critic.md 形態：description 值含未跳脫 `Use when: ...`
- language-agent-template.md 形態：`{language}` 觸發 flow-mapping 誤判
- PC-059 形態：list item 值含未跳脫 `permissionMode: acceptEdits`

測試覆蓋：
| 測試 | 場景 | 驗證 |
|------|------|------|
| test_valid_frontmatter_allowed | 合法 frontmatter | exit 0，無 stderr |
| test_no_frontmatter_allowed | 檔案不以 --- 開頭 | exit 0，跳過 |
| test_non_md_file_skipped | 副檔名非 .md | exit 0，跳過 |
| test_wrong_tool_skipped | tool_name 非 Edit/Write | exit 0，跳過 |
| test_missing_stdin_input_allowed | stdin 無 JSON | exit 0 |
| test_file_read_failure_fail_open | 檔案不存在 | exit 0（fail-open） |
| test_basil_writing_critic_style_blocked | 語料 1：未跳脫冒號 | exit 2，行號正確 |
| test_language_agent_template_style_blocked_without_marker | 語料 2：flow-style 誤判，無 marker | exit 2 |
| test_language_agent_template_style_exempt_with_marker | 語料 2 + marker | exit 0，降級警告 |
| test_pc059_style_blocked | 語料 3：list item 內未跳脫冒號 | exit 2，行號正確 |
| test_missing_closing_fence_blocked | 起始 --- 無對應結束 --- | exit 2 |
| test_non_dict_toplevel_blocked | frontmatter 頂層為 list | exit 2 |
| test_line_number_offset_accounts_for_leading_blank_lines | frontmatter 區塊前有空白行 | 行號正確換算 |

策略：
- importlib 動態載入（檔名含 hyphen）
- 以真實 tmp_path 檔案模擬「編輯後磁碟內容」（PostToolUse 讀當前磁碟狀態，
  不需重建 old_string/new_string）
- monkeypatch sys.stdin 餵入 stdin JSON，呼叫 main() 驗證端到端行為
- capsys 捕獲 stderr 訊息
"""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest


HOOK_PATH = Path(__file__).parent.parent / "frontmatter-yaml-syntax-guard-hook.py"


def _load_hook_module():
    spec = importlib.util.spec_from_file_location(
        "frontmatter_yaml_syntax_guard_hook", HOOK_PATH
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


def _edit_payload(file_path: str) -> dict:
    """組合最小 Edit payload（本 hook 直接讀磁碟內容，不解析 old/new_string）。"""
    return {
        "tool_name": "Edit",
        "tool_input": {
            "file_path": file_path,
            "old_string": "占位",
            "new_string": "占位",
        },
    }


# ---------------------------------------------------------------------------
# 基本放行路徑
# ---------------------------------------------------------------------------


class TestAllowPaths:
    def test_valid_frontmatter_allowed(self, hook_mod, monkeypatch, tmp_path, capsys):
        target = tmp_path / "valid.md"
        target.write_text(
            "---\nname: foo\ndescription: 一段正常敘述\n---\n\nBody.\n",
            encoding="utf-8",
        )
        rc = _run_main(hook_mod, monkeypatch, _edit_payload(str(target)))
        err = capsys.readouterr().err

        assert rc == 0
        assert err == ""

    def test_no_frontmatter_allowed(self, hook_mod, monkeypatch, tmp_path, capsys):
        target = tmp_path / "no-frontmatter.md"
        target.write_text("# 標題\n\n內容不含 frontmatter。\n", encoding="utf-8")
        rc = _run_main(hook_mod, monkeypatch, _edit_payload(str(target)))
        err = capsys.readouterr().err

        assert rc == 0
        assert err == ""

    def test_non_md_file_skipped(self, hook_mod, monkeypatch, tmp_path, capsys):
        target = tmp_path / "script.py"
        target.write_text("---\nbroken: [unterminated\n", encoding="utf-8")
        rc = _run_main(hook_mod, monkeypatch, _edit_payload(str(target)))
        err = capsys.readouterr().err

        assert rc == 0
        assert err == ""

    def test_wrong_tool_skipped(self, hook_mod, monkeypatch, tmp_path, capsys):
        target = tmp_path / "broken.md"
        target.write_text("---\nname: {a}-b\n---\n", encoding="utf-8")
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": "echo hi"},
        }
        rc = _run_main(hook_mod, monkeypatch, payload)
        err = capsys.readouterr().err

        assert rc == 0
        assert err == ""

    def test_multiedit_tool_covered(self, hook_mod, monkeypatch, tmp_path, capsys):
        # MultiEdit 亦寫入檔案內容，與 Edit/Write 共用同一機制（直接讀磁碟
        # 內容，不解析 tool_input 內部結構），本 hook 一併涵蓋。
        target = tmp_path / "multiedit.md"
        target.write_text("---\nname: {a}-b\n---\n", encoding="utf-8")
        payload = {
            "tool_name": "MultiEdit",
            "tool_input": {
                "file_path": str(target),
                "edits": [{"old_string": "a", "new_string": "b"}],
            },
        }
        rc = _run_main(hook_mod, monkeypatch, payload)
        err = capsys.readouterr().err

        assert rc == 2
        assert "BLOCKED" in err

    def test_missing_stdin_input_allowed(self, hook_mod, monkeypatch):
        monkeypatch.setattr(sys, "stdin", io.StringIO(""))
        rc = hook_mod.main()
        assert rc == 0

    def test_file_read_failure_fail_open(self, hook_mod, monkeypatch, tmp_path, capsys):
        missing = tmp_path / "does-not-exist.md"
        rc = _run_main(hook_mod, monkeypatch, _edit_payload(str(missing)))
        err = capsys.readouterr().err

        assert rc == 0
        assert err == ""


# ---------------------------------------------------------------------------
# 三個現成命中語料（acceptance 4）
# ---------------------------------------------------------------------------


class TestKnownCorpora:
    def test_basil_writing_critic_style_blocked(
        self, hook_mod, monkeypatch, tmp_path, capsys
    ):
        # 語料 1：description 值含未跳脫 `Use when: ...`（第 3 行）
        content = (
            "---\n"
            "name: basil-writing-critic\n"
            "description: 文字品質常駐審查委員。Use when: 規則變更後。\n"
            "tools: Read, Grep\n"
            "---\n"
        )
        target = tmp_path / "basil-writing-critic.md"
        target.write_text(content, encoding="utf-8")

        rc = _run_main(hook_mod, monkeypatch, _edit_payload(str(target)))
        err = capsys.readouterr().err

        assert rc == 2
        assert "BLOCKED" in err
        assert "第 3 行" in err

    def test_language_agent_template_style_blocked_without_marker(
        self, hook_mod, monkeypatch, tmp_path, capsys
    ):
        # 語料 2：{language} 觸發 flow-mapping 誤判（第 2 行）
        content = "---\nname: {language}-developer\nmodel: haiku\n---\n"
        target = tmp_path / "language-agent-template.md"
        target.write_text(content, encoding="utf-8")

        rc = _run_main(hook_mod, monkeypatch, _edit_payload(str(target)))
        err = capsys.readouterr().err

        assert rc == 2
        assert "BLOCKED" in err

    def test_language_agent_template_style_exempt_with_marker(
        self, hook_mod, monkeypatch, tmp_path, capsys
    ):
        content = (
            "---\nname: {language}-developer\nmodel: haiku\n---\n\n"
            "<!-- yaml-frontmatter-exempt: 範本檔案示範用途 -->\n"
        )
        target = tmp_path / "language-agent-template.md"
        target.write_text(content, encoding="utf-8")

        rc = _run_main(hook_mod, monkeypatch, _edit_payload(str(target)))
        err = capsys.readouterr().err

        assert rc == 0
        assert "BLOCKED" not in err
        assert "WARNING" in err
        assert "範本檔案示範用途" in err

    def test_pc059_style_blocked(self, hook_mod, monkeypatch, tmp_path, capsys):
        # 語料 3：list item 值含未跳脫冒號（第 4 行）
        content = (
            "---\n"
            "id: PC-059\n"
            "retries:\n"
            " - retry6: 內容含 `permissionMode: acceptEdits` 未加引號\n"
            "---\n"
        )
        target = tmp_path / "PC-059-example.md"
        target.write_text(content, encoding="utf-8")

        rc = _run_main(hook_mod, monkeypatch, _edit_payload(str(target)))
        err = capsys.readouterr().err

        assert rc == 2
        assert "BLOCKED" in err
        assert "第 4 行" in err


# ---------------------------------------------------------------------------
# 結構異常（缺結束 fence / 頂層非 dict）
# ---------------------------------------------------------------------------


class TestStructuralErrors:
    def test_missing_closing_fence_blocked(self, hook_mod, monkeypatch, tmp_path, capsys):
        target = tmp_path / "unclosed.md"
        target.write_text("---\nname: foo\n\n沒有結束 fence\n", encoding="utf-8")

        rc = _run_main(hook_mod, monkeypatch, _edit_payload(str(target)))
        err = capsys.readouterr().err

        assert rc == 2
        assert "BLOCKED" in err

    def test_non_dict_toplevel_blocked(self, hook_mod, monkeypatch, tmp_path, capsys):
        target = tmp_path / "list-toplevel.md"
        target.write_text("---\n- a\n- b\n---\nbody\n", encoding="utf-8")

        rc = _run_main(hook_mod, monkeypatch, _edit_payload(str(target)))
        err = capsys.readouterr().err

        assert rc == 2
        assert "BLOCKED" in err


# ---------------------------------------------------------------------------
# 行號換算（實作陷阱）
# ---------------------------------------------------------------------------


class TestLineNumberOffset:
    def test_line_number_offset_accounts_for_leading_blank_lines(
        self, hook_mod, monkeypatch, tmp_path, capsys
    ):
        # frontmatter 區塊起始邊界後有一個空白行，stripped_block 實際從
        # 檔案第 3 行開始；錯誤落在 stripped_block 第 2 行（0-indexed 1）
        # → 檔案真實行號應為 3 + 1 = 4。
        content = (
            "---\n"
            "\n"
            "name: foo\n"
            "description: 值含未跳脫 X: Y\n"
            "---\n"
        )
        target = tmp_path / "offset.md"
        target.write_text(content, encoding="utf-8")

        rc = _run_main(hook_mod, monkeypatch, _edit_payload(str(target)))
        err = capsys.readouterr().err

        assert rc == 2
        assert "第 4 行" in err
