"""bash_tool_response helper 與三支改接 hook 的測試（真實 payload 形狀為主）。

真實 PostToolUse 的 Bash tool_response 只有 stdout、stderr、interrupted、
isImage、noOutputExpected，沒有 exit_code。斷言一律比對結構化結果
（函式回傳值、audit 檔內容、hook 輸出 JSON），不以輸出是否含某段文字當唯一依據。
"""

import importlib.util
import io
import json
import logging
import sys
from pathlib import Path

import pytest

_CLAUDE = Path(__file__).resolve().parents[2]
if str(_CLAUDE) not in sys.path:
    sys.path.insert(0, str(_CLAUDE))
if str(_CLAUDE / "hooks") not in sys.path:
    sys.path.insert(0, str(_CLAUDE / "hooks"))

from lib.bash_tool_response import is_bash_success  # noqa: E402

_LOGGER = logging.getLogger("test_bash_tool_response")


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _real(stdout="", stderr="", interrupted=False):
    """平台真實形狀：無 exit_code。"""
    return {
        "stdout": stdout,
        "stderr": stderr,
        "interrupted": interrupted,
        "isImage": False,
        "noOutputExpected": False,
    }


# ---------------------------------------------------------------------------
# helper 自身
# ---------------------------------------------------------------------------

_OK = ("[OK]",)


@pytest.mark.parametrize(
    "resp, expected",
    [
        (_real("[OK] 完成"), True),  # 真實形狀成功
        (_real("[OK] 完成", interrupted=True), False),  # 被中斷
        (_real("nothing"), False),  # 無成功回音（被管線遮蔽的失敗）
        ({"exit_code": 0, "stdout": "[OK] x"}, True),  # 相容 payload
        ({"exit_code": 75, "stdout": "[OK] x"}, True),  # 相容 payload 的 75
        ({"exit_code": 1, "stdout": "[OK] x"}, False),  # 相容 payload 失敗
        ("not a dict", False),
        ({"stdout": None}, False),
    ],
)
def test_is_bash_success_shapes(resp, expected):
    assert is_bash_success(resp, _OK) is expected


def test_is_bash_success_ignore_case():
    assert is_bash_success(_real("COMPLETED"), ("completed",), ignore_case=True) is True


# ---------------------------------------------------------------------------
# 分層判定（command / state_verifier）
# ---------------------------------------------------------------------------

_UNMASKED_CMD = "ticket track finish T > /tmp/log 2>&1"
_MASKED_CMD = "ticket track finish T > /tmp/log 2>&1; echo rc=$?"
_NO_MARKER = _real("rc=0\n")  # 285 實例：標記被吸走


def test_layered_e1_same_payload_unmasked_vs_masked_differ():
    """E1：同一無標記 payload，未遮蔽判成功，遮蔽（無驗證器）退回標記判失敗。"""
    unmasked = is_bash_success(_NO_MARKER, _OK, command=_UNMASKED_CMD)
    masked = is_bash_success(_NO_MARKER, _OK, command=_MASKED_CMD)
    assert (unmasked, masked) == (True, False)


def test_layered_masked_uses_verifier_over_marker():
    assert is_bash_success(_NO_MARKER, _OK, command=_MASKED_CMD, state_verifier=lambda: True) is True
    # 驗證器否決優先於 stdout 內的標記
    assert is_bash_success(_real("[OK] x"), _OK, command=_MASKED_CMD, state_verifier=lambda: False) is False


def test_layered_unmasked_ignores_verifier():
    def boom():
        raise AssertionError("未遮蔽時不應呼叫驗證器")

    assert is_bash_success(_NO_MARKER, _OK, command=_UNMASKED_CMD, state_verifier=boom) is True


def test_layered_verifier_exception_falls_back_to_marker():
    def boom():
        raise OSError("讀票失敗")

    assert is_bash_success(_real("[OK] x"), _OK, command=_MASKED_CMD, state_verifier=boom) is True
    assert is_bash_success(_NO_MARKER, _OK, command=_MASKED_CMD, state_verifier=boom) is False


def test_layered_unparseable_falls_back_to_marker():
    bad = "ticket track finish 'abc"
    assert is_bash_success(_real("[OK] x"), _OK, command=bad, state_verifier=lambda: False) is True
    assert is_bash_success(_NO_MARKER, _OK, command=bad) is False


def test_layered_interrupted_and_bad_exit_code_still_fail():
    assert is_bash_success(_real("", interrupted=True), _OK, command=_UNMASKED_CMD) is False
    assert is_bash_success({"exit_code": 1, "stdout": ""}, _OK, command=_UNMASKED_CMD) is False


def test_no_new_args_behaviour_unchanged_for_masked_shapes():
    """不傳 command 時，無標記一律判失敗（與舊版相同），即使命令實際未遮蔽。"""
    assert is_bash_success(_NO_MARKER, _OK) is False
    assert is_bash_success(_real("COMPLETED"), ("completed",)) is False


# ---------------------------------------------------------------------------
# cli-error-feedback：成功命令 stdout 引述錯誤字樣不得誤報
# ---------------------------------------------------------------------------

_CEF = _load(_CLAUDE / "skills" / "ticket" / "hooks" / "cli-error-feedback-hook.py", "cef279")


def _cef_input(stdout, stderr, command="ticket track append-log 0.1.0-W1-001 --section S x"):
    return {
        "tool_input": {"command": command},
        "tool_response": _real(stdout, stderr),
    }


def test_cef_success_quoting_error_text_is_not_reported():
    stdout = "[OK] 0.1.0-W1-001 已追加日誌到 'S'\nerror: unrecognized arguments: --x"
    assert _CEF.check_skill_cli_error(_cef_input(stdout, ""), _LOGGER) is None


def test_cef_masked_failure_is_reported():
    """`cmd | tail` 遮蔽結束碼：stderr 有錯誤、stdout 無成功回音，仍須回饋。"""
    masked = "ticket track append-log 0.1.0-W1-001 --section S x 2>&1 | tail -5"
    result = _CEF.check_skill_cli_error(
        _cef_input("", "error: unrecognized arguments: --x", masked), _LOGGER
    )
    assert result is not None
    assert "參數不存在" in result


def test_cef_unmasked_with_error_text_is_not_reported():
    """286.3 第 1 層：未遮蔽收到 PostToolUse 即成功，stdout 引述錯誤字樣不誤報。"""
    result = _CEF.check_skill_cli_error(
        _cef_input("", "error: unrecognized arguments: --x"), _LOGGER
    )
    assert result is None


# ---------------------------------------------------------------------------
# parallel-claim-audit：讀 tool_response，失敗的 claim 不入 audit
# ---------------------------------------------------------------------------

_PCA = _load(_CLAUDE / "hooks" / "parallel-claim-audit-hook.py", "pca279")
_TID = "0.19.0-W3-048"


@pytest.fixture
def project(tmp_path):
    tickets = tmp_path / "docs" / "work-logs" / "v0" / "v0.19" / "v0.19.0" / "tickets"
    tickets.mkdir(parents=True)
    (tickets / (_TID + ".md")).write_text(
        "---\nid: {}\nstatus: in_progress\nstarted_at: '2026-06-02T16:00:00'\n"
        "who:\n  current: pm\n---\n\n# t\n".format(_TID),
        encoding="utf-8",
    )
    return tmp_path


def _pca_run(monkeypatch, root, response):
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": "ticket track claim " + _TID},
        "tool_response": response,
    }
    monkeypatch.setattr(_PCA, "get_project_root", lambda: root)
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    assert _PCA.main() == 0
    audit = root / ".claude" / "hook-logs" / "parallel-claim-audit.log"
    if not audit.exists():
        return []
    return [json.loads(x) for x in audit.read_text(encoding="utf-8").splitlines() if x.strip()]


def test_pca_real_shape_success_is_audited(monkeypatch, project):
    entries = _pca_run(monkeypatch, project, _real("[OK] 已接手 " + _TID))
    assert [e["ticket_id"] for e in entries] == [_TID]


def test_pca_real_shape_failure_is_not_audited(monkeypatch, project):
    entries = _pca_run(monkeypatch, project, _real("", "Error: ticket not found"))
    assert entries == []


def test_pca_interrupted_is_not_audited(monkeypatch, project):
    entries = _pca_run(monkeypatch, project, _real("[OK] 已接手 " + _TID, interrupted=True))
    assert entries == []


# ---------------------------------------------------------------------------
# needs-context-listener：被中斷不通知；fail-open
# ---------------------------------------------------------------------------

_NCL = _load(
    _CLAUDE / "skills" / "ticket" / "hooks" / "needs-context-listener-hook.py", "ncl279"
)


def _ncl_run(monkeypatch, capsys, response):
    payload = {
        "tool_input": {
            "command": 'ticket track append-log 0.1.0-W1-001 --section NeedsContext "x"'
        },
        "tool_response": response,
    }
    monkeypatch.setattr(_NCL, "read_json_from_stdin", lambda _l: payload)
    rc = _NCL.main_logic()
    return rc, capsys.readouterr().out


def test_ncl_real_shape_success_emits_context(monkeypatch, capsys):
    rc, out = _ncl_run(monkeypatch, capsys, _real("[OK] 0.1.0-W1-001 已追加日誌到 'NeedsContext'"))
    assert rc == 0
    assert "0.1.0-W1-001" in json.loads(out)["hookSpecificOutput"]["additionalContext"]


def test_ncl_interrupted_emits_nothing(monkeypatch, capsys):
    rc, out = _ncl_run(
        monkeypatch, capsys, _real("[OK] 0.1.0-W1-001 已追加日誌到 'NeedsContext'", interrupted=True)
    )
    assert rc == 0
    assert out.strip() == ""


# ---------------------------------------------------------------------------
# fail-open：畸形 payload 三支 hook 皆不拋例外、不阻擋
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad", ["str response", None, 42, []])
def test_fail_open_on_malformed_tool_response(monkeypatch, capsys, bad):
    inp = {"tool_input": {"command": "ticket track append-log 0.1.0-W1-001 x"}, "tool_response": bad}
    _CEF.check_skill_cli_error(inp, _LOGGER)  # 不得拋例外
    assert _PCA.is_claim_successful(bad) in (True, False)
    rc, _ = _ncl_run(monkeypatch, capsys, bad)
    assert rc == 0
