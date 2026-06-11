"""
test_checklist_enforcement_consistency
======================================

建票路徑 checklist 執法一致性回歸測試（1.0.0-W1-027）。

背景：W11-003.5 將 5W1H 必填升級為阻擋，但驗證只綁在 create 命令層；
batch-create（bulk_create.py）與 generate（ticket_generator.py）兩條路徑
直接 save_ticket，繞過驗證，可建出殘缺票且無 hook 安全網。

本 ticket 將 `validate_create_checklist` 下沉至 lib/ticket_builder.py，
三路徑共用：
- create：缺失 + 未 --force 時阻擋（既有行為不變）
- batch-create / generate：warning 級不阻擋（補側門缺口）

驗證點：
1. 驗證函式已下沉至 builder，且 create 保留向後相容別名
2. batch-create 缺必填欄位時 result.warned 列全，ticket 仍建立
3. generate 缺必填欄位時 GeneratedTicket.missing_fields 列全，tickets 仍生成
4. Never break userspace：warning 不阻擋既有流程

Source: ticket 1.0.0-W1-027（parent ANA 1.0.0-W1-024 對抗性複審挑戰 4）
"""
import pytest

from ticket_system.constants import DEFAULT_UNDEFINED_VALUE
from ticket_system.lib.ticket_builder import validate_create_checklist
from ticket_system.commands import bulk_create as bulk_create_cmd
from ticket_system.lib import ticket_generator as gen_lib
from ticket_system.lib.plan_parser import PlanParseResult, PlanTask


# ---------------------------------------------------------------------------
# 步驟 1：驗證函式下沉 + 向後相容別名
# ---------------------------------------------------------------------------


def test_validate_create_checklist_lists_all_missing_fields():
    """全缺 config（IMP，非子任務）應一次列全所有必填缺失欄位。"""
    config = {
        "ticket_type": "IMP",
        "who": "pending",
        "what": "",
        "why": DEFAULT_UNDEFINED_VALUE,
        "when": DEFAULT_UNDEFINED_VALUE,
        "how_strategy": DEFAULT_UNDEFINED_VALUE,
        "where_files": [],
        "acceptance": None,
    }

    missing = validate_create_checklist(config, "IMP")

    # 8 類必填欄位全部應被列出（列全，非分批）
    for field in (
        "where.files",
        "acceptance",
        "decision_tree_path",
        "when",
        "who",
        "what",
        "why",
        "how_strategy",
    ):
        assert field in missing, f"缺失欄位 {field} 未被列出: {missing}"


def test_validate_create_checklist_passes_when_complete():
    """完整 config 應回傳空清單。"""
    config = {
        "ticket_type": "IMP",
        "who": "thyme-python-developer",
        "what": "實作功能",
        "why": "需求依據",
        "when": "觸發時機",
        "how_strategy": "實作策略",
        "where_files": ["src/x.py"],
        "acceptance": ["條件 A"],
        "decision_tree_path": {
            "entry_point": "第五層",
            "final_decision": "採方案 A",
            "rationale": "規則 5",
        },
    }

    assert validate_create_checklist(config, "IMP") == []


def test_doc_type_exempt_from_why_and_decision_tree():
    """DOC 類型豁免 why 與 decision_tree_path。"""
    config = {
        "ticket_type": "DOC",
        "who": "thyme-documentation-integrator",
        "what": "撰寫文件",
        "why": DEFAULT_UNDEFINED_VALUE,  # DOC 豁免
        "when": "觸發時機",
        "how_strategy": "策略",
        "where_files": ["docs/x.md"],
        "acceptance": ["條件 A"],
    }

    missing = validate_create_checklist(config, "DOC")

    assert "why" not in missing
    assert "decision_tree_path" not in missing


def test_create_keeps_backward_compat_alias():
    """create._validate_create_checklist 應為下沉函式的別名（向後相容）。"""
    from ticket_system.commands.create import _validate_create_checklist

    assert _validate_create_checklist is validate_create_checklist


# ---------------------------------------------------------------------------
# 步驟 2：batch-create 接線（warning 級，不阻擋）
# ---------------------------------------------------------------------------


def test_bulk_create_warns_missing_fields(monkeypatch):
    """batch-create 缺必填欄位時應將缺失列入 result.warned。"""
    # 隔離磁碟：固定序號，dry_run 不寫檔
    monkeypatch.setattr(bulk_create_cmd, "get_next_seq", lambda v, w: 1)

    result = bulk_create_cmd._create_batch_tickets(
        template_defaults={"type": "IMP"},
        targets=["目標 A"],
        version="9.9.9",
        wave=1,
        dry_run=True,
    )

    assert len(result.warned) == 1, f"應有 1 筆警告: {result.warned}"
    ticket_id, warning_msg = result.warned[0]
    # 預設模板缺：where.files / acceptance / decision_tree_path / when / who
    for field in ("where.files", "acceptance", "when", "who"):
        assert field in warning_msg, f"警告未列出 {field}: {warning_msg}"


def test_bulk_create_does_not_block_on_missing(monkeypatch):
    """batch-create 缺欄位時 ticket 仍建立（Never break userspace）。"""
    monkeypatch.setattr(bulk_create_cmd, "get_next_seq", lambda v, w: 1)

    result = bulk_create_cmd._create_batch_tickets(
        template_defaults={"type": "IMP"},
        targets=["目標 A", "目標 B"],
        version="9.9.9",
        wave=1,
        dry_run=True,
    )

    # 缺欄位不阻擋建立
    assert len(result.created) == 2
    assert result.failed == []


# ---------------------------------------------------------------------------
# 步驟 3：generate 接線（warning 級，不阻擋）
# ---------------------------------------------------------------------------


def _make_parse_result(files=None):
    """建立含單一缺欄位任務的 PlanParseResult。"""
    return PlanParseResult(
        plan_title="測試 Plan",
        plan_description="Plan 描述",
        tasks=[
            PlanTask(
                title="建立 X 模組",
                description="X 模組說明",
                action="建立",
                target="X 模組",
                files=files if files is not None else [],
                task_type="IMP",
                complexity=5,
                order=1,
            )
        ],
        total_tasks=1,
        success=True,
    )


def test_generate_marks_missing_fields(monkeypatch):
    """generate 缺必填欄位時應寫入 GeneratedTicket.missing_fields。"""
    monkeypatch.setattr(gen_lib, "get_next_seq", lambda v, w: 1)

    gen_result = gen_lib.generate(
        _make_parse_result(files=[]),
        version="9.9.9",
        base_wave=1,
        dry_run=True,
    )

    assert gen_result.success
    assert len(gen_result.tickets) == 1
    missing = gen_result.tickets[0].missing_fields
    # generate 預設缺：who / when / how_strategy / acceptance /
    # decision_tree_path / where.files（files=[]）
    for field in ("who", "when", "how_strategy", "acceptance", "where.files"):
        assert field in missing, f"missing_fields 未列出 {field}: {missing}"


def test_generate_does_not_block_on_missing(monkeypatch):
    """generate 缺欄位時 tickets 仍生成（Never break userspace）。"""
    monkeypatch.setattr(gen_lib, "get_next_seq", lambda v, w: 1)

    gen_result = gen_lib.generate(
        _make_parse_result(files=[]),
        version="9.9.9",
        base_wave=1,
        dry_run=True,
    )

    assert gen_result.success
    assert gen_result.total == 1


# ---------------------------------------------------------------------------
# 1.0.0-W1-043：空字串 why / how_strategy 漏判修補
# ---------------------------------------------------------------------------


def test_empty_string_why_and_how_strategy_flagged():
    """空字串 why / how_strategy 應視為缺失（W1-043，補既有 == 待定義 漏判）。

    既有判定僅檢查是否等於 DEFAULT_UNDEFINED_VALUE，空字串漏網；
    bulk_create 預設 why="" / how_strategy="" 因此不觸發。本修補後
    falsy（含 ""）亦列為缺失。
    """
    config = {
        "ticket_type": "IMP",
        "who": "thyme-python-developer",
        "what": "實作功能",
        "why": "",            # 空字串（非「待定義」）
        "when": "觸發時機",
        "how_strategy": "",   # 空字串
        "where_files": ["src/x.py"],
        "acceptance": ["條件 A"],
        "decision_tree_path": {
            "entry_point": "第五層",
            "final_decision": "採方案 A",
            "rationale": "規則 5",
        },
    }

    missing = validate_create_checklist(config, "IMP")

    assert "why" in missing
    assert "how_strategy" in missing


def test_doc_type_still_exempt_from_empty_why():
    """DOC 類型對空字串 why 仍豁免（一致性：DOC 不檢查 why）。"""
    config = {
        "ticket_type": "DOC",
        "who": "thyme-documentation-integrator",
        "what": "撰寫文件",
        "why": "",
        "when": "觸發時機",
        "how_strategy": "策略",
        "where_files": ["docs/x.md"],
        "acceptance": ["條件 A"],
    }

    assert "why" not in validate_create_checklist(config, "DOC")


def test_create_block_path_consistent_for_empty_string():
    """create 阻擋路徑（共用同函式）對空字串判定一致。

    create 透過 _validate_create_checklist 別名呼叫同一函式，故空字串
    why/how_strategy 在 create 端同樣被列入缺失（阻擋來源一致）。
    """
    from ticket_system.commands.create import _validate_create_checklist

    config = {
        "ticket_type": "IMP",
        "who": "agent",
        "what": "x",
        "why": "",
        "when": "t",
        "how_strategy": "",
        "where_files": ["src/x.py"],
        "acceptance": ["a"],
        "decision_tree_path": {
            "entry_point": "e",
            "final_decision": "d",
            "rationale": "r",
        },
    }

    missing = _validate_create_checklist(config, "IMP")
    assert "why" in missing
    assert "how_strategy" in missing


def test_bulk_create_warning_now_covers_why_and_how_strategy(monkeypatch):
    """batch-create 預設模板（why=''/how_strategy=''）warning 現涵蓋此兩欄。"""
    monkeypatch.setattr(bulk_create_cmd, "get_next_seq", lambda v, w: 1)

    result = bulk_create_cmd._create_batch_tickets(
        template_defaults={"type": "IMP"},  # 預設 why=''/how_strategy=''
        targets=["目標 A"],
        version="9.9.9",
        wave=1,
        dry_run=True,
    )

    assert len(result.warned) == 1
    _, warning_msg = result.warned[0]
    assert "why" in warning_msg
    assert "how_strategy" in warning_msg
