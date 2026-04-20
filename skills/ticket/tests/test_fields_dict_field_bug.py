"""W10-086 regression test：set-* dict 欄位子欄位更新修復驗證。

Why: 修復前 execute_set_field 將 dict 型欄位（who/where/how）整個覆寫為 string，
導致後續 dict.get 操作 AttributeError（如 ticket create --parent 失敗）。
修復採 DICT_FIELD_SUBKEY 映射表分流 + _build_dict_field helper 降級復原。

測試 3 場景（AC 5 要求的 regression fixture）：
1. 原為完整 dict → 僅更新子欄位，其他 key 保留
2. 原為 string（壓扁後降級場景）→ 重建完整 dict 結構
3. 原為預設 string「待定義」（初始化場景）→ 升級為 dict 結構
"""

import argparse

import pytest
import yaml

from ticket_system.commands.fields import (
    DICT_FIELD_SUBKEY,
    _build_dict_field,
    execute_set_who,
    execute_set_where,
    execute_set_how,
)


def _create_ticket_file(tmp_path, ticket_id, version, **extra_fields):
    """建立測試用 Ticket 檔案，回傳檔案路徑。"""
    tickets_dir = tmp_path / "docs" / "work-logs" / f"v{version}" / "tickets"
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


def _make_args(ticket_id, value, version=None):
    """建立 argparse.Namespace mock。"""
    return argparse.Namespace(ticket_id=ticket_id, value=value, version=version)


def _load_frontmatter(ticket_path):
    """讀回 ticket frontmatter dict。"""
    content = ticket_path.read_text(encoding="utf-8")
    parts = content.split("---", 2)
    return yaml.safe_load(parts[1])


# ============================================================
# 單元測試：DICT_FIELD_SUBKEY 映射表 + _build_dict_field helper
# ============================================================


def test_dict_field_subkey_mapping_integrity():
    """映射表涵蓋 who/where/how 三個 dict 型欄位，子鍵正確。"""
    assert DICT_FIELD_SUBKEY == {
        "who": "current",
        "where": "layer",
        "how": "strategy",
    }


def test_build_dict_field_who_preserves_history():
    result = _build_dict_field("who", "current", "new-agent")
    assert result == {"current": "new-agent", "history": {}}


def test_build_dict_field_where_preserves_files():
    result = _build_dict_field("where", "layer", "Domain Layer")
    assert result == {"layer": "Domain Layer", "files": []}


def test_build_dict_field_how_preserves_task_type():
    result = _build_dict_field("how", "strategy", "新策略")
    assert result == {"task_type": "Implementation", "strategy": "新策略"}


# ============================================================
# 整合測試：3 fixture 場景（AC 5 核心驗證）
# ============================================================


def test_scenario_1_dict_to_subkey_update(tmp_path, monkeypatch):
    """場景 1：who 原為完整 dict，set-who 僅更新 current 保留 history。"""
    version = "1.0.0"
    ticket_id = f"{version}-W1-001"
    ticket_path = _create_ticket_file(
        tmp_path, ticket_id, version,
        who={"current": "agent-a", "history": {"phase1": "lavender"}},
    )

    monkeypatch.chdir(tmp_path)
    args = _make_args(ticket_id, "agent-b", version)
    result = execute_set_who(args, version)

    assert result == 0
    fm = _load_frontmatter(ticket_path)
    assert isinstance(fm["who"], dict), "who 必須保持 dict 結構"
    assert fm["who"]["current"] == "agent-b", "current 子欄位已更新"
    assert fm["who"]["history"] == {"phase1": "lavender"}, "history 子欄位保留"


def test_scenario_2_squashed_string_recovery(tmp_path, monkeypatch):
    """場景 2：where 已被壓扁為 string（降級），set-where 重建 dict 結構。"""
    version = "1.0.0"
    ticket_id = f"{version}-W1-002"
    ticket_path = _create_ticket_file(
        tmp_path, ticket_id, version,
        where="先前被 bug 壓扁後的 string",
    )

    monkeypatch.chdir(tmp_path)
    args = _make_args(ticket_id, "Domain Layer", version)
    result = execute_set_where(args, version)

    assert result == 0
    fm = _load_frontmatter(ticket_path)
    assert isinstance(fm["where"], dict), "where 必須重建為 dict"
    assert fm["where"]["layer"] == "Domain Layer", "layer 子欄位設為新值"
    assert fm["where"]["files"] == [], "files 子欄位建立為空 list"


def test_scenario_3_placeholder_string_init(tmp_path, monkeypatch):
    """場景 3：how 原為預設 string「待定義」（初始化），set-how 升級為 dict。"""
    version = "1.0.0"
    ticket_id = f"{version}-W1-003"
    ticket_path = _create_ticket_file(
        tmp_path, ticket_id, version,
        how="待定義",
    )

    monkeypatch.chdir(tmp_path)
    args = _make_args(ticket_id, "新策略說明", version)
    result = execute_set_how(args, version)

    assert result == 0
    fm = _load_frontmatter(ticket_path)
    assert isinstance(fm["how"], dict), "how 必須升級為 dict"
    assert fm["how"]["strategy"] == "新策略說明", "strategy 子欄位設為新值"
    assert fm["how"]["task_type"] == "Implementation", "task_type 預設為 Implementation"


# ============================================================
# 驗證非 dict 欄位不受影響（迴歸保護）
# ============================================================


def test_non_dict_field_unaffected(tmp_path, monkeypatch):
    """what 是 string 欄位，不在 DICT_FIELD_SUBKEY，設定邏輯維持原 string 覆寫。"""
    from ticket_system.commands.fields import execute_set_what

    version = "1.0.0"
    ticket_id = f"{version}-W1-004"
    ticket_path = _create_ticket_file(
        tmp_path, ticket_id, version,
        what="原標題",
    )

    monkeypatch.chdir(tmp_path)
    args = _make_args(ticket_id, "新標題", version)
    result = execute_set_what(args, version)

    assert result == 0
    fm = _load_frontmatter(ticket_path)
    assert fm["what"] == "新標題", "string 欄位應保持原邏輯，直接覆寫"
    assert not isinstance(fm["what"], dict), "string 欄位不應被誤轉為 dict"
