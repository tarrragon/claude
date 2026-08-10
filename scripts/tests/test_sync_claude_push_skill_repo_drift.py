"""sync-claude-push.py 的 skill 庫漂移檢查（0.2.1-W3-351 建立，0.2.1-W3-353 重構）。

沿革：0.3.5-W1-001 建立的版本字串比對於 0.2.1-W3-131 的 schema 變更後失準，
0.2.1-W3-134 移除該實作並改印靜態提示，該提示引用的子命令不存在。
0.2.1-W3-351 恢復自動檢查，但只重用了中段分類器，取檔與 repo 來源仍自行重寫，
因此硬編 URL 繞過 `SKILL_SYNC_REPO` 覆寫（ARCH-BAL-016），且 try 只包住取檔
使分類階段的例外逃逸（IMP-BAL-008）。

0.2.1-W3-353 改為呼叫 skill-sync 的 public `sync_status_report`，整段流程只剩
一個外部呼叫。本檔因此只測「呈現層」與「降級行為」兩件事——repo 解析、取檔、
分類的正確性由 skill-sync 自己的測試套件負責，在此重測等於再造一次雙份斷言。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parent.parent / "sync-claude-push.py"
_spec = importlib.util.spec_from_file_location("sync_claude_push", _SCRIPT)
assert _spec and _spec.loader
sync_mod = importlib.util.module_from_spec(_spec)
sys.modules["sync_claude_push"] = sync_mod
_spec.loader.exec_module(sync_mod)  # type: ignore[union-attr]

from skill_sync.cli import DivergedSkill, SyncStatus  # noqa: E402


def _status(**overrides) -> SyncStatus:
    defaults = dict(
        repo_url="https://github.com/owner/repo.git",
        remote_count=1,
        up_to_date=[],
        diverged=[],
        overridden=[],
        skipped_no_hash=[],
        skipped_remote_missing=[],
    )
    defaults.update(overrides)
    return SyncStatus(**defaults)


def _diverged(name: str, local: str, remote: str) -> DivergedSkill:
    return DivergedSkill(
        name=name,
        local=local,
        remote=remote,
        pull_command=f"skill-sync pull {name}",
        push_command=f"skill-sync push {name}",
    )


def _stub_report(monkeypatch, result):
    """替換 skill-sync 的 public 入口；result 可為 SyncStatus 或要拋出的例外。"""
    import skill_sync.cli as cli_module

    def _fake(skills_dir, repo_url=None):
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(cli_module, "sync_status_report", _fake)


# --- 單一外部呼叫（重構後的核心契約） ---------------------------------------


def test_source_holds_no_second_repo_url_or_fetch(monkeypatch):
    """本檔不得再持有 repo URL 或 raw URL 拼裝——那正是兩端比對不同遠端的來源。"""
    source = _SCRIPT.read_text(encoding="utf-8")

    assert "raw.githubusercontent.com" not in source
    assert "claude-skills.git" not in source
    assert not hasattr(sync_mod, "SKILL_REPO_URL")
    assert not hasattr(sync_mod, "fetch_remote_skill_manifest")
    assert not hasattr(sync_mod, "_load_skill_sync_classifier")


def test_drift_report_delegates_repo_resolution_to_skill_sync(tmp_path, monkeypatch):
    """設了 SKILL_SYNC_REPO 時，本檔的報告必須跟著 skill-sync 走同一個 repo。"""
    monkeypatch.setenv("SKILL_SYNC_REPO", "https://github.com/example/other.git")
    import skill_sync.cli as cli_module

    monkeypatch.setattr(cli_module, "fetch_remote_manifest", lambda url: {})
    seen = {}
    real = cli_module.sync_status_report

    def _spy(skills_dir, repo_url=None):
        status = real(skills_dir, repo_url)
        seen["repo_url"] = status.repo_url
        return status

    monkeypatch.setattr(cli_module, "sync_status_report", _spy)

    sync_mod.report_skill_repo_drift(tmp_path / ".claude")

    assert seen["repo_url"] == "https://github.com/example/other.git"


# --- 降級行為（IMP-BAL-008 防線） -------------------------------------------


@pytest.mark.parametrize(
    "failure",
    [
        OSError("network unreachable"),
        ValueError("versions.json is list, expected an object"),
        AttributeError("classifier renamed"),
    ],
    ids=["network", "malformed-manifest", "broken-contract"],
)
def test_drift_report_degrades_instead_of_raising(tmp_path, monkeypatch, failure):
    """三類失敗都必須降級為字串。分類階段的例外曾因 try 範圍過窄而逃逸。"""
    _stub_report(monkeypatch, failure)

    report = sync_mod.report_skill_repo_drift(tmp_path / ".claude")

    assert report.startswith("[skill 庫檢查] 略過：")
    assert type(failure).__name__ in report


def test_report_prefixes_remote_url_on_all_success_paths(tmp_path, monkeypatch):
    """成功路徑（含空手/空清單）首行都須標示比對遠端，URL 來自 status.repo_url。"""
    _stub_report(monkeypatch, _status(repo_url="https://github.com/owner/repo.git"))

    report = sync_mod.report_skill_repo_drift(tmp_path / ".claude")

    assert report.startswith(
        "[skill 庫檢查] 比對遠端：https://github.com/owner/repo.git"
    )


def test_report_remote_line_no_local_skills(tmp_path, monkeypatch):
    _stub_report(
        monkeypatch,
        _status(repo_url="https://github.com/owner/repo.git"),
    )

    report = sync_mod.report_skill_repo_drift(tmp_path / ".claude")

    assert report.startswith(
        "[skill 庫檢查] 比對遠端：https://github.com/owner/repo.git"
    )
    assert "本地無已安裝 skill" in report


def test_report_remote_line_empty_remote_manifest(tmp_path, monkeypatch):
    _stub_report(
        monkeypatch,
        _status(
            repo_url="https://github.com/owner/repo.git",
            remote_count=0,
            skipped_no_hash=["a"],
        ),
    )

    report = sync_mod.report_skill_repo_drift(tmp_path / ".claude")

    assert report.startswith(
        "[skill 庫檢查] 比對遠端：https://github.com/owner/repo.git"
    )
    assert "未進行比對" in report


def test_diverged_annotation_distinguishes_skill_repo_from_sync_target(
    tmp_path, monkeypatch
):
    """分歧提示須說明本檢查對象是 skill 發佈庫，與 sync-push 目標 repo 不同。"""
    _stub_report(
        monkeypatch, _status(diverged=[_diverged("demo", "1.0.0", "0.9.0")])
    )

    report = sync_mod.report_skill_repo_drift(tmp_path / ".claude")

    assert "此為 skill 發佈庫，與 sync-push 目標 repo 不同" in report


def test_degraded_message_distinguishes_failure_kinds(tmp_path, monkeypatch):
    """網路不通與契約破損不得呈現為同一行，否則讀者無從判斷該重試還是修安裝。"""
    _stub_report(monkeypatch, OSError("unreachable"))
    network = sync_mod.report_skill_repo_drift(tmp_path / ".claude")

    _stub_report(monkeypatch, ImportError("no module named skill_sync"))
    contract = sync_mod.report_skill_repo_drift(tmp_path / ".claude")

    assert network != contract
    assert "OSError" in network
    assert "ImportError" in contract


# --- 呈現層 -----------------------------------------------------------------


def test_report_counts_each_category(tmp_path, monkeypatch):
    _stub_report(
        monkeypatch,
        _status(
            remote_count=3,
            up_to_date=["a", "b"],
            diverged=[_diverged("c", "1.0.0", "0.9.0")],
            overridden=["d"],
            skipped_no_hash=["e", "f", "g"],
        ),
    )

    report = sync_mod.report_skill_repo_drift(tmp_path / ".claude")

    assert "一致 2" in report
    assert "分歧 1" in report
    assert "本地客製 1" in report
    assert "遠端有記錄無雜湊 3" in report
    assert "遠端無記錄 0" in report


def test_report_distinguishes_remote_missing_from_no_hash(tmp_path, monkeypatch):
    """兩種盲區成因不同，計數與名單都要能分辨（0.2.1-W3-369）。"""
    _stub_report(
        monkeypatch,
        _status(
            skipped_no_hash=["e"],
            skipped_remote_missing=["x", "y"],
        ),
    )

    report = sync_mod.report_skill_repo_drift(tmp_path / ".claude")

    assert "遠端有記錄無雜湊 1" in report
    assert "遠端無記錄 2" in report
    assert "e" in report
    assert "x" in report and "y" in report


def test_report_annotates_same_version_divergence(tmp_path, monkeypatch):
    """版本號相同而內容不同是最常見形態；不註明成因會被讀者當誤報略過。"""
    _stub_report(
        monkeypatch, _status(diverged=[_diverged("demo", "1.0.0", "1.0.0")])
    )

    report = sync_mod.report_skill_repo_drift(tmp_path / ".claude")

    assert "版本相同，內容不同" in report


def test_report_omits_annotation_when_versions_differ(tmp_path, monkeypatch):
    _stub_report(
        monkeypatch, _status(diverged=[_diverged("demo", "2.0.0", "1.0.0")])
    )

    report = sync_mod.report_skill_repo_drift(tmp_path / ".claude")

    assert "版本相同" not in report


def test_report_uses_commands_supplied_by_skill_sync(tmp_path, monkeypatch):
    """指引命令取自 skill-sync 提供的欄位，本檔不再自備字串（會與 CLI 脫節）。"""
    _stub_report(
        monkeypatch, _status(diverged=[_diverged("demo", "1.0.0", "0.9.0")])
    )

    report = sync_mod.report_skill_repo_drift(tmp_path / ".claude")

    assert "skill-sync pull demo" in report
    assert "skill-sync push demo" in report


def test_report_truncates_long_diverged_list(tmp_path, monkeypatch):
    count = sync_mod.SKILL_DRIFT_PREVIEW_LIMIT + 3
    _stub_report(
        monkeypatch,
        _status(
            diverged=[_diverged(f"s{i:02d}", "1.0.0", "0.9.0") for i in range(count)]
        ),
    )

    report = sync_mod.report_skill_repo_drift(tmp_path / ".claude")

    listed = [line for line in report.splitlines() if line.strip().startswith("- s")]
    assert len(listed) == sync_mod.SKILL_DRIFT_PREVIEW_LIMIT
    assert "另有 3 個" in report


def test_report_flags_empty_remote_manifest(tmp_path, monkeypatch):
    """遠端可達但無資料時，全數落入 skipped 會讀起來像通過；必須明說未比對。"""
    _stub_report(monkeypatch, _status(remote_count=0, skipped_no_hash=["a", "b"]))

    report = sync_mod.report_skill_repo_drift(tmp_path / ".claude")

    assert "未進行比對" in report


def test_report_handles_no_local_skills(tmp_path, monkeypatch):
    _stub_report(monkeypatch, _status())

    report = sync_mod.report_skill_repo_drift(tmp_path / ".claude")

    assert "本地無已安裝 skill" in report


# --- 既有本地版本摘要功能不受影響（自 W3-134 測試檔移入） --------------------


def test_extract_skill_versions_unaffected(tmp_path):
    """本函式讀本地 SKILL.md，從不讀 remote versions.json，與漂移檢查是獨立路徑。"""
    skills_dir = tmp_path / "skills"
    skill_dir = skills_dir / "demo-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: demo-skill\n---\n\n**Version**: 1.2.3\n", encoding="utf-8"
    )

    assert sync_mod.extract_skill_versions(skills_dir) == {"demo-skill": "1.2.3"}


def test_format_skill_version_diff_unaffected():
    diff = sync_mod.format_skill_version_diff(
        {"demo-skill": "1.0.0"}, {"demo-skill": "1.1.0", "new-skill": "0.1.0"}
    )

    assert diff is not None
    assert "demo-skill 1.0.0 -> 1.1.0" in diff
    assert "new-skill (0.1.0)" in diff
