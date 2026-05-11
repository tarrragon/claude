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


def _make(id_, type_="IMP", parent="P", blocked_by=None):
    return {
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
