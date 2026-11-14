"""ticket-reinstall-hook 只從主 checkout 重裝（3.3.0-W1-204.1.5.3）。

源碼與已安裝版本不同時：主 checkout 照常重裝；linked worktree 或判定失敗時
不重裝，改在 stdout（SessionStart 進入模型 context）提醒，寫明原因。
"""
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock

import pytest


def _load_hook_module():
    path = Path(__file__).resolve().parents[1] / "hooks" / "ticket-reinstall-hook.py"
    spec = importlib.util.spec_from_file_location("ticket_reinstall_hook_wt", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


hook = _load_hook_module()


@pytest.fixture
def stale_cli(tmp_path, monkeypatch):
    """布置「symlink 形態、源碼與已安裝版本不同」的情境，回傳 reinstall 替身。"""
    (tmp_path / ".claude" / "skills" / "ticket" / "ticket_system").mkdir(parents=True)
    monkeypatch.setattr(hook, "setup_hook_logging", lambda name: MagicMock())
    monkeypatch.setattr(hook, "get_project_root", lambda: tmp_path)
    monkeypatch.setattr(hook, "is_shimmed_cli", lambda cli, logger=None: False)
    monkeypatch.setattr(hook, "find_ticket_cli_path", lambda logger: Path("/bin/ticket"))
    monkeypatch.setattr(
        hook, "find_ticket_module_path", lambda binary, logger: Path("/installed")
    )
    monkeypatch.setattr(
        hook, "compute_file_hashes",
        lambda d: {"a.py": "src"} if d != Path("/installed") else {"a.py": "old"},
    )
    reinstall = MagicMock(return_value=True)
    monkeypatch.setattr(hook, "reinstall_ticket_cli", reinstall)
    return reinstall


def test_main_checkout_still_reinstalls(stale_cli, monkeypatch):
    # 正向對照：主 checkout 在源碼不同時照常重裝
    monkeypatch.setattr(hook, "reinstall_skip_reason", lambda root, logger=None: None)
    assert hook.main() == 0
    stale_cli.assert_called_once()


def test_linked_worktree_reminds_without_reinstall(stale_cli, monkeypatch, capsys):
    monkeypatch.setattr(
        hook, "reinstall_skip_reason",
        lambda root, logger=None: "/wt 是 linked worktree（主 checkout 為 /main）",
    )
    assert hook.main() == 0
    stale_cli.assert_not_called()
    out = capsys.readouterr().out
    assert "未自動重裝 ticket CLI" in out
    assert "linked worktree" in out
    assert ".claude/skills/ticket" in out


def test_detection_failure_reminds_without_reinstall(stale_cli, monkeypatch, capsys):
    monkeypatch.setattr(
        hook, "reinstall_skip_reason",
        lambda root, logger=None: "無法判定 /x 是否為主 checkout（git 執行失敗）",
    )
    assert hook.main() == 0
    stale_cli.assert_not_called()
    assert "無法判定" in capsys.readouterr().out


def test_identical_does_not_query_worktree(stale_cli, monkeypatch):
    # 源碼與已安裝版本相同時不判定來源、不重裝
    monkeypatch.setattr(hook, "compute_file_hashes", lambda d: {"a.py": "same"})
    called = []
    monkeypatch.setattr(
        hook, "reinstall_skip_reason",
        lambda root, logger=None: called.append(root) or "x",
    )
    assert hook.main() == 0
    stale_cli.assert_not_called()
    assert called == []
