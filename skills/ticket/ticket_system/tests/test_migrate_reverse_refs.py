"""
反向引用更新邏輯回歸測試（migrate.py `_update_cross_references` + `_migrate_single_ticket` + `_batch_migrate`）

來源 Ticket: 0.18.0-W11-003.6（TDD Phase 3b — thyme 補測試體 GREEN）

測試目標：
鎖定 migrate.py 既有六欄位反向引用更新邏輯，預防未來退化；覆蓋 W11 重組情境。

涵蓋的反向引用六欄位（migrate.py:82-182 `_update_cross_references`）：
| 欄位            | 形式                          | 已實作位置        |
| --------------- | ----------------------------- | ----------------- |
| blockedBy       | string list                   | migrate.py:126-131 |
| relatedTo       | string list                   | migrate.py:134-139 |
| children        | string list + dict {id:...}   | migrate.py:142-150 |
| source_ticket   | string                        | migrate.py:153-155 |
| parent_id       | string                        | migrate.py:158-160 |
| spawned_tickets | string list                   | migrate.py:163-168 |

AC 對應（4 條）：
- AC1：單筆 migrate 後父 ticket children（string list + dict 兩形式）自動更新 → TestAC1_*
- AC2：單筆 migrate 後外部 ticket 的 blockedBy/relatedTo/parent_id/source_ticket/
       spawned_tickets 多欄位同步更新 → TestAC2_*
- AC3：批量遷移正確處理跨遷移引用（A→B、C 引用 A 自動改為 B）→ TestAC3_*
- AC4：W11 重組情境（多 child 跨 wave 遷入新父子結構）父子反向引用完整一致 → TestAC4_*
- TD#2：_update_ticket_id_references self-loop 行為（PC-093 強制決斷追加）→ TestTD2_*

測試環境：
- pytest + tmp_path fixture 隔離 docs/work-logs/v*/tickets/ 結構
- 透過 monkeypatch 將 migrate / paths 模組的 get_project_root 指向 tmp_path
"""

from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _write_ticket(tickets_dir: Path, ticket_id: str, extra_fields: dict) -> Path:
    """寫入最小化 Ticket 檔案（含 frontmatter + body）。

    支援欄位形式：
    - 純值：`status: pending`
    - list of string：`children: [a, b]` → `- a` / `- b`
    - list of dict：`children: [{id: a, type: IMP}]` → `- id: a` / `  type: IMP`
    """
    filename = f"{ticket_id}.md"
    path = tickets_dir / filename

    lines = [
        "---",
        f"id: {ticket_id}",
        f"title: Test {ticket_id}",
        "type: IMP",
        "status: pending",
    ]
    for key, value in extra_fields.items():
        if isinstance(value, list):
            lines.append(f"{key}:")
            for item in value:
                if isinstance(item, dict):
                    items = list(item.items())
                    first_k, first_v = items[0]
                    lines.append(f"  - {first_k}: {first_v}")
                    for k, v in items[1:]:
                        lines.append(f"    {k}: {v}")
                else:
                    lines.append(f"  - {item}")
        else:
            lines.append(f"{key}: {value}")
    lines.append("---")
    lines.append("")
    lines.append("# Body")

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _read_frontmatter(path: Path) -> dict:
    """讀取 frontmatter dict。"""
    from ticket_system.lib.parser import parse_frontmatter

    content = path.read_text(encoding="utf-8")
    fm, _ = parse_frontmatter(content)
    return fm


@pytest.fixture
def project_with_tickets(tmp_path, monkeypatch):
    """建立 tmp 專案結構並 patch get_project_root 到 migrate / paths 模組。

    Returns:
        (tmp_path, tickets_dir) — 用於後續寫入測試 ticket
    """
    work_logs = tmp_path / "docs" / "work-logs" / "v0.18.0" / "tickets"
    work_logs.mkdir(parents=True)

    import ticket_system.commands.migrate as migrate_mod
    import ticket_system.lib.ticket_loader as loader_mod

    monkeypatch.setattr(migrate_mod, "get_project_root", lambda: tmp_path)
    monkeypatch.setattr(loader_mod, "get_project_root", lambda: tmp_path)

    # paths 模組可能不存在或結構不同，盡量也 patch
    try:
        import ticket_system.lib.paths as paths_mod  # type: ignore
        if hasattr(paths_mod, "get_project_root"):
            monkeypatch.setattr(paths_mod, "get_project_root", lambda: tmp_path)
    except ImportError:
        pass

    return tmp_path, work_logs


# ---------------------------------------------------------------------------
# AC1：單筆 migrate 後父 ticket children 自動更新（string + dict 兩形式）
# ---------------------------------------------------------------------------


class TestAC1_ParentChildrenUpdated:
    """AC1：單筆 migrate 後，父 ticket children 自動更新為新 ID。"""

    def test_children_as_string_list_updated(self, project_with_tickets):
        """
        Given: 父 ticket P.children = [old_id, sibling_id]（純 string list）
        When: 對 old_id → new_id 呼叫 _update_cross_references
        Then: P.children = [new_id, sibling_id]，old_id 完全消失
        """
        from ticket_system.commands.migrate import _update_cross_references

        _, tickets_dir = project_with_tickets

        old_id = "0.18.0-W5-018"
        new_id = "0.18.0-W11-003.1"
        sibling = "0.18.0-W5-019"

        _write_ticket(tickets_dir, "0.18.0-W11-003", {"children": [old_id, sibling]})

        updated = _update_cross_references(old_id, new_id)

        fm = _read_frontmatter(tickets_dir / "0.18.0-W11-003.md")
        assert fm["children"] == [new_id, sibling]
        assert old_id not in fm["children"]
        assert updated >= 1

    def test_children_as_dict_list_updated(self, project_with_tickets):
        """
        Given: 父 ticket P.children = [{id: old_id, type: IMP}, {id: sibling_id, type: ANA}]
        When: 對 old_id → new_id 呼叫 _update_cross_references
        Then: 對應 dict.id 變為 new_id；其他鍵值（type 等）保留
        """
        from ticket_system.commands.migrate import _update_cross_references

        _, tickets_dir = project_with_tickets

        old_id = "0.18.0-W5-018"
        new_id = "0.18.0-W11-003.1"
        sibling = "0.18.0-W5-019"

        _write_ticket(
            tickets_dir,
            "0.18.0-W11-003",
            {"children": [{"id": old_id, "type": "IMP"}, {"id": sibling, "type": "ANA"}]},
        )

        _update_cross_references(old_id, new_id)

        fm = _read_frontmatter(tickets_dir / "0.18.0-W11-003.md")
        assert fm["children"][0] == {"id": new_id, "type": "IMP"}
        assert fm["children"][1] == {"id": sibling, "type": "ANA"}

    def test_children_mixed_string_and_dict_forms(self, project_with_tickets):
        """
        Given: 父 ticket children 同時混用 string + dict 形式且都引用 old_id
        When: 對 old_id → new_id 呼叫 _update_cross_references
        Then: 兩種形式的引用都被更新；其他 children 不受影響
        """
        from ticket_system.commands.migrate import _update_cross_references

        _, tickets_dir = project_with_tickets

        old_id = "0.18.0-W5-018"
        new_id = "0.18.0-W11-003.1"
        other = "0.18.0-W5-099"

        _write_ticket(
            tickets_dir,
            "0.18.0-W11-003",
            {"children": [old_id, {"id": old_id, "type": "IMP"}, other]},
        )

        _update_cross_references(old_id, new_id)

        fm = _read_frontmatter(tickets_dir / "0.18.0-W11-003.md")
        assert fm["children"][0] == new_id
        assert fm["children"][1] == {"id": new_id, "type": "IMP"}
        assert fm["children"][2] == other

    def test_full_single_migrate_flow_updates_parent_children(
        self, project_with_tickets
    ):
        """
        端到端驗證（透過 _migrate_single_ticket）。
        """
        from ticket_system.commands.migrate import _migrate_single_ticket

        _, tickets_dir = project_with_tickets

        old_id = "0.18.0-W5-018"
        new_id = "0.18.0-W11-003.1"

        _write_ticket(tickets_dir, "0.18.0-W11-003", {"children": [old_id]})
        _write_ticket(tickets_dir, old_id, {})

        rc = _migrate_single_ticket(
            "0.18.0", old_id, new_id, dry_run=False, backup=False
        )
        assert rc == 0

        # 子 ticket 已 rename
        assert (tickets_dir / f"{new_id}.md").exists()
        assert not (tickets_dir / f"{old_id}.md").exists()

        # 父 ticket children 同步
        fm = _read_frontmatter(tickets_dir / "0.18.0-W11-003.md")
        assert fm["children"] == [new_id]


# ---------------------------------------------------------------------------
# AC2：單筆 migrate 後外部 ticket 多欄位同步更新
# ---------------------------------------------------------------------------


class TestAC2_ExternalReferencesUpdated:
    """AC2：外部 ticket 五欄位引用同步更新。"""

    def test_blockedby_updated(self, project_with_tickets):
        from ticket_system.commands.migrate import _update_cross_references

        _, tickets_dir = project_with_tickets
        old_id, new_id, other = "0.18.0-W5-001", "0.18.0-W11-001", "0.18.0-W5-002"
        _write_ticket(tickets_dir, "0.18.0-W11-EXT", {"blockedBy": [old_id, other]})

        _update_cross_references(old_id, new_id)

        fm = _read_frontmatter(tickets_dir / "0.18.0-W11-EXT.md")
        assert fm["blockedBy"] == [new_id, other]

    def test_relatedto_updated(self, project_with_tickets):
        from ticket_system.commands.migrate import _update_cross_references

        _, tickets_dir = project_with_tickets
        old_id, new_id, other = "0.18.0-W5-001", "0.18.0-W11-001", "0.18.0-W5-002"
        _write_ticket(tickets_dir, "0.18.0-W11-EXT", {"relatedTo": [old_id, other]})

        _update_cross_references(old_id, new_id)

        fm = _read_frontmatter(tickets_dir / "0.18.0-W11-EXT.md")
        assert fm["relatedTo"] == [new_id, other]

    def test_parent_id_updated(self, project_with_tickets):
        from ticket_system.commands.migrate import _update_cross_references

        _, tickets_dir = project_with_tickets
        old_id, new_id = "0.18.0-W5-001", "0.18.0-W11-001"
        _write_ticket(tickets_dir, "0.18.0-W11-EXT", {"parent_id": old_id})

        _update_cross_references(old_id, new_id)

        fm = _read_frontmatter(tickets_dir / "0.18.0-W11-EXT.md")
        assert fm["parent_id"] == new_id

    def test_source_ticket_updated(self, project_with_tickets):
        from ticket_system.commands.migrate import _update_cross_references

        _, tickets_dir = project_with_tickets
        old_id, new_id = "0.18.0-W5-001", "0.18.0-W11-001"
        _write_ticket(tickets_dir, "0.18.0-W11-EXT", {"source_ticket": old_id})

        _update_cross_references(old_id, new_id)

        fm = _read_frontmatter(tickets_dir / "0.18.0-W11-EXT.md")
        assert fm["source_ticket"] == new_id

    def test_spawned_tickets_updated(self, project_with_tickets):
        from ticket_system.commands.migrate import _update_cross_references

        _, tickets_dir = project_with_tickets
        old_id, new_id, other = "0.18.0-W5-001", "0.18.0-W11-001", "0.18.0-W5-002"
        _write_ticket(
            tickets_dir, "0.18.0-W11-EXT", {"spawned_tickets": [old_id, other]}
        )

        _update_cross_references(old_id, new_id)

        fm = _read_frontmatter(tickets_dir / "0.18.0-W11-EXT.md")
        assert fm["spawned_tickets"] == [new_id, other]

    def test_multiple_fields_in_single_ticket_all_updated(
        self, project_with_tickets
    ):
        """
        Given: 同一 ticket E 五欄位都引用 old_id
        Then: 五欄位都更新；updated_count == 1（同檔案只計一次）
        """
        from ticket_system.commands.migrate import _update_cross_references

        _, tickets_dir = project_with_tickets
        old_id, new_id = "0.18.0-W5-001", "0.18.0-W11-001"

        _write_ticket(
            tickets_dir,
            "0.18.0-W11-EXT",
            {
                "blockedBy": [old_id],
                "relatedTo": [old_id],
                "parent_id": old_id,
                "source_ticket": old_id,
                "spawned_tickets": [old_id],
            },
        )

        updated = _update_cross_references(old_id, new_id)

        fm = _read_frontmatter(tickets_dir / "0.18.0-W11-EXT.md")
        assert fm["blockedBy"] == [new_id]
        assert fm["relatedTo"] == [new_id]
        assert fm["parent_id"] == new_id
        assert fm["source_ticket"] == new_id
        assert fm["spawned_tickets"] == [new_id]
        assert updated == 1


# ---------------------------------------------------------------------------
# AC3：批量遷移正確處理跨遷移引用
# ---------------------------------------------------------------------------


def _write_migrations_yaml(tmp_path: Path, migrations: list) -> Path:
    import yaml

    config = tmp_path / "migrations.yaml"
    config.write_text(yaml.dump({"migrations": migrations}), encoding="utf-8")
    return config


class TestAC3_BatchCrossMigrationReferences:
    """AC3：批量遷移時跨遷移引用正確解析。"""

    def test_batch_migrate_updates_subsequent_references(
        self, project_with_tickets
    ):
        """
        Given: A 存在；C.blockedBy = [A]；migrations.yaml 含 {A→B}
        When: _batch_migrate
        Then: A 不存、B 存、C.blockedBy = [B]
        """
        from ticket_system.commands.migrate import _batch_migrate

        tmp_path, tickets_dir = project_with_tickets
        a, b = "0.18.0-W5-001", "0.18.0-W11-001"
        c = "0.18.0-W11-CONS"

        _write_ticket(tickets_dir, a, {})
        _write_ticket(tickets_dir, c, {"blockedBy": [a]})

        config = _write_migrations_yaml(tmp_path, [{"from": a, "to": b}])

        rc = _batch_migrate("0.18.0", str(config), dry_run=False, backup=False)
        assert rc == 0

        assert not (tickets_dir / f"{a}.md").exists()
        assert (tickets_dir / f"{b}.md").exists()

        fm_c = _read_frontmatter(tickets_dir / f"{c}.md")
        assert fm_c["blockedBy"] == [b]

    def test_batch_migrate_two_step_chain(self, project_with_tickets):
        """
        Given: A、C 存在；C.blockedBy = [A]；yaml = [A→A_new, C→C_new]
        Then: A、C 舊不存；A_new、C_new 存；C_new.blockedBy = [A_new]
        """
        from ticket_system.commands.migrate import _batch_migrate

        tmp_path, tickets_dir = project_with_tickets
        a, a_new = "0.18.0-W5-001", "0.18.0-W11-001"
        c, c_new = "0.18.0-W5-002", "0.18.0-W11-002"

        _write_ticket(tickets_dir, a, {})
        _write_ticket(tickets_dir, c, {"blockedBy": [a]})

        config = _write_migrations_yaml(
            tmp_path, [{"from": a, "to": a_new}, {"from": c, "to": c_new}]
        )

        rc = _batch_migrate("0.18.0", str(config), dry_run=False, backup=False)
        assert rc == 0

        assert not (tickets_dir / f"{a}.md").exists()
        assert not (tickets_dir / f"{c}.md").exists()
        assert (tickets_dir / f"{a_new}.md").exists()
        assert (tickets_dir / f"{c_new}.md").exists()

        fm_c_new = _read_frontmatter(tickets_dir / f"{c_new}.md")
        assert fm_c_new["blockedBy"] == [a_new]

    def test_batch_migrate_with_dict_children_in_parent(
        self, project_with_tickets
    ):
        """
        Given: P.children = [{id: A, type: IMP}, {id: D, type: IMP}]
               yaml = [A→A_new, D→D_new]
        Then: P.children = [{id: A_new, type: IMP}, {id: D_new, type: IMP}]
        """
        from ticket_system.commands.migrate import _batch_migrate

        tmp_path, tickets_dir = project_with_tickets
        a, a_new = "0.18.0-W5-001", "0.18.0-W11-001"
        d, d_new = "0.18.0-W5-002", "0.18.0-W11-002"
        p = "0.18.0-W11-PARENT"

        _write_ticket(tickets_dir, a, {})
        _write_ticket(tickets_dir, d, {})
        _write_ticket(
            tickets_dir,
            p,
            {"children": [{"id": a, "type": "IMP"}, {"id": d, "type": "IMP"}]},
        )

        config = _write_migrations_yaml(
            tmp_path, [{"from": a, "to": a_new}, {"from": d, "to": d_new}]
        )

        rc = _batch_migrate("0.18.0", str(config), dry_run=False, backup=False)
        assert rc == 0

        fm_p = _read_frontmatter(tickets_dir / f"{p}.md")
        assert fm_p["children"][0] == {"id": a_new, "type": "IMP"}
        assert fm_p["children"][1] == {"id": d_new, "type": "IMP"}


# ---------------------------------------------------------------------------
# AC4：W11 重組情境
# ---------------------------------------------------------------------------


class TestAC4_W11ReorganizationScenario:
    """AC4：W11 重組整合情境。"""

    def test_w11_reorganization_full_consistency(self, project_with_tickets):
        """W11 重組三筆批量遷移 + 父 children 混合形式 + 三類外部引用 + 零殘留檢查（精確比對）。"""
        from ticket_system.commands.migrate import _batch_migrate

        tmp_path, tickets_dir = project_with_tickets

        p_id = "0.18.0-W11-003"
        c1, c1_new = "0.18.0-W5-018", "0.18.0-W11-003.1"
        c2, c2_new = "0.18.0-W10-022", "0.18.0-W11-003.2"
        c3, c3_new = "0.18.0-W10-038", "0.18.0-W11-003.3"

        _write_ticket(
            tickets_dir,
            p_id,
            {"children": [c1, c2, {"id": c3, "type": "IMP"}]},
        )
        for cid in (c1, c2, c3):
            _write_ticket(tickets_dir, cid, {})
        _write_ticket(tickets_dir, "0.18.0-W11-E1", {"blockedBy": [c1]})
        _write_ticket(tickets_dir, "0.18.0-W11-E2", {"relatedTo": [c2]})
        _write_ticket(tickets_dir, "0.18.0-W11-E3", {"parent_id": c3})

        config = _write_migrations_yaml(
            tmp_path,
            [
                {"from": c1, "to": c1_new},
                {"from": c2, "to": c2_new},
                {"from": c3, "to": c3_new},
            ],
        )

        rc = _batch_migrate("0.18.0", str(config), dry_run=False, backup=False)
        assert rc == 0

        # 1. child rename
        for old, new in [(c1, c1_new), (c2, c2_new), (c3, c3_new)]:
            assert not (tickets_dir / f"{old}.md").exists(), f"{old} should be renamed"
            assert (tickets_dir / f"{new}.md").exists(), f"{new} should exist"

        # 2. 父 P.children 完整更新（順序保持、形式保留）
        fm_p = _read_frontmatter(tickets_dir / f"{p_id}.md")
        assert fm_p["children"] == [c1_new, c2_new, {"id": c3_new, "type": "IMP"}]

        # 3. 外部引用同步
        fm_e1 = _read_frontmatter(tickets_dir / "0.18.0-W11-E1.md")
        fm_e2 = _read_frontmatter(tickets_dir / "0.18.0-W11-E2.md")
        fm_e3 = _read_frontmatter(tickets_dir / "0.18.0-W11-E3.md")
        assert fm_e1["blockedBy"] == [c1_new]
        assert fm_e2["relatedTo"] == [c2_new]
        assert fm_e3["parent_id"] == c3_new

        # 4. 零殘留（TD#3：用集合精確比對 frontmatter 欄位，避免 prefix 誤判）
        old_ids = {c1, c2, c3}
        for md_file in tickets_dir.glob("*.md"):
            fm = _read_frontmatter(md_file)
            # children: 同時檢查 string 與 dict 形式
            children = fm.get("children") or []
            for ch in children:
                if isinstance(ch, str):
                    assert ch not in old_ids, f"{md_file.name} children 仍含舊 ID {ch}"
                elif isinstance(ch, dict):
                    assert ch.get("id") not in old_ids, (
                        f"{md_file.name} children dict 仍含舊 ID {ch.get('id')}"
                    )
            # 其他欄位
            for field in ("blockedBy", "relatedTo", "spawned_tickets"):
                values = fm.get(field) or []
                for v in values:
                    assert v not in old_ids, (
                        f"{md_file.name} {field} 仍含舊 ID {v}"
                    )
            for field in ("parent_id", "source_ticket"):
                v = fm.get(field)
                assert v not in old_ids, f"{md_file.name} {field} 仍含舊 ID {v}"

    def test_w11_reorganization_idempotency(self, project_with_tickets):
        """重複執行 batch migrate 的冪等性：來源不存在 → skip → P.children 不變。"""
        from ticket_system.commands.migrate import _batch_migrate

        tmp_path, tickets_dir = project_with_tickets

        p_id = "0.18.0-W11-003"
        c1, c1_new = "0.18.0-W5-018", "0.18.0-W11-003.1"

        _write_ticket(tickets_dir, p_id, {"children": [c1]})
        _write_ticket(tickets_dir, c1, {})

        config = _write_migrations_yaml(
            tmp_path, [{"from": c1, "to": c1_new}]
        )

        # 第一次：成功
        rc1 = _batch_migrate("0.18.0", str(config), dry_run=False, backup=False)
        assert rc1 == 0
        fm_p_first = _read_frontmatter(tickets_dir / f"{p_id}.md")
        assert fm_p_first["children"] == [c1_new]

        # 第二次：來源已不存在 → skip 全部 → 視為 0（無 fail）
        rc2 = _batch_migrate("0.18.0", str(config), dry_run=False, backup=False)
        assert rc2 == 0

        # P.children 維持新 ID
        fm_p_second = _read_frontmatter(tickets_dir / f"{p_id}.md")
        assert fm_p_second["children"] == [c1_new]
        assert (tickets_dir / f"{c1_new}.md").exists()
        assert not (tickets_dir / f"{c1}.md").exists()


# ---------------------------------------------------------------------------
# TD#2：_update_ticket_id_references self-loop 行為
# ---------------------------------------------------------------------------


class TestTD2_UpdateTicketIdReferencesSelfLoop:
    """TD#2（PC-093 強制決斷追加）：鎖定 _update_ticket_id_references 既有實作行為。

    現行實作（migrate.py:58-79）覆蓋三欄位：
    - blockedBy（list 替換）
    - children dict 形式（id 替換）
    - source_ticket（直接替換）
    其他欄位（relatedTo / parent_id / spawned_tickets / children string）為已知未覆蓋，
    本測試僅鎖定既有行為以防退化（此函式為 self-loop 異常情境，實務罕見）。
    """

    def test_self_loop_source_ticket_updated(self):
        """source_ticket 自我引用會被更新。"""
        from ticket_system.commands.migrate import _update_ticket_id_references

        old_id, new_id = "0.18.0-W5-001", "0.18.0-W11-001"
        ticket = {"id": old_id, "source_ticket": old_id}

        _update_ticket_id_references(ticket, old_id, new_id)

        assert ticket["source_ticket"] == new_id
