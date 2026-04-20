"""
Acceptance Gate Hook - 父 Ticket complete 前置 block 檢查測試

對應 Ticket 0.18.0-W10-036.2 AC 5：
測試覆蓋四情境：
  (1) 父有子未完成 block
  (2) 父有子全完成 pass
  (3) 父無子 pass
  (4) 孫層未完成 block（遞迴檢查）

測試目標：驗證 `check_children_completed_from_frontmatter` 正確處理
父子遞迴檢查，並將「任一後代未 completed/closed」視為 block 條件。
"""

import sys
import logging
from pathlib import Path

import pytest

# 將 .claude/hooks 加入 sys.path，讓測試能 import acceptance_checkers
_hooks_dir = Path(__file__).parent.parent
if str(_hooks_dir) not in sys.path:
    sys.path.insert(0, str(_hooks_dir))

from hook_utils import parse_ticket_frontmatter
from acceptance_checkers.children_checker import (
    check_children_completed_from_frontmatter,
)


# ----------------------------------------------------------------------------
# 測試工具
# ----------------------------------------------------------------------------

def _write_ticket(
    project_dir: Path,
    ticket_id: str,
    status: str,
    children: list = None,
    title: str = None,
) -> Path:
    """建立一個最小可解析的 Ticket 檔案。

    Ticket 目錄結構遵循 find_ticket_file 的預期：
        docs/work-logs/v{version}/tickets/{ticket_id}.md

    ticket_id 格式：{major}.{minor}.{patch}-W{wave}-{seq}
    """
    version_part = ticket_id.split("-W")[0]  # e.g. "0.18.0"
    ticket_dir = project_dir / "docs" / "work-logs" / f"v{version_part}" / "tickets"
    ticket_dir.mkdir(parents=True, exist_ok=True)

    if children:
        # 使用 inline list 格式，因 parse_ticket_frontmatter 對列 0 `- item` 不會展開，
        # 但能保留 inline `[a, b]` 為原始字串，由 extract_children_from_frontmatter 解析。
        children_block = "children: [" + ", ".join(children) + "]"
    else:
        children_block = "children: []"

    content = f"""---
id: {ticket_id}
title: {title or ticket_id}
type: IMP
status: {status}
version: {version_part}
{children_block}
---

# Body

"""
    ticket_file = ticket_dir / f"{ticket_id}.md"
    ticket_file.write_text(content, encoding="utf-8")
    return ticket_file


@pytest.fixture
def logger():
    """靜音 logger，避免汙染測試輸出。"""
    log = logging.getLogger("test-acceptance-gate")
    log.addHandler(logging.NullHandler())
    log.setLevel(logging.CRITICAL)
    return log


@pytest.fixture
def project_dir(tmp_path):
    """以 tmp_path 作為專案根目錄。"""
    return tmp_path


# ----------------------------------------------------------------------------
# 情境 1：父有子未完成 → block (exit 2)
# ----------------------------------------------------------------------------

def test_parent_with_pending_child_should_block(project_dir, logger):
    """
    情境 1：父有子未完成（pending），必須 block。

    對應 AC 2：任一子 Ticket 非 completed/closed → exit 2 (block)
    """
    parent_file = _write_ticket(
        project_dir,
        "0.18.0-W10-900",
        status="in_progress",
        children=["0.18.0-W10-900.1"],
    )
    _write_ticket(project_dir, "0.18.0-W10-900.1", status="pending")

    frontmatter = parse_ticket_frontmatter(parent_file.read_text(encoding="utf-8"))
    should_block, error_msg = check_children_completed_from_frontmatter(
        parent_file, frontmatter, project_dir, "0.18.0-W10-900", logger
    )

    assert should_block is True, "父有 pending 子任務時必須 block"
    assert error_msg is not None
    assert "0.18.0-W10-900.1" in error_msg, "錯誤訊息必須列出未完成子 ID（AC 3）"


def test_parent_with_in_progress_child_should_block(project_dir, logger):
    """子狀態為 in_progress 也應 block。"""
    parent_file = _write_ticket(
        project_dir,
        "0.18.0-W10-901",
        status="in_progress",
        children=["0.18.0-W10-901.1"],
    )
    _write_ticket(project_dir, "0.18.0-W10-901.1", status="in_progress")

    frontmatter = parse_ticket_frontmatter(parent_file.read_text(encoding="utf-8"))
    should_block, error_msg = check_children_completed_from_frontmatter(
        parent_file, frontmatter, project_dir, "0.18.0-W10-901", logger
    )
    assert should_block is True
    assert "0.18.0-W10-901.1" in error_msg


# ----------------------------------------------------------------------------
# 情境 2：父有子全完成 → pass (exit 0)
# ----------------------------------------------------------------------------

def test_parent_with_all_completed_children_should_pass(project_dir, logger):
    """
    情境 2：父的所有子任務皆為 completed，必須 pass。
    """
    parent_file = _write_ticket(
        project_dir,
        "0.18.0-W10-902",
        status="in_progress",
        children=["0.18.0-W10-902.1", "0.18.0-W10-902.2"],
    )
    _write_ticket(project_dir, "0.18.0-W10-902.1", status="completed")
    _write_ticket(project_dir, "0.18.0-W10-902.2", status="completed")

    frontmatter = parse_ticket_frontmatter(parent_file.read_text(encoding="utf-8"))
    should_block, error_msg = check_children_completed_from_frontmatter(
        parent_file, frontmatter, project_dir, "0.18.0-W10-902", logger
    )

    assert should_block is False, "所有子任務 completed 時必須 pass"
    assert error_msg is None


def test_parent_with_closed_children_should_pass(project_dir, logger):
    """
    closed 狀態等同 completed，應視為終止狀態（AC 2 規格：completed/closed）。
    """
    parent_file = _write_ticket(
        project_dir,
        "0.18.0-W10-903",
        status="in_progress",
        children=["0.18.0-W10-903.1"],
    )
    _write_ticket(project_dir, "0.18.0-W10-903.1", status="closed")

    frontmatter = parse_ticket_frontmatter(parent_file.read_text(encoding="utf-8"))
    should_block, error_msg = check_children_completed_from_frontmatter(
        parent_file, frontmatter, project_dir, "0.18.0-W10-903", logger
    )

    assert should_block is False, "closed 應被視為終止狀態，不阻擋 complete"


# ----------------------------------------------------------------------------
# 情境 3：父無子任務 → pass (exit 0)
# ----------------------------------------------------------------------------

def test_parent_without_children_should_pass(project_dir, logger):
    """
    情境 3：父沒有任何子任務，必須 pass。
    """
    parent_file = _write_ticket(
        project_dir,
        "0.18.0-W10-904",
        status="in_progress",
        children=None,
    )

    frontmatter = parse_ticket_frontmatter(parent_file.read_text(encoding="utf-8"))
    should_block, error_msg = check_children_completed_from_frontmatter(
        parent_file, frontmatter, project_dir, "0.18.0-W10-904", logger
    )

    assert should_block is False
    assert error_msg is None


# ----------------------------------------------------------------------------
# 情境 4：孫層未完成 → block（遞迴檢查）
# ----------------------------------------------------------------------------

def test_grandchild_pending_should_block(project_dir, logger):
    """
    情境 4：子已 completed，但孫 pending，仍需 block（遞迴檢查，AC 1）。

    結構：
        parent (complete 嘗試中)
          └─ child.1 (completed)
                └─ grandchild.1.1 (pending)  ← 未完成的孫

    父責任是「分析問題被解決」，若孫層尚未落實，父的責任鏈未完成。
    """
    parent_file = _write_ticket(
        project_dir,
        "0.18.0-W10-905",
        status="in_progress",
        children=["0.18.0-W10-905.1"],
    )
    _write_ticket(
        project_dir,
        "0.18.0-W10-905.1",
        status="completed",
        children=["0.18.0-W10-905.1.1"],
    )
    _write_ticket(project_dir, "0.18.0-W10-905.1.1", status="pending")

    frontmatter = parse_ticket_frontmatter(parent_file.read_text(encoding="utf-8"))
    should_block, error_msg = check_children_completed_from_frontmatter(
        parent_file, frontmatter, project_dir, "0.18.0-W10-905", logger
    )

    assert should_block is True, "孫層未完成時父必須 block（遞迴檢查）"
    assert error_msg is not None
    assert "0.18.0-W10-905.1.1" in error_msg, "錯誤訊息必須指出實際未完成的後代 ID"


def test_grandchild_all_completed_should_pass(project_dir, logger):
    """
    子和孫全部 completed → pass（遞迴檢查正面案例）。
    """
    parent_file = _write_ticket(
        project_dir,
        "0.18.0-W10-906",
        status="in_progress",
        children=["0.18.0-W10-906.1"],
    )
    _write_ticket(
        project_dir,
        "0.18.0-W10-906.1",
        status="completed",
        children=["0.18.0-W10-906.1.1"],
    )
    _write_ticket(project_dir, "0.18.0-W10-906.1.1", status="completed")

    frontmatter = parse_ticket_frontmatter(parent_file.read_text(encoding="utf-8"))
    should_block, error_msg = check_children_completed_from_frontmatter(
        parent_file, frontmatter, project_dir, "0.18.0-W10-906", logger
    )

    assert should_block is False
    assert error_msg is None


# ----------------------------------------------------------------------------
# 情境 5：非終止狀態（blocked / failed / unknown）→ block
#
# TERMINAL_STATUSES = {"completed", "closed"}。所有其他狀態（含自訂狀態）
# 均視為未完成，必須 block。
# 對應 W10-039.3 bay 審查發現：未覆蓋 blocked/failed/unknown 分支。
# ----------------------------------------------------------------------------

@pytest.mark.parametrize("non_terminal_status", ["blocked", "failed", "unknown"])
def test_child_with_non_terminal_status_should_block(
    project_dir, logger, non_terminal_status
):
    """子任務為 blocked/failed/unknown（非 completed/closed）時必須 block。

    這三種狀態在 TERMINAL_STATUSES 之外，守門機制應一致判為未完成。
    """
    parent_id = f"0.18.0-W10-910-{non_terminal_status}"
    child_id = f"{parent_id}.1"
    parent_file = _write_ticket(
        project_dir, parent_id, status="in_progress", children=[child_id]
    )
    _write_ticket(project_dir, child_id, status=non_terminal_status)

    frontmatter = parse_ticket_frontmatter(parent_file.read_text(encoding="utf-8"))
    should_block, error_msg = check_children_completed_from_frontmatter(
        parent_file, frontmatter, project_dir, parent_id, logger
    )

    assert should_block is True, f"status={non_terminal_status} 必須被視為未完成"
    assert child_id in error_msg
    assert non_terminal_status in error_msg, "錯誤訊息應列出實際狀態值"


# ----------------------------------------------------------------------------
# 情境 6：循環引用 → visited 防止無限遞迴
#
# 結構：A.children=[B], B.children=[A]（互相引用）
# 預期：呼叫端以 visited={root} 初始化，遞迴至 B 時 B 已 visit、再訪 A 被 visited
# 阻擋，不會 stack overflow。
# 對應 W10-039.3 bay 審查發現：未測 visited 機制。
# ----------------------------------------------------------------------------

def test_circular_reference_does_not_infinite_loop(project_dir, logger):
    """A→B→A 循環時，visited 機制必須阻止無限遞迴。

    _collect_incomplete_descendants 在訪問前檢查 visited，已訪問的 ID 會被跳過。
    check_children_completed_from_frontmatter 呼叫時以 visited={ticket_id} 初始化，
    因此即便子任務反向引用父，也不會重入父節點。
    """
    # 建立父 A，含子 B
    parent_file = _write_ticket(
        project_dir,
        "0.18.0-W10-920",
        status="in_progress",
        children=["0.18.0-W10-920.B"],
    )
    # 建立子 B，反向引用父 A（循環）
    _write_ticket(
        project_dir,
        "0.18.0-W10-920.B",
        status="completed",
        children=["0.18.0-W10-920"],
    )

    frontmatter = parse_ticket_frontmatter(parent_file.read_text(encoding="utf-8"))

    # 若 visited 機制失效，此呼叫會 stack overflow 或超時
    should_block, error_msg = check_children_completed_from_frontmatter(
        parent_file, frontmatter, project_dir, "0.18.0-W10-920", logger
    )

    # B 已 completed 且透過 visited 不會重入 A → pass
    assert should_block is False, "循環中所有可達節點皆 completed，應 pass"
    assert error_msg is None


def test_circular_reference_with_incomplete_descendant_still_reports(
    project_dir, logger
):
    """循環引用中仍有未完成節點時，錯誤訊息必須正確列出未完成者。

    結構：
        parent (X) → child (Y, pending) → grandchild (X, 循環回父)
    即便有循環，Y 為 pending 仍應被報告，visited 只防重訪不影響偵測。
    """
    parent_id = "0.18.0-W10-921"
    child_id = "0.18.0-W10-921.Y"

    parent_file = _write_ticket(
        project_dir, parent_id, status="in_progress", children=[child_id]
    )
    _write_ticket(
        project_dir, child_id, status="pending", children=[parent_id]  # 循環
    )

    frontmatter = parse_ticket_frontmatter(parent_file.read_text(encoding="utf-8"))
    should_block, error_msg = check_children_completed_from_frontmatter(
        parent_file, frontmatter, project_dir, parent_id, logger
    )

    assert should_block is True
    assert child_id in error_msg, "未完成的子任務仍須被報告，循環不可掩蓋問題"


# ----------------------------------------------------------------------------
# 情境 7：多分支子樹 → 錯誤訊息列出正確的未完成後代
#
# 結構：
#     parent
#       ├─ A (completed, 無子)
#       └─ B (completed)
#             └─ B.1 (pending)  ← 應被列出
# 對應 W10-039.3 bay 審查發現：未測多分支情境，只測單鏈。
# ----------------------------------------------------------------------------

def test_multi_branch_tree_reports_correct_pending_descendant(project_dir, logger):
    """多分支子樹：一兄弟完整、另一兄弟的孫未完成，錯誤訊息應只列孫。

    驗證 _collect_incomplete_descendants 在遇到已 completed 的中間節點時
    仍會下潛檢查後代，且不會把已 completed 的兄弟誤報為未完成。
    """
    parent_file = _write_ticket(
        project_dir,
        "0.18.0-W10-930",
        status="in_progress",
        children=["0.18.0-W10-930.A", "0.18.0-W10-930.B"],
    )
    # 兄弟 A：completed 且無子
    _write_ticket(project_dir, "0.18.0-W10-930.A", status="completed")
    # 兄弟 B：completed 但有 pending 孫
    _write_ticket(
        project_dir,
        "0.18.0-W10-930.B",
        status="completed",
        children=["0.18.0-W10-930.B.1"],
    )
    _write_ticket(project_dir, "0.18.0-W10-930.B.1", status="pending")

    frontmatter = parse_ticket_frontmatter(parent_file.read_text(encoding="utf-8"))
    should_block, error_msg = check_children_completed_from_frontmatter(
        parent_file, frontmatter, project_dir, "0.18.0-W10-930", logger
    )

    assert should_block is True, "B 的孫 pending，父必須 block"
    assert "0.18.0-W10-930.B.1" in error_msg, "未完成的孫必須被列出"
    # A 和 B 本身都 completed，不應被列為未完成
    assert "0.18.0-W10-930.A" not in error_msg, "completed 兄弟不應被誤報"
    # B 本身 completed 不應列出（但 B.1 含 B 前綴，需用更嚴格斷言）
    # 改檢查：錯誤訊息應只含 B.1 這一條未完成項目
    pending_lines = [
        line for line in error_msg.splitlines() if "status:" in line
    ]
    assert len(pending_lines) == 1, (
        f"應只報告一個未完成後代，實際: {pending_lines}"
    )


# ----------------------------------------------------------------------------
# 情境 8：Fallback parser 路徑覆蓋
#
# _extract_children_robust 先走 extract_children_from_frontmatter（dict 型）
# 失敗後降級到 _read_children_from_file（原始文字掃描）。
# 兩條路徑都需測試。
# 對應 W10-039.3 bay 審查發現：未測 fallback 路徑。
# ----------------------------------------------------------------------------

def _write_raw_ticket(
    project_dir: Path, ticket_id: str, frontmatter_text: str
) -> Path:
    """以原始 frontmatter 文字建立 Ticket（繞過 _write_ticket helper 限制）。

    用於測試 fallback parser 路徑：需要建構 hook_utils parser 解析失敗
    但原始文字可抽取的 frontmatter（例如 block-style 列表）。
    """
    version_part = ticket_id.split("-W")[0]
    ticket_dir = project_dir / "docs" / "work-logs" / f"v{version_part}" / "tickets"
    ticket_dir.mkdir(parents=True, exist_ok=True)
    content = f"---\n{frontmatter_text}\n---\n\n# Body\n"
    ticket_file = ticket_dir / f"{ticket_id}.md"
    ticket_file.write_text(content, encoding="utf-8")
    return ticket_file


def test_fallback_parser_handles_block_style_children_list(project_dir, logger):
    """block-style YAML 列表（`children:\\n- id`）走 fallback 仍能抽取 children。

    hook_utils parse_ticket_frontmatter 對頂層列表可能返回空字串，
    _read_children_from_file 負責直接掃描原始 frontmatter 文字。
    若此 fallback 失效，block-style 列表的子任務會被視為「無子」而錯誤 pass。
    """
    parent_file = _write_raw_ticket(
        project_dir,
        "0.18.0-W10-940",
        frontmatter_text=(
            "id: 0.18.0-W10-940\n"
            "title: parent\n"
            "type: IMP\n"
            "status: in_progress\n"
            "version: 0.18.0\n"
            "children:\n"
            "- 0.18.0-W10-940.1\n"
            "- 0.18.0-W10-940.2\n"
        ),
    )
    _write_ticket(project_dir, "0.18.0-W10-940.1", status="completed")
    _write_ticket(project_dir, "0.18.0-W10-940.2", status="pending")

    frontmatter = parse_ticket_frontmatter(parent_file.read_text(encoding="utf-8"))
    should_block, error_msg = check_children_completed_from_frontmatter(
        parent_file, frontmatter, project_dir, "0.18.0-W10-940", logger
    )

    assert should_block is True, (
        "block-style 列表的子任務必須被抽取，fallback 路徑不可漏偵"
    )
    assert "0.18.0-W10-940.2" in error_msg
    assert "0.18.0-W10-940.1" not in error_msg, "completed 子任務不應被列出"


def test_fallback_parser_empty_children_returns_no_descendants(project_dir, logger):
    """parser 返回空 children（無 children 欄位或為 []）時，視為無子任務 → pass。

    確認當 extract_children_from_frontmatter 返回空 list 且 fallback
    _read_children_from_file 亦返回空時，orchestrator 走 pass 分支。
    """
    parent_file = _write_raw_ticket(
        project_dir,
        "0.18.0-W10-941",
        frontmatter_text=(
            "id: 0.18.0-W10-941\n"
            "title: parent-no-children-field\n"
            "type: IMP\n"
            "status: in_progress\n"
            "version: 0.18.0\n"
            # 刻意省略 children 欄位
        ),
    )

    frontmatter = parse_ticket_frontmatter(parent_file.read_text(encoding="utf-8"))
    should_block, error_msg = check_children_completed_from_frontmatter(
        parent_file, frontmatter, project_dir, "0.18.0-W10-941", logger
    )

    assert should_block is False, "無 children 欄位時 fallback 應返回空清單 → pass"
    assert error_msg is None
