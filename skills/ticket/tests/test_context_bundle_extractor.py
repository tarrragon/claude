"""
Context Bundle 自動抽取測試（Phase 2 v2 15 場景，L1 單元 + merge 整合）

權威規格：Phase 2 v2 §v2.3 15 場景 + Phase 3a 虛擬碼。
Mock 邊界：load_ticket（外部 I/O）、extract_version_from_ticket_id（S19 驗證）。
"""

from unittest.mock import patch

import pytest

from ticket_system.lib.context_bundle_extractor import (
    AUTO_EXTRACTED_BLOCK_PATTERN,
    EXTRACTABLE_FIELDS,
    MAX_ITEMS_PER_FIELD,
    MAX_TOTAL_CHARS,
    SOURCE_PRIORITY,
    ContextBundleExtractionError,
    ExtractedField,
    ExtractResult,
    detect_self_reference,
    extract_and_write_context_bundle,
    extract_context_bundle,
    format_cli_summary,
    format_cli_summary_json,
    merge_auto_extracted_block,
    render_context_bundle_markdown,
    set_metric_sink,
)

LOAD_TICKET_PATH = "ticket_system.lib.context_bundle_extractor.load_ticket"
EXTRACT_VERSION_PATH = (
    "ticket_system.lib.context_bundle_extractor.extract_version_from_ticket_id"
)


def _make_source(
    ticket_id: str,
    what: str = "實作 X 功能",
    why: str = "因為 Y 需求",
    where_files: list = None,
    acceptance: list = None,
) -> dict:
    return {
        "id": ticket_id,
        "what": what,
        "why": why,
        "where": {"files": where_files if where_files is not None else ["a.py"]},
        "acceptance": acceptance if acceptance is not None else ["- [ ] 完成 A"],
    }


def _make_target(
    target_id: str = "0.18.0-W17-010",
    source_ticket=None,
    blocked_by=None,
    related_to=None,
    where_files: list = None,
) -> dict:
    return {
        "id": target_id,
        "source_ticket": source_ticket,
        "blocked_by": blocked_by,
        "related_to": related_to,
        "where": {"files": where_files if where_files is not None else []},
    }


# ============================================================================
# 群組 A：正常抽取
# ============================================================================


class TestGroupA_NormalExtraction:
    """S1, S2, S3"""

    def test_s1_single_source_extracts_four_fields(self):
        target = _make_target(source_ticket="0.18.0-W17-001")
        source = _make_source(
            "0.18.0-W17-001",
            what="W17-001 任務",
            why="W17-001 理由",
            where_files=["file1.py"],
            acceptance=["- [ ] ac1"],
        )
        with patch(LOAD_TICKET_PATH, return_value=source):
            result = extract_context_bundle(target)
        assert result.status == "success"
        assert len(result.extracted) == 4
        assert result.sources_declared == 1
        assert result.sources_ok == 1
        # 驗證 raw_value（SIMP-4）
        whats = [f for f in result.extracted if f.source_field == "what"]
        assert whats[0].raw_value == "W17-001 任務"

    def test_s2_three_sources_priority_order(self):
        target = _make_target(
            source_ticket="0.18.0-W17-001",
            blocked_by=["0.18.0-W17-002"],
            related_to=["0.18.0-W17-003"],
        )
        sources = {
            "0.18.0-W17-001": _make_source("0.18.0-W17-001"),
            "0.18.0-W17-002": _make_source("0.18.0-W17-002"),
            "0.18.0-W17-003": _make_source("0.18.0-W17-003"),
        }
        with patch(LOAD_TICKET_PATH, side_effect=lambda v, i: sources.get(i)):
            result = extract_context_bundle(target)
        assert result.sources_declared == 3
        assert result.status == "success"
        # 第一個 extracted 必為 source_ticket（SOURCE_PRIORITY 首位）
        source_ids_order = []
        for f in result.extracted:
            if f.source_id not in source_ids_order:
                source_ids_order.append(f.source_id)
        assert source_ids_order == [
            "0.18.0-W17-001",
            "0.18.0-W17-002",
            "0.18.0-W17-003",
        ]

    def test_s3_where_files_dedup(self):
        target = _make_target(
            source_ticket="0.18.0-W17-001",
            blocked_by=["0.18.0-W17-002"],
            where_files=[],
        )
        sources = {
            "0.18.0-W17-001": _make_source("0.18.0-W17-001", where_files=["f1", "f2"]),
            "0.18.0-W17-002": _make_source("0.18.0-W17-002", where_files=["f2", "f3"]),
        }
        with patch(LOAD_TICKET_PATH, side_effect=lambda v, i: sources.get(i)):
            result = extract_context_bundle(target)
        # 收集所有 Related Files 項
        files_items = []
        for f in result.extracted:
            if f.target_subsection == "Related Files":
                files_items.extend(f.raw_value)
        # f2 只應出現一次（跨 source 去重）
        assert files_items.count("f2") == 1


# ============================================================================
# 群組 B：邊界條件
# ============================================================================


class TestGroupB_Boundary:
    """S5, S6P, S7, S9P"""

    def test_s5_no_source(self):
        target = _make_target(source_ticket=None, blocked_by=None, related_to=None)
        result = extract_context_bundle(target)
        assert result.status == "no_source"
        assert result.extracted == []
        assert result.sources_declared == 0
        assert any("無可抽取來源" in w for w in result.warnings)

    @pytest.mark.parametrize(
        "case_name,source_present,blocked_present,expected_status,expected_declared,expected_ok",
        [
            ("partial", False, True, "partial", 2, 1),
            ("all_missing", False, False, "all_sources_missing", 2, 0),
        ],
    )
    def test_s6p_sources_availability(
        self,
        case_name,
        source_present,
        blocked_present,
        expected_status,
        expected_declared,
        expected_ok,
    ):
        target = _make_target(
            source_ticket="0.18.0-W99-001",
            blocked_by=["0.18.0-W99-002"],
        )
        sources = {}
        if source_present:
            sources["0.18.0-W99-001"] = _make_source("0.18.0-W99-001")
        if blocked_present:
            sources["0.18.0-W99-002"] = _make_source("0.18.0-W99-002")
        with patch(LOAD_TICKET_PATH, side_effect=lambda v, i: sources.get(i)):
            result = extract_context_bundle(target)
        assert result.status == expected_status
        assert result.sources_declared == expected_declared
        assert result.sources_ok == expected_ok
        # skipped 均為 source_missing
        for sk in result.skipped:
            assert sk.reason == "source_missing"

    def test_s7_placeholder_field_skipped(self):
        target = _make_target(source_ticket="0.18.0-W17-001")
        source = _make_source("0.18.0-W17-001", what="待定義")
        with patch(LOAD_TICKET_PATH, return_value=source):
            result = extract_context_bundle(target)
        assert not any(f.source_field == "what" for f in result.extracted)
        assert any(
            sk.reason == "source_field_undefined" and "what" in sk.detail
            for sk in result.skipped
        )

    def test_s9p_per_field_where_files_truncation(self):
        target = _make_target(source_ticket="0.18.0-W17-001")
        source = _make_source(
            "0.18.0-W17-001", where_files=[f"f{i}.py" for i in range(10)]
        )
        with patch(LOAD_TICKET_PATH, return_value=source):
            result = extract_context_bundle(target)
        files_field = next(
            f for f in result.extracted if f.source_field == "where.files"
        )
        assert len(files_field.raw_value) == MAX_ITEMS_PER_FIELD
        assert files_field.truncated is True

    def test_s9p_per_field_acceptance_truncation(self):
        """§v3.3 BLK-v3-3：is_list=True 欄位統一套 MAX_ITEMS_PER_FIELD。"""
        target = _make_target(source_ticket="0.18.0-W17-001")
        source = _make_source(
            "0.18.0-W17-001", acceptance=[f"- [ ] ac{i}" for i in range(8)]
        )
        with patch(LOAD_TICKET_PATH, return_value=source):
            result = extract_context_bundle(target)
        ac_field = next(
            f for f in result.extracted if f.source_field == "acceptance"
        )
        assert len(ac_field.raw_value) == MAX_ITEMS_PER_FIELD
        assert ac_field.truncated is True

    def test_s9p_total_chars_truncation(self):
        target = _make_target(source_ticket="0.18.0-W17-001")
        long_str = "X" * (MAX_TOTAL_CHARS + 500)
        source = _make_source("0.18.0-W17-001", what=long_str)
        with patch(LOAD_TICKET_PATH, return_value=source):
            result = extract_context_bundle(target)
        assert result.total_chars_estimate <= MAX_TOTAL_CHARS
        assert any(f.truncated for f in result.extracted)


# ============================================================================
# 群組 C：衝突與幂等（merge_auto_extracted_block）
# ============================================================================


class TestGroupC_MergeIdempotency:
    """S11, S12, S13"""

    def test_s11_pm_handwritten_plus_append(self):
        existing = "PM 手寫段落\n\n重要脈絡說明。"
        new_md = (
            "<!-- auto-extracted: v1 | sources: 0.18.0-W17-001 | chars: 100 -->\n"
            "\n### Task Reference\n- ..."
        )
        merged, notes = merge_auto_extracted_block(existing, new_md)
        assert notes == ["appended_new_block"]
        assert merged.startswith("PM 手寫段落")
        assert "<!-- auto-extracted:" in merged

    @pytest.mark.parametrize(
        "existing_chars,new_chars",
        [
            (100, 100),  # chars 相同
            (100, 250),  # chars 不同但 sources 相同（§v3.2 主鍵）
        ],
    )
    def test_s12_sources_unchanged_idempotent(self, existing_chars, new_chars):
        existing = (
            f"<!-- auto-extracted: v1 | sources: A,B | chars: {existing_chars} -->\n"
            "\n### Task Reference\n- A what\n- B what\n"
        )
        new = (
            f"<!-- auto-extracted: v1 | sources: A,B | chars: {new_chars} -->\n"
            "\n### Task Reference\n- A what\n- B what\n"
        )
        merged, notes = merge_auto_extracted_block(existing, new)
        assert notes == ["no_change_idempotent"]
        assert merged == existing

    def test_s13_sources_changed_replace_with_h2_after(self):
        existing = (
            "<!-- auto-extracted: v1 | sources: A | chars: 50 -->\n"
            "### Task Reference\n- A what\n\n"
            "## Other Section\n內容保留\n"
        )
        new = (
            "<!-- auto-extracted: v1 | sources: A,B | chars: 100 -->\n"
            "### Task Reference\n- A what\n- B what\n"
        )
        merged, notes = merge_auto_extracted_block(existing, new)
        assert "replaced_auto_block" in notes
        assert "## Other Section" in merged
        assert "內容保留" in merged
        assert "- B what" in merged

    def test_s13_sources_changed_replace_at_eof(self):
        existing = (
            "<!-- auto-extracted: v1 | sources: A | chars: 50 -->\n"
            "### Task Reference\n- A what\n"
        )
        new = (
            "<!-- auto-extracted: v1 | sources: A,B | chars: 100 -->\n"
            "### Task Reference\n- A what\n- B what\n"
        )
        merged, notes = merge_auto_extracted_block(existing, new)
        assert "replaced_auto_block" in notes
        assert "- B what" in merged

    def test_s13_h3_not_a_boundary(self):
        """§v3.1：H3 子節為 managed block 內部，不作邊界。"""
        existing = (
            "<!-- auto-extracted: v1 | sources: A | chars: 50 -->\n"
            "### Sub1\n- x\n### Sub2\n- y\n"
        )
        new = (
            "<!-- auto-extracted: v1 | sources: A,B | chars: 100 -->\n"
            "### Task Reference\n- new\n"
        )
        merged, notes = merge_auto_extracted_block(existing, new)
        assert "replaced_auto_block" in notes
        # 舊 H3 子節應被整塊替換（非保留）
        assert "### Sub1" not in merged
        assert "### Task Reference" in merged


# ============================================================================
# 群組 E：新增語義場景
# ============================================================================


class TestGroupE_Semantics:
    """S17, S19"""

    def test_s17_self_reference_short_circuit(self):
        target = _make_target(target_id="0.18.0-W17-010", source_ticket="0.18.0-W17-010")
        assert detect_self_reference(target) is True
        with patch(LOAD_TICKET_PATH) as mock_load:
            result = extract_context_bundle(target)
        assert result.status == "self_reference"
        assert result.extracted == []
        assert any(sk.reason == "self_reference" for sk in result.skipped)
        assert any("self-reference" in w for w in result.warnings)
        # 關鍵：短路，load_ticket 未被呼叫
        mock_load.assert_not_called()

    def test_s19_cross_version_source(self):
        """target 是 0.18.0，source 是 0.17.5 → 應以 0.17.5 版本呼叫 load_ticket。"""
        target = _make_target(
            target_id="0.18.0-W17-010", source_ticket="0.17.5-W10-001"
        )
        source = _make_source("0.17.5-W10-001")
        captured_versions = []

        def _fake_load(version, tid):
            captured_versions.append(version)
            return source if tid == "0.17.5-W10-001" else None

        with patch(LOAD_TICKET_PATH, side_effect=_fake_load):
            result = extract_context_bundle(target)
        assert "0.17.5" in captured_versions
        assert result.status == "success"
        assert result.extracted[0].source_id == "0.17.5-W10-001"


# ============================================================================
# Render 測試
# ============================================================================


class TestRender:
    def test_render_no_source_returns_empty(self):
        result = ExtractResult(status="no_source", target_ticket_id="T")
        assert render_context_bundle_markdown(result) == ""

    def test_render_self_reference_returns_empty(self):
        result = ExtractResult(status="self_reference", target_ticket_id="T")
        assert render_context_bundle_markdown(result) == ""

    def test_render_all_missing_returns_empty(self):
        result = ExtractResult(status="all_sources_missing", target_ticket_id="T")
        assert render_context_bundle_markdown(result) == ""

    def test_render_success_contains_marker_and_headings(self):
        target = _make_target(source_ticket="0.18.0-W17-001")
        source = _make_source("0.18.0-W17-001")
        with patch(LOAD_TICKET_PATH, return_value=source):
            result = extract_context_bundle(target)
        md = render_context_bundle_markdown(result)
        assert "<!-- auto-extracted:" in md
        assert "sources: 0.18.0-W17-001" in md
        # managed block 不含 ## Context Bundle（該 H2 由 section 容器提供）
        assert "### Task Reference" in md
        assert "### Rationale Chain" in md
        assert AUTO_EXTRACTED_BLOCK_PATTERN.search(md) is not None


# ============================================================================
# 群組 D：CLI 對接（L2 整合 + S16smoke）
# ============================================================================


class TestGroupD_CLI:
    """S14 integration, S16smoke, S20"""

    @pytest.mark.parametrize(
        "flag_case,expected_pattern",
        [
            # W17-002.1 acceptance #1：quiet 預設單行輸出
            ("default", r"\[Context Bundle\] 已抽取（\d+ 項，\d+ 字元）"),
            ("quiet", r"\[Context Bundle\] 已抽取（\d+ 項，\d+ 字元）"),
            ("explicit_non_quiet", r"已從 \d+ 個來源抽取 \d+ 項欄位"),
            ("verbose", r"預覽："),
        ],
    )
    def test_s16smoke_verbosity(self, flag_case, expected_pattern):
        import re as _re

        target = _make_target(source_ticket="0.18.0-W17-001")
        source = _make_source("0.18.0-W17-001")
        with patch(LOAD_TICKET_PATH, return_value=source):
            result = extract_context_bundle(target)
        kwargs = {
            "default": {},
            "quiet": {"quiet": True},
            "explicit_non_quiet": {"quiet": False},
            "verbose": {"verbose": True},
        }[flag_case]
        out = format_cli_summary(result, **kwargs)
        assert _re.search(expected_pattern, out), f"pattern not matched: {out}"

    def test_s14_extract_and_write_writes_section(self, tmp_path):
        """S14：extract_and_write_context_bundle 寫入 ticket md 可見 marker + headings。"""
        target_body = "## Context Bundle\n\n（待自動填入）\n\n## Other\n保留\n"
        target = {
            "id": "0.18.0-W17-010",
            "source_ticket": "0.18.0-W17-001",
            "blocked_by": None,
            "related_to": None,
            "where": {"files": []},
            "_body": target_body,
        }
        source = _make_source("0.18.0-W17-001")

        saved_calls = []

        def _fake_load(version, tid):
            if tid == "0.18.0-W17-010":
                return target
            if tid == "0.18.0-W17-001":
                return source
            return None

        def _fake_save(ticket_obj, path):
            saved_calls.append((ticket_obj, path))

        with patch(
            "ticket_system.lib.context_bundle_extractor.load_ticket",
            side_effect=_fake_load,
        ), patch(
            "ticket_system.lib.context_bundle_extractor.save_ticket",
            side_effect=_fake_save,
        ), patch(
            "ticket_system.lib.context_bundle_extractor.get_ticket_path",
            return_value=tmp_path / "t.md",
        ):
            result, notes = extract_and_write_context_bundle(
                "0.18.0", "0.18.0-W17-010"
            )

        assert result.status == "success"
        assert len(saved_calls) == 1
        written_body = saved_calls[0][0]["_body"]
        assert "<!-- auto-extracted:" in written_body
        assert "### Task Reference" in written_body
        assert "## Other" in written_body  # 其他 section 保留

    def test_s14_idempotent_second_call(self, tmp_path):
        """二次呼叫 sources 不變 → 不再寫入（no_change_idempotent）。"""
        source = _make_source("0.18.0-W17-001")
        # 先渲染一次得到預期 body
        target_ticket = _make_target(source_ticket="0.18.0-W17-001")
        with patch(LOAD_TICKET_PATH, return_value=source):
            first_result = extract_context_bundle(target_ticket)
        rendered = render_context_bundle_markdown(first_result)

        pre_filled_body = f"## Context Bundle\n\n{rendered}\n\n## Other\n保留\n"
        target = {
            "id": "0.18.0-W17-010",
            "source_ticket": "0.18.0-W17-001",
            "blocked_by": None,
            "related_to": None,
            "where": {"files": []},
            "_body": pre_filled_body,
        }

        def _fake_load(version, tid):
            return target if tid == "0.18.0-W17-010" else source

        saved_calls = []
        with patch(
            "ticket_system.lib.context_bundle_extractor.load_ticket",
            side_effect=_fake_load,
        ), patch(
            "ticket_system.lib.context_bundle_extractor.save_ticket",
            side_effect=lambda t, p: saved_calls.append((t, p)),
        ), patch(
            "ticket_system.lib.context_bundle_extractor.get_ticket_path",
            return_value=tmp_path / "t.md",
        ):
            result, notes = extract_and_write_context_bundle(
                "0.18.0", "0.18.0-W17-010"
            )
        assert "no_change_idempotent" in notes
        assert saved_calls == []  # 未寫入

    def test_s20_extraction_exception_non_raising(self, tmp_path):
        """S20：target load 失敗 → 拋 ContextBundleExtractionError（W17-002.1 #5 專屬 Exception）。

        原因鏈以 __cause__ 保留原始例外（RuntimeError），caller 可
        except ContextBundleExtractionError 一次涵蓋所有底層 I/O 問題。
        """
        def _fake_load(version, tid):
            raise RuntimeError("simulated I/O failure")

        with patch(
            "ticket_system.lib.context_bundle_extractor.load_ticket",
            side_effect=_fake_load,
        ):
            with pytest.raises(ContextBundleExtractionError) as exc_info:
                extract_and_write_context_bundle("0.18.0", "0.18.0-W17-010")
        assert isinstance(exc_info.value.__cause__, RuntimeError)

    def test_s20_extract_context_bundle_non_raising_on_source_load_failure(self):
        """extract_context_bundle 對 source load 失敗 → 記錄 warning 不拋例外。"""
        target = _make_target(source_ticket="0.18.0-W17-001")

        def _fake_load(version, tid):
            raise RuntimeError("source fetch broken")

        with patch(LOAD_TICKET_PATH, side_effect=_fake_load):
            result = extract_context_bundle(target)
        # 未拋例外，status 為 all_sources_missing
        assert result.status == "all_sources_missing"
        assert any("失敗" in w for w in result.warnings)


# ============================================================================
# 群組 F：W17-002.1 P2 風格增強（acceptance #1-#10）
# ============================================================================


class TestGroupF_P2Enhancements:
    """W17-002.1 新增 acceptance 對應測試。"""

    # --- acceptance #2：MAX_TOTAL_CHARS rationale ---
    def test_max_total_chars_has_rationale_in_constants(self):
        """常數值從 constants.py 集中管理，並附 rationale 註解（#2, #3）。"""
        from ticket_system.constants import (
            CONTEXT_BUNDLE_MAX_ITEMS_PER_FIELD,
            CONTEXT_BUNDLE_MAX_TOTAL_CHARS,
        )

        assert CONTEXT_BUNDLE_MAX_TOTAL_CHARS == MAX_TOTAL_CHARS == 2000
        assert CONTEXT_BUNDLE_MAX_ITEMS_PER_FIELD == MAX_ITEMS_PER_FIELD == 5

    # --- acceptance #3：Literal 源自 lib/constants.py ---
    def test_literal_values_from_constants(self):
        from ticket_system.constants import (
            CONTEXT_BUNDLE_EXTRACT_STATUSES,
            CONTEXT_BUNDLE_SKIP_REASONS,
            CONTEXT_BUNDLE_SOURCE_KINDS,
        )

        assert CONTEXT_BUNDLE_SOURCE_KINDS == SOURCE_PRIORITY
        # 新增 opt_out 狀態
        assert "opt_out" in CONTEXT_BUNDLE_EXTRACT_STATUSES
        assert "opt_out" in CONTEXT_BUNDLE_SKIP_REASONS

    # --- acceptance #4：SkipRecord dataclass ---
    def test_skip_record_is_dataclass(self):
        from dataclasses import is_dataclass

        from ticket_system.lib.context_bundle_extractor import SkipRecord

        assert is_dataclass(SkipRecord)
        rec = SkipRecord(
            source_id="T", source_kind="source_ticket", reason="source_missing"
        )
        assert rec.detail == ""

    # --- acceptance #6：ac_parser 整合 acceptance 過濾 ---
    def test_ac_parser_filters_checked_acceptance_items(self):
        """已勾選的 acceptance（[x]）應被過濾，不出現在抽取結果中。"""
        target = _make_target(source_ticket="0.18.0-W17-001")
        source = _make_source(
            "0.18.0-W17-001",
            acceptance=[
                "- [x] 已完成 A",
                "- [ ] 未完成 B",
                "- [x] 已完成 C",
                "- [ ] 未完成 D",
            ],
        )
        with patch(LOAD_TICKET_PATH, return_value=source):
            result = extract_context_bundle(target)
        ac_field = next(
            (f for f in result.extracted if f.source_field == "acceptance"), None
        )
        assert ac_field is not None
        # 僅未完成項被保留
        joined = " ".join(ac_field.raw_value)
        assert "未完成 B" in joined
        assert "未完成 D" in joined
        assert "已完成 A" not in joined
        assert "已完成 C" not in joined

    def test_ac_parser_all_checked_yields_no_field(self):
        """所有 acceptance 皆已完成 → 過濾後為空，該欄位不寫入 extracted。"""
        target = _make_target(source_ticket="0.18.0-W17-001")
        source = _make_source(
            "0.18.0-W17-001",
            acceptance=["- [x] done 1", "- [x] done 2"],
        )
        with patch(LOAD_TICKET_PATH, return_value=source):
            result = extract_context_bundle(target)
        assert not any(f.source_field == "acceptance" for f in result.extracted)

    # --- acceptance #7：--json 結構化輸出 ---
    def test_format_cli_summary_json_schema(self):
        target = _make_target(source_ticket="0.18.0-W17-001")
        source = _make_source(
            "0.18.0-W17-001",
            what="task W",
            why="reason R",
            where_files=["a.py"],
            acceptance=["- [ ] ac1"],
        )
        with patch(LOAD_TICKET_PATH, return_value=source):
            result = extract_context_bundle(target)
        out = format_cli_summary_json(result)

        import json as _json

        payload = _json.loads(out)
        assert payload["status"] == "success"
        assert payload["sources_declared"] == 1
        assert payload["sources_ok"] == 1
        assert isinstance(payload["extracted"], list)
        assert isinstance(payload["skipped"], list)
        assert isinstance(payload["warnings"], list)
        assert payload["total_chars_estimate"] >= 0
        # extracted 各項含 required keys
        for f in payload["extracted"]:
            assert set(f.keys()) >= {
                "source_id",
                "source_kind",
                "source_field",
                "target_subsection",
                "truncated",
                "value",
            }

    def test_format_cli_summary_json_for_no_source(self):
        result = ExtractResult(status="no_source", target_ticket_id="T")
        import json as _json

        payload = _json.loads(format_cli_summary_json(result))
        assert payload["status"] == "no_source"
        assert payload["extracted"] == []

    # --- acceptance #8：metric event 埋點 ---
    def test_metric_sink_is_invoked_on_extract(self):
        events: list = []

        def _sink(event_type, payload):
            events.append((event_type, dict(payload)))

        set_metric_sink(_sink)
        try:
            target = _make_target(source_ticket="0.18.0-W17-001")
            source = _make_source("0.18.0-W17-001")
            with patch(LOAD_TICKET_PATH, return_value=source):
                extract_context_bundle(target)
        finally:
            set_metric_sink(None)

        assert len(events) == 1
        event_type, payload = events[0]
        assert event_type == "context_bundle.extract"
        assert payload["status"] == "success"
        assert payload["sources_declared"] == 1
        assert payload["sources_ok"] == 1
        assert payload["fields_extracted"] >= 1
        assert payload["total_chars"] >= 0
        assert payload["truncated_count"] == 0

    def test_metric_sink_failure_does_not_break_extract(self, capsys):
        def _bad_sink(event_type, payload):
            raise RuntimeError("sink boom")

        set_metric_sink(_bad_sink)
        try:
            target = _make_target(source_ticket="0.18.0-W17-001")
            source = _make_source("0.18.0-W17-001")
            with patch(LOAD_TICKET_PATH, return_value=source):
                result = extract_context_bundle(target)
        finally:
            set_metric_sink(None)
        # 主流程仍成功
        assert result.status == "success"
        captured = capsys.readouterr()
        assert "metric sink 失敗" in captured.err

    # --- acceptance #9：opt-out 標記 context-bundle: manual ---
    def test_opt_out_marker_short_circuits_extraction(self):
        target = _make_target(source_ticket="0.18.0-W17-001")
        target["context_bundle"] = "manual"
        with patch(LOAD_TICKET_PATH) as mock_load:
            result = extract_context_bundle(target)
        assert result.status == "opt_out"
        assert result.extracted == []
        assert any(sk.reason == "opt_out" for sk in result.skipped)
        # 短路：未載入 source
        mock_load.assert_not_called()

    def test_opt_out_with_hyphen_key_also_detected(self):
        """支援 YAML key 為 `context-bundle`（hyphen 形式）。"""
        target = _make_target(source_ticket="0.18.0-W17-001")
        target["context-bundle"] = "manual"
        result = extract_context_bundle(target)
        assert result.status == "opt_out"

    def test_opt_out_other_values_do_not_trigger(self):
        """值非 "manual" 時不觸發 opt-out（例如 "auto"）。"""
        target = _make_target(source_ticket="0.18.0-W17-001")
        target["context_bundle"] = "auto"
        source = _make_source("0.18.0-W17-001")
        with patch(LOAD_TICKET_PATH, return_value=source):
            result = extract_context_bundle(target)
        assert result.status == "success"

    def test_render_opt_out_returns_empty(self):
        result = ExtractResult(status="opt_out", target_ticket_id="T")
        assert render_context_bundle_markdown(result) == ""

    def test_format_cli_summary_opt_out_quiet(self):
        result = ExtractResult(status="opt_out", target_ticket_id="T")
        out = format_cli_summary(result)  # quiet 預設
        assert "opt-out" in out

    # --- acceptance #10：placeholder 擴為 list ---
    @pytest.mark.parametrize(
        "placeholder",
        ["待定義", "TBD", "TODO", "待填寫", "(待填寫)", "（待填寫）", "N/A"],
    )
    def test_placeholder_list_detects_common_variants(self, placeholder):
        target = _make_target(source_ticket="0.18.0-W17-001")
        source = _make_source("0.18.0-W17-001", what=placeholder)
        with patch(LOAD_TICKET_PATH, return_value=source):
            result = extract_context_bundle(target)
        # what 欄位應被略過
        assert not any(f.source_field == "what" for f in result.extracted)
        assert any(
            sk.reason == "source_field_undefined" and sk.detail == "what"
            for sk in result.skipped
        )

    # --- acceptance #1：quiet 預設單行 ---
    def test_format_cli_summary_default_is_quiet_single_line(self):
        target = _make_target(source_ticket="0.18.0-W17-001")
        source = _make_source("0.18.0-W17-001")
        with patch(LOAD_TICKET_PATH, return_value=source):
            result = extract_context_bundle(target)
        out = format_cli_summary(result)  # 預設（無 kwargs）
        # 單行
        assert "\n" not in out
        assert "已抽取" in out
