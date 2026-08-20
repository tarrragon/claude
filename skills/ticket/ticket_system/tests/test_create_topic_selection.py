"""create --topic / --new-topic 建票主題選取測試。

覆蓋 acceptance：
1. --topic 可指定既有主題名；指定不存在的主題名時明確拒絕（列出既有清單）
2. --new-topic 為新增主題的獨立顯式旗標，--topic 不接受自由輸入新名稱
3. 未指派主題不阻擋建票，且該狀態在輸出中有明確表示
4. 建票前後 ticket frontmatter 欄位集合與值逐字不變（主題全程不進 frontmatter）
"""
from __future__ import annotations

import argparse
import io
from contextlib import redirect_stderr, redirect_stdout

from ticket_system.commands import create as create_cmd
from ticket_system.lib.parser import load_ticket
from ticket_system.lib.paths import get_project_root
from ticket_system.lib.topic_assignments import list_assignments
from ticket_system.lib.topic_registry import (
    TOPICS_REGISTRY_RELATIVE_PATH,
    append_topic,
    list_topics,
)


def _registry_file():
    return get_project_root() / TOPICS_REGISTRY_RELATIVE_PATH


def _make_args(**overrides):
    """建立 argparse.Namespace，欄位對齊 create.execute 預期簽名。"""
    defaults = dict(
        version="1.0.1",
        wave=1,
        seq=None,
        action="實作",
        target="主題選取測試",
        title=None,
        type="IMP",
        priority=None,
        who="待派發",
        what=None,
        when="立即",
        where_layer=None,
        where_files="ticket_system/commands/create.py",
        why="測試主題選取",
        how_type=None,
        how_strategy="驗證主題選取行為",
        parent=None,
        source_ticket=None,
        blocked_by=None,
        related_to=None,
        acceptance=["測試通過"],
        decision_tree_entry="Ticket",
        decision_tree_decision="直接派發",
        decision_tree_rationale="測試情境",
        quiet=False,
        verbose=False,
        json_output=False,
        force=False,
        allow_duplicate=False,
        topic=None,
        new_topic=None,
        no_topic=False,
    )
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def _capture(args):
    """執行 create.execute(args) 並擷取 stdout / stderr / exit code。"""
    out_buf = io.StringIO()
    err_buf = io.StringIO()
    exit_code = None
    try:
        with redirect_stdout(out_buf), redirect_stderr(err_buf):
            exit_code = create_cmd.execute(args)
    except SystemExit as exc:
        exit_code = exc.code
    return out_buf.getvalue(), err_buf.getvalue(), exit_code


class TestTopicRejectsUnknownName:
    def test_unknown_topic_rejected_without_creating_ticket(self, seeded_repo_root):
        append_topic("既有主題 A")
        args = _make_args(topic="不存在的主題")
        stdout, _, exit_code = _capture(args)
        assert exit_code == 1
        assert "不存在" in stdout

    def test_error_message_lists_existing_topics(self, seeded_repo_root):
        append_topic("既有主題 A")
        append_topic("既有主題 B")
        args = _make_args(topic="不存在的主題")
        stdout, _, _ = _capture(args)
        assert "既有主題 A" in stdout
        assert "既有主題 B" in stdout

    def test_unknown_topic_with_empty_registry_hints_new_topic_flag(self, seeded_repo_root):
        args = _make_args(topic="任何主題")
        stdout, _, exit_code = _capture(args)
        assert exit_code == 1
        assert "--new-topic" in stdout


class TestNewTopicExplicitFlag:
    def test_new_topic_flag_creates_ticket_and_registers_topic(self, seeded_repo_root):
        args = _make_args(new_topic="全新主題")
        stdout, _, exit_code = _capture(args)
        assert exit_code == 0
        assert "全新主題" in list_topics()
        assert "全新主題" in stdout

    def test_topic_and_new_topic_together_rejected(self, seeded_repo_root):
        append_topic("既有主題 A")
        args = _make_args(topic="既有主題 A", new_topic="另一個新主題")
        stdout, _, exit_code = _capture(args)
        assert exit_code == 1
        assert "--topic" in stdout
        assert "--new-topic" in stdout
        # 衝突時不應寫入任何新主題
        assert "另一個新主題" not in list_topics()

    def test_topic_flag_does_not_accept_free_text_for_new_name(self, seeded_repo_root):
        # --topic 只能選既有主題；未預先 append_topic 的名稱一律視為未命中
        args = _make_args(topic="從未存在過的主題")
        _, _, exit_code = _capture(args)
        assert exit_code == 1
        assert "從未存在過的主題" not in list_topics()


class TestTopicSelectionExisting:
    def test_topic_flag_selects_existing_topic_successfully(self, seeded_repo_root):
        append_topic("既有主題 A")
        args = _make_args(topic="既有主題 A")
        stdout, _, exit_code = _capture(args)
        assert exit_code == 0
        assert "既有主題 A" in stdout
        # 選取既有主題不應重複寫入清單
        assert list_topics() == ["既有主題 A"]


class TestUnassignedTopicDoesNotBlockCreation:
    def test_no_topic_specified_still_creates_ticket(self, seeded_repo_root):
        args = _make_args()
        _, _, exit_code = _capture(args)
        assert exit_code == 0

    def test_no_topic_specified_shows_explicit_unassigned_message(self, seeded_repo_root):
        args = _make_args()
        stdout, _, exit_code = _capture(args)
        assert exit_code == 0
        assert "未指派主題" in stdout


class TestFrontmatterUnaffectedByTopic:
    def test_frontmatter_fields_identical_with_and_without_topic(self, seeded_repo_root):
        # 兩票分別以「無主題」與「--new-topic」建立，比較 frontmatter 欄位
        # 集合與值：主題全程不寫入 frontmatter，故兩者除 ticket 識別性欄位
        # （seq 遞增造成 id/title 差異）外，其餘欄位集合與值須逐字相同。
        args_plain = _make_args(target="無主題票")
        _, _, exit_code_plain = _capture(args_plain)
        assert exit_code_plain == 0

        args_topic = _make_args(
            target="無主題票", new_topic="旁路驗證主題", allow_duplicate=True
        )
        _, _, exit_code_topic = _capture(args_topic)
        assert exit_code_topic == 0

        version = "1.0.1"
        ticket_plain = load_ticket(version, "1.0.1-W1-001")
        ticket_topic = load_ticket(version, "1.0.1-W1-002")

        assert ticket_plain is not None
        assert ticket_topic is not None

        # 排除因不同 ticket 而必然不同的識別性欄位。
        identity_fields = {"id", "created", "updated", "_path"}
        keys_plain = set(ticket_plain.keys()) - identity_fields
        keys_topic = set(ticket_topic.keys()) - identity_fields
        assert keys_plain == keys_topic

        for key in keys_plain:
            assert ticket_plain[key] == ticket_topic[key], (
                f"欄位 {key} 因主題參數而改變："
                f"{ticket_plain[key]!r} != {ticket_topic[key]!r}"
            )

        # 主題名不得出現在任一 ticket 的任何 frontmatter 值中。
        assert "旁路驗證主題" not in str(ticket_topic.values())


class TestCreateWritesTicketTopicAssignment:
    """0.2.1-W3-799：建票成功後除主題名清單外，亦須寫入 ticket_id -> topic
    映射，使新建票與回填票在映射表中口徑一致。
    """

    def test_new_topic_writes_assignment_mapping(self, seeded_repo_root):
        args = _make_args(new_topic="映射驗證主題")
        _, _, exit_code = _capture(args)
        assert exit_code == 0
        assignments = list_assignments()
        assert assignments == {"1.0.1-W1-001": "映射驗證主題"}

    def test_existing_topic_flag_writes_assignment_mapping(self, seeded_repo_root):
        append_topic("既有主題 A")
        args = _make_args(topic="既有主題 A")
        _, _, exit_code = _capture(args)
        assert exit_code == 0
        assert list_assignments() == {"1.0.1-W1-001": "既有主題 A"}
        # 選取既有主題不應重複寫入主題名清單
        assert list_topics() == ["既有主題 A"]

    def test_no_topic_specified_does_not_write_mapping(self, seeded_repo_root):
        args = _make_args()
        _, _, exit_code = _capture(args)
        assert exit_code == 0
        assert list_assignments() == {}

    def test_create_failure_leaves_mapping_untouched(self, seeded_repo_root):
        # 刻意省略 how_strategy 觸發 checklist 阻擋（不加 --force），
        # 建票在持久化前即中止，映射表逐字不變（原不存在時不被建立）。
        args = _make_args(new_topic="失敗票候選主題", how_strategy=None)
        _, _, exit_code = _capture(args)
        assert exit_code == 1
        assert list_assignments() == {}


class TestNewTopicNotPersistedWhenCreateFails:
    """--new-topic 於建票失敗時不得留下孤兒主題（append_topic 副作用洩漏修復）。

    刻意省略 how_strategy 使 PROP-009 checklist 驗證失敗（不加 --force），
    建票在持久化前即中止；此時 registry 內容必須逐字不變。
    """

    def test_registry_untouched_when_checklist_fails(self, seeded_repo_root):
        assert not _registry_file().exists()
        args = _make_args(new_topic="孤兒主題候選", how_strategy=None)
        _, _, exit_code = _capture(args)
        assert exit_code == 1
        # registry 原不存在時，失敗建票不應建立該檔案。
        assert not _registry_file().exists()
        assert list_topics() == []

    def test_registry_content_unchanged_when_checklist_fails_with_existing_entries(
        self, seeded_repo_root
    ):
        append_topic("既有主題 A")
        before = _registry_file().read_text(encoding="utf-8")

        args = _make_args(new_topic="孤兒主題候選", how_strategy=None)
        _, _, exit_code = _capture(args)
        assert exit_code == 1

        after = _registry_file().read_text(encoding="utf-8")
        assert after == before
        assert list_topics() == ["既有主題 A"]

    def test_new_topic_persisted_only_after_create_succeeds(self, seeded_repo_root):
        assert not _registry_file().exists()
        args = _make_args(new_topic="成功建票才落地的主題")
        _, _, exit_code = _capture(args)
        assert exit_code == 0
        assert "成功建票才落地的主題" in list_topics()


class TestTopicInferenceS1UpstreamInheritance:
    """0.2.1-W3-828 判準 S1：有 source_ticket 或 parent_id 且上游已有主題時，
    新票自動繼承同主題，不需建票者輸入。

    覆蓋 0.2.1-W3-826 實測：39 張 pending 未歸屬票中 33 張（85%）帶
    source_ticket，此判準是覆蓋率最高的一條。
    """

    def test_inherits_topic_from_source_ticket(self, seeded_repo_root):
        _capture(_make_args(new_topic="上游主題"))
        args = _make_args(source_ticket="1.0.1-W1-001", target="S1 繼承驗證")
        out, _, exit_code = _capture(args)
        assert exit_code == 0
        assert list_assignments()["1.0.1-W1-002"] == "上游主題"
        assert "S1" in out

    def test_inherits_topic_from_parent(self, seeded_repo_root):
        _capture(_make_args(new_topic="父票主題"))
        args = _make_args(parent="1.0.1-W1-001", target="S1 父票驗證")
        out, _, exit_code = _capture(args)
        assert exit_code == 0
        inherited = [t for tid, t in list_assignments().items() if tid != "1.0.1-W1-001"]
        assert inherited == ["父票主題"]
        assert "S1" in out

    def test_no_inheritance_when_upstream_has_no_topic(self, seeded_repo_root):
        _capture(_make_args())
        args = _make_args(source_ticket="1.0.1-W1-001", target="S1 空上游驗證")
        _, _, exit_code = _capture(args)
        assert exit_code == 0
        assert list_assignments() == {}


class TestTopicInferenceS2FileCluster:
    """0.2.1-W3-828 判準 S2：where.files 與某既有主題涵蓋的檔案叢集有交集時
    推導該主題。僅於 S1 未命中時執行（用戶裁示 2026-08-20：不加快取，
    以 S1 優先短路控制成本；實測全量掃描 351ms）。
    """

    def test_infers_topic_from_overlapping_file_path(self, seeded_repo_root):
        _capture(_make_args(
            new_topic="叢集主題",
            where_files=".claude/hooks/sample-guard-hook.py",
        ))
        args = _make_args(where_files=".claude/hooks/sample-guard-hook.py", target="S2 叢集驗證")
        out, _, exit_code = _capture(args)
        assert exit_code == 0
        assert list_assignments()["1.0.1-W1-002"] == "叢集主題"
        assert "S2" in out

    def test_no_inference_when_no_path_overlap(self, seeded_repo_root):
        _capture(_make_args(
            new_topic="無關主題",
            where_files=".claude/hooks/other-hook.py",
        ))
        args = _make_args(where_files="docs/spec/unrelated.md", target="S2 無交集驗證")
        _, _, exit_code = _capture(args)
        assert exit_code == 0
        assert "1.0.1-W1-002" not in list_assignments()


class TestTopicInferenceS3AnaRequiresTopic:
    """0.2.1-W3-828 判準 S3：ANA 型票必然 spawn 衍生票，其主題經 S1 放大到
    整串後續票，故 ANA 未歸屬不得靜默略過。本票只負責標記，實際的要求
    邏輯由 0.2.1-W3-829 承接。
    """

    def test_ana_without_inferable_topic_is_flagged(self, seeded_repo_root):
        args = _make_args(type="ANA")
        out, _, exit_code = _capture(args)
        assert exit_code == 0
        assert "S3" in out

    def test_non_ana_without_inferable_topic_is_not_flagged(self, seeded_repo_root):
        args = _make_args(type="IMP")
        out, _, exit_code = _capture(args)
        assert exit_code == 0
        assert "S3" not in out


class TestExplicitTopicUnaffectedByInference:
    """acceptance 5：既有帶 --topic / --new-topic 的呼叫端行為逐字不變。
    推導只在兩個旗標皆未給時啟動，不得改寫顯式選擇。
    """

    def test_explicit_topic_wins_over_inferable_upstream(self, seeded_repo_root):
        _capture(_make_args(new_topic="上游主題"))
        append_topic("顯式主題")
        args = _make_args(source_ticket="1.0.1-W1-001", topic="顯式主題", target="顯式優先驗證")
        out, _, exit_code = _capture(args)
        assert exit_code == 0
        assert list_assignments()["1.0.1-W1-002"] == "顯式主題"
        assert "S1" not in out


class TestTopicInferenceRejectsShallowClusterPaths:
    """S2 的路徑交集需有足夠特異性才算命中。

    真實票庫中存在 `docs/`、`.claude/hooks/` 這類單段或雙段的 where.files，
    它們與該目錄下任何路徑都相交。若不設深度門檻，擁有這種淺層路徑的主題
    會成為所有新票的推導結果——推導從「找出相關主題」退化為「總是指向同
    一個主題」。門檻對齊 track parallel-check 的「共同祖先深度 >= 3 段」慣例。
    """

    def test_single_segment_cluster_path_does_not_infer(self, seeded_repo_root):
        _capture(_make_args(new_topic="淺層路徑主題", where_files="docs/"))
        args = _make_args(where_files="docs/spec/unrelated-area.md", target="淺層門檻驗證")
        out, _, exit_code = _capture(args)
        assert exit_code == 0
        assert "1.0.1-W1-002" not in list_assignments()
        assert "S2" not in out

    def test_sufficiently_deep_cluster_path_still_infers(self, seeded_repo_root):
        _capture(_make_args(
            new_topic="深層路徑主題",
            where_files=".claude/skills/ticket/lib/sample.py",
        ))
        args = _make_args(
            where_files=".claude/skills/ticket/lib/sample.py",
            target="深層命中驗證",
        )
        out, _, exit_code = _capture(args)
        assert exit_code == 0
        assert list_assignments()["1.0.1-W1-002"] == "深層路徑主題"
        assert "S2" in out


class TestTopicInferenceDeterministicOnTie:
    """同一路徑被多個主題涵蓋時，推導結果必須可預測。

    真實票庫中同一檔案可能出現在多個主題的票裡（如 lease.py 同時見於
    「lease 與 registry」與「並行分組演算法」）。若以 dict 迭代順序決定勝者，
    結果取決於映射表的寫入順序，同樣輸入在不同時間會給出不同主題，
    使推導無法被測試也無法被信任。
    """

    def test_same_input_yields_same_topic_across_repeated_calls(self, seeded_repo_root):
        _capture(_make_args(
            new_topic="主題甲",
            where_files=".claude/skills/ticket/lib/shared.py",
        ))
        _capture(_make_args(
            new_topic="主題乙",
            where_files=".claude/skills/ticket/lib/shared.py",
            target="第二個主題來源",
        ))
        results = []
        for index in range(2):
            # 本測試刻意建立 where.files 與標題皆高度相似的多張票——那正是
            # 平手情境的必要條件，也正是 Tier 2 重複偵測的目標形態。旁路它
            # 才能測到推導的決定性，不旁路則測到的是重複偵測（已另有測試）。
            args = _make_args(
                where_files=".claude/skills/ticket/lib/shared.py",
                target=f"平手決定性驗證{index}",
                allow_duplicate=True,
            )
            out, _, exit_code = _capture(args)
            assert exit_code == 0
            results.append(list_assignments()[f"1.0.1-W1-00{index + 3}"])
        assert results[0] == results[1]
        assert results[0] in {"主題甲", "主題乙"}


class TestNoTopicExplicitOptOut:
    """0.2.1-W3-829：--no-topic 使「不指派主題」成為明示選擇。

    0.2.1-W3-826 實驗 H1/H2 證實現行未指派零阻力——只印一行資訊訊息、
    不影響 rc、hook 層零感知，於是「不指派」與「指派」在系統行為上完全
    等價，差別只在人眼會滑過的一行文字。--no-topic 讓不指派需要一個動作，
    使它從預設變成選擇。
    """

    def test_no_topic_writes_no_assignment(self, seeded_repo_root):
        args = _make_args(no_topic=True)
        _, _, exit_code = _capture(args)
        assert exit_code == 0
        assert list_assignments() == {}

    def test_no_topic_suppresses_warning(self, seeded_repo_root):
        args = _make_args(no_topic=True)
        out, _, exit_code = _capture(args)
        assert exit_code == 0
        assert "無法自動推導" not in out

    def test_no_topic_conflicts_with_topic(self, seeded_repo_root):
        append_topic("既有主題 A")
        args = _make_args(no_topic=True, topic="既有主題 A")
        out, _, exit_code = _capture(args)
        assert exit_code == 1
        assert "--no-topic" in out

    def test_no_topic_conflicts_with_new_topic(self, seeded_repo_root):
        args = _make_args(no_topic=True, new_topic="新主題")
        out, _, exit_code = _capture(args)
        assert exit_code == 1
        assert "--no-topic" in out


class TestUnassignedTopicWarnsInTransition:
    """0.2.1-W3-829：三旗標皆未給且推導未命中時發出 WARNING，但不改 rc。

    過渡期刻意 warn-only 不硬擋：代理人對建票 exit 非 0 的標準反應是重試
    或放棄（同 claim --verify 無 TTY fail-closed 的已知問題），以 exit code
    表達強制力會讓建票在代理人環境退化成重複建票。轉硬擋與否由獨立 ticket
    以實際資料評估。
    """

    def test_warns_when_no_flag_and_no_inference(self, seeded_repo_root):
        args = _make_args()
        out, _, exit_code = _capture(args)
        assert exit_code == 0
        assert "無法自動推導" in out
        assert "--no-topic" in out

    def test_no_warning_when_inference_hits(self, seeded_repo_root):
        _capture(_make_args(new_topic="上游主題"))
        args = _make_args(source_ticket="1.0.1-W1-001", target="推導命中免警告")
        out, _, exit_code = _capture(args)
        assert exit_code == 0
        assert "無法自動推導" not in out

    def test_no_warning_when_topic_explicitly_given(self, seeded_repo_root):
        args = _make_args(new_topic="顯式主題")
        out, _, exit_code = _capture(args)
        assert exit_code == 0
        assert "無法自動推導" not in out

    def test_exit_code_unchanged_for_legacy_callers(self, seeded_repo_root):
        """過渡期不破壞：既有不帶任何主題旗標的呼叫端 rc 仍為 0。"""
        args = _make_args()
        _, _, exit_code = _capture(args)
        assert exit_code == 0
        assert load_ticket("1.0.1", "1.0.1-W1-001") is not None
