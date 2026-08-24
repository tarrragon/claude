"""
ANA Spawn Consistency Checker Tests (W17-168)

對應 ANA: 0.18.0-W17-167 L2 hook 強制層
驗證 acceptance-gate-hook ANA complete 前 spawn 一致性檢查邏輯。

覆蓋情境：
  (a) W17-162 元反例舊版（complete 前 spawned=[]，Solution 含 4 項規劃）→ block
  (b) W17-167 自身元反例舊版（complete 前 spawned=[]，Solution 含 3 項規劃）→ block
  (c) 豁免宣告數 >= 規劃數 → 跳過（通過）
  (d) S+C < N（部分漏建）→ warning 不阻擋
  (e) S+C >= N（全建）→ 通過
  (f) Solution 無 spawn 表格行 → 通過
  (g) 非 ANA ticket → 跳過
  (l) 已判定（processed / 附理由 dismissed）Spawn Request 計入落地證據
  (m) pending / 無理由 dismissed / status 缺失的 SR 不計入
  (n) 豁免宣告逐項扣抵：宣告數少於規劃數時剩餘項目仍受檢
  (o) 阻擋訊息的建票指令為實際存在的 CLI 入口
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


# ---------------------------------------------------------------------------
# (l)(m) Spawn Request 作為落地證據（2026-08-23）
#
# 框架文件明列 add-spawn-request 為兩條合法建票通道之一，原實作只認
# spawned_tickets / children，使走該通道的 ANA 無論登記多少筆 SR 都被硬擋。
# 計入的僅限已判定終態；pending 是無 trigger 延後，刻意不計入。
# ---------------------------------------------------------------------------

_TWO_ROW_SPAWN_TABLE = (
    "### Spawn 規劃\n\n"
    "| # | Type | Priority | 標題 |\n"
    "|---|------|----------|------|\n"
    "| 1 | IMP | P1 | A |\n"
    "| 2 | DOC | P2 | B |\n"
)


def _sr_entry(label: str, status_value: str) -> str:
    """組出一則 Spawn Request 條目，格式對齊 add-spawn-request CLI 產出。"""
    return (
        f"- **{label}** (2026-08-23 08:10)\n"
        f"  - what: 範例項目\n"
        f"  - why: 範例理由\n"
        f"  - suggested_type: IMP\n"
        f"  - suggested_priority: P2\n"
        f"  - related_files: \n"
        f"  - context: \n"
        f"  - status: {status_value}\n"
    )


def _make_content_with_srs(solution_body: str, sr_entries: str) -> str:
    """組合含 Spawn Requests 章節的最小 ticket 內容。"""
    return (
        "---\nid: 0.18.0-W17-980\ntype: ANA\n---\n\n"
        "## Problem Analysis\n\nsome\n\n"
        "## Solution\n\n"
        f"{solution_body}\n\n"
        "## Spawn Requests\n\n"
        f"{sr_entries}\n"
        "## Completion Info\n\n"
    )


def test_processed_spawn_requests_count_as_landed(logger):
    """2 項規劃 + 2 筆 processed SR + spawned_tickets 為空 → 放行。"""
    sr = (
        _sr_entry("SR-1", "processed（已建 0.18.0-W17-901）")
        + "\n"
        + _sr_entry("SR-2", "processed（已建 0.18.0-W17-902）")
    )
    content = _make_content_with_srs(_TWO_ROW_SPAWN_TABLE, sr)
    fm = {"id": "0.18.0-W17-980", "type": "ANA", "spawned_tickets": [], "children": []}

    should_block, msg = check_ana_spawn_consistency(content, fm, logger)

    assert should_block is False
    assert msg is None


def test_dismissed_with_reason_counts_as_resolved(logger):
    """dismissed 附理由視為已判定；2 項規劃 + 2 筆帶理由 dismissed → 放行。"""
    sr = (
        _sr_entry("SR-1", "dismissed（範疇已由既有票涵蓋）")
        + "\n"
        + _sr_entry("SR-2", "dismissed（經評估屬既有行為，非缺陷）")
    )
    content = _make_content_with_srs(_TWO_ROW_SPAWN_TABLE, sr)
    fm = {"id": "0.18.0-W17-980", "type": "ANA", "spawned_tickets": [], "children": []}

    should_block, msg = check_ana_spawn_consistency(content, fm, logger)

    assert should_block is False
    assert msg is None


def test_dismissed_without_reason_does_not_count(logger):
    """無理由的 dismissed 缺可稽核依據，不計入落地證據 → 仍硬擋。"""
    sr = _sr_entry("SR-1", "dismissed") + "\n" + _sr_entry("SR-2", "dismissed")
    content = _make_content_with_srs(_TWO_ROW_SPAWN_TABLE, sr)
    fm = {"id": "0.18.0-W17-980", "type": "ANA", "spawned_tickets": [], "children": []}

    should_block, msg = check_ana_spawn_consistency(content, fm, logger)

    assert should_block is True
    assert msg is not None


def test_pending_spawn_requests_do_not_count(logger):
    """2 項規劃 + 2 筆 pending SR → 仍硬擋（pending 是未判定的延後）。"""
    sr = _sr_entry("SR-1", "pending") + "\n" + _sr_entry("SR-2", "pending")
    content = _make_content_with_srs(_TWO_ROW_SPAWN_TABLE, sr)
    fm = {"id": "0.18.0-W17-980", "type": "ANA", "spawned_tickets": [], "children": []}

    should_block, msg = check_ana_spawn_consistency(content, fm, logger)

    assert should_block is True
    assert msg is not None
    assert "0.18.0-W17-980" in msg


def test_missing_status_spawn_request_does_not_count(logger):
    """status 欄位缺失的 SR 走 fail-closed，不計入落地證據。"""
    sr_without_status = (
        "- **SR-1** (2026-08-23 08:10)\n"
        "  - what: 範例項目\n"
        "  - why: 範例理由\n"
    )
    content = _make_content_with_srs(_TWO_ROW_SPAWN_TABLE, sr_without_status)
    fm = {"id": "0.18.0-W17-980", "type": "ANA", "spawned_tickets": [], "children": []}

    should_block, msg = check_ana_spawn_consistency(content, fm, logger)

    assert should_block is True
    assert msg is not None


def test_mixed_frontmatter_and_spawn_request_sum(logger):
    """落地證據為 spawned_tickets + children + 已判定 SR 的總和。"""
    sr = _sr_entry("SR-1", "processed（已建 0.18.0-W17-902）")
    content = _make_content_with_srs(_TWO_ROW_SPAWN_TABLE, sr)
    fm = {
        "id": "0.18.0-W17-980",
        "type": "ANA",
        "spawned_tickets": ["0.18.0-W17-901"],
        "children": [],
    }

    should_block, msg = check_ana_spawn_consistency(content, fm, logger)

    assert should_block is False
    assert msg is None


def test_partial_landing_warning_reports_both_sources(logger):
    """部分落地時 warning 須分列具名 ticket 與無 ID 已判定兩種來源的數量。"""
    three_row_table = _TWO_ROW_SPAWN_TABLE + "| 3 | DOC | P2 | C |\n"
    sr = _sr_entry("SR-1", "dismissed（經評估屬既有行為）")
    content = _make_content_with_srs(three_row_table, sr)
    fm = {
        "id": "0.18.0-W17-980",
        "type": "ANA",
        "spawned_tickets": ["0.18.0-W17-901"],
        "children": [],
    }

    should_block, msg = check_ana_spawn_consistency(content, fm, logger)

    assert should_block is False
    assert msg is not None
    assert "WARNING" in msg
    assert "具名 ticket 去重後 = 1" in msg
    assert "無 ticket ID 的已判定項 = 1" in msg


# ---------------------------------------------------------------------------
# (p) 落地證據去重（2026-08-23）
#
# resolve-spawn-request --status processed --spawned-ticket 會同步回填
# spawned_tickets，同一筆落地因此同時出現在 frontmatter 與 SR 附註兩處。
# 直接相加會把它計兩次，使本該警告的部分漏建靜默通過。
# ---------------------------------------------------------------------------


def test_processed_sr_backfilled_to_frontmatter_counted_once(logger):
    """4 項規劃、實際只落地 2 項（2 筆 processed SR 且已回填）→ warning 而非放行。"""
    four_row_table = (
        _TWO_ROW_SPAWN_TABLE + "| 3 | DOC | P2 | C |\n| 4 | DOC | P2 | D |\n"
    )
    sr = (
        _sr_entry("SR-1", "processed（已建 0.18.0-W17-901）")
        + "\n"
        + _sr_entry("SR-2", "processed（已建 0.18.0-W17-902）")
    )
    content = _make_content_with_srs(four_row_table, sr)
    fm = {
        "id": "0.18.0-W17-970",
        "type": "ANA",
        "spawned_tickets": ["0.18.0-W17-901", "0.18.0-W17-902"],
        "children": [],
    }

    should_block, msg = check_ana_spawn_consistency(content, fm, logger)

    assert should_block is False
    assert msg is not None
    assert "WARNING" in msg
    assert "具名 ticket 去重後 = 2" in msg


def test_multiple_ids_in_single_sr_note_each_counted(logger):
    """單一 SR 附註記載多個 ticket ID（`已建 A、B`）時各計一次。"""
    sr = _sr_entry("SR-1", "processed（已建 0.18.0-W17-901、0.18.0-W17-902）")
    content = _make_content_with_srs(_TWO_ROW_SPAWN_TABLE, sr)
    fm = {"id": "0.18.0-W17-971", "type": "ANA", "spawned_tickets": [], "children": []}

    should_block, msg = check_ana_spawn_consistency(content, fm, logger)

    assert should_block is False
    assert msg is None


def test_note_with_ids_and_reason_parses_ids_only(logger):
    """附註同時含 ticket ID 與理由（`已建 A、B，理由`）時只取 ID 段。"""
    sr = _sr_entry(
        "SR-1", "processed（已建 0.18.0-W17-901、0.18.0-W17-902，兩項合併處理）"
    )
    content = _make_content_with_srs(_TWO_ROW_SPAWN_TABLE, sr)
    fm = {"id": "0.18.0-W17-972", "type": "ANA", "spawned_tickets": [], "children": []}

    should_block, msg = check_ana_spawn_consistency(content, fm, logger)

    assert should_block is False
    assert msg is None


def test_duplicate_id_across_spawned_and_children_counted_once(logger):
    """spawned_tickets 與 children 列出同一 ID 時只計一次 → 2 項規劃僅落地 1 項。"""
    content = _make_content(_TWO_ROW_SPAWN_TABLE)
    fm = {
        "id": "0.18.0-W17-973",
        "type": "ANA",
        "spawned_tickets": ["0.18.0-W17-901"],
        "children": ["0.18.0-W17-901"],
    }

    should_block, msg = check_ana_spawn_consistency(content, fm, logger)

    assert should_block is False
    assert msg is not None
    assert "WARNING" in msg
    assert "具名 ticket 去重後 = 1" in msg


def test_processed_without_ticket_id_counts_as_judged(logger):
    """未帶 ticket ID 的 processed 與附理由 dismissed 同列無 ID 已判定，各計一次。"""
    sr = _sr_entry("SR-1", "processed") + "\n" + _sr_entry("SR-2", "dismissed（不需要）")
    content = _make_content_with_srs(_TWO_ROW_SPAWN_TABLE, sr)
    fm = {"id": "0.18.0-W17-974", "type": "ANA", "spawned_tickets": [], "children": []}

    should_block, msg = check_ana_spawn_consistency(content, fm, logger)

    assert should_block is False
    assert msg is None


def test_unparseable_note_falls_back_to_judged_count(logger):
    """附註為非建立端格式而無法解析 ID 時退回無 ID 計數（偏向阻擋，不誤放）。

    兩筆 processed 的附註皆非 `已建 ...` 格式，各計一次無 ID 已判定；
    frontmatter 另有兩個 ID。3 項規劃 → 落地 4 項不阻擋，但此測試的重點是
    解析失敗不會拋例外且計數方向保守。
    """
    sr = (
        _sr_entry("SR-1", "processed（已於他處處理）")
        + "\n"
        + _sr_entry("SR-2", "processed（同上）")
    )
    three_row_table = _TWO_ROW_SPAWN_TABLE + "| 3 | DOC | P2 | C |\n"
    content = _make_content_with_srs(three_row_table, sr)
    fm = {
        "id": "0.18.0-W17-975.b",
        "type": "ANA",
        "spawned_tickets": ["0.18.0-W17-901", "0.18.0-W17-902"],
        "children": [],
    }

    should_block, msg = check_ana_spawn_consistency(content, fm, logger)

    assert should_block is False
    assert msg is None


# ---------------------------------------------------------------------------
# (n) 豁免宣告逐項扣抵（2026-08-23）
#
# 原實作對整段掃描豁免字串，命中即跳過全部計數——一行說明就能關閉整張票的
# 檢查。改為逐項扣抵後，豁免成本與規劃項數成正比。
# ---------------------------------------------------------------------------


def test_single_exemption_does_not_clear_two_planned_items(logger):
    """2 項規劃 + 1 則豁免宣告 + 0 項落地 → 剩餘 1 項仍硬擋。"""
    solution = (
        "無需建 ticket：第 2 項已由既有防護涵蓋。\n\n" + _TWO_ROW_SPAWN_TABLE
    )
    content = _make_content(solution)
    fm = {"id": "0.18.0-W17-979", "type": "ANA", "spawned_tickets": [], "children": []}

    should_block, msg = check_ana_spawn_consistency(content, fm, logger)

    assert should_block is True
    assert msg is not None
    # 扣抵後待落地數為 1（非原始的 2）
    assert "待落地 spawn 規劃數: 1" in msg


def test_exemption_declarations_matching_planned_count_clear_all(logger):
    """宣告數與規劃數相符時全數扣抵 → 放行。"""
    solution = (
        "無需建 ticket：第 1 項屬既有行為。\n"
        "無需建 ticket：第 2 項已由既有防護涵蓋。\n\n" + _TWO_ROW_SPAWN_TABLE
    )
    content = _make_content(solution)
    fm = {"id": "0.18.0-W17-978", "type": "ANA", "spawned_tickets": [], "children": []}

    should_block, msg = check_ana_spawn_consistency(content, fm, logger)

    assert should_block is False
    assert msg is None


def test_exemption_declaration_plus_one_landed_ticket_passes(logger):
    """1 則豁免宣告扣抵一項，剩餘一項有實際落地 → 放行。"""
    solution = "無需建 ticket：第 2 項屬既有行為。\n\n" + _TWO_ROW_SPAWN_TABLE
    content = _make_content(solution)
    fm = {
        "id": "0.18.0-W17-977",
        "type": "ANA",
        "spawned_tickets": ["0.18.0-W17-901"],
        "children": [],
    }

    should_block, msg = check_ana_spawn_consistency(content, fm, logger)

    assert should_block is False
    assert msg is None


def test_row_level_exemption_not_double_counted(logger):
    """行級豁免的表格行已排除於計數，不應再由宣告計數重複扣抵。

    表格內兩行皆帶行級豁免標記 → N_raw=0；若宣告計數也把表格行算進去，
    扣抵後仍為 0，此測試無法分辨。故第三行不帶豁免標記，驗證扣抵只發生一次：
    N_raw=1（僅第三行），無非表格宣告行 → 待落地 1 項，硬擋。
    """
    solution = (
        "### Spawn 規劃\n\n"
        "| # | Type | Priority | 標題 |\n"
        "|---|------|----------|------|\n"
        "| 1 | IMP | P1 | A（無需建 ticket：已涵蓋） |\n"
        "| 2 | DOC | P2 | B（無需建 ticket：已涵蓋） |\n"
        "| 3 | DOC | P2 | C |\n"
    )
    content = _make_content(solution)
    fm = {"id": "0.18.0-W17-976", "type": "ANA", "spawned_tickets": [], "children": []}

    should_block, msg = check_ana_spawn_consistency(content, fm, logger)

    assert should_block is True
    assert msg is not None
    assert "待落地 spawn 規劃數: 1" in msg


# ---------------------------------------------------------------------------
# (o) 阻擋訊息的修復指引必須可執行（2026-08-23）
# ---------------------------------------------------------------------------


def test_block_message_uses_existing_cli_entrypoint(logger):
    """阻擋訊息不得指向不存在的 `ticket track create` 子命令。

    `ticket track` 的合法子命令清單中沒有 create，建票入口是 `ticket create`。
    訊息指向不存在的指令時，依指引操作者會得到 INVALID_CHOICE。
    """
    content = _make_content(_TWO_ROW_SPAWN_TABLE)
    fm = {"id": "0.18.0-W17-975", "type": "ANA", "spawned_tickets": [], "children": []}

    should_block, msg = check_ana_spawn_consistency(content, fm, logger)

    assert should_block is True
    assert msg is not None
    assert "ticket track create" not in msg
    assert "ticket create --source-ticket" in msg
    # 第二條通道的兩個步驟皆須出現，避免只提登記不提 resolve
    assert "add-spawn-request" in msg
    assert "resolve-spawn-request" in msg
