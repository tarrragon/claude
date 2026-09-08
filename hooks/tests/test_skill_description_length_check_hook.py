"""Tests for skill-description-length-check-hook.py 執法升級（baseline 加硬擋）

背景：本 hook 原僅在 SessionStart 掃描並輸出 warning（WARNING_THRESHOLD=250），
對 AI agent 無約束力。本次升級新增 PreToolUse Edit/Write/MultiEdit 執法層：
description 超過門檻時，依 baseline 檔（既有存量 21+ 支）判斷是否阻擋，
避免既有超標存量一次全部變紅。

測試覆蓋：
| 測試 | 場景 | 驗證 |
|------|------|------|
| test_new_skill_over_threshold_blocked | 新建 SKILL.md 超標，不在 baseline | 阻擋 exit 2 |
| test_existing_skill_newly_over_threshold_blocked | 既有 skill 編輯後首次超標，不在 baseline | 阻擋 exit 2 |
| test_baseline_skill_unchanged_not_blocked | baseline 內 skill 長度不變 | 不阻擋 |
| test_baseline_skill_shorter_not_blocked | baseline 內 skill 縮短但仍超標 | 不阻擋 |
| test_baseline_skill_grows_longer_blocked | baseline 內 skill 變得更長 | 阻擋 exit 2，訊息含 baseline 記錄值 |
| test_baseline_missing_downgrades_to_warning | baseline 檔不存在 | 不阻擋，stderr 含降級警告 |
| test_baseline_malformed_downgrades_to_warning | baseline 檔非合法 JSON | 不阻擋，降級為 warning |
| test_under_threshold_not_blocked | description 未超過門檻 | 不阻擋 |
| test_non_skill_md_path_not_checked | 編輯目標非 SKILL.md | 不阻擋，不觸發執法邏輯 |
| test_multiedit_reconstruction_over_threshold_blocked | MultiEdit 多筆編輯疊加後超標 | 阻擋 exit 2 |
| test_session_start_scan_unaffected | 無 tool_name（SessionStart 形態）仍走既有掃描 | exit 0 |

策略：
- importlib 動態載入（檔名含 hyphen）
- 以真實 tmp_path 檔案模擬「編輯前磁碟內容」與 baseline 檔
- monkeypatch get_project_root 指向 tmp_path，隔離對本專案真實 baseline 的依賴
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


HOOK_PATH = Path(__file__).parent.parent / "skill-description-length-check-hook.py"


def _load_hook_module():
    spec = importlib.util.spec_from_file_location(
        "skill_description_length_check_hook", HOOK_PATH
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


def _make_skill_md(root: Path, skill_name: str, description: str) -> Path:
    """在 tmp_path 下建立 .claude/skills/<skill_name>/SKILL.md，回傳其路徑。"""
    skill_dir = root / ".claude" / "skills" / skill_name
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(
        f"---\nname: {skill_name}\ndescription: {description}\n---\n\n# {skill_name}\n",
        encoding="utf-8",
    )
    return skill_md


def _write_baseline(root: Path, skills: dict) -> Path:
    baseline_path = root / ".claude" / "hooks" / "skill-description-baseline.json"
    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    baseline_path.write_text(
        json.dumps({"generated_at": "2026-01-01T00:00:00", "threshold": 250, "skills": skills}),
        encoding="utf-8",
    )
    return baseline_path


@pytest.fixture(autouse=True)
def _patch_project_root(hook_mod, monkeypatch, tmp_path):
    """所有測試預設隔離對本專案真實 get_project_root() / baseline 檔的依賴。"""
    monkeypatch.setattr(hook_mod, "get_project_root", lambda: tmp_path)


def _over_threshold_description(extra_chars: int) -> str:
    """組出長度為 WARNING_THRESHOLD + extra_chars 的 description 字串。"""
    base = "測" * (250 + extra_chars)
    return base


# ---------------------------------------------------------------------------
# 新增違規（acceptance 1）：新建或首次超標的 skill 未列入 baseline，硬擋
# ---------------------------------------------------------------------------


class TestNewViolationBlocked:
    def test_new_skill_over_threshold_blocked(self, hook_mod, monkeypatch, tmp_path, capsys):
        """Write 建立全新 SKILL.md，description 超標且不在 baseline → 阻擋。

        baseline 檔存在（代表執法已上線、既有存量已入 baseline）但不含此
        新 skill，區別於「baseline 檔整個缺失」的降級情境（acceptance 3）。
        """
        _write_baseline(tmp_path, {"some-other-legacy-skill": 300})
        new_skill_dir = tmp_path / ".claude" / "skills" / "brand-new-skill"
        new_skill_md = new_skill_dir / "SKILL.md"
        description = _over_threshold_description(10)
        content = f"---\nname: brand-new-skill\ndescription: {description}\n---\n\n# brand-new-skill\n"

        payload = {
            "tool_name": "Write",
            "tool_input": {
                "file_path": str(new_skill_md),
                "content": content,
            },
        }
        rc = _run_main(hook_mod, monkeypatch, payload)
        err = capsys.readouterr().err

        assert rc == 2
        assert "BLOCKED" in err
        assert "brand-new-skill" in err
        assert str(250 + 10) in err

    def test_existing_skill_newly_over_threshold_blocked(
        self, hook_mod, monkeypatch, tmp_path, capsys
    ):
        """既有 skill 原本未超標，Edit 後首次超標且不在 baseline → 阻擋。"""
        _write_baseline(tmp_path, {"some-other-legacy-skill": 300})
        skill_md = _make_skill_md(tmp_path, "growing-skill", "簡短描述")

        new_description = _over_threshold_description(5)
        payload = {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": str(skill_md),
                "old_string": "description: 簡短描述",
                "new_string": f"description: {new_description}",
            },
        }
        rc = _run_main(hook_mod, monkeypatch, payload)
        err = capsys.readouterr().err

        assert rc == 2
        assert "growing-skill" in err
        assert "BLOCKED" in err

    def test_under_threshold_not_blocked(self, hook_mod, monkeypatch, tmp_path, capsys):
        """description 未超過門檻 → 不阻擋，無論 baseline 狀態。"""
        skill_md = _make_skill_md(tmp_path, "short-skill", "簡短描述")

        payload = {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": str(skill_md),
                "old_string": "簡短描述",
                "new_string": "簡短描述（微調但仍很短）",
            },
        }
        rc = _run_main(hook_mod, monkeypatch, payload)
        err = capsys.readouterr().err

        assert rc == 0
        assert "BLOCKED" not in err

    def test_non_skill_md_path_not_checked(self, hook_mod, monkeypatch, tmp_path, capsys):
        """編輯目標不是 SKILL.md → 不觸發執法邏輯，直接放行。"""
        other_file = tmp_path / ".claude" / "skills" / "some-skill" / "scripts" / "run.py"
        other_file.parent.mkdir(parents=True, exist_ok=True)
        other_file.write_text("print('hi')\n", encoding="utf-8")

        payload = {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": str(other_file),
                "old_string": "print('hi')",
                "new_string": "print('hello ' * 200)",
            },
        }
        rc = _run_main(hook_mod, monkeypatch, payload)
        err = capsys.readouterr().err

        assert rc == 0
        assert err == ""


# ---------------------------------------------------------------------------
# baseline 存量（acceptance 2）：既有超標不阻擋；惡化才阻擋
# ---------------------------------------------------------------------------


class TestBaselineExistingViolation:
    def test_baseline_skill_unchanged_not_blocked(self, hook_mod, monkeypatch, tmp_path, capsys):
        """baseline 內 skill 長度不變（仍超標但等於 baseline 記錄值）→ 不阻擋。"""
        description = _over_threshold_description(50)
        skill_md = _make_skill_md(tmp_path, "legacy-skill", description)
        _write_baseline(tmp_path, {"legacy-skill": len(description)})

        payload = {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": str(skill_md),
                "old_string": "# legacy-skill",
                "new_string": "# legacy-skill\n\n無關內容變更",
            },
        }
        rc = _run_main(hook_mod, monkeypatch, payload)
        err = capsys.readouterr().err

        assert rc == 0
        assert "BLOCKED" not in err

    def test_baseline_skill_shorter_not_blocked(self, hook_mod, monkeypatch, tmp_path, capsys):
        """baseline 內 skill 縮短（仍超標但小於 baseline 記錄值）→ 不阻擋。"""
        old_description = _over_threshold_description(100)
        skill_md = _make_skill_md(tmp_path, "shrinking-skill", old_description)
        _write_baseline(tmp_path, {"shrinking-skill": len(old_description)})

        new_description = _over_threshold_description(20)  # 仍超標但比 baseline 短
        payload = {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": str(skill_md),
                "old_string": f"description: {old_description}",
                "new_string": f"description: {new_description}",
            },
        }
        rc = _run_main(hook_mod, monkeypatch, payload)
        err = capsys.readouterr().err

        assert rc == 0
        assert "BLOCKED" not in err

    def test_baseline_skill_grows_longer_blocked(self, hook_mod, monkeypatch, tmp_path, capsys):
        """baseline 內 skill 變得更長（超過 baseline 記錄值）→ 阻擋，訊息含 baseline 記錄值。"""
        old_description = _over_threshold_description(30)
        skill_md = _make_skill_md(tmp_path, "worsening-skill", old_description)
        baseline_count = len(old_description)
        _write_baseline(tmp_path, {"worsening-skill": baseline_count})

        new_description = _over_threshold_description(60)  # 比 baseline 更長
        payload = {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": str(skill_md),
                "old_string": f"description: {old_description}",
                "new_string": f"description: {new_description}",
            },
        }
        rc = _run_main(hook_mod, monkeypatch, payload)
        err = capsys.readouterr().err

        assert rc == 2
        assert "BLOCKED" in err
        assert "worsening-skill" in err
        assert str(baseline_count) in err


# ---------------------------------------------------------------------------
# baseline 缺失（acceptance 3）：降級為 warning，不誤擋
# ---------------------------------------------------------------------------


class TestBaselineMissingDowngrade:
    def test_baseline_missing_downgrades_to_warning(
        self, hook_mod, monkeypatch, tmp_path, capsys
    ):
        """baseline 檔不存在 → 不阻擋，stderr 含降級警告。"""
        description = _over_threshold_description(10)
        skill_md = _make_skill_md(tmp_path, "no-baseline-skill", "簡短描述")

        payload = {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": str(skill_md),
                "old_string": "description: 簡短描述",
                "new_string": f"description: {description}",
            },
        }
        rc = _run_main(hook_mod, monkeypatch, payload)
        err = capsys.readouterr().err

        assert rc == 0
        assert "baseline-missing" in err
        assert "no-baseline-skill" in err

    def test_baseline_malformed_downgrades_to_warning(
        self, hook_mod, monkeypatch, tmp_path, capsys
    ):
        """baseline 檔存在但非合法 JSON → 視同缺失，降級為 warning，不阻擋。"""
        baseline_path = tmp_path / ".claude" / "hooks" / "skill-description-baseline.json"
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        baseline_path.write_text("這不是合法的 JSON {{{", encoding="utf-8")

        description = _over_threshold_description(10)
        skill_md = _make_skill_md(tmp_path, "malformed-baseline-skill", "簡短描述")

        payload = {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": str(skill_md),
                "old_string": "description: 簡短描述",
                "new_string": f"description: {description}",
            },
        }
        rc = _run_main(hook_mod, monkeypatch, payload)
        err = capsys.readouterr().err

        assert rc == 0
        assert "baseline-missing" in err


# ---------------------------------------------------------------------------
# MultiEdit 重建（回歸）與 SessionStart 掃描不受影響（回歸）
# ---------------------------------------------------------------------------


class TestReconstructionAndScanRegression:
    def test_multiedit_reconstruction_over_threshold_blocked(
        self, hook_mod, monkeypatch, tmp_path, capsys
    ):
        """MultiEdit 多筆編輯疊加後 description 超標 → 阻擋。"""
        _write_baseline(tmp_path, {"some-other-legacy-skill": 300})
        skill_md = _make_skill_md(tmp_path, "multiedit-skill", "AAA簡短描述")

        long_tail = "測" * 260
        payload = {
            "tool_name": "MultiEdit",
            "tool_input": {
                "file_path": str(skill_md),
                "edits": [
                    {
                        "old_string": "description: AAA簡短描述",
                        "new_string": "description: AAA簡短描述已修改",
                    },
                    {
                        "old_string": "description: AAA簡短描述已修改",
                        "new_string": f"description: {long_tail}",
                    },
                ],
            },
        }
        rc = _run_main(hook_mod, monkeypatch, payload)
        err = capsys.readouterr().err

        assert rc == 2
        assert "multiedit-skill" in err

    def test_session_start_scan_unaffected(self, hook_mod, monkeypatch, tmp_path, capsys):
        """無 tool_name（SessionStart 形態）仍走既有掃描邏輯，恆 exit 0。"""
        _make_skill_md(tmp_path, "scan-skill", _over_threshold_description(5))

        payload = {"hook_event_name": "SessionStart", "session_id": "abc", "source": "startup"}
        rc = _run_main(hook_mod, monkeypatch, payload)

        assert rc == 0
