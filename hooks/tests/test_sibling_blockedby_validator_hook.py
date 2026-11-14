"""
Sibling blockedBy Validator Hook 測試（W10-040 / ARCH-017 v1.1.0）

對應測試案例：
- A1-A12：4 條件純邏輯單元測試（每條件 2 違反 + 1 合法）
- B1-B2：行為分級整合測試（block / warn pass）
- C1-C2：邊界與容錯（無 parent_id skip / frontmatter fallback）
"""

import importlib.util
import sys
import textwrap
from pathlib import Path
from unittest.mock import MagicMock

import pytest


_HOOKS_DIR = Path(__file__).parent.parent
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))


@pytest.fixture
def hook_module():
    spec = importlib.util.spec_from_file_location(
        "sibling_blockedby_validator_hook",
        _HOOKS_DIR / "sibling-blockedby-validator-hook.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def logger():
    return MagicMock()


def _make(id_, type_="IMP", parent="P", blocked_by=None, status="pending"):
    return {
        "status": status,
        "id": id_,
        "type": type_,
        "parent_id": parent,
        "blockedBy": blocked_by or [],
    }


# ============================================================================
# Group A：4 條件純邏輯（A1-A12）
# ============================================================================

# 條件 1：單向

def test_a1_violation_bidirectional(hook_module):
    """A1: 雙向依賴 → 違反條件 1 BLOCK"""
    a = _make("A", blocked_by=["B"])
    b = _make("B", blocked_by=["A"])
    smap = {"A": a, "B": b}
    v = hook_module.check_condition_1_unidirectional(a, smap)
    assert v is not None
    assert v["condition"] == 1
    assert v["severity"] == "BLOCK"


def test_a2_violation_multi_sibling_dep(hook_module):
    """A2: 多兄弟依賴（>=2） → 違反條件 1 BLOCK"""
    b = _make("B", blocked_by=["A", "C"])
    smap = {"A": _make("A"), "B": b, "C": _make("C")}
    v = hook_module.check_condition_1_unidirectional(b, smap)
    assert v is not None
    assert v["condition"] == 1
    assert v["severity"] == "BLOCK"


def test_e1_multi_sibling_terminal_vs_nonterminal_differs(hook_module):
    """E1: 同一張多前驅票，前驅全終態放行、任一非終態 BLOCK，結果不同"""
    b = _make("B", blocked_by=["A", "C"])
    done = {"A": _make("A", status="completed"), "B": b,
            "C": _make("C", status="closed")}
    mixed = {"A": _make("A", status="completed"), "B": b,
             "C": _make("C", status="in_progress")}
    assert hook_module.check_condition_1_unidirectional(b, done) is None
    v = hook_module.check_condition_1_unidirectional(b, mixed)
    assert v is not None and v["severity"] == "BLOCK"


def test_e2_bidirectional_blocks_even_when_predecessors_terminal(hook_module):
    """E2: 雙向依賴即使前驅終態仍 BLOCK"""
    a = _make("A", blocked_by=["B"], status="completed")
    b = _make("B", blocked_by=["A"], status="completed")
    v = hook_module.check_condition_1_unidirectional(a, {"A": a, "B": b})
    assert v is not None and v["severity"] == "BLOCK"


def test_a3_legal_single_predecessor(hook_module):
    """A3: 單一前驅 → 通過條件 1"""
    b = _make("B", blocked_by=["A"])
    smap = {"A": _make("A"), "B": b}
    assert hook_module.check_condition_1_unidirectional(b, smap) is None


# 條件 2：無環

def test_a4_violation_three_cycle(hook_module):
    """A4: A→B→C→A → 違反條件 2 BLOCK"""
    a = _make("A", blocked_by=["C"])
    b = _make("B", blocked_by=["A"])
    c = _make("C", blocked_by=["B"])
    smap = {"A": a, "B": b, "C": c}
    v = hook_module.check_condition_2_acyclic(a, smap)
    assert v is not None
    assert v["condition"] == 2
    assert v["severity"] == "BLOCK"


def test_a5_violation_self_dependency(hook_module):
    """A5: 自依賴 → 違反條件 2 BLOCK"""
    a = _make("A", blocked_by=["A"])
    smap = {"A": a}
    v = hook_module.check_condition_2_acyclic(a, smap)
    assert v is not None
    assert v["condition"] == 2


def test_a6_legal_linear_chain(hook_module):
    """A6: A→B→C 線性鏈 → 通過條件 2"""
    a = _make("A")
    b = _make("B", blocked_by=["A"])
    c = _make("C", blocked_by=["B"])
    smap = {"A": a, "B": b, "C": c}
    assert hook_module.check_condition_2_acyclic(c, smap) is None


def test_a6b_cycle_among_predecessors_not_containing_target_passes(hook_module):
    """3.3.0-W1-213.10：前驅 A、B 互為前驅成環，目標 T 不在環上 → 條件 2 不擋。"""
    a = _make("A", blocked_by=["B"], status="completed")
    b = _make("B", blocked_by=["A"], status="completed")
    t = _make("T", blocked_by=["A"])
    smap = {"A": a, "B": b, "T": t}
    assert hook_module.check_condition_2_acyclic(t, smap) is None


def test_a6c_target_on_cycle_through_predecessors_still_blocks(hook_module):
    """正向對照：同形態但 B 再以 T 為前驅，T 在環上 → 仍 BLOCK。"""
    a = _make("A", blocked_by=["B"], status="completed")
    b = _make("B", blocked_by=["A", "T"], status="completed")
    t = _make("T", blocked_by=["A"])
    smap = {"A": a, "B": b, "T": t}
    v = hook_module.check_condition_2_acyclic(t, smap)
    assert v is not None and v["condition"] == 2 and v["severity"] == "BLOCK"


def test_c7_run_check_predecessor_cycle_without_target_passes(
        hook_module, project_with_tickets, logger, capsys):
    """3.3.0-W1-213.10 整合：真實票檔，前驅間有環且皆終態、目標不在環上 → rc=0。"""
    root, td = project_with_tickets
    _write_ticket(td, "T-A", type="ANA", blocked_by=["T-B"], status="completed")
    _write_ticket(td, "T-B", type="ANA", blocked_by=["T-A"], status="completed")
    _write_ticket(td, "T-T", type="IMP", blocked_by=["T-A"], status="pending")
    assert hook_module.run_check(root, "T-T", ack="已評估", logger=logger) == 0
    assert "條件 2" not in capsys.readouterr().err


# 條件 3：規格→實作時序

def test_a7_violation_imp_to_imp(hook_module):
    """A7: IMP→IMP → 違反條件 3 WARN"""
    a = _make("IMP_A", type_="IMP")
    b = _make("IMP_B", type_="IMP", blocked_by=["IMP_A"])
    smap = {"IMP_A": a, "IMP_B": b}
    v = hook_module.check_condition_3_spec_to_impl(b, smap)
    assert v is not None
    assert v["condition"] == 3
    assert v["severity"] == "WARN"


def test_a8_violation_doc_to_ana_inverted(hook_module):
    """A8: ANA 依賴 IMP（時序錯反） → 違反條件 3 WARN"""
    imp = _make("IMP_A", type_="IMP")
    ana = _make("ANA_B", type_="ANA", blocked_by=["IMP_A"])
    smap = {"IMP_A": imp, "ANA_B": ana}
    v = hook_module.check_condition_3_spec_to_impl(ana, smap)
    assert v is not None
    assert v["condition"] == 3
    assert v["severity"] == "WARN"


def test_a9_legal_ana_to_imp(hook_module):
    """A9: ANA→IMP → 通過條件 3"""
    ana = _make("ANA_A", type_="ANA")
    imp = _make("IMP_B", type_="IMP", blocked_by=["ANA_A"])
    smap = {"ANA_A": ana, "IMP_B": imp}
    assert hook_module.check_condition_3_spec_to_impl(imp, smap) is None


# 條件 4：不可深度化

def test_a10_violation_no_acknowledge(hook_module):
    """A10: 串行兄弟 + 無 ack → 違反條件 4 WARN"""
    target = _make("B", blocked_by=["A"])
    v = hook_module.check_condition_4_no_deepening(target, ack=None)
    assert v is not None
    assert v["condition"] == 4
    assert v["severity"] == "WARN"


def test_a11_legal_with_acknowledge(hook_module):
    """A11: 串行兄弟 + 有 ack → 通過條件 4"""
    target = _make("B", blocked_by=["A"])
    assert hook_module.check_condition_4_no_deepening(target, ack="rationale") is None


def test_a12_violation_empty_acknowledge(hook_module):
    """A12: 空字串 ack → 違反條件 4 WARN"""
    target = _make("B", blocked_by=["A"])
    v = hook_module.check_condition_4_no_deepening(target, ack="   ")
    assert v is not None
    assert v["condition"] == 4
    assert v["severity"] == "WARN"


# ============================================================================
# Group B：行為分級整合（B1, B2）
# ============================================================================

def _write_ticket(dir_path: Path, ticket_id: str, **kwargs):
    fm = {
        "id": ticket_id,
        "type": kwargs.get("type", "IMP"),
        "parent_id": kwargs.get("parent_id", "P"),
        "blockedBy": kwargs.get("blocked_by", kwargs.get("blockedBy", [])),
    }
    if "status" in kwargs:  # 不給則 frontmatter 不含 status 欄位（缺欄位情境）
        fm["status"] = kwargs["status"]
    lines = ["---"]
    for k, v in fm.items():
        if isinstance(v, list):
            if v:
                lines.append(f"{k}:")
                for x in v:
                    lines.append(f"  - {x}")
            else:
                lines.append(f"{k}: []")
        elif v is None:
            lines.append(f"{k}: null")
        else:
            lines.append(f"{k}: {v}")
    lines.append("---")
    lines.append("")
    lines.append(f"# {ticket_id}")
    md = dir_path / f"{ticket_id}.md"
    md.write_text("\n".join(lines), encoding="utf-8")
    return md


@pytest.fixture
def project_with_tickets(tmp_path):
    tickets_dir = tmp_path / "docs" / "work-logs" / "v0" / "tickets"
    tickets_dir.mkdir(parents=True)
    return tmp_path, tickets_dir


def test_b1_block_on_bidirectional(hook_module, project_with_tickets, logger, capsys):
    """B1: 雙向依賴 claim → exit 2，stderr 含條件 1"""
    root, td = project_with_tickets
    _write_ticket(td, "T-A", blocked_by=["T-B"])
    _write_ticket(td, "T-B", blocked_by=["T-A"])
    code = hook_module.run_check(root, "T-A", ack=None, logger=logger)
    captured = capsys.readouterr()
    assert code == 2
    assert "條件 1" in captured.err


def test_b2_warn_pass_imp_to_imp(hook_module, project_with_tickets, logger, capsys):
    """B2: 純 IMP→IMP 兄弟，無 ack → exit 0，stderr 含警告"""
    root, td = project_with_tickets
    _write_ticket(td, "T-A", type="IMP")
    _write_ticket(td, "T-B", type="IMP", blocked_by=["T-A"])
    code = hook_module.run_check(root, "T-B", ack=None, logger=logger)
    captured = capsys.readouterr()
    assert code == 0
    assert "WARN" in captured.err
    # 條件 3 或 4 至少其一警告
    assert ("條件 3" in captured.err) or ("條件 4" in captured.err)


# ============================================================================
# Group C：邊界與容錯（C1, C2）
# ============================================================================

def test_c1_skip_when_no_parent(hook_module, project_with_tickets, logger, capsys):
    """C1: parent_id=null → skip 通過，無違規輸出"""
    root, td = project_with_tickets
    _write_ticket(td, "T-X", parent_id=None, blocked_by=[])
    code = hook_module.run_check(root, "T-X", ack=None, logger=logger)
    captured = capsys.readouterr()
    assert code == 0
    assert "違反" not in captured.err


def _multi_predecessor(td, status_a, status_c):
    """T-B 以兩張兄弟票為前驅（條件 1 的多前驅形態）；前驅 status 為 None 時不寫該欄位。"""
    for tid, status in (("T-A", status_a), ("T-C", status_c)):
        kwargs = {"type": "ANA"}
        if status is not None:
            kwargs["status"] = status
        _write_ticket(td, tid, **kwargs)
    _write_ticket(td, "T-B", type="IMP", blocked_by=["T-A", "T-C"], status="pending")


def test_c3_run_check_terminal_predecessors_pass_vs_nonterminal_block(
        hook_module, project_with_tickets, logger, capsys):
    """C3（E1）：真實票檔走 run_check，前驅皆終態 rc=0，任一非終態 rc=2，同批對照結果不同。"""
    root, td = project_with_tickets
    _multi_predecessor(td, "completed", "closed")
    done = hook_module.run_check(root, "T-B", ack="已評估", logger=logger)
    _multi_predecessor(td, "completed", "in_progress")
    mixed = hook_module.run_check(root, "T-B", ack="已評估", logger=logger)
    assert (done, mixed) == (0, 2)
    assert "條件 1" in capsys.readouterr().err


def test_c4_predecessor_missing_status_blocks(hook_module, project_with_tickets, logger, capsys):
    """C4：前驅缺 status 欄位時不視為終態，多前驅形態判 BLOCK。"""
    root, td = project_with_tickets
    _multi_predecessor(td, "completed", None)
    assert "status" not in (td / "T-C.md").read_text(encoding="utf-8")
    assert hook_module.run_check(root, "T-B", ack="已評估", logger=logger) == 2
    assert "條件 1" in capsys.readouterr().err


def _skip_messages(logger):
    return [str(c.args[0]) for c in logger.debug.call_args_list if c.args]


def test_c5_skip_no_parent_even_with_violating_blockedby(hook_module, project_with_tickets, logger):
    """C5：無 parent_id 時略過；blockedBy 構成雙向依賴（有 parent 時會 BLOCK）仍 rc=0，且走無 parent 分支。"""
    root, td = project_with_tickets
    _write_ticket(td, "T-X", parent_id=None, blocked_by=["T-Y"])
    _write_ticket(td, "T-Y", parent_id=None, blocked_by=["T-X"])
    assert hook_module.run_check(root, "T-X", ack=None, logger=logger) == 0
    messages = _skip_messages(logger)
    assert any("無 parent_id" in m for m in messages)
    assert not any("無 blockedBy" in m for m in messages)


def test_c6_skip_parent_without_blockedby(hook_module, project_with_tickets, logger):
    """C6：有 parent 而無 blockedBy 時略過，走無 blockedBy 分支（與 C5 分辨是哪個條件生效）。"""
    root, td = project_with_tickets
    _write_ticket(td, "T-Z", parent_id="P", blocked_by=[])
    assert hook_module.run_check(root, "T-Z", ack=None, logger=logger) == 0
    messages = _skip_messages(logger)
    assert any("無 blockedBy" in m for m in messages)
    assert not any("無 parent_id" in m for m in messages)


def test_c2_fallback_on_corrupt_yaml(hook_module, project_with_tickets, logger, capsys):
    """C2: YAML 損毀 → fallback warn-only，exit 0"""
    root, td = project_with_tickets
    bad = td / "T-BAD.md"
    bad.write_text("---\nthis is : : not yaml : :\n  - bad\n---\n", encoding="utf-8")
    code = hook_module.run_check(root, "T-BAD", ack=None, logger=logger)
    captured = capsys.readouterr()
    assert code == 0
    assert "fallback warn-only" in captured.err


# ============================================================================
# 額外：parse_bash_command 工具測試
# ============================================================================

def test_parse_bash_command_claim(hook_module):
    p = hook_module.parse_bash_command("ticket track claim 0.18.0-W10-040")
    assert p == {"action": "claim", "ticket_id": "0.18.0-W10-040", "acknowledge": None}


def test_parse_bash_command_with_ack(hook_module):
    p = hook_module.parse_bash_command(
        'ticket track complete 0.18.0-W10-040 --acknowledge "deepening N/A"'
    )
    assert p["action"] == "complete"
    assert p["acknowledge"] == "deepening N/A"


def test_parse_bash_command_unrelated(hook_module):
    assert hook_module.parse_bash_command("git status") is None


# ============================================================================
# D：main() 的 project_root 解析不受 cwd 影響（0.2.1-W3-1199）
# ============================================================================
#
# 修復前：project_root = Path(os.environ.get("CLAUDE_PROJECT_DIR", ".")).
# resolve()，未設環境變數時退回 cwd，使讀取 docs/work-logs/ 靜默失敗。本組
# 測試不檢查「錯置檔案是否消失」（本 hook 是讀取路徑，失效無痕跡可觀察），
# 而是直接驗證 main() 呼叫 get_project_root() 取得的值有被傳給 run_check()，
# 不論呼叫端 cwd 為何。


def test_d1_main_uses_get_project_root_result(hook_module, monkeypatch, tmp_path):
    """main() 應把 get_project_root() 的回傳值傳給 run_check()，而非自行
    以 CLAUDE_PROJECT_DIR-or-cwd 重新解析。"""
    sentinel_root = tmp_path / "sentinel-repo"
    sentinel_root.mkdir()

    captured = {}

    def fake_run_check(project_root, ticket_id, ack, logger):
        captured["project_root"] = project_root
        return 0

    monkeypatch.setattr(hook_module, "get_project_root", lambda: sentinel_root)
    monkeypatch.setattr(hook_module, "run_check", fake_run_check)
    monkeypatch.setattr(
        hook_module, "read_json_from_stdin",
        lambda logger: {
            "tool_name": "Bash",
            "tool_input": {"command": "ticket track claim 0.1.1-W1-001"},
        },
    )

    exit_code = hook_module.main()

    assert exit_code == 0
    assert captured["project_root"] == sentinel_root


def test_d2_main_independent_of_caller_cwd(hook_module, monkeypatch, tmp_path):
    """模擬呼叫端 cwd 落在非專案根目錄（如 .claude/hooks/），
    get_project_root() 的回傳值仍應原樣傳遞，不被呼叫端 cwd 覆蓋或污染。"""
    real_root = tmp_path / "real-repo"
    real_root.mkdir()
    nested_cwd = real_root / ".claude" / "hooks"
    nested_cwd.mkdir(parents=True)
    monkeypatch.chdir(nested_cwd)
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)

    captured = {}

    def fake_run_check(project_root, ticket_id, ack, logger):
        captured["project_root"] = project_root
        return 0

    monkeypatch.setattr(hook_module, "get_project_root", lambda: real_root)
    monkeypatch.setattr(hook_module, "run_check", fake_run_check)
    monkeypatch.setattr(
        hook_module, "read_json_from_stdin",
        lambda logger: {
            "tool_name": "Bash",
            "tool_input": {"command": "ticket track claim 0.1.1-W1-001"},
        },
    )

    hook_module.main()

    assert captured["project_root"] == real_root
    assert captured["project_root"] != nested_cwd


# E2：確認方式不得使條件 1 BLOCK 放行（正向對照：已知應被擋的輸入）
def test_e2_block_not_bypassed_by_acknowledge(hook_module, project_with_tickets, logger, capsys):
    root, td = project_with_tickets
    _write_ticket(td, "T-A")
    _write_ticket(td, "T-B")
    _write_ticket(td, "T-C", blocked_by=["T-A", "T-B"])
    cmd = 'ticket track claim T-C --acknowledge "理由"'
    parsed = hook_module.parse_bash_command(cmd)
    assert parsed["acknowledge"] == "理由"
    code = hook_module.run_check(root, "T-C", parsed["acknowledge"], logger)
    assert code == 2
    assert "條件 1" in capsys.readouterr().err


# E1：條件 3（純 IMP→IMP）的 WARN 必須隨 --acknowledge 調整
# 同一批 payload 分別帶與不帶 ack，斷言輸出不同，且帶 ack 時不再建議已附的旗標。
def _imp_to_imp_project(td):
    _write_ticket(td, "T-A", type="IMP")
    _write_ticket(td, "T-B", type="IMP", blocked_by=["T-A"])


def test_e1_condition3_differs_with_and_without_ack(hook_module, project_with_tickets, logger, capsys):
    root, td = project_with_tickets
    _imp_to_imp_project(td)
    hook_module.run_check(root, "T-B", None, logger)
    err_without = capsys.readouterr().err
    hook_module.run_check(root, "T-B", "確認非規格實作關係", logger)
    err_with = capsys.readouterr().err
    assert "條件 3" in err_without
    assert "條件 3" not in err_with
    assert err_without != err_with


def test_e1_ack_present_never_suggests_ack_again(hook_module, project_with_tickets, logger, capsys):
    root, td = project_with_tickets
    _imp_to_imp_project(td)
    code = hook_module.run_check(root, "T-B", "確認非規格實作關係", logger)
    err = capsys.readouterr().err
    assert code == 0
    assert "--acknowledge" not in err


def test_e1_inverted_timing_warn_not_offset_by_ack(hook_module, project_with_tickets, logger, capsys):
    """IMP→spec 時序錯反是不同判定，ack 不抵消（對照：抵消僅限 IMP→IMP）。"""
    root, td = project_with_tickets
    _write_ticket(td, "T-A", type="IMP")
    _write_ticket(td, "T-B", type="ANA", blocked_by=["T-A"])
    hook_module.run_check(root, "T-B", "理由", logger)
    assert "條件 3" in capsys.readouterr().err


# E2：條件 1 雙向依賴帶 ack 仍 BLOCK（正向對照）
def test_e2_bidirectional_still_blocks_with_ack(hook_module, project_with_tickets, logger, capsys):
    root, td = project_with_tickets
    _write_ticket(td, "T-A", blocked_by=["T-B"])
    _write_ticket(td, "T-B", blocked_by=["T-A"])
    code = hook_module.run_check(root, "T-A", "理由", logger)
    assert code == 2
    assert "條件 1" in capsys.readouterr().err


# ============================================================================
# 命令作用範圍：作用在其他 repo 時不讀 session repo 的同 ID 票
# ============================================================================


def _git_repo(path):
    import subprocess

    path.mkdir()
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    return path.resolve()


def _run_main_scope(hook_module, monkeypatch, session, command):
    import io
    import json

    calls = []
    monkeypatch.setattr(hook_module, "run_check", lambda root, tid, *a, **k: calls.append(tid) or 2)
    payload = {"tool_name": "Bash", "cwd": str(session), "tool_input": {"command": command}}
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    return hook_module.main(), calls


def test_scope_direct_claim_checked(hook_module, monkeypatch, tmp_path):
    """正向對照：直接 claim 會讀票判定。"""
    session = _git_repo(tmp_path / "s")
    rc, calls = _run_main_scope(hook_module, monkeypatch, session, "ticket track claim 0.0.0-W1-001")
    assert calls == ["0.0.0-W1-001"] and rc == 2


def test_scope_other_repo_skipped(hook_module, monkeypatch, tmp_path):
    """子 shell cd 到其他 repo：不讀 session repo 的同 ID 票，放行。"""
    session = _git_repo(tmp_path / "s")
    other = _git_repo(tmp_path / "o")
    rc, calls = _run_main_scope(
        hook_module, monkeypatch, session, f"(cd {other} && ticket track claim 0.0.0-W1-001)"
    )
    assert calls == [] and rc == 0


def test_scope_unknown_dir_keeps_previous_behavior(hook_module, monkeypatch, tmp_path):
    """目錄無法靜態解析：沿用修改前的判定（仍讀票）。"""
    session = _git_repo(tmp_path / "s")
    rc, calls = _run_main_scope(
        hook_module, monkeypatch, session, 'cd "$X" && ticket track claim 0.0.0-W1-001'
    )
    assert calls == ["0.0.0-W1-001"]


# ============================================================================
# 共用狀態根：linked worktree 內讀主 repo 票面（204.1.2 O1）
# ============================================================================


@pytest.fixture
def linked_worktree(tmp_path, monkeypatch):
    """tmp 主 repo + linked worktree；關閉 HOOK_TEST_ISOLATION。回 (main, wt)。"""
    import subprocess

    monkeypatch.delenv("HOOK_TEST_ISOLATION", raising=False)
    main_repo = _git_repo(tmp_path / "main")
    git = ["git", "-C", str(main_repo), "-c", "user.name=t", "-c", "user.email=t@t"]
    subprocess.run(git + ["commit", "-q", "--allow-empty", "-m", "init"], check=True)
    wt = tmp_path / "wt"
    subprocess.run(git + ["worktree", "add", "-q", "-b", "feat/x", str(wt)], check=True)
    return main_repo, wt.resolve()


def _capture_root(hook_module, monkeypatch, cwd, command="ticket track claim 0.0.0-W1-001"):
    import io
    import json

    monkeypatch.chdir(cwd)
    captured = []
    monkeypatch.setattr(hook_module, "run_check", lambda root, *a, **k: captured.append(root) or 0)
    monkeypatch.setattr(hook_module, "get_project_root", lambda: Path(cwd).resolve())
    payload = {"tool_name": "Bash", "cwd": str(cwd), "tool_input": {"command": command}}
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    hook_module.main()
    return captured


def test_shared_root_in_linked_worktree_reads_main_repo(hook_module, monkeypatch, linked_worktree):
    main_repo, wt = linked_worktree
    assert _capture_root(hook_module, monkeypatch, wt) == [main_repo]


def test_shared_root_in_main_repo_unchanged(hook_module, monkeypatch, linked_worktree):
    main_repo, _ = linked_worktree
    assert _capture_root(hook_module, monkeypatch, main_repo) == [main_repo]


def test_shared_root_identity_old_behavior_gets_wt_root(hook_module, monkeypatch, linked_worktree):
    """E1 對照：get_shared_state_root 換成恆等函式（舊碼語意）時收到 WT 根。"""
    _, wt = linked_worktree
    monkeypatch.setattr(
        hook_module, "get_shared_state_root", lambda default_root=None: default_root, raising=False
    )
    assert _capture_root(hook_module, monkeypatch, wt) == [wt]


def test_shared_root_scope_other_skips_run_check(hook_module, monkeypatch, linked_worktree, tmp_path):
    other = _git_repo(tmp_path / "o")
    _, wt = linked_worktree
    cmd = f"(cd {other} && ticket track claim 0.0.0-W1-001)"
    assert _capture_root(hook_module, monkeypatch, wt, cmd) == []
