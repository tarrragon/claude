"""_run_all_checks 逐支隔離例外（3.6.0-W1-289）。

單支 check 拋例外不得讓其他 check 的 deny 失效；例外轉為 warn finding，
stderr 與 logger 含 check 名稱。
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib import commit_content_guards as ccg  # noqa: E402
from lib.commit_content_guards import Finding, StagedFile  # noqa: E402

LOGGER = logging.getLogger("check-isolation-test")


def _check_boom(sf, logger):
    raise RuntimeError("injected-failure")


def _check_always_deny(sf, logger):
    return [Finding("deny", "stub-deny", "stub deny reason")]


def _check_quiet(sf, logger):
    return []


def _files():
    return [StagedFile("docs/x.txt", "", "a\n", "a\n")]


def _run(tmp_path):
    return ccg._run_all_checks(_files(), tmp_path, LOGGER)


def test_exception_in_one_check_keeps_other_deny_and_adds_warn(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(ccg, "_PER_FILE_CHECKS", [_check_boom, _check_always_deny])
    findings = _run(tmp_path)
    assert any(f.severity == "deny" and f.source == "stub-deny" for f in findings)
    warns = [f for f in findings if f.severity == "warn" and f.source == "_check_boom"]
    assert len(warns) == 1
    assert "injected-failure" in warns[0].message
    assert "_check_boom" in capsys.readouterr().err


def test_exception_logged_with_check_name(monkeypatch, tmp_path, caplog):
    monkeypatch.setattr(ccg, "_PER_FILE_CHECKS", [_check_boom])
    with caplog.at_level(logging.WARNING, logger=LOGGER.name):
        _run(tmp_path)
    assert any("_check_boom" in r.getMessage() for r in caplog.records)


def test_no_injection_has_no_isolation_warn(monkeypatch, tmp_path):
    monkeypatch.setattr(ccg, "_PER_FILE_CHECKS", [_check_quiet, _check_always_deny])
    findings = _run(tmp_path)
    assert any(f.severity == "deny" for f in findings)
    assert not [f for f in findings if f.source == "_check_boom"]
    assert not [f for f in findings if "injected-failure" in f.message]


def test_global_wrap_skill_yaml_exception_isolated(monkeypatch, tmp_path, capsys):
    def _boom(sf, logger, project_root):
        raise RuntimeError("wrap-failure")

    monkeypatch.setattr(ccg, "_PER_FILE_CHECKS", [_check_always_deny])
    monkeypatch.setattr(ccg, "_check_wrap_skill_yaml", _boom)
    findings = _run(tmp_path)
    assert any(f.severity == "deny" for f in findings)
    assert any(f.severity == "warn" and f.source == "_boom" for f in findings)
    assert "_boom" in capsys.readouterr().err
