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
import yaml

from ticket_system.commands.migrate import (
    _batch_migrate,
    _migrate_single_ticket,
    _update_cross_references,
    _update_ticket_id_references,
)
from ticket_system.lib.parser import parse_frontmatter


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _patch_get_project_root(monkeypatch, tmp_path: Path) -> None:
    """集中將 migrate / ticket_loader / paths（若存在）的 get_project_root 指向 tmp_path。

    收斂原本散布於 fixture 的三處 monkeypatch；paths 模組以 try/except 保留
    跨版本容錯（並非所有版本都暴露 paths.get_project_root）。
    """
    import ticket_system.commands.migrate as migrate_mod
    import ticket_system.lib.ticket_loader as loader_mod

    monkeypatch.setattr(migrate_mod, "get_project_root", lambda: tmp_path)
    monkeypatch.setattr(loader_mod, "get_project_root", lambda: tmp_path)

    # ImportError 預期 fallback：舊版 ticket_system 未抽出 lib/paths.py，import 失敗時跳過 monkeypatch 不影響其他兩個模組的 patch
    try:
        import ticket_system.lib.paths as paths_mod  # type: ignore

        if hasattr(paths_mod, "get_project_root"):
            monkeypatch.setattr(paths_mod, "get_project_root", lambda: tmp_path)
    except ImportError:
        pass


def _write_ticket(tickets_dir: Path, ticket_id: str, extra_fields: dict) -> Path:
    """寫入最小化 Ticket 檔案（含 frontmatter + body）。

    使用 yaml.safe_dump 序列化 frontmatter，自然支援純值 / list of string /
    list of dict 三種欄位形式，無需手寫分支邏輯。
    """
    path = tickets_dir / f"{ticket_id}.md"

    frontmatter = {
        "id": ticket_id,
        "title": f"Test {ticket_id}",
        "type": "IMP",
        "status": "pending",
        **extra_fields,
    }

    content = (
        "---\n"
        + yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=True)
        + "---\n\n# Body"
    )
    path.write_text(content, encoding="utf-8")
    return path


def _read_frontmatter(path: Path) -> dict:
    """讀取 frontmatter dict。"""
    content = path.read_text(encoding="utf-8")
    fm, _ = parse_frontmatter(content)
    return fm


@pytest.fixture
def project_with_tickets(tmp_path, monkeypatch):
    """建立 tmp 專案結構並 patch get_project_root（集中於 _patch_get_project_root）。

    Returns:
        (tmp_path, tickets_dir) — 用於後續寫入測試 ticket
    """
    work_logs = tmp_path / "docs" / "work-logs" / "v0" / "v0.18" / "v0.18.0" / "tickets"
    work_logs.mkdir(parents=True)

    _patch_get_project_root(monkeypatch, tmp_path)

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

    # 五個單欄位場景：(欄位名, 初始值 builder, 期望值 builder)
    # list 形式（blockedBy / relatedTo / spawned_tickets）含 other 驗證部分替換；
    # scalar 形式（parent_id / source_ticket）只放 old_id。
    @pytest.mark.parametrize(
        "field, build_initial, build_expected",
        [
            (
                "blockedBy",
                lambda old, other: [old, other],
                lambda new, other: [new, other],
            ),
            (
                "relatedTo",
                lambda old, other: [old, other],
                lambda new, other: [new, other],
            ),
            (
                "parent_id",
                lambda old, other: old,
                lambda new, other: new,
            ),
            (
                "source_ticket",
                lambda old, other: old,
                lambda new, other: new,
            ),
            (
                "spawned_tickets",
                lambda old, other: [old, other],
                lambda new, other: [new, other],
            ),
        ],
        ids=["blockedBy", "relatedTo", "parent_id", "source_ticket", "spawned_tickets"],
    )
    def test_single_field_updated(
        self, project_with_tickets, field, build_initial, build_expected
    ):
        """五個單欄位場景共用驗證骨架；失敗訊息以 ids 標示欄位名。"""

        _, tickets_dir = project_with_tickets
        old_id, new_id, other = "0.18.0-W5-001", "0.18.0-W11-001", "0.18.0-W5-002"

        _write_ticket(
            tickets_dir, "0.18.0-W11-EXT", {field: build_initial(old_id, other)}
        )

        _update_cross_references(old_id, new_id)

        fm = _read_frontmatter(tickets_dir / "0.18.0-W11-EXT.md")
        assert fm[field] == build_expected(new_id, other)

    def test_multiple_fields_in_single_ticket_all_updated(
        self, project_with_tickets
    ):
        """
        Given: 同一 ticket E 五欄位都引用 old_id
        Then: 五欄位都更新；updated_count == 1（同檔案只計一次）
        """

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

    # W11 重組共用情境常數（p_id / 3 對 child id mapping）
    P_ID = "0.18.0-W11-003"
    C1, C1_NEW = "0.18.0-W5-018", "0.18.0-W11-003.1"
    C2, C2_NEW = "0.18.0-W10-022", "0.18.0-W11-003.2"
    C3, C3_NEW = "0.18.0-W10-038", "0.18.0-W11-003.3"

    def _setup_w11_scenario(self, project_with_tickets):
        """建立 W11 重組情境：父 + 3 child（混合 string/dict 形式）+ 3 外部引用，
        執行 _batch_migrate 並回傳 (tickets_dir, rc) 供後續驗證使用。
        """

        tmp_path, tickets_dir = project_with_tickets

        _write_ticket(
            tickets_dir,
            self.P_ID,
            {"children": [self.C1, self.C2, {"id": self.C3, "type": "IMP"}]},
        )
        for cid in (self.C1, self.C2, self.C3):
            _write_ticket(tickets_dir, cid, {})
        _write_ticket(tickets_dir, "0.18.0-W11-E1", {"blockedBy": [self.C1]})
        _write_ticket(tickets_dir, "0.18.0-W11-E2", {"relatedTo": [self.C2]})
        _write_ticket(tickets_dir, "0.18.0-W11-E3", {"parent_id": self.C3})

        config = _write_migrations_yaml(
            tmp_path,
            [
                {"from": self.C1, "to": self.C1_NEW},
                {"from": self.C2, "to": self.C2_NEW},
                {"from": self.C3, "to": self.C3_NEW},
            ],
        )

        rc = _batch_migrate("0.18.0", str(config), dry_run=False, backup=False)
        return tickets_dir, rc

    def _verify_child_renamed(self, tickets_dir):
        """驗證面向 1：3 個 child ticket 都 rename 為新 ID。"""
        for old, new in [(self.C1, self.C1_NEW), (self.C2, self.C2_NEW), (self.C3, self.C3_NEW)]:
            assert not (tickets_dir / f"{old}.md").exists(), f"{old} should be renamed"
            assert (tickets_dir / f"{new}.md").exists(), f"{new} should exist"

    def _verify_parent_children_updated(self, tickets_dir):
        """驗證面向 2：父 P.children 順序保持、形式保留（string + dict 混合）。"""
        fm_p = _read_frontmatter(tickets_dir / f"{self.P_ID}.md")
        assert fm_p["children"] == [
            self.C1_NEW,
            self.C2_NEW,
            {"id": self.C3_NEW, "type": "IMP"},
        ]

    def _verify_external_refs_synced(self, tickets_dir):
        """驗證面向 3：外部 ticket 三類欄位（blockedBy/relatedTo/parent_id）同步。"""
        fm_e1 = _read_frontmatter(tickets_dir / "0.18.0-W11-E1.md")
        fm_e2 = _read_frontmatter(tickets_dir / "0.18.0-W11-E2.md")
        fm_e3 = _read_frontmatter(tickets_dir / "0.18.0-W11-E3.md")
        assert fm_e1["blockedBy"] == [self.C1_NEW]
        assert fm_e2["relatedTo"] == [self.C2_NEW]
        assert fm_e3["parent_id"] == self.C3_NEW

    def _verify_no_stale_old_ids(self, tickets_dir):
        """驗證面向 4：所有 ticket frontmatter 六欄位精確比對無舊 ID 殘留
        （TD#3：用集合精確比對避免 prefix 誤判）。
        """
        old_ids = {self.C1, self.C2, self.C3}
        for md_file in tickets_dir.glob("*.md"):
            fm = _read_frontmatter(md_file)
            # children: 同時檢查 string 與 dict 形式
            for ch in fm.get("children") or []:
                if isinstance(ch, str):
                    assert ch not in old_ids, f"{md_file.name} children 仍含舊 ID {ch}"
                elif isinstance(ch, dict):
                    assert ch.get("id") not in old_ids, (
                        f"{md_file.name} children dict 仍含舊 ID {ch.get('id')}"
                    )
            for field in ("blockedBy", "relatedTo", "spawned_tickets"):
                for v in fm.get(field) or []:
                    assert v not in old_ids, f"{md_file.name} {field} 仍含舊 ID {v}"
            for field in ("parent_id", "source_ticket"):
                assert fm.get(field) not in old_ids, (
                    f"{md_file.name} {field} 仍含舊 ID {fm.get(field)}"
                )

    def test_w11_reorganization_full_consistency(self, project_with_tickets):
        """W11 重組三筆批量遷移：四個驗證面向組合（child rename / 父 children /
        外部引用 / 零殘留）。各面向細節下放至 `_verify_*` helper。"""
        tickets_dir, rc = self._setup_w11_scenario(project_with_tickets)
        assert rc == 0

        self._verify_child_renamed(tickets_dir)
        self._verify_parent_children_updated(tickets_dir)
        self._verify_external_refs_synced(tickets_dir)
        self._verify_no_stale_old_ids(tickets_dir)

    def test_w11_reorganization_idempotency(self, project_with_tickets):
        """重複執行 batch migrate 的冪等性：來源不存在 → skip → P.children 不變。"""

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
    """TD#2：鎖定 _update_ticket_id_references 既有實作行為。

    W11-003.11 補齊六欄位完整處理（與 _update_cross_references 對齊）：
    - blockedBy（list of string）
    - relatedTo（list of string）
    - children（string list + dict 兩形式）
    - source_ticket（scalar）
    - parent_id（scalar）
    - spawned_tickets（list of string）
    """

    def test_self_loop_source_ticket_updated(self):
        """source_ticket 自我引用會被更新。"""

        old_id, new_id = "0.18.0-W5-001", "0.18.0-W11-001"
        ticket = {"id": old_id, "source_ticket": old_id}

        _update_ticket_id_references(ticket, old_id, new_id)

        assert ticket["source_ticket"] == new_id

    def test_blockedBy_updated(self):
        """blockedBy list 自我引用會被更新；其他保留。"""
        old_id, new_id, other = "0.18.0-W5-001", "0.18.0-W11-001", "0.18.0-W5-099"
        ticket = {"id": old_id, "blockedBy": [old_id, other]}

        _update_ticket_id_references(ticket, old_id, new_id)

        assert ticket["blockedBy"] == [new_id, other]

    def test_relatedTo_updated(self):
        """relatedTo list 自我引用會被更新（W11-003.11 新支援）。"""
        old_id, new_id, other = "0.18.0-W5-001", "0.18.0-W11-001", "0.18.0-W5-099"
        ticket = {"id": old_id, "relatedTo": [old_id, other]}

        _update_ticket_id_references(ticket, old_id, new_id)

        assert ticket["relatedTo"] == [new_id, other]

    def test_parent_id_updated(self):
        """parent_id 自我引用會被更新（W11-003.11 新支援）。"""
        old_id, new_id = "0.18.0-W5-001", "0.18.0-W11-001"
        ticket = {"id": old_id, "parent_id": old_id}

        _update_ticket_id_references(ticket, old_id, new_id)

        assert ticket["parent_id"] == new_id

    def test_spawned_tickets_updated(self):
        """spawned_tickets list 自我引用會被更新（W11-003.11 新支援）。"""
        old_id, new_id, other = "0.18.0-W5-001", "0.18.0-W11-001", "0.18.0-W5-099"
        ticket = {"id": old_id, "spawned_tickets": [old_id, other]}

        _update_ticket_id_references(ticket, old_id, new_id)

        assert ticket["spawned_tickets"] == [new_id, other]

    def test_children_string_list_updated(self):
        """children 為純 string list 時自我引用會被更新（W11-003.11 新支援）。"""
        old_id, new_id, sibling = "0.18.0-W5-001", "0.18.0-W11-001", "0.18.0-W5-019"
        ticket = {"id": old_id, "children": [old_id, sibling]}

        _update_ticket_id_references(ticket, old_id, new_id)

        assert ticket["children"] == [new_id, sibling]

    def test_children_dict_list_updated(self):
        """children 為 dict list 時自我引用會被更新（既有行為保留）。"""
        old_id, new_id = "0.18.0-W5-001", "0.18.0-W11-001"
        ticket = {
            "id": old_id,
            "children": [{"id": old_id, "type": "IMP"}, {"id": "other", "type": "ANA"}],
        }

        _update_ticket_id_references(ticket, old_id, new_id)

        assert ticket["children"][0] == {"id": new_id, "type": "IMP"}
        assert ticket["children"][1] == {"id": "other", "type": "ANA"}

    def test_children_mixed_string_and_dict(self):
        """children 同時含 string 與 dict 形式時，兩者都會被更新。"""
        old_id, new_id = "0.18.0-W5-001", "0.18.0-W11-001"
        ticket = {
            "id": old_id,
            "children": [old_id, {"id": old_id, "type": "IMP"}, "kept"],
        }

        _update_ticket_id_references(ticket, old_id, new_id)

        assert ticket["children"][0] == new_id
        assert ticket["children"][1] == {"id": new_id, "type": "IMP"}
        assert ticket["children"][2] == "kept"

    def test_six_fields_all_updated_together(self):
        """單一 ticket 六欄位皆引用 old_id 時一次性全部更新。"""
        old_id, new_id = "0.18.0-W5-001", "0.18.0-W11-001"
        ticket = {
            "id": old_id,
            "blockedBy": [old_id],
            "relatedTo": [old_id],
            "children": [old_id],
            "source_ticket": old_id,
            "parent_id": old_id,
            "spawned_tickets": [old_id],
        }

        _update_ticket_id_references(ticket, old_id, new_id)

        assert ticket["blockedBy"] == [new_id]
        assert ticket["relatedTo"] == [new_id]
        assert ticket["children"] == [new_id]
        assert ticket["source_ticket"] == new_id
        assert ticket["parent_id"] == new_id
        assert ticket["spawned_tickets"] == [new_id]

    def test_non_matching_id_left_untouched(self):
        """ticket 不引用 old_id 時欄位不變。"""
        old_id, new_id = "0.18.0-W5-001", "0.18.0-W11-001"
        ticket = {
            "id": old_id,
            "blockedBy": ["0.18.0-W5-099"],
            "relatedTo": ["0.18.0-W5-099"],
            "parent_id": "0.18.0-W5-099",
        }
        snapshot = {k: list(v) if isinstance(v, list) else v for k, v in ticket.items()}

        _update_ticket_id_references(ticket, old_id, new_id)

        assert ticket["blockedBy"] == snapshot["blockedBy"]
        assert ticket["relatedTo"] == snapshot["relatedTo"]
        assert ticket["parent_id"] == snapshot["parent_id"]
