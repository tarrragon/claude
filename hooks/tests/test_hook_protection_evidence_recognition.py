"""防護類 hook 票的證據辨識放寬：已存在的證據寫法、三種標記、例外退回。

驗證：
1. 正向對照（E2）：票面沒有失敗語意、也沒有觸發條件時仍判缺；acceptance
   也沒有字面時阻擋 complete
2. 已存在證據的寫法可被辨識：
   - 失敗語意宣告只寫在 acceptance
   - 失敗語意以「放行／阻擋」加同一行「觸發條件：」表達
   - 日誌行沒附 hook-logs/ 路徑，但該行或其區塊標頭含本票 hook 名
3. 來源追不到的日誌行不算：無 hook 名、其他 hook 的名稱
4. 標記：證據不適用、延後取證（票號須存在且未完成）可抵實地觸發／liveness；
   失敗語意不接受標記；待主線程補證不抵任何類別
5. 放寬辨識拋例外時退回原有判定

fixture 皆為合成票面，函式級，無共用狀態。
"""

import logging
import sys
from pathlib import Path

import pytest

_hooks_dir = Path(__file__).parent.parent
if str(_hooks_dir) not in sys.path:
    sys.path.insert(0, str(_hooks_dir))

import acceptance_checkers.hook_protection_acceptance_checker as mod  # noqa: E402
from acceptance_checkers.hook_protection_acceptance_checker import (  # noqa: E402
    check_hook_protection_acceptance,
    missing_evidence_categories,
)

TRIGGER = "本 session 實地觸發確認"
LIVENESS = "liveness 驗證方式"
FAILURE = "失敗語意（fail-open/fail-closed）"
HOOK = ".claude/hooks/demo-guard-hook.py"
NAMES = ("demo-guard-hook", "demo-guard")
OPEN_TICKET = "9.9.9" + "-W1-" + "7"

_TABLE = (
    "| 產生路徑 | 是否覆蓋 | 未覆蓋原因 |\n|---|---|---|\n| 經工具寫入 | 是 | — |\n"
)


def _body(solution="", test_results=""):
    return (
        "# Execution Log\n\n## Solution\n\n" + solution + "\n\n---\n\n"
        "## Test Results\n\n" + test_results + "\n\n---\n\n## NeedsContext\n"
    )


def _fm(acceptance):
    return {
        "id": "9.9.9-W1-1",
        "type": "IMP",
        "where": {"files": [HOOK]},
        "acceptance": acceptance,
        "how": {"task_type": "Implementation", "strategy": _TABLE},
    }


@pytest.fixture
def logger():
    log = logging.getLogger("test-evidence-recognition")
    log.handlers = []
    log.records = []

    class _H(logging.Handler):
        def emit(self, record):
            log.records.append(record)

    log.addHandler(_H(level=logging.DEBUG))
    log.setLevel(logging.DEBUG)
    log.propagate = False
    return log


def _transitions(log):
    return [r for r in log.records if r.getMessage().startswith("[evidence-transition]")]


# ---------- 1. 正向對照 ----------

def test_no_failure_semantics_anywhere_still_missing():
    body = _body(solution="修改判定函式", test_results="12 passed")
    assert FAILURE in missing_evidence_categories(body, "", NAMES)


def test_no_evidence_and_no_literal_blocks(logger):
    should_block, msg = check_hook_protection_acceptance(
        _fm(["[x] 新增守衛偵測 X"]), logger, content=_body(test_results="12 passed")
    )
    assert should_block is True
    assert FAILURE in msg and TRIGGER in msg


# ---------- 2. 已存在證據的寫法 ----------

def test_failure_declaration_in_acceptance_counts():
    acc = "[x] 異常時的放行或阻擋行為：fail-open。觸發條件：main 拋例外時"
    assert FAILURE not in missing_evidence_categories(_body(), acc, NAMES)


def test_cn_release_word_with_trigger_on_same_line_counts():
    body = _body(solution="- 放行。觸發條件：main 內發生例外，記錄後 exit 0")
    assert FAILURE not in missing_evidence_categories(body, "", NAMES)


def test_cn_word_and_trigger_on_different_lines_not_counted():
    body = _body(solution="判定改為放行\n\n其他段落。觸發條件：無關敘述")
    assert FAILURE in missing_evidence_categories(body, "", NAMES)


def test_template_item_name_alone_is_not_a_declaration():
    acc = "[x] 異常時的放行或阻擋行為：觸發條件：main 拋例外時"
    assert FAILURE in missing_evidence_categories(_body(), acc, NAMES)


def _load_create_template(label):
    # 以 ast 讀 create.py 的常數字面值：import create.py 會拉入 hooks 環境沒有的依賴
    import ast

    src = (
        _hooks_dir.parent / "skills" / "ticket" / "ticket_system" / "commands" / "create.py"
    ).read_text(encoding="utf-8")
    for node in ast.parse(src).body:
        if isinstance(node, ast.Assign) and any(
            getattr(t, "id", "") == "_HOOK_ACCEPTANCE_TEMPLATES" for t in node.targets
        ):
            return dict(ast.literal_eval(node.value))[label]
    raise AssertionError("找不到 _HOOK_ACCEPTANCE_TEMPLATES")


def test_unfilled_create_template_is_not_a_declaration():
    # 正向對照（E2）：未改寫的佔位條目含「放行或阻擋」與「觸發條件：」字樣，
    # 範本措辭改動後不得被行內判定當成宣告
    item = _load_create_template(FAILURE)
    assert "觸發條件：" in item and "放行" in item and "阻擋" in item
    assert FAILURE in missing_evidence_categories(_body(), item, NAMES)


def test_log_line_with_hook_name_counts():
    body = _body(test_results="- `demo-guard-20261112.log:9` `[2026-11-12 19:10:11] INFO - 檢查完成`")
    missing = missing_evidence_categories(body, "", NAMES)
    assert TRIGGER not in missing and LIVENESS not in missing


def test_log_block_header_with_hook_name_counts():
    body = _body(
        test_results="demo-guard 日誌引文：\n\n```\n[2026-11-12 03:41:22] INFO - decision=deny\n```"
    )
    assert TRIGGER not in missing_evidence_categories(body, "", NAMES)


# ---------- 3. 來源追不到的日誌行 ----------

def test_log_line_without_source_not_counted():
    body = _body(test_results="hook-logs 引文：\n\n```\n[2026-11-12 03:41:22] INFO - decision=deny\n```")
    assert TRIGGER in missing_evidence_categories(body, "", NAMES)


def test_log_line_of_other_hook_not_counted():
    body = _body(test_results="- `[2026-11-12 03:41:22] INFO - other-guard 檢查完成`")
    assert TRIGGER in missing_evidence_categories(body, "", NAMES)


def test_log_line_without_known_hook_names_not_counted():
    body = _body(test_results="- `[2026-11-12 03:41:22] INFO - demo-guard 檢查完成`")
    assert TRIGGER in missing_evidence_categories(body, "", ())


# ---------- 4. 標記 ----------

def test_not_applicable_marker_covers_category(logger):
    body = _body(test_results="證據不適用（實地觸發）：hook 只以 stdout 輸出報告，引文如下")
    missing = missing_evidence_categories(body, "", NAMES, logger)
    assert TRIGGER not in missing
    assert LIVENESS in missing
    assert any("[evidence-not-applicable]" in r.getMessage() for r in logger.records)


def test_not_applicable_marker_rejected_for_failure_semantics():
    body = _body(solution="證據不適用（失敗語意）：沒有例外路徑")
    assert FAILURE in missing_evidence_categories(body, "", NAMES)


def test_deferred_marker_with_open_ticket_covers(logger):
    body = _body(test_results=f"延後取證（實地觸發）：{OPEN_TICKET}")
    missing = missing_evidence_categories(
        body, "", NAMES, logger, deferred_lookup=lambda tid, log: tid == OPEN_TICKET
    )
    assert TRIGGER not in missing
    assert any("[evidence-deferred]" in r.getMessage() for r in logger.records)


def test_deferred_marker_with_closed_or_missing_ticket_rejected():
    body = _body(test_results=f"延後取證（liveness）：{OPEN_TICKET}")
    missing = missing_evidence_categories(body, "", NAMES, deferred_lookup=lambda tid, log: False)
    assert LIVENESS in missing


def test_deferred_marker_without_ticket_id_rejected():
    body = _body(test_results="延後取證（liveness）：合併後再補")
    missing = missing_evidence_categories(body, "", NAMES, deferred_lookup=lambda tid, log: True)
    assert LIVENESS in missing


def test_handback_marker_is_not_evidence():
    body = _body(test_results="待主線程補證（實地觸發）：合併後以 stdin payload 實跑")
    assert TRIGGER in missing_evidence_categories(body, "", NAMES)


def test_deferred_lookup_failure_does_not_pass(monkeypatch, logger):
    def boom(*_a, **_k):
        raise RuntimeError("lookup boom")

    monkeypatch.setattr("lib.hook_ticket.find_ticket_file", boom, raising=False)
    assert mod._deferred_ticket_open(OPEN_TICKET, logger) is False


# ---------- 5. 例外退回原有判定 ----------

def test_relaxed_exception_falls_back_to_strict(monkeypatch, logger):
    def boom(*_a, **_k):
        raise RuntimeError("boom")

    monkeypatch.setattr(mod, "_relaxed_missing_evidence", boom)
    acc = "[x] 異常時的放行或阻擋行為：fail-open。觸發條件：main 拋例外時"
    # 放寬辨識失效時，只寫在 acceptance 的宣告不再被承認（退回原有判定）
    assert FAILURE in missing_evidence_categories(_body(), acc, NAMES, logger)


# ---------- 整合：check_hook_protection_acceptance 的過渡期紀錄 ----------

def test_acceptance_only_declaration_no_longer_records_transition(logger):
    acc = [
        "[x] 當次執行環境下的觸發驗證結果：見 Test Results",
        "[x] 載入與執行的確認方式：liveness 見 Test Results",
        "[x] 異常時的放行或阻擋行為：fail-open。觸發條件：main 拋例外時",
    ]
    body = _body(test_results="- `[2026-11-12 19:10:11] INFO - demo-guard 檢查完成`")
    assert check_hook_protection_acceptance(_fm(acc), logger, content=body) == (False, None)
    assert _transitions(logger) == []
