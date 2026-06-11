"""
ANA Spawn Consistency Checker Tests (W17-168)

對應 ANA: 0.18.0-W17-167 L2 hook 強制層
驗證 acceptance-gate-hook ANA complete 前 spawn 一致性檢查邏輯。

覆蓋情境：
  (a) W17-162 元反例舊版（complete 前 spawned=[]，Solution 含 4 項規劃）→ block
  (b) W17-167 自身元反例舊版（complete 前 spawned=[]，Solution 含 3 項規劃）→ block
  (c) 含豁免標記「無需建 ticket」→ 跳過（通過）
  (d) S+C < N（部分漏建）→ warning 不阻擋
  (e) S+C >= N（全建）→ 通過
  (f) Solution 無 spawn 表格行 → 通過
  (g) 非 ANA ticket → 跳過
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import pytest

_hooks_dir = Path(__file__).parent.parent
if str(_hooks_dir) not in sys.path:
    sys.path.insert(0, str(_hooks_dir))

from acceptance_checkers.ana_spawn_consistency_checker import (  # noqa: E402
    check_ana_spawn_consistency,
)


@pytest.fixture
def logger():
    log = logging.getLogger("test-ana-spawn-consistency")
    log.addHandler(logging.NullHandler())
    log.setLevel(logging.CRITICAL)
    return log


def _make_content(solution_body: str) -> str:
    """組合最小 ticket 內容：frontmatter + Solution 區段。"""
    return (
        "---\nid: 0.18.0-W17-999\ntype: ANA\n---\n\n"
        "## Problem Analysis\n\nsome\n\n"
        "## Solution\n\n"
        f"{solution_body}\n\n"
        "## Test Results\n\n"
    )


# ---------------------------------------------------------------------------
# (a) W17-162 元反例：4 項規劃 + spawned=[] → block
# ---------------------------------------------------------------------------

def test_w17_162_legacy_should_block(logger):
    solution = (
        "### Spawn 規劃\n\n"
        "| # | Type | Priority | 標題 | 範圍 | 代理人 |\n"
        "|---|------|----------|------|------|-------|\n"
        "| 1 | IMP | P1 | 修復 A | a.py | thyme |\n"
        "| 2 | IMP | P1 | 修復 B | b.py | thyme |\n"
        "| 3 | DOC | P2 | 文件 C | c.md | thyme |\n"
        "| 4 | DOC | P2 | 文件 D | d.md | thyme |\n"
    )
    content = _make_content(solution)
    fm = {"id": "0.18.0-W17-162", "type": "ANA", "spawned_tickets": [], "children": []}

    should_block, msg = check_ana_spawn_consistency(content, fm, logger)

    assert should_block is True
    assert msg is not None
    assert "0.18.0-W17-162" in msg
    assert "4" in msg


# ---------------------------------------------------------------------------
# (b) W17-167 自身元反例：3 項規劃 + spawned=[] → block
# ---------------------------------------------------------------------------

def test_w17_167_self_reference_should_block(logger):
    solution = (
        "### Spawned IMP/DOC 清單\n\n"
        "| # | Type | Priority | 標題 | 範圍 | 建議代理人 |\n"
        "|---|------|----------|------|------|-----------|\n"
        "| 1 | IMP | P1 | 實作 ana_spawn_consistency_checker | hook | thyme |\n"
        "| 2 | DOC | P2 | 規則升級 | rules | thyme |\n"
        "| 3 | DOC | P2 | PM checklist | pm-rules | thyme |\n"
    )
    content = _make_content(solution)
    fm = {"id": "0.18.0-W17-167", "type": "ANA", "spawned_tickets": [], "children": []}

    should_block, msg = check_ana_spawn_consistency(content, fm, logger)

    assert should_block is True
    assert msg is not None
    assert "3" in msg


# ---------------------------------------------------------------------------
# (c) 豁免標記：含「無需建 ticket」→ 跳過
# ---------------------------------------------------------------------------

def test_exemption_marker_should_skip(logger):
    solution = (
        "本 ANA 結論：無需建 ticket：所有規劃項目已併入 W17-100。\n\n"
        "| # | Type | Priority | 標題 |\n"
        "|---|------|----------|------|\n"
        "| 1 | IMP | P1 | 範例 |\n"
    )
    content = _make_content(solution)
    fm = {"id": "0.18.0-W17-998", "type": "ANA", "spawned_tickets": [], "children": []}

    should_block, msg = check_ana_spawn_consistency(content, fm, logger)

    assert should_block is False
    assert msg is None


def test_exemption_no_spawn_marker_should_skip(logger):
    solution = (
        "結論：不 spawn，本 ANA 為純文件梳理。\n\n"
        "| # | Type | Priority | 標題 |\n"
        "|---|------|----------|------|\n"
        "| 1 | DOC | P2 | 範例 |\n"
    )
    content = _make_content(solution)
    fm = {"id": "0.18.0-W17-997", "type": "ANA", "spawned_tickets": [], "children": []}

    should_block, msg = check_ana_spawn_consistency(content, fm, logger)

    assert should_block is False
    assert msg is None


# ---------------------------------------------------------------------------
# (d) 部分漏建：N=3, S+C=2 → warning 不阻擋
# ---------------------------------------------------------------------------

def test_partial_spawn_should_warn_not_block(logger):
    solution = (
        "| # | Type | Priority | 標題 |\n"
        "|---|------|----------|------|\n"
        "| 1 | IMP | P1 | A |\n"
        "| 2 | IMP | P1 | B |\n"
        "| 3 | DOC | P2 | C |\n"
    )
    content = _make_content(solution)
    fm = {
        "id": "0.18.0-W17-996",
        "type": "ANA",
        "spawned_tickets": ["0.18.0-W17-901", "0.18.0-W17-902"],
        "children": [],
    }

    should_block, msg = check_ana_spawn_consistency(content, fm, logger)

    assert should_block is False
    assert msg is not None
    assert "WARNING" in msg or "warning" in msg.lower()
    assert "3" in msg
    assert "2" in msg


# ---------------------------------------------------------------------------
# (e) 全建：N=3, S+C=3 → 通過
# ---------------------------------------------------------------------------

def test_full_spawn_should_pass(logger):
    solution = (
        "| # | Type | Priority | 標題 |\n"
        "|---|------|----------|------|\n"
        "| 1 | IMP | P1 | A |\n"
        "| 2 | DOC | P2 | B |\n"
        "| 3 | DOC | P2 | C |\n"
    )
    content = _make_content(solution)
    fm = {
        "id": "0.18.0-W17-995",
        "type": "ANA",
        "spawned_tickets": ["0.18.0-W17-901", "0.18.0-W17-902", "0.18.0-W17-903"],
        "children": [],
    }

    should_block, msg = check_ana_spawn_consistency(content, fm, logger)

    assert should_block is False
    assert msg is None


def test_children_count_as_spawn(logger):
    """children 也計入 S+C（PC-091 路線：ANA 落地統一用 --parent）。"""
    solution = (
        "| # | Type | Priority | 標題 |\n"
        "|---|------|----------|------|\n"
        "| 1 | IMP | P1 | A |\n"
        "| 2 | IMP | P1 | B |\n"
    )
    content = _make_content(solution)
    fm = {
        "id": "0.18.0-W17-994",
        "type": "ANA",
        "spawned_tickets": [],
        "children": ["0.18.0-W17-994.1", "0.18.0-W17-994.2"],
    }

    should_block, msg = check_ana_spawn_consistency(content, fm, logger)

    assert should_block is False
    assert msg is None


# ---------------------------------------------------------------------------
# (f) 無 spawn 表格行 → 通過
# ---------------------------------------------------------------------------

def test_no_spawn_table_should_pass(logger):
    solution = "純文字結論，無 spawn 規劃表格。"
    content = _make_content(solution)
    fm = {"id": "0.18.0-W17-993", "type": "ANA", "spawned_tickets": [], "children": []}

    should_block, msg = check_ana_spawn_consistency(content, fm, logger)

    assert should_block is False
    assert msg is None


# ---------------------------------------------------------------------------
# (g) 非 ANA ticket → 跳過
# ---------------------------------------------------------------------------

def test_non_ana_should_skip(logger):
    solution = (
        "| # | Type | Priority | 標題 |\n"
        "|---|------|----------|------|\n"
        "| 1 | IMP | P1 | A |\n"
    )
    content = _make_content(solution).replace("type: ANA", "type: IMP")
    fm = {"id": "0.18.0-W17-992", "type": "IMP", "spawned_tickets": [], "children": []}

    should_block, msg = check_ana_spawn_consistency(content, fm, logger)

    assert should_block is False
    assert msg is None


# ---------------------------------------------------------------------------
# (h) Solution 為空 → 跳過
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# (i) heading-based 偵測：W17-176 key-value 表格格式 → 至少 N=1（W17-178 擴充）
# ---------------------------------------------------------------------------


def test_w17_176_keyvalue_heading_should_block(logger):
    """W17-176 案例：### Spawned IMP 規劃 + key-value 表格，row-per-spawn N=0
    但 heading-based N=1，整合後應偵測為 1 項 spawn 規劃並阻擋 complete。
    """
    solution = (
        "### Spawned IMP 規劃\n\n"
        "| 欄位 | 值 |\n"
        "|------|------|\n"
        "| action | 修復 stop-worklog hook |\n"
        "| target | `.claude/hooks/x.py` |\n"
        "| priority | P1 |\n"
        "| who | thyme-extension-engineer |\n"
        "| blockedBy | 無 |\n"
    )
    content = _make_content(solution)
    fm = {"id": "0.18.0-W17-176", "type": "ANA", "spawned_tickets": [], "children": []}

    should_block, msg = check_ana_spawn_consistency(content, fm, logger)

    assert should_block is True
    assert msg is not None
    assert "0.18.0-W17-176" in msg


def test_heading_with_spawn_passes_when_actual_present(logger):
    """heading-based 偵測 N=1，spawned_tickets 有 1 項 → 通過。"""
    solution = (
        "### Spawned DOC 規劃\n\n"
        "| 欄位 | 值 |\n"
        "|------|------|\n"
        "| action | 文件更新 |\n"
        "| priority | P2 |\n"
    )
    content = _make_content(solution)
    fm = {
        "id": "0.18.0-W17-989",
        "type": "ANA",
        "spawned_tickets": ["0.18.0-W17-989.1"],
        "children": [],
    }

    should_block, msg = check_ana_spawn_consistency(content, fm, logger)

    assert should_block is False
    assert msg is None


def test_heading_without_spawn_keyword_should_not_trigger(logger):
    """非 spawn 語境的 H3（如 ### 根因分析、### Implementation Plan）不應被誤判。"""
    solution = (
        "### 根因分析\n\n"
        "說明 IMP 階段發生的問題。\n\n"
        "### Implementation Plan\n\n"
        "DOC 文件已涵蓋。\n"
    )
    content = _make_content(solution)
    fm = {"id": "0.18.0-W17-988", "type": "ANA", "spawned_tickets": [], "children": []}

    should_block, msg = check_ana_spawn_consistency(content, fm, logger)

    # 無 Spawn 關鍵字的 H3 + 無 row-per-spawn 表格 → N=0 → 通過
    assert should_block is False
    assert msg is None


def test_combined_strategies_takes_max(logger):
    """雙策略整合：row-per-spawn 偵測 2 項，heading-based 偵測 1 項 → max=2。"""
    solution = (
        "### Spawned IMP/DOC 清單\n\n"
        "| # | Type | Priority | 標題 |\n"
        "|---|------|----------|------|\n"
        "| 1 | IMP | P1 | A |\n"
        "| 2 | DOC | P2 | B |\n"
    )
    content = _make_content(solution)
    fm = {"id": "0.18.0-W17-987", "type": "ANA", "spawned_tickets": [], "children": []}

    should_block, msg = check_ana_spawn_consistency(content, fm, logger)

    assert should_block is True
    assert msg is not None
    # 應顯示 2（max(2 row, 1 heading)）而非 3
    assert "2" in msg


# ---------------------------------------------------------------------------
# (j) W1-024 真實表格變體：type 欄帶註記 + 無 P0-P3 欄（W1-037 強健化）
# ---------------------------------------------------------------------------


def test_w1_024_real_table_variant_should_block(logger):
    """W1-024 真實失效樣本：

    表格 `| 項目 | 形態 | 狀態 |`，形態欄含 `IMP（child）`/`IMP`（帶註記、無 P0-P3 欄），
    且 H3 為 `### Spawn 落地確認`（含 Spawn 關鍵字但無 IMP/DOC/ANA 在同行）。

    舊雙偵測策略（row-per-spawn 需 P[0-3]、heading 需同行含 IMP/DOC/ANA）皆 N=0，
    導致 acceptance-gate 對該票實質失效。強健化後須計入帶 type 註記的 spawn 行。
    """
    solution = (
        "### Spawn 落地確認\n\n"
        "| 項目 | 形態 | 狀態 |\n"
        "|------|------|------|\n"
        "| create 命令 UX 修復 | IMP（child） | 本 ticket spawn |\n"
        "| 裸 cd hook 絕對路徑排除過寬 | IMP | 本 session 已 spawn W1-026 |\n"
        "| append-log Context Bundle 摩擦 | IMP | 已 spawn W1-025 |\n"
    )
    content = _make_content(solution)
    fm = {"id": "1.0.0-W1-024", "type": "ANA", "spawned_tickets": [], "children": []}

    should_block, msg = check_ana_spawn_consistency(content, fm, logger)

    assert should_block is True
    assert msg is not None
    assert "1.0.0-W1-024" in msg


def test_type_annotated_row_with_actual_spawn_passes(logger):
    """type 欄帶註記偵測為 N，spawned_tickets/children 達標 → 通過（不誤阻擋）。"""
    solution = (
        "### Spawn 落地確認\n\n"
        "| 項目 | 形態 | 狀態 |\n"
        "|------|------|------|\n"
        "| 修復 A | IMP（child） | spawn |\n"
        "| 修復 B | DOC | spawn |\n"
    )
    content = _make_content(solution)
    fm = {
        "id": "1.0.0-W1-024.x",
        "type": "ANA",
        "spawned_tickets": [],
        "children": ["1.0.0-W1-024.1", "1.0.0-W1-024.2"],
    }

    should_block, msg = check_ana_spawn_consistency(content, fm, logger)

    assert should_block is False
    assert msg is None


# ---------------------------------------------------------------------------
# (k) 「無需 spawn」系列豁免語彙（W1-037）
# ---------------------------------------------------------------------------


def test_exemption_wuxu_spawn_should_skip(logger):
    """「無需 spawn」豁免語彙：合法無 spawn 的 ANA 不被阻擋。"""
    solution = (
        "結論：本 ANA 無需 spawn，所有規劃項目併入既有 ticket。\n\n"
        "### Spawn 落地確認\n\n"
        "| 項目 | 形態 | 狀態 |\n"
        "|------|------|------|\n"
        "| 項目 A | IMP | 併入 W1-100 |\n"
    )
    content = _make_content(solution)
    fm = {"id": "1.0.0-W1-024.y", "type": "ANA", "spawned_tickets": [], "children": []}

    should_block, msg = check_ana_spawn_consistency(content, fm, logger)

    assert should_block is False
    assert msg is None


def test_type_annotated_row_without_spawn_heading_not_triggered(logger):
    """type 欄帶註記但表格不在 Spawn 語境（無 Spawn 關鍵字 H3）→ 不誤判。

    避免 false positive：合法的一般說明表格（含 IMP/DOC 字樣）不應被當 spawn 規劃。
    """
    solution = (
        "### 風險評估\n\n"
        "| 風險 | 影響類型 | 緩解 |\n"
        "|------|----------|------|\n"
        "| 回歸 | IMP 範圍擴大 | 測試 |\n"
        "| 文件 | DOC 不同步 | 同步檢查 |\n"
    )
    content = _make_content(solution)
    fm = {"id": "1.0.0-W1-024.z", "type": "ANA", "spawned_tickets": [], "children": []}

    should_block, msg = check_ana_spawn_consistency(content, fm, logger)

    assert should_block is False
    assert msg is None


# ---------------------------------------------------------------------------
# (h) Solution 為空 → 跳過
# ---------------------------------------------------------------------------


def _legacy_test_empty_solution_should_skip_marker():
    """anchor for next test definition (no-op)."""


def test_empty_solution_should_skip(logger):
    content = (
        "---\nid: 0.18.0-W17-991\ntype: ANA\n---\n\n"
        "## Problem Analysis\n\nsome\n\n"
        "## Solution\n\n<!-- placeholder -->\n\n"
        "## Test Results\n\n"
    )
    fm = {"id": "0.18.0-W17-991", "type": "ANA", "spawned_tickets": [], "children": []}

    should_block, msg = check_ana_spawn_consistency(content, fm, logger)

    assert should_block is False
    assert msg is None
