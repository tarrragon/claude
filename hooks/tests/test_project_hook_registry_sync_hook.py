"""project-hook-registry-sync hook 測試（3.3.0-W1-036.2）。

依專案清冊重建 settings.local.json 的 hooks 區段。清冊外條目的處置依用戶裁定
（2026-11-12）：只移除可判定為錯誤者（幽靈、重複註冊框架 hook），其餘保留並示警。
本測試以三種情況做正向對照：清冊內保留、兩類被移除且列出、其他清冊外保留且示警。
"""

import importlib.util
import json
import logging
from pathlib import Path

import pytest

_HOOK_PATH = Path(__file__).resolve().parent.parent / "project-hook-registry-sync-hook.py"
_spec = importlib.util.spec_from_file_location("project_hook_registry_sync", _HOOK_PATH)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)

LOG = logging.getLogger("test-project-hook-registry-sync")
P = "$CLAUDE_PROJECT_DIR"


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _manifest(root: Path, body: str) -> None:
    _write(root, ".claude/project-integration/hook-registry.yaml", "version: 1\nhooks:\n" + body)


def _local(root: Path) -> dict:
    return json.loads((root / ".claude/settings.local.json").read_text(encoding="utf-8"))


def _local_commands(root: Path) -> list:
    return [h["command"] for _e, _m, h in hook.iter_hook_entries(_local(root))]


@pytest.fixture
def project(tmp_path):
    _write(tmp_path, ".claude/project-integration/hooks/api-check.py", "# project\n")
    _write(tmp_path, ".claude/project-integration/hooks/notify.sh", "#!/bin/sh\n")
    _write(tmp_path, ".claude/hooks/fw-hook.py", "# framework\n")
    _write(tmp_path, ".claude/hooks/user-own.py", "# user wrote, not in manifest\n")
    _write(tmp_path, ".claude/settings.json", json.dumps({"hooks": {"PreToolUse": [
        {"matcher": "Bash", "hooks": [{"type": "command", "command": "uv run --quiet {}/.claude/hooks/fw-hook.py".format(P)}]}
    ]}}))
    return tmp_path


class TestBuildCommand:
    def test_python_script_uses_uv_run(self):
        assert hook.build_command(".claude/x/a.py") == "uv run --quiet {}/.claude/x/a.py".format(P)

    def test_other_script_is_direct_path(self):
        assert hook.build_command(".claude/x/a.sh") == "{}/.claude/x/a.sh".format(P)

    def test_leading_dot_slash_removed_but_dot_claude_kept(self):
        assert hook.build_command("./.claude/x/a.py").endswith("/.claude/x/a.py")


class TestManifestParsing:
    @pytest.mark.parametrize("body", [
        "version: 2\nhooks: {}\n",
        "hooks: {}\n",
        "version: 1\nhooks:\n  a.py:\n    event: Stop\n",
        "version: 1\nhooks:\n  a.py:\n    script: x.py\n    event: Stop\n    timeout: '10'\n",
        "version: [\n",
    ])
    def test_invalid_manifest_raises(self, body):
        with pytest.raises(hook.ManifestError):
            hook.parse_manifest(body)


class TestSync:
    def test_three_way_control(self, project):
        _manifest(project, (
            "  api-check.py:\n    script: .claude/project-integration/hooks/api-check.py\n"
            "    event: PreToolUse\n    matcher: Edit\n    timeout: 10\n"
        ))
        ghost = "uv run --quiet {}/.claude/hooks/gone.py".format(P)
        dup = "{}/.claude/hooks/fw-hook.py".format(P)  # 字串不同但同一框架腳本
        own = "uv run --quiet {}/.claude/hooks/user-own.py".format(P)
        _write(project, ".claude/settings.local.json", json.dumps({
            "outputStyle": "x",
            "permissions": {"allow": ["Bash(ls)"]},
            "hooks": {"Stop": [{"hooks": [
                {"type": "command", "command": ghost},
                {"type": "command", "command": dup},
                {"type": "command", "command": own},
            ]}]},
        }))

        report = hook.sync(project, LOG)

        cmds = _local_commands(project)
        # 清冊內：產生並保留
        assert "uv run --quiet {}/.claude/project-integration/hooks/api-check.py".format(P) in cmds
        # 兩類被移除且列出
        assert ghost not in cmds and dup not in cmds
        assert "[指向不存在的檔案] " + ghost in report
        assert "[重複註冊框架 hook] " + dup in report
        # 其他清冊外：保留且示警
        assert own in cmds
        assert "不在專案清冊" in report and own in report
        # 非 hooks 鍵不動
        local = _local(project)
        assert local["outputStyle"] == "x" and local["permissions"] == {"allow": ["Bash(ls)"]}
        # timeout 照清冊（秒）
        entry = local["hooks"]["PreToolUse"][0]
        assert entry["matcher"] == "Edit" and entry["hooks"][0]["timeout"] == 10

    def test_manifest_edit_then_delete_tracks_manifest(self, project):
        _manifest(project, "  notify.sh:\n    script: .claude/project-integration/hooks/notify.sh\n    event: Stop\n")
        hook.sync(project, LOG)
        notify = "{}/.claude/project-integration/hooks/notify.sh".format(P)
        assert _local_commands(project) == [notify]

        # 修改：改事件
        _manifest(project, "  notify.sh:\n    script: .claude/project-integration/hooks/notify.sh\n    event: SubagentStop\n")
        hook.sync(project, LOG)
        assert list(_local(project)["hooks"]) == ["SubagentStop"]

        # 刪除：先前由清冊產生的條目被移除並列出
        _manifest(project, "")
        _write(project, ".claude/project-integration/hook-registry.yaml", "version: 1\nhooks: {}\n")
        report = hook.sync(project, LOG)
        assert "hooks" not in _local(project)
        assert "[已從清冊刪除] " + notify in report

    def test_silent_when_consistent(self, project):
        _manifest(project, "  notify.sh:\n    script: .claude/project-integration/hooks/notify.sh\n    event: Stop\n")
        hook.sync(project, LOG)
        assert hook.sync(project, LOG) == ""

    def test_no_manifest_no_local_hooks_is_noop(self, project):
        assert hook.sync(project, LOG) == ""
        assert not (project / ".claude/settings.local.json").exists()

    def test_invalid_manifest_reports_and_does_not_write(self, project):
        _write(project, ".claude/settings.local.json", json.dumps({"outputStyle": "x"}))
        _write(project, ".claude/project-integration/hook-registry.yaml", "version: 9\nhooks: {}\n")
        report = hook.sync(project, LOG)
        assert "清冊無法使用" in report
        assert _local(project) == {"outputStyle": "x"}
