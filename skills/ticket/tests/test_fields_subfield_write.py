"""W1-009 regression test：set-who/set-where/set-how 子欄位寫入路徑。

Why: 0.0.1-W1-008 WRAP 決策方案 C 確認三個 set-* 子命令僅接受位置參數整體覆寫，
不接受 --layer/--files/--current/--task-type/--strategy 等子欄位 flag，
使用者嘗試這些 flag 會得 `unrecognized arguments`。本測試涵蓋：

1. Parser 層：新 flag 確實已註冊、可被解析（不再 unrecognized arguments）
2. 執行層：子欄位寫入正確更新對應 key，其餘 key 保留
3. 既有整體寫入路徑（value 位置參數）未回歸
4. 兩者皆未提供時的錯誤處理
"""

import argparse

import pytest
import yaml

from ticket_system.commands.fields import (
    _get_str_arg,
    _parse_comma_list,
    execute_set_who,
    execute_set_where,
    execute_set_how,
)
from ticket_system.commands.track import register as track_register


# ============================================================
# Parser 層：flag 註冊驗證（AC 1-3 的前置條件——flag 必須可被解析）
# ============================================================


def _build_parser():
    """建立獨立的頂層 parser 並掛載 track 子命令（不觸發全域 CLI 副作用）。"""
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")
    track_register(subparsers)
    return parser


def test_set_who_parser_accepts_current_flag():
    """set-who 接受 --current，且省略 value 時不報錯（nargs='?'）。"""
    parser = _build_parser()
    args = parser.parse_args(["track", "set-who", "0.1.0-W1-001", "--current", "sage"])
    assert args.current == "sage"
    assert args.value is None


def test_set_where_parser_accepts_layer_and_files_flags():
    """set-where 接受 --layer 與 --files，且可省略 value。"""
    parser = _build_parser()
    args = parser.parse_args([
        "track", "set-where", "0.1.0-W1-001",
        "--layer", "Domain", "--files", ".claude/hooks/a.py,.claude/lib/b.py",
    ])
    assert args.layer == "Domain"
    assert args.files == ".claude/hooks/a.py,.claude/lib/b.py"
    assert args.value is None


def test_set_how_parser_accepts_task_type_and_strategy_flags():
    """set-how 接受 --task-type 與 --strategy，且可省略 value。"""
    parser = _build_parser()
    args = parser.parse_args([
        "track", "set-how", "0.1.0-W1-001",
        "--task-type", "Analysis", "--strategy", "先分析後實作",
    ])
    assert args.task_type == "Analysis"
    assert args.strategy == "先分析後實作"
    assert args.value is None


def test_set_where_positional_value_still_parses_alone():
    """既有整體寫入語意保留：僅提供位置參數 value 時仍可正常解析。"""
    parser = _build_parser()
    args = parser.parse_args(["track", "set-where", "0.1.0-W1-001", "lib/commands/"])
    assert args.value == "lib/commands/"
    assert args.layer is None
    assert args.files is None


def test_set_who_positional_value_still_parses_alone():
    """既有整體寫入語意保留：set-who 僅提供位置參數 value 時仍可正常解析。"""
    parser = _build_parser()
    args = parser.parse_args(["track", "set-who", "0.1.0-W1-001", "parsley-flutter-developer"])
    assert args.value == "parsley-flutter-developer"
    assert args.current is None


# ============================================================
# 單元測試：_get_str_arg / _parse_comma_list 輔助函式
# ============================================================


def test_get_str_arg_returns_none_when_missing():
    args = argparse.Namespace(ticket_id="x")
    assert _get_str_arg(args, "current") is None


def test_get_str_arg_returns_none_when_explicitly_none():
    args = argparse.Namespace(current=None)
    assert _get_str_arg(args, "current") is None


def test_get_str_arg_returns_value_when_string():
    args = argparse.Namespace(current="sage")
    assert _get_str_arg(args, "current") == "sage"


def test_get_str_arg_filters_non_string_mock_autovivified_attribute():
    """Mock() 自動生成的屬性（非字串）必須被視為未提供（測試相容性防護）。"""
    from unittest.mock import Mock

    args = Mock()
    args.value = "既有整體寫入值"
    # args.current 未顯式設定，Mock() 會自動生成非 None 的子 Mock
    assert _get_str_arg(args, "current") is None


def test_parse_comma_list_strips_whitespace():
    assert _parse_comma_list(" a.py, b.py ,c.py") == ["a.py", "b.py", "c.py"]


def test_parse_comma_list_empty_string_returns_empty_list():
    assert _parse_comma_list("") == []


# ============================================================
# 整合測試 fixtures（同 test_fields_dict_field_bug.py 模式）
# ============================================================


def _create_ticket_file(tmp_path, ticket_id, version, **extra_fields):
    tickets_dir = (
        tmp_path / "docs" / "work-logs"
        / f"v{version.split('.')[0]}"
        / f"v{'.'.join(version.split('.')[:2])}"
        / f"v{version}" / "tickets"
    )
    tickets_dir.mkdir(parents=True)

    frontmatter = {
        "id": ticket_id,
        "title": "Test",
        "type": "IMP",
        "status": "in_progress",
        "version": version,
        "wave": 1,
        "priority": "P2",
    }
    frontmatter.update(extra_fields)

    ticket_path = tickets_dir / f"{ticket_id}.md"
    content = "---\n" + yaml.dump(frontmatter, allow_unicode=True, default_flow_style=False) + "---\n\n# Execution Log\n"
    ticket_path.write_text(content, encoding="utf-8")
    return ticket_path


def _load_frontmatter(ticket_path):
    content = ticket_path.read_text(encoding="utf-8")
    parts = content.split("---", 2)
    return yaml.safe_load(parts[1])


def _setup_env(tmp_path, monkeypatch):
    """統一測試環境：chdir + CLAUDE_PROJECT_DIR override（同 W10-086 測試模式）。"""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))


def _make_args(ticket_id, version=None, value=None, **flags):
    """建立 argparse.Namespace，模擬 parser 產出的 args（未提供的子欄位 flag 為 None）。"""
    base = {"ticket_id": ticket_id, "value": value, "version": version}
    base.update(flags)
    return argparse.Namespace(**base)


# ============================================================
# 整合測試：set-who --current
# ============================================================


def test_execute_set_who_current_only_preserves_history(tmp_path, monkeypatch):
    """--current 單獨提供：僅更新 current，history 保留，value 未回歸寫入。"""
    version = "1.0.0"
    ticket_id = f"{version}-W1-201"
    ticket_path = _create_ticket_file(
        tmp_path, ticket_id, version,
        who={"current": "agent-a", "history": {"phase1": "agent-a"}},
    )
    _setup_env(tmp_path, monkeypatch)

    args = _make_args(ticket_id, version, current="agent-b")
    result = execute_set_who(args, version)

    assert result == 0
    fm = _load_frontmatter(ticket_path)
    assert fm["who"]["current"] == "agent-b"
    assert fm["who"]["history"] == {"phase1": "agent-a"}


def test_execute_set_who_neither_value_nor_current_errors(tmp_path, monkeypatch):
    """value 與 --current 皆未提供：回傳錯誤，不寫入檔案。"""
    version = "1.0.0"
    ticket_id = f"{version}-W1-202"
    ticket_path = _create_ticket_file(
        tmp_path, ticket_id, version,
        who={"current": "agent-a", "history": {}},
    )
    _setup_env(tmp_path, monkeypatch)

    args = _make_args(ticket_id, version)
    result = execute_set_who(args, version)

    assert result == 1
    fm = _load_frontmatter(ticket_path)
    assert fm["who"]["current"] == "agent-a", "錯誤路徑不應變更既有值"


# ============================================================
# 整合測試：set-where --layer / --files
# ============================================================


def test_execute_set_where_layer_only_preserves_files(tmp_path, monkeypatch):
    """--layer 單獨提供：僅更新 layer，files 保留（不觸發 value 路徑型同步啟發式）。"""
    version = "1.0.0"
    ticket_id = f"{version}-W1-203"
    ticket_path = _create_ticket_file(
        tmp_path, ticket_id, version,
        where={"layer": "舊層級", "files": [".claude/hooks/keep.py"]},
    )
    _setup_env(tmp_path, monkeypatch)

    args = _make_args(ticket_id, version, layer="Domain Layer")
    result = execute_set_where(args, version)

    assert result == 0
    fm = _load_frontmatter(ticket_path)
    assert fm["where"]["layer"] == "Domain Layer"
    assert fm["where"]["files"] == [".claude/hooks/keep.py"]


def test_execute_set_where_files_only_preserves_layer(tmp_path, monkeypatch):
    """--files 單獨提供：僅更新 files（逗號解析成清單），layer 保留。"""
    version = "1.0.0"
    ticket_id = f"{version}-W1-204"
    ticket_path = _create_ticket_file(
        tmp_path, ticket_id, version,
        where={"layer": "Domain Layer", "files": ["stale/old.py"]},
    )
    _setup_env(tmp_path, monkeypatch)

    args = _make_args(ticket_id, version, files=".claude/hooks/a.py, .claude/lib/b.py")
    result = execute_set_where(args, version)

    assert result == 0
    fm = _load_frontmatter(ticket_path)
    assert fm["where"]["layer"] == "Domain Layer"
    assert fm["where"]["files"] == [".claude/hooks/a.py", ".claude/lib/b.py"]


def test_execute_set_where_layer_and_files_combined(tmp_path, monkeypatch):
    """--layer 與 --files 合併提供：兩子欄位皆依明確輸入更新。"""
    version = "1.0.0"
    ticket_id = f"{version}-W1-205"
    ticket_path = _create_ticket_file(
        tmp_path, ticket_id, version,
        where={"layer": "舊層級", "files": ["stale/old.py"]},
    )
    _setup_env(tmp_path, monkeypatch)

    args = _make_args(
        ticket_id, version,
        layer="Infrastructure", files=".claude/skills/ticket/commands",
    )
    result = execute_set_where(args, version)

    assert result == 0
    fm = _load_frontmatter(ticket_path)
    assert fm["where"]["layer"] == "Infrastructure"
    assert fm["where"]["files"] == [".claude/skills/ticket/commands"]


def test_execute_set_where_flattened_string_rebuilds_dict_via_subfield(tmp_path, monkeypatch):
    """where 已被壓扁為 string 時，子欄位路徑仍能重建 dict 結構（沿用預設值）。"""
    version = "1.0.0"
    ticket_id = f"{version}-W1-206"
    ticket_path = _create_ticket_file(
        tmp_path, ticket_id, version,
        where="先前被壓扁的 string",
    )
    _setup_env(tmp_path, monkeypatch)

    args = _make_args(ticket_id, version, layer="Domain")
    result = execute_set_where(args, version)

    assert result == 0
    fm = _load_frontmatter(ticket_path)
    assert isinstance(fm["where"], dict)
    assert fm["where"]["layer"] == "Domain"
    assert fm["where"]["files"] == []


def test_execute_set_where_neither_value_nor_subfields_errors(tmp_path, monkeypatch):
    """value、--layer、--files 皆未提供：回傳錯誤，不寫入檔案。"""
    version = "1.0.0"
    ticket_id = f"{version}-W1-207"
    ticket_path = _create_ticket_file(
        tmp_path, ticket_id, version,
        where={"layer": "舊層級", "files": ["a.py"]},
    )
    _setup_env(tmp_path, monkeypatch)

    args = _make_args(ticket_id, version)
    result = execute_set_where(args, version)

    assert result == 1
    fm = _load_frontmatter(ticket_path)
    assert fm["where"]["layer"] == "舊層級"


# ============================================================
# 整合測試：set-how --task-type / --strategy
# ============================================================


def test_execute_set_how_task_type_only_preserves_strategy(tmp_path, monkeypatch):
    """--task-type 單獨提供：僅更新 task_type，strategy 保留。"""
    version = "1.0.0"
    ticket_id = f"{version}-W1-208"
    ticket_path = _create_ticket_file(
        tmp_path, ticket_id, version,
        how={"task_type": "Implementation", "strategy": "舊策略"},
    )
    _setup_env(tmp_path, monkeypatch)

    args = _make_args(ticket_id, version, task_type="Analysis")
    result = execute_set_how(args, version)

    assert result == 0
    fm = _load_frontmatter(ticket_path)
    assert fm["how"]["task_type"] == "Analysis"
    assert fm["how"]["strategy"] == "舊策略"


def test_execute_set_how_strategy_only_preserves_task_type(tmp_path, monkeypatch):
    """--strategy 單獨提供：僅更新 strategy，task_type 保留。"""
    version = "1.0.0"
    ticket_id = f"{version}-W1-209"
    ticket_path = _create_ticket_file(
        tmp_path, ticket_id, version,
        how={"task_type": "Analysis", "strategy": "舊策略"},
    )
    _setup_env(tmp_path, monkeypatch)

    args = _make_args(ticket_id, version, strategy="新策略")
    result = execute_set_how(args, version)

    assert result == 0
    fm = _load_frontmatter(ticket_path)
    assert fm["how"]["strategy"] == "新策略"
    assert fm["how"]["task_type"] == "Analysis"


def test_execute_set_how_both_subfields_combined(tmp_path, monkeypatch):
    """--task-type 與 --strategy 合併提供：兩子欄位皆更新。"""
    version = "1.0.0"
    ticket_id = f"{version}-W1-210"
    ticket_path = _create_ticket_file(
        tmp_path, ticket_id, version,
        how={"task_type": "Implementation", "strategy": "舊策略"},
    )
    _setup_env(tmp_path, monkeypatch)

    args = _make_args(ticket_id, version, task_type="Dispatch", strategy="派發後驗收")
    result = execute_set_how(args, version)

    assert result == 0
    fm = _load_frontmatter(ticket_path)
    assert fm["how"]["task_type"] == "Dispatch"
    assert fm["how"]["strategy"] == "派發後驗收"


def test_execute_set_how_neither_value_nor_subfields_errors(tmp_path, monkeypatch):
    """value、--task-type、--strategy 皆未提供：回傳錯誤，不寫入檔案。"""
    version = "1.0.0"
    ticket_id = f"{version}-W1-211"
    ticket_path = _create_ticket_file(
        tmp_path, ticket_id, version,
        how={"task_type": "Implementation", "strategy": "舊策略"},
    )
    _setup_env(tmp_path, monkeypatch)

    args = _make_args(ticket_id, version)
    result = execute_set_how(args, version)

    assert result == 1
    fm = _load_frontmatter(ticket_path)
    assert fm["how"]["strategy"] == "舊策略"


# ============================================================
# 回歸測試：既有整體寫入路徑（value 位置參數）不受影響
# ============================================================


def test_execute_set_who_value_only_unchanged_legacy_behavior(tmp_path, monkeypatch):
    """僅提供 value（無 --current）：延續既有整體覆寫至 current 子欄位的行為。"""
    version = "1.0.0"
    ticket_id = f"{version}-W1-212"
    ticket_path = _create_ticket_file(
        tmp_path, ticket_id, version,
        who={"current": "agent-a", "history": {"t0": "agent-a"}},
    )
    _setup_env(tmp_path, monkeypatch)

    args = _make_args(ticket_id, version, value="agent-c")
    result = execute_set_who(args, version)

    assert result == 0
    fm = _load_frontmatter(ticket_path)
    assert fm["who"]["current"] == "agent-c"
    assert fm["who"]["history"] == {"t0": "agent-a"}


def test_execute_set_where_value_only_still_syncs_files(tmp_path, monkeypatch):
    """僅提供 value（無 --layer/--files）：延續 W1-078 路徑型輸入同步 files 行為。"""
    version = "1.0.0"
    ticket_id = f"{version}-W1-213"
    ticket_path = _create_ticket_file(
        tmp_path, ticket_id, version,
        where={"layer": "待定義", "files": ["stale/old.py"]},
    )
    _setup_env(tmp_path, monkeypatch)

    value = ".claude/hooks/a.py,.claude/lib/b.py"
    args = _make_args(ticket_id, version, value=value)
    result = execute_set_where(args, version)

    assert result == 0
    fm = _load_frontmatter(ticket_path)
    assert fm["where"]["layer"] == value
    assert fm["where"]["files"] == [".claude/hooks/a.py", ".claude/lib/b.py"]


def test_execute_set_how_value_only_unchanged_legacy_behavior(tmp_path, monkeypatch):
    """僅提供 value（無 --task-type/--strategy）：延續既有整體覆寫至 strategy 子欄位的行為。"""
    version = "1.0.0"
    ticket_id = f"{version}-W1-214"
    ticket_path = _create_ticket_file(
        tmp_path, ticket_id, version,
        how={"task_type": "Analysis", "strategy": "舊策略"},
    )
    _setup_env(tmp_path, monkeypatch)

    args = _make_args(ticket_id, version, value="新策略說明")
    result = execute_set_how(args, version)

    assert result == 0
    fm = _load_frontmatter(ticket_path)
    assert fm["how"]["strategy"] == "新策略說明"
    assert fm["how"]["task_type"] == "Analysis"
