"""W1-078 regression test：set-where 路徑型輸入同步更新 where.files。

Why: 修復前 set-where 僅更新 where.layer，where.files 保留 stale 值；
agent-dispatch-validation-hook 以 where.files 為 scope source of truth
（L3 純 .claude/ 覆蓋），stale 值導致 dispatch 誤擋（W1-061.1 三次派發失敗實證）。

修復設計：路徑型輸入（所有逗號分隔項目皆含 /）同步覆寫 where.files；
描述性輸入（如 "Domain Layer"）僅更新 layer、不污染 files——
非路徑項目混入 files 會使 dispatch hook has_other=True，破壞 L3 分類。
"""

import argparse

import yaml

from ticket_system.commands.fields import (
    _parse_where_path_entries,
    execute_set_where,
)


def _create_ticket_file(tmp_path, ticket_id, version, **extra_fields):
    """建立測試用 Ticket 檔案，回傳檔案路徑。"""
    tickets_dir = tmp_path / "docs" / "work-logs" / f"v{version.split('.')[0]}" / f"v{'.'.join(version.split('.')[:2])}" / f"v{version}" / "tickets"
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


def _setup_env(tmp_path, monkeypatch):
    """統一測試環境：chdir + CLAUDE_PROJECT_DIR override（同 W10-086 測試模式）。"""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))


# ============================================================
# 單元測試：_parse_where_path_entries 路徑判定
# ============================================================


def test_parse_single_path():
    """單一路徑（含 /）→ 單元素清單。"""
    assert _parse_where_path_entries(".claude/hooks/foo.py") == [".claude/hooks/foo.py"]


def test_parse_comma_separated_paths_trimmed():
    """逗號分隔多路徑 → 逐項 strip 後的清單。"""
    result = _parse_where_path_entries(".claude/hooks/a.py, src/core/b.js ,tests/unit/")
    assert result == [".claude/hooks/a.py", "src/core/b.js", "tests/unit/"]


def test_parse_descriptive_value_returns_none():
    """描述性輸入（無 /）→ None，不同步 files。"""
    assert _parse_where_path_entries("Domain Layer") is None
    assert _parse_where_path_entries("Framework Rules") is None


def test_parse_mixed_value_returns_none():
    """混合輸入（路徑 + 描述）→ None，整體視為 layer 描述。"""
    assert _parse_where_path_entries("Domain Layer, .claude/hooks/foo.py") is None


def test_parse_empty_value_returns_none():
    """空字串 / 純逗號 → None。"""
    assert _parse_where_path_entries("") is None
    assert _parse_where_path_entries(" , ") is None


# ============================================================
# 整合測試：AC 1 — set-where 後 where.files 與輸入值一致
# ============================================================


def test_set_where_path_value_syncs_files(tmp_path, monkeypatch):
    """路徑型輸入：layer 寫入原值，files 同步為解析後清單。"""
    version = "1.0.0"
    ticket_id = f"{version}-W1-101"
    ticket_path = _create_ticket_file(
        tmp_path, ticket_id, version,
        where={"layer": "待定義", "files": ["stale/old.py"]},
    )

    _setup_env(tmp_path, monkeypatch)
    value = ".claude/hooks/a.py,.claude/lib/b.py"
    result = execute_set_where(_make_args(ticket_id, value, version), version)

    assert result == 0
    fm = _load_frontmatter(ticket_path)
    assert fm["where"]["layer"] == value, "layer 保留原始輸入字串"
    assert fm["where"]["files"] == [".claude/hooks/a.py", ".claude/lib/b.py"], \
        "files 同步為解析後清單（stale 值被覆寫）"


def test_set_where_descriptive_value_preserves_files(tmp_path, monkeypatch):
    """描述性輸入：僅更新 layer，既有 files 保留不被污染。"""
    version = "1.0.0"
    ticket_id = f"{version}-W1-102"
    ticket_path = _create_ticket_file(
        tmp_path, ticket_id, version,
        where={"layer": "待定義", "files": [".claude/hooks/keep.py"]},
    )

    _setup_env(tmp_path, monkeypatch)
    result = execute_set_where(_make_args(ticket_id, "Framework Rules", version), version)

    assert result == 0
    fm = _load_frontmatter(ticket_path)
    assert fm["where"]["layer"] == "Framework Rules"
    assert fm["where"]["files"] == [".claude/hooks/keep.py"], \
        "描述性輸入不得覆寫 files（防 dispatch hook has_other 污染）"


# ============================================================
# 回歸測試：AC 2 — 既有 where.files 為空或缺失時不崩潰
# ============================================================


def test_set_where_with_empty_files(tmp_path, monkeypatch):
    """既有 files 為空 list → 路徑型輸入正常同步。"""
    version = "1.0.0"
    ticket_id = f"{version}-W1-103"
    ticket_path = _create_ticket_file(
        tmp_path, ticket_id, version,
        where={"layer": "待定義", "files": []},
    )

    _setup_env(tmp_path, monkeypatch)
    result = execute_set_where(_make_args(ticket_id, "src/core/x.js", version), version)

    assert result == 0
    fm = _load_frontmatter(ticket_path)
    assert fm["where"]["files"] == ["src/core/x.js"]


def test_set_where_with_missing_files_key(tmp_path, monkeypatch):
    """既有 where dict 缺 files key → 不崩潰，files 建立並同步。"""
    version = "1.0.0"
    ticket_id = f"{version}-W1-104"
    ticket_path = _create_ticket_file(
        tmp_path, ticket_id, version,
        where={"layer": "待定義"},
    )

    _setup_env(tmp_path, monkeypatch)
    result = execute_set_where(_make_args(ticket_id, ".claude/skills/ticket/", version), version)

    assert result == 0
    fm = _load_frontmatter(ticket_path)
    assert fm["where"]["files"] == [".claude/skills/ticket/"]
    assert fm["where"]["layer"] == ".claude/skills/ticket/"


def test_set_where_squashed_string_with_path_value(tmp_path, monkeypatch):
    """where 被壓扁為 string（W10-086 降級場景）+ 路徑型輸入 → 重建 dict 且 files 同步。"""
    version = "1.0.0"
    ticket_id = f"{version}-W1-105"
    ticket_path = _create_ticket_file(
        tmp_path, ticket_id, version,
        where="先前被壓扁的 string",
    )

    _setup_env(tmp_path, monkeypatch)
    result = execute_set_where(_make_args(ticket_id, ".claude/hooks/foo.py", version), version)

    assert result == 0
    fm = _load_frontmatter(ticket_path)
    assert isinstance(fm["where"], dict), "where 重建為 dict"
    assert fm["where"]["layer"] == ".claude/hooks/foo.py"
    assert fm["where"]["files"] == [".claude/hooks/foo.py"]
