"""
parallel-suggestion-hook 測試套件（0.2.1-W3-233）

驗證：
1. extract_ticket_info() 回傳 dict 含 wave 欄位，既有欄位不受影響
2. main() 在繼續請求且無並行建議時不輸出 additionalContext；有並行建議時仍輸出
"""

import logging
from pathlib import Path
import importlib.util

import pytest

hooks_path = Path(__file__).parent.parent

# 動態導入 parallel-suggestion-hook（檔案名含 dash，需用 importlib）
hook_file = hooks_path / "parallel-suggestion-hook.py"
spec = importlib.util.spec_from_file_location("parallel_suggestion_hook", hook_file)
parallel_suggestion_hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parallel_suggestion_hook)


@pytest.fixture
def logger():
    return logging.getLogger("test")


def _write_ticket(tickets_dir: Path, filename: str, status: str, wave, extra: str = "") -> Path:
    ticket_file = tickets_dir / filename
    ticket_file.write_text(
        f"---\nid: {filename[:-3]}\nstatus: {status}\nwave: {wave}\n{extra}---\nContent",
        encoding="utf-8",
    )
    return ticket_file


# ============================================================================
# extract_ticket_info() 補 wave 欄位
# ============================================================================


def test_extract_ticket_info_includes_wave(tmp_path, logger):
    """驗證 extract_ticket_info() 回傳 dict 含 wave 欄位"""
    ticket_file = _write_ticket(tmp_path, "0.2.1-W3-999.md", "pending", 3)

    info = parallel_suggestion_hook.extract_ticket_info(ticket_file, logger)

    assert info is not None
    assert "wave" in info, "extract_ticket_info() 回傳缺少 wave 欄位"
    # 註：parse_ticket_frontmatter() 已改用 yaml.safe_load（0.2.1-W3-665.2），
    # 純量依 YAML 規範原生推斷型別，故 wave 欄位值為 int 3 而非字串 "3"。
    assert info["wave"] == 3


def test_extract_ticket_info_existing_fields_unaffected(tmp_path, logger):
    """驗證新增 wave 欄位不影響既有欄位"""
    ticket_file = _write_ticket(tmp_path, "0.2.1-W3-998.md", "in_progress", 3)

    info = parallel_suggestion_hook.extract_ticket_info(ticket_file, logger)

    assert info["id"] == "0.2.1-W3-998"
    assert info["status"] == "in_progress"
    assert info["type"] == "unknown"
    assert info["priority"] == "P2"


def test_extract_ticket_info_missing_wave_defaults_none(tmp_path, logger):
    """驗證無 wave frontmatter 時安全降級為 None"""
    ticket_file = tmp_path / "0.2.1-W3-997.md"
    ticket_file.write_text(
        "---\nid: 0.2.1-W3-997\nstatus: pending\n---\nContent",
        encoding="utf-8",
    )

    info = parallel_suggestion_hook.extract_ticket_info(ticket_file, logger)

    assert info["wave"] is None


# ============================================================================
# find_parallelizable_tickets()：seed_tickets（在飛票）納入衝突判定
# ============================================================================


def _make_ticket(ticket_id, files, blocked_by=""):
    return {
        "id": ticket_id,
        "path": Path(f"/tmp/{ticket_id}.md"),
        "status": "pending",
        "type": "IMP",
        "priority": "P1",
        "title": ticket_id,
        "blockedBy": blocked_by,
        "where_files": files,
        "where_layer": "",
        "chain": {},
        "wave": 3,
    }


def test_find_parallelizable_tickets_excludes_conflict_with_seed(logger):
    """在飛票（seed）存在時，並行建議不含與其檔案重疊的候選票"""
    pending = [
        _make_ticket("A", "lib/a.dart"),
        _make_ticket("B", "lib/b.dart"),
    ]
    seed = [_make_ticket("SEED", "lib/a.dart")]
    # SEED 本身狀態應為 in_progress，_make_ticket 預設 pending，這裡覆寫
    seed[0]["status"] = "in_progress"

    groups = parallel_suggestion_hook.find_parallelizable_tickets(
        pending, logger, seed_tickets=seed
    )

    # A 與在飛票 SEED 檔案重疊被排除，僅剩 B 一個候選（< 2 無法成組）
    assert groups == []


def test_find_parallelizable_tickets_seed_not_in_output_group(logger):
    """seed 本身不出現於回傳分組，僅作為排除依據"""
    pending = [
        _make_ticket("A", "lib/a.dart"),
        _make_ticket("B", "lib/b.dart"),
        _make_ticket("C", "lib/c.dart"),
    ]
    seed = [_make_ticket("SEED", "lib/a.dart")]
    seed[0]["status"] = "in_progress"

    groups = parallel_suggestion_hook.find_parallelizable_tickets(
        pending, logger, seed_tickets=seed
    )

    assert groups, "B 與 C 檔案無重疊，且皆與 seed 無重疊，應可並行"
    all_ids = {t["id"] for group in groups for t in group}
    assert "SEED" not in all_ids
    assert "A" not in all_ids
    assert {"B", "C"} <= all_ids


def test_find_parallelizable_tickets_no_seed_unaffected(logger):
    """無 seed_tickets（預設 None）時行為與既有邏輯一致"""
    pending = [
        _make_ticket("A", "lib/a.dart"),
        _make_ticket("B", "lib/b.dart"),
    ]

    groups = parallel_suggestion_hook.find_parallelizable_tickets(pending, logger)

    assert len(groups) == 1
    assert {t["id"] for t in groups[0]} == {"A", "B"}


# ============================================================================
# where.files 讀寫意圖判定改 import ticket_system 共用實作
# ============================================================================


def test_filter_write_files_uses_shared_parse_file_intent():
    """驗證 _filter_write_files 透過共用 parse_file_intent 正確過濾 ::read 標記"""
    files = {"lib/a.dart::read", "lib/b.dart::write", "lib/c.dart"}
    ticket_info = {"type": "IMP"}

    result = parallel_suggestion_hook._filter_write_files(files, ticket_info)

    assert result == {"lib/b.dart", "lib/c.dart"}


def test_filter_write_files_ana_default_read():
    """驗證 ANA 型別未標記路徑預設 read，故被過濾（同 file_conflict._default_intent）"""
    files = {"lib/a.dart", "lib/b.dart::write"}
    ticket_info = {"type": "ANA"}

    result = parallel_suggestion_hook._filter_write_files(files, ticket_info)

    assert result == {"lib/b.dart"}


# ============================================================================
# extract_ticket_files()：現行巢狀 where.files schema（0.2.1-W3-883）
#
# 修復前 extract_ticket_files 僅讀平面鍵 frontmatter["where_files"]，現行
# schema 為巢狀 where: {files: [...]}，平面鍵恆為空，優先路徑永遠落入
# extract_ticket_info() 從未寫入巢狀 where 的舊行為，故此處同時涵蓋
# extract_ticket_info() 是否正確保留巢狀 dict，以及 extract_ticket_files()
# 是否優先採用巢狀路徑。
# ============================================================================


def test_extract_ticket_info_preserves_nested_where_dict(tmp_path, logger):
    """驗證 extract_ticket_info() 回傳 dict 保留巢狀 where.files（非空平面鍵）"""
    ticket_file = tmp_path / "0.2.1-W3-996.md"
    ticket_file.write_text(
        "---\nid: 0.2.1-W3-996\nstatus: pending\nwhere:\n  files:\n"
        "  - lib/a.dart\n  - lib/b.dart\n---\nContent",
        encoding="utf-8",
    )

    info = parallel_suggestion_hook.extract_ticket_info(ticket_file, logger)

    assert info["where"] == {"files": ["lib/a.dart", "lib/b.dart"]}
    # 平面鍵在現行 schema 下恆為空字串（未提供 frontmatter["where_files"]）
    assert info["where_files"] == ""


def test_extract_ticket_files_reads_nested_where_files(tmp_path, logger):
    """驗證 extract_ticket_files() 對現行巢狀 where.files schema 正確抽取寫入檔案集合"""
    ticket_file = tmp_path / "0.2.1-W3-995.md"
    ticket_file.write_text(
        "---\nid: 0.2.1-W3-995\nstatus: pending\ntype: IMP\nwhere:\n  files:\n"
        "  - lib/a.dart\n  - lib/b.dart\n---\nContent",
        encoding="utf-8",
    )
    info = parallel_suggestion_hook.extract_ticket_info(ticket_file, logger)

    files = parallel_suggestion_hook.extract_ticket_files(info, logger)

    assert files == {"lib/a.dart", "lib/b.dart"}


def test_extract_ticket_files_nested_where_respects_read_intent(tmp_path, logger):
    """驗證巢狀 where.files 路徑仍套用讀寫意圖標記（::read 排除、ANA 預設 read）"""
    ticket_file = tmp_path / "0.2.1-W3-994.md"
    ticket_file.write_text(
        "---\nid: 0.2.1-W3-994\nstatus: pending\ntype: ANA\nwhere:\n  files:\n"
        "  - lib/a.dart\n  - lib/b.dart::write\n---\nContent",
        encoding="utf-8",
    )
    info = parallel_suggestion_hook.extract_ticket_info(ticket_file, logger)

    files = parallel_suggestion_hook.extract_ticket_files(info, logger)

    # ANA 型別未標記路徑預設 read 被過濾，僅保留逐檔標記 ::write 的路徑
    assert files == {"lib/b.dart"}


# ============================================================================
# main()：繼續請求的輸出（無並行建議不輸出提醒；有並行建議仍輸出）
# ============================================================================


def _run_main(monkeypatch, capsys, parallel_groups):
    """以 stub 掃描結果執行 main()，回傳解析後的 hook 輸出 JSON"""
    import json

    ticket = {"id": "T-1", "status": "pending", "wave": 1, "chain": {"root": "R"}}
    hook = parallel_suggestion_hook
    monkeypatch.setattr(hook, "read_json_from_stdin", lambda logger: {"prompt": "繼續"})
    monkeypatch.setattr(hook, "find_ticket_files", lambda root, logger=None: [Path("a.md")])
    monkeypatch.setattr(hook, "extract_ticket_info", lambda f, logger: ticket)
    monkeypatch.setattr(hook, "find_latest_completed_ticket_root", lambda t, logger: "R")
    monkeypatch.setattr(hook, "find_pending_tickets_in_chain", lambda r, t, logger: [ticket])
    monkeypatch.setattr(
        hook, "find_parallelizable_tickets", lambda p, logger, seed_tickets=None: parallel_groups
    )
    monkeypatch.setattr(
        hook, "generate_parallel_suggestion_report", lambda g, p, logger: "PARALLEL_SUGGESTION"
    )
    monkeypatch.setattr(hook, "save_analysis_log", lambda *a, **k: None)
    assert hook.main() == 0
    return json.loads(capsys.readouterr().out)


def test_continuation_without_parallel_suggestion_has_no_additional_context(monkeypatch, capsys):
    """繼續請求且無並行建議時，輸出不含 additionalContext"""
    output = _run_main(monkeypatch, capsys, parallel_groups=[])

    assert "additionalContext" not in output["hookSpecificOutput"]


def test_continuation_with_parallel_tickets_still_outputs_suggestion(monkeypatch, capsys):
    """正向對照：任務鏈有可並行 pending 票時仍輸出並行建議"""
    output = _run_main(monkeypatch, capsys, parallel_groups=[[{"id": "T-1"}]])

    assert output["hookSpecificOutput"]["additionalContext"] == "PARALLEL_SUGGESTION"
