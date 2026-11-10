"""error-pattern 來源前綴 ID 分配器測試（1.0.0-W1-019.3）。

allocator 程式碼自包含於 .claude/skills/error-pattern/lib/allocator.py；
測試暫借 hooks pytest env 執行（skill 完整 package 化屬 W1-001 上架範圍）。

驗證：
- identify_project_code：git toplevel basename 對應 registry dir → code
- allocate_pattern_id：掃 <CAT>-<PROJ>-*.md 取 max+1，flat base 不參與遞增
- allocate_pattern_id 的 ticket 文字引用掃描（0.2.1-W3-167，封閉 W3-165/W3-150
  型撞號：ticket 已預留但檔案未建立的編號）
- allocate_and_reserve_pattern_id：持鎖 + 原子建立佔位檔（0.2.1-W3-167，封閉
  框架 issue 28 TOCTOU：並行呼叫不撞號）
"""

import sys
import threading
from pathlib import Path

import pytest

_skill_lib = (
    Path(__file__).resolve().parent.parent.parent
    / "skills"
    / "error-pattern"
    / "lib"
)
if str(_skill_lib) not in sys.path:
    sys.path.insert(0, str(_skill_lib))

from allocator import (  # noqa: E402
    allocate_and_reserve_pattern_id,
    allocate_pattern_id,
    identify_project_code,
)

_REGISTRY = """\
projects:
  - code: V1
    dir: book_overview_v1
  - code: APP
    dir: book_overview_app
reserved_codes: []
"""


def _write_registry(claude_dir: Path) -> Path:
    ep = claude_dir / "error-patterns"
    ep.mkdir(parents=True, exist_ok=True)
    reg = ep / "_project-registry.yaml"
    reg.write_text(_REGISTRY, encoding="utf-8")
    return reg


def _touch_pc(claude_dir: Path, category_dir: str, filename: str) -> None:
    d = claude_dir / "error-patterns" / category_dir
    d.mkdir(parents=True, exist_ok=True)
    (d / filename).write_text("# stub\n", encoding="utf-8")


def _write_ticket(project_root: Path, ticket_name: str, body: str) -> Path:
    """在 `{project_root}/docs/work-logs/.../tickets/` 下建立一個 ticket md 檔。"""
    d = project_root / "docs" / "work-logs" / "v0" / "tickets"
    d.mkdir(parents=True, exist_ok=True)
    path = d / ticket_name
    path.write_text(body, encoding="utf-8")
    return path


# --- identify_project_code ---


def test_identify_known_project(tmp_path):
    claude_dir = tmp_path / ".claude"
    reg = _write_registry(claude_dir)
    repo = tmp_path / "book_overview_v1"
    assert identify_project_code(reg, repo) == "V1"


def test_identify_other_project(tmp_path):
    claude_dir = tmp_path / ".claude"
    reg = _write_registry(claude_dir)
    repo = tmp_path / "book_overview_app"
    assert identify_project_code(reg, repo) == "APP"


def test_identify_unknown_project_raises(tmp_path):
    claude_dir = tmp_path / ".claude"
    reg = _write_registry(claude_dir)
    repo = tmp_path / "some_unregistered_repo"
    with pytest.raises(Exception):
        identify_project_code(reg, repo)


# --- allocate_pattern_id ---


def test_first_allocation_starts_001(tmp_path):
    """無既有前綴 PC → 首次分配 001。"""
    claude_dir = tmp_path / ".claude"
    _write_registry(claude_dir)
    assert allocate_pattern_id("PC", claude_dir, "V1") == "PC-V1-001"


def test_increments_from_max(tmp_path):
    """既有 PC-V1-001 / PC-V1-003 → 下一號 004（取 max+1，非 count+1）。"""
    claude_dir = tmp_path / ".claude"
    _write_registry(claude_dir)
    _touch_pc(claude_dir, "process-compliance", "PC-V1-001-foo.md")
    _touch_pc(claude_dir, "process-compliance", "PC-V1-003-bar.md")
    assert allocate_pattern_id("PC", claude_dir, "V1") == "PC-V1-004"


def test_flat_base_not_counted(tmp_path):
    """flat 凍結 base（PC-099）不參與前綴遞增。"""
    claude_dir = tmp_path / ".claude"
    _write_registry(claude_dir)
    _touch_pc(claude_dir, "process-compliance", "PC-099-legacy.md")
    _touch_pc(claude_dir, "process-compliance", "PC-180-legacy.md")
    assert allocate_pattern_id("PC", claude_dir, "V1") == "PC-V1-001"


def test_other_project_prefix_isolated(tmp_path):
    """不同專案前綴命名空間隔離：APP 的號不影響 V1 遞增。"""
    claude_dir = tmp_path / ".claude"
    _write_registry(claude_dir)
    _touch_pc(claude_dir, "process-compliance", "PC-APP-005-x.md")
    assert allocate_pattern_id("PC", claude_dir, "V1") == "PC-V1-001"


def test_category_prefix_mapping(tmp_path):
    """category 前綴對應正確目錄（IMP → implementation）。"""
    claude_dir = tmp_path / ".claude"
    _write_registry(claude_dir)
    _touch_pc(claude_dir, "implementation", "IMP-V1-002-x.md")
    assert allocate_pattern_id("IMP", claude_dir, "V1") == "IMP-V1-003"


def test_unknown_category_raises(tmp_path):
    claude_dir = tmp_path / ".claude"
    _write_registry(claude_dir)
    with pytest.raises(Exception):
        allocate_pattern_id("BOGUS", claude_dir, "V1")


# --- allocate_pattern_id：ticket 文字引用掃描（0.2.1-W3-167 原始範圍） ---


def test_skips_number_reserved_in_ticket_title_not_yet_filed(tmp_path):
    """重現 0.2.1-W3-165/W3-150：ticket 標題已預留 IMP-V1-005 但檔案未建，
    下一次配號須跳過 005（不可再發出撞號的 005）。"""
    claude_dir = tmp_path / ".claude"
    _write_registry(claude_dir)
    _write_ticket(
        tmp_path,
        "0.1-W1-150.md",
        "---\ntitle: 記錄 IMP-V1-005 某個問題\n---\n\n" "what: 記錄 IMP-V1-005 某個問題\n",
    )
    # 無任何 IMP-V1-*.md 檔案存在，純檔案掃描會誤配 IMP-V1-001。
    assert allocate_pattern_id("IMP", claude_dir, "V1") == "IMP-V1-006"


def test_ticket_reference_merges_with_file_scan_max(tmp_path):
    """檔案 max（003）與 ticket 引用 max（005）取較大者 +1。"""
    claude_dir = tmp_path / ".claude"
    _write_registry(claude_dir)
    _touch_pc(claude_dir, "implementation", "IMP-V1-003-x.md")
    _write_ticket(tmp_path, "0.1-W1-150.md", "what: 記錄 IMP-V1-005 某問題\n")
    assert allocate_pattern_id("IMP", claude_dir, "V1") == "IMP-V1-006"


def test_ignores_flat_and_other_project_refs_in_tickets(tmp_path):
    """精確前綴過濾：flat 格式（PC-048）與其他專案前綴（IMP-APP-999）的討論文字
    不應被誤判為本專案（V1）的預留編號（對應真實 repo 稽核發現的誤判樣態）。"""
    claude_dir = tmp_path / ".claude"
    _write_registry(claude_dir)
    _write_ticket(
        tmp_path,
        "0.1-W1-099.md",
        "移除死連結列 PC-048 / PC-049，另見 IMP-APP-999 的歷史討論。\n",
    )
    assert allocate_pattern_id("PC", claude_dir, "V1") == "PC-V1-001"
    assert allocate_pattern_id("IMP", claude_dir, "V1") == "IMP-V1-001"


def test_tickets_root_false_disables_ticket_scan(tmp_path):
    """tickets_root=False 顯式停用掃描，回到純檔案掃描行為。"""
    claude_dir = tmp_path / ".claude"
    _write_registry(claude_dir)
    _write_ticket(tmp_path, "0.1-W1-150.md", "what: 記錄 IMP-V1-005 某問題\n")
    assert allocate_pattern_id("IMP", claude_dir, "V1", tickets_root=False) == "IMP-V1-001"


def test_missing_tickets_dir_graceful(tmp_path):
    """無 docs/work-logs 目錄時不丟例外，行為等同純檔案掃描。"""
    claude_dir = tmp_path / ".claude"
    _write_registry(claude_dir)
    assert allocate_pattern_id("IMP", claude_dir, "V1") == "IMP-V1-001"


# --- allocate_and_reserve_pattern_id：原子建立佔位檔 + 鎖（issue 28 併入範圍） ---


def test_reserve_creates_stub_file_with_reserved_status(tmp_path):
    claude_dir = tmp_path / ".claude"
    _write_registry(claude_dir)
    stub = allocate_and_reserve_pattern_id("IMP", claude_dir, "V1", reserved_by="tester")
    assert stub.name == "IMP-V1-001.md"
    assert stub.is_file()
    text = stub.read_text(encoding="utf-8")
    assert "status: reserved" in text
    assert "reserved_by: tester" in text


def test_reserve_sequential_calls_increment(tmp_path):
    """連續呼叫 allocate_and_reserve_pattern_id 各自建立佔位檔，編號遞增不重複。"""
    claude_dir = tmp_path / ".claude"
    _write_registry(claude_dir)
    first = allocate_and_reserve_pattern_id("IMP", claude_dir, "V1")
    second = allocate_and_reserve_pattern_id("IMP", claude_dir, "V1")
    assert first.name == "IMP-V1-001.md"
    assert second.name == "IMP-V1-002.md"


def test_reserve_respects_pending_ticket_reference(tmp_path):
    """原子保留亦納入 ticket 文字預留編號（與 allocate_pattern_id 同一 max 計算）。"""
    claude_dir = tmp_path / ".claude"
    _write_registry(claude_dir)
    _write_ticket(tmp_path, "0.1-W1-150.md", "what: 記錄 IMP-V1-005 某問題\n")
    stub = allocate_and_reserve_pattern_id("IMP", claude_dir, "V1")
    assert stub.name == "IMP-V1-006.md"


def test_reserve_concurrent_threads_no_duplicate_ids(tmp_path):
    """真實並行呼叫（threading + barrier 強制同時起跑）：N 個 thread 同時搶配號，
    佔位檔數與回傳 ID 集合皆須等於 N，不可出現重複編號（0.2.1-W3-167 acceptance
    #4，重現框架 issue 28 的 TOCTOU 場景並驗證鎖已封閉該競爭）。"""
    claude_dir = tmp_path / ".claude"
    _write_registry(claude_dir)

    n_workers = 12
    barrier = threading.Barrier(n_workers)
    results = [None] * n_workers
    errors = []

    def _worker(idx):
        try:
            barrier.wait(timeout=5)
            path = allocate_and_reserve_pattern_id(
                "IMP", claude_dir, "V1", tickets_root=False, reserved_by=f"worker-{idx}"
            )
            results[idx] = path.name
        except Exception as exc:  # pragma: no cover - 失敗即由下方斷言攔截並失敗
            errors.append(exc)

    threads = [threading.Thread(target=_worker, args=(i,)) for i in range(n_workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert not errors, f"worker 執行期間發生例外：{errors}"
    assert None not in results, "有 worker 未完成配號"
    assert len(set(results)) == n_workers, f"出現重複編號：{results}"

    cat_dir = claude_dir / "error-patterns" / "implementation"
    stub_files = sorted(p.name for p in cat_dir.glob("IMP-V1-*.md"))
    assert len(stub_files) == n_workers
    assert set(stub_files) == set(results)
