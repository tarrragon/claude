"""framework-issue rebuild-owned 測試：送出前揭露、dry-run 不送出、整份覆寫登記檔。

gh 以注入的假 runner 取代；登記檔路徑以 monkeypatch 指到 tmp_path。
"""

import json
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import gh_common  # noqa: E402
import owned_issues_registry  # noqa: E402
import rebuild_owned  # noqa: E402


class FakeGh:
    def __init__(self, candidates=(), first_lines=None, fail=False):
        self.candidates = list(candidates)
        self.first_lines = first_lines or {}
        self.fail = fail
        self.calls = []

    def __call__(self, args):
        self.calls.append(args)
        if self.fail:
            raise rebuild_owned.RebuildError("network down")
        if args[0] == "search":
            return json.dumps([{"number": n} for n in self.candidates])
        if args[0] == "api":
            number = int(args[2].split("/issues/")[1].split("/")[0])
            return "\n".join(self.first_lines.get(number, []))
        raise AssertionError(f"unexpected gh call: {args}")


@pytest.fixture
def registry_file(tmp_path, monkeypatch):
    path = tmp_path / ".claude" / "state" / "framework-issue-owned.json"
    monkeypatch.setattr(owned_issues_registry, "registry_path", lambda project_root=None: path)
    monkeypatch.setattr(gh_common, "check_gh_available", lambda: True)
    monkeypatch.setattr(gh_common, "check_gh_authenticated", lambda: True)
    return path


def test_dry_run_sends_nothing_and_writes_nothing(registry_file, capsys):
    gh = FakeGh(candidates=[1])
    rc = rebuild_owned.main(["--owner-prefix", "my-proj", "--dry-run"], gh=gh)
    out = capsys.readouterr().out
    assert rc == 0
    assert gh.calls == []
    assert not registry_file.exists()
    assert '"owner my-proj"' in out


def test_rebuild_keeps_only_issues_with_matching_owner(registry_file, capsys):
    gh = FakeGh(
        candidates=[81, 82],
        first_lines={
            81: ["<!-- section: 當前結論 owner: my-proj-99 -->", "plain"],
            82: ["<!-- section: 當前結論 owner: other-proj-1 -->"],
        },
    )
    rc = rebuild_owned.main(["--owner-prefix", "my-proj"], gh=gh)
    out = capsys.readouterr().out
    assert rc == 0
    data = json.loads(registry_file.read_text(encoding="utf-8"))
    assert [(e["number"], e["owner"]) for e in data["issues"]] == [(81, "my-proj-99")]
    assert out.index("將送到 GitHub") < out.index("已寫入")
    assert "#81（my-proj-99）" in out


def test_no_candidates_writes_empty_registry(registry_file):
    """查無時寫入空清單：讀取端據此確認本專案無擁有項目，之後不再發 gh 命令。"""
    rc = rebuild_owned.main(["--owner-prefix", "my-proj"], gh=FakeGh())
    assert rc == 0
    assert owned_issues_registry.owned_issue_numbers() == []


def test_rebuild_replaces_stale_entries(registry_file):
    owned_issues_registry.write_registry([{"number": 5, "owner": "my-proj-1", "updated_at": "t"}])
    gh = FakeGh(candidates=[81], first_lines={81: ["<!-- section: x owner: my-proj-2 -->"]})
    rebuild_owned.main(["--owner-prefix", "my-proj"], gh=gh)
    assert owned_issues_registry.owned_issue_numbers() == [81]


def test_gh_failure_leaves_registry_untouched(registry_file):
    rc = rebuild_owned.main(["--owner-prefix", "my-proj"], gh=FakeGh(fail=True))
    assert rc == gh_common.EXIT_DEGRADED
    assert not registry_file.exists()


def test_default_prefix_is_project_dir_name(monkeypatch, tmp_path):
    root = tmp_path / "my_proj"
    monkeypatch.setattr(owned_issues_registry, "get_shared_state_root", lambda default_root=None: root)
    assert rebuild_owned.default_prefix() == "my-proj"
