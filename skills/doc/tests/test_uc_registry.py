"""uc_registry 模組測試 — SSOT 解析、豁免判定、self-test、fingerprint。"""

import json

from doc_system.core import uc_registry


def _write_spec(tmp_path, headings):
    """在 tmp_path/docs/app-use-cases.md 寫入標題行。"""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    lines = []
    for uc_id, title in headings:
        lines.append(f"## {uc_id}: {title}")
        lines.append("")
        lines.append("內容...")
        lines.append("")
    (docs_dir / "app-use-cases.md").write_text("\n".join(lines), encoding="utf-8")


class TestParseSsot:
    def test_parses_headings_with_line_numbers(self, tmp_path):
        _write_spec(tmp_path, [("UC-01", "匯入書庫"), ("UC-02", "匯出書庫")])

        result = uc_registry.parse_ssot(str(tmp_path))

        assert set(result.keys()) == {"UC-01", "UC-02"}
        assert result["UC-01"]["title"] == "匯入書庫"
        assert result["UC-01"]["line"] == 1
        assert result["UC-02"]["line"] == 5

    def test_missing_ssot_file_returns_empty(self, tmp_path):
        result = uc_registry.parse_ssot(str(tmp_path))
        assert result == {}

    def test_ignores_three_digit_or_non_standard_headings(self, tmp_path):
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir(parents=True)
        (docs_dir / "app-use-cases.md").write_text(
            "## UC-001: 三位數不合法\n## UC-MP-01: 非標準前綴\n## UC-05: 合法\n",
            encoding="utf-8",
        )

        result = uc_registry.parse_ssot(str(tmp_path))

        assert set(result.keys()) == {"UC-05"}


class TestGetValidUcMap:
    def test_returns_title_only_projection(self, tmp_path):
        _write_spec(tmp_path, [("UC-01", "匯入書庫")])
        assert uc_registry.get_valid_uc_map(str(tmp_path)) == {"UC-01": "匯入書庫"}


class TestIsExemptPath:
    def test_exempts_worklog_path(self, tmp_path):
        p = str(tmp_path / "docs" / "work-logs" / "v1" / "ticket.md")
        assert uc_registry.is_exempt_path(p, str(tmp_path)) is True

    def test_exempts_spec_dir(self, tmp_path):
        p = str(tmp_path / "docs" / "spec" / "uc-numbering-convention.md")
        assert uc_registry.is_exempt_path(p, str(tmp_path)) is True

    def test_exempts_test_fixtures(self, tmp_path):
        p = str(tmp_path / "test" / "fixtures" / "sample.dart")
        assert uc_registry.is_exempt_path(p, str(tmp_path)) is True

    def test_exempts_ssot_file_itself(self, tmp_path):
        p = str(tmp_path / "docs" / "app-use-cases.md")
        assert uc_registry.is_exempt_path(p, str(tmp_path)) is True

    def test_does_not_exempt_lib_code(self, tmp_path):
        p = str(tmp_path / "lib" / "domains" / "book.dart")
        assert uc_registry.is_exempt_path(p, str(tmp_path)) is False


class TestPatternExemptToken:
    def test_exempts_uc_pattern_token(self):
        assert uc_registry.is_pattern_exempt_token("UC-Pattern") is True

    def test_exempts_uc_mp_token(self):
        assert uc_registry.is_pattern_exempt_token("UC-MP") is True

    def test_does_not_exempt_numeric_token(self):
        assert uc_registry.is_pattern_exempt_token("UC-01") is False


class TestFindUcTokensInText:
    def test_finds_tokens_with_line_numbers(self):
        text = "第一行無關\n// 參考 UC-05 步驟 3\n再一行 UC-001.4.20"
        hits = uc_registry.find_uc_tokens_in_text(text)
        assert ("UC-05", 2) in hits
        assert ("UC-001.4.20", 3) in hits


class TestIsViolationToken:
    def test_undefined_two_digit_uc_is_violation(self):
        assert uc_registry.is_violation_token("UC-99", {"UC-01": "x"}) is True

    def test_defined_two_digit_uc_is_not_violation(self):
        assert uc_registry.is_violation_token("UC-01", {"UC-01": "x"}) is False

    def test_three_digit_format_is_violation(self):
        assert uc_registry.is_violation_token("UC-001", {"UC-01": "x"}) is True

    def test_pseudo_subtree_is_violation(self):
        assert uc_registry.is_violation_token("UC-01.4.20", {"UC-01": "x"}) is True

    def test_pattern_token_is_not_violation(self):
        assert uc_registry.is_violation_token("UC-Pattern", {"UC-01": "x"}) is False


class TestSelfTest:
    def test_passes_when_any_valid_uc_present(self, tmp_path):
        headings = [(f"UC-{i:02d}", f"標題{i}") for i in range(1, 4)]
        _write_spec(tmp_path, headings)

        ok, message = uc_registry.self_test(str(tmp_path))

        assert ok is True
        assert "3" in message

    def test_fails_when_ssot_empty(self, tmp_path):
        ok, message = uc_registry.self_test(str(tmp_path))

        assert ok is False
        assert "空" in message

    def test_fails_when_malformed_key_present(self, tmp_path, monkeypatch):
        _write_spec(tmp_path, [("UC-01", "合法")])
        monkeypatch.setattr(
            uc_registry,
            "get_valid_uc_map",
            lambda project_root: {"UC-01": "合法", "UC-XYZ": "格式異常"},
        )

        ok, message = uc_registry.self_test(str(tmp_path))

        assert ok is False
        assert "UC-XYZ" in message

    def test_real_project_spec_has_at_least_one_valid_uc(self):
        """回歸驗證：本專案現行 docs/app-use-cases.md 應解析出至少一個合法 UC。"""
        from doc_system.core.file_locator import FileLocator

        project_root = FileLocator.get_project_root()
        ok, message = uc_registry.self_test(project_root)
        assert ok is True, message


class TestNormalizeToken:
    def test_uppercases_lowercase_token(self):
        assert uc_registry.normalize_token("uc-01") == "UC-01"

    def test_converts_fullwidth_hyphen_and_digits(self):
        assert uc_registry.normalize_token("ＵＣ－０１") == "UC-01"

    def test_leaves_already_normalized_token_unchanged(self):
        assert uc_registry.normalize_token("UC-01") == "UC-01"


class TestTokenVariantDetection:
    def test_lowercase_variant_is_found(self):
        hits = uc_registry.find_uc_tokens_in_text("參考 uc-01 步驟")
        assert ("uc-01", 1) in hits

    def test_fullwidth_variant_is_found(self):
        hits = uc_registry.find_uc_tokens_in_text("參考 ＵＣ－０１ 步驟")
        assert ("ＵＣ－０１", 1) in hits

    def test_lowercase_variant_violation_judged_after_normalize(self):
        assert uc_registry.is_violation_token("uc-99", {"UC-01": "x"}) is True
        assert uc_registry.is_violation_token("uc-01", {"UC-01": "x"}) is False

    def test_plain_word_containing_uc_prefix_without_dash_not_matched(self):
        """負向案例：合法描述文字「uc verify 命令」不應被誤判為 token（無連字號緊接）。"""
        hits = uc_registry.find_uc_tokens_in_text("執行 uc verify 命令")
        assert hits == []


class TestGetUcSummary:
    def test_returns_none_when_uc_not_in_ssot(self, tmp_path):
        _write_spec(tmp_path, [("UC-01", "匯入書庫")])
        assert uc_registry.get_uc_summary("UC-99", str(tmp_path)) is None

    def test_returns_title_and_spec_location(self, tmp_path):
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir(parents=True)
        (docs_dir / "app-use-cases.md").write_text(
            "## UC-01: 匯入書庫\n\n### 主要成功場景\n\n1. **選擇檔案**\n   - 細節\n",
            encoding="utf-8",
        )

        summary = uc_registry.get_uc_summary("UC-01", str(tmp_path))

        assert summary["uc_id"] == "UC-01"
        assert summary["title"] == "匯入書庫"
        assert summary["spec_path"] == "docs/app-use-cases.md"
        assert summary["spec_line"] == 1
        assert summary["main_flow"] == ["1. **選擇檔案**"]
        assert summary["is_section_summary"] is False

    def test_main_flow_stops_at_next_h3(self, tmp_path):
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir(parents=True)
        (docs_dir / "app-use-cases.md").write_text(
            "## UC-01: 標題\n\n"
            "### 主要成功場景\n\n"
            "1. **步驟一**\n   - 細節\n\n"
            "2. **步驟二**\n\n"
            "### 替代流程\n\n"
            "1. **不應被收錄**\n",
            encoding="utf-8",
        )

        summary = uc_registry.get_uc_summary("UC-01", str(tmp_path))

        assert summary["main_flow"] == ["1. **步驟一**", "2. **步驟二**"]

    def test_missing_main_flow_heading_falls_back_to_section_titles(self, tmp_path):
        """無「主要成功場景」時 fallback 收集章節標題，並標記 is_section_summary（W1-076 修復）。"""
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir(parents=True)
        (docs_dir / "app-use-cases.md").write_text(
            "## UC-05: 標題\n\n### 其他標題\n內容\n",
            encoding="utf-8",
        )

        summary = uc_registry.get_uc_summary("UC-05", str(tmp_path))

        assert summary["main_flow"] == ["其他標題"]
        assert summary["is_section_summary"] is True

    def test_no_main_flow_and_no_section_headings_returns_empty_list(self, tmp_path):
        """區塊內完全無 `### ` 標題時，fallback 也無內容可摘要，回傳空 list 且非 section summary。"""
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir(parents=True)
        (docs_dir / "app-use-cases.md").write_text(
            "## UC-05: 標題\n\n內容，無任何 H3 標題\n",
            encoding="utf-8",
        )

        summary = uc_registry.get_uc_summary("UC-05", str(tmp_path))

        assert summary["main_flow"] == []
        assert summary["is_section_summary"] is False

    def test_truncates_to_max_steps(self, tmp_path):
        steps = "\n".join(f"{i}. **步驟{i}**" for i in range(1, 15))
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir(parents=True)
        (docs_dir / "app-use-cases.md").write_text(
            f"## UC-01: 標題\n\n### 主要成功場景\n\n{steps}\n",
            encoding="utf-8",
        )

        summary = uc_registry.get_uc_summary("UC-01", str(tmp_path))

        assert len(summary["main_flow"]) == uc_registry.MAX_MAIN_FLOW_STEPS
        assert summary["main_flow"][0] == "1. **步驟1**"
        assert summary["main_flow"][-1] == "10. **步驟10**"

    def test_does_not_leak_into_next_uc_subheading(self, tmp_path):
        """次級標題如 `## 6A.` 不應被誤判為下一個合法 UC 導致提前中止（W1-066.4 修復回歸）。

        真實案例 UC-06：`## 6A. 圖書館借書管理` 在「### 主要成功場景」之前出現，
        若誤判為新 UC 邊界會導致步驟一項都收不到。
        """
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir(parents=True)
        (docs_dir / "app-use-cases.md").write_text(
            "## UC-06: 標題\n\n"
            "### 基本資訊\n內容\n\n"
            "## 6A. 子場景\n\n"
            "### 主要成功場景\n\n"
            "1. **步驟一**\n\n"
            "## 6B. 子場景2\n\n"
            "### 主要成功場景\n\n"
            "1. **步驟二**\n",
            encoding="utf-8",
        )

        summary = uc_registry.get_uc_summary("UC-06", str(tmp_path))

        assert summary["main_flow"] == ["[6A] 1. **步驟一**", "[6B] 1. **步驟二**"]

    def test_merges_multiple_h2_subsection_main_flows_with_label_prefix(self, tmp_path):
        """UC-06 型：`## 6A.`/`## 6B.` 各自的主流程步驟合併，並加子場景前綴（W1-076 修復）。"""
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir(parents=True)
        (docs_dir / "app-use-cases.md").write_text(
            "## UC-06: 標題\n\n"
            "### 基本資訊\n內容\n\n"
            "## 6A. 子場景\n\n"
            "### 主要成功場景\n\n"
            "1. **步驟一**\n\n"
            "2. **步驟二**\n\n"
            "## 6B. 子場景2\n\n"
            "### 主要成功場景\n\n"
            "1. **步驟三**\n\n"
            "### 替代流程\n\n"
            "1. **不應被收錄**\n",
            encoding="utf-8",
        )

        summary = uc_registry.get_uc_summary("UC-06", str(tmp_path))

        assert summary["main_flow"] == [
            "[6A] 1. **步驟一**",
            "[6A] 2. **步驟二**",
            "[6B] 1. **步驟三**",
        ]
        assert summary["is_section_summary"] is False

    def test_merges_h4_sub_scenarios_with_label_prefix(self, tmp_path):
        """UC-08/09 型：單一主流程內以 `#### 8A.` 劃分子場景，加前綴消除編號重複歧義（W1-076 修復）。"""
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir(parents=True)
        (docs_dir / "app-use-cases.md").write_text(
            "## UC-08: 標題\n\n"
            "### 主要成功場景\n\n"
            "#### 8A. 自動版本識別\n\n"
            "1. **觸發版本檢測**\n\n"
            "2. **相似度計算**\n\n"
            "#### 8B. 手動版本管理\n\n"
            "1. **版本管理界面存取**\n\n"
            "### 延伸場景\n\n"
            "#### 8D. 翻譯版本自動識別\n\n"
            "1. **不應被收錄**\n",
            encoding="utf-8",
        )

        summary = uc_registry.get_uc_summary("UC-08", str(tmp_path))

        assert summary["main_flow"] == [
            "[8A] 1. **觸發版本檢測**",
            "[8A] 2. **相似度計算**",
            "[8B] 1. **版本管理界面存取**",
        ]
        assert summary["is_section_summary"] is False

    def test_real_project_uc01_has_main_flow(self):
        """回歸驗證：本專案 UC-01 應能解析出至少一個主流程步驟。"""
        from doc_system.core.file_locator import FileLocator

        project_root = FileLocator.get_project_root()
        summary = uc_registry.get_uc_summary("UC-01", project_root)
        assert summary is not None
        assert len(summary["main_flow"]) > 0

    def test_real_project_standard_ucs_do_not_regress(self):
        """回歸驗證：UC-01~04/07/10（標準單段結構）解析結果不受本次修復影響。"""
        from doc_system.core.file_locator import FileLocator

        project_root = FileLocator.get_project_root()
        for uc_id in ("UC-01", "UC-02", "UC-03", "UC-04", "UC-07", "UC-10"):
            summary = uc_registry.get_uc_summary(uc_id, project_root)
            assert summary is not None, uc_id
            assert len(summary["main_flow"]) > 0, uc_id
            assert summary["is_section_summary"] is False, uc_id
            # 標準單段結構無子場景前綴
            assert all(not step.startswith("[") for step in summary["main_flow"]), uc_id

    def test_real_project_uc05_returns_section_summary(self):
        """回歸驗證：UC-05（無主要成功場景）fallback 回傳非空章節標題摘要（W1-076 acceptance 1）。"""
        from doc_system.core.file_locator import FileLocator

        project_root = FileLocator.get_project_root()
        summary = uc_registry.get_uc_summary("UC-05", project_root)
        assert summary is not None
        assert len(summary["main_flow"]) > 0
        assert summary["is_section_summary"] is True

    def test_real_project_uc06_merges_6a_6b_with_prefix(self):
        """回歸驗證：UC-06 合併 6A+6B 主流程步驟並加子場景前綴（W1-076 acceptance 2）。"""
        from doc_system.core.file_locator import FileLocator

        project_root = FileLocator.get_project_root()
        summary = uc_registry.get_uc_summary("UC-06", project_root)
        assert summary is not None
        assert summary["is_section_summary"] is False
        labels = {step.split("]")[0].lstrip("[") for step in summary["main_flow"]}
        assert labels == {"6A", "6B"}

    def test_real_project_uc08_uc09_prefix_h4_sub_scenarios(self):
        """回歸驗證：UC-08/09 的 H4 子場景步驟加前綴消除編號重複歧義（W1-076 acceptance 3）。"""
        from doc_system.core.file_locator import FileLocator

        project_root = FileLocator.get_project_root()
        for uc_id in ("UC-08", "UC-09"):
            summary = uc_registry.get_uc_summary(uc_id, project_root)
            assert summary is not None, uc_id
            assert summary["is_section_summary"] is False, uc_id
            assert all(step.startswith("[") for step in summary["main_flow"]), uc_id
            # 同前綴內步驟編號從 1 開始（未跨子場景累加）
            first_label = summary["main_flow"][0].split("]")[0].lstrip("[")
            assert summary["main_flow"][0].split("] ", 1)[1].startswith("1. "), uc_id
            assert first_label


class TestIsExemptPathWorktree:
    def test_exempts_worklog_path_when_file_outside_project_root(self, tmp_path):
        """worktree 情境：file_path 位於與 project_root 不同根的鏡射目錄下，
        relpath 前綴比對恆假，須靠絕對路徑片段比對（錨點 2）辨識豁免。
        """
        worktree_root = tmp_path / "worktree-a"
        p = worktree_root / "docs" / "work-logs" / "v1" / "ticket.md"
        p.parent.mkdir(parents=True)
        p.write_text("內容", encoding="utf-8")

        main_root = tmp_path / "main-repo"
        main_root.mkdir()

        assert uc_registry.is_exempt_path(str(p), str(main_root)) is True

    def test_does_not_exempt_lib_code_when_outside_project_root(self, tmp_path):
        worktree_root = tmp_path / "worktree-a"
        p = worktree_root / "lib" / "domains" / "book.dart"
        p.parent.mkdir(parents=True)
        p.write_text("內容", encoding="utf-8")

        main_root = tmp_path / "main-repo"
        main_root.mkdir()

        assert uc_registry.is_exempt_path(str(p), str(main_root)) is False


def _write_spec_with_content(tmp_path, sections):
    """寫入含完整內容的 spec，sections 為 [(uc_id, title, body), ...]。"""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    lines = []
    for uc_id, title, body in sections:
        lines.append(f"## {uc_id}: {title}")
        lines.append("")
        lines.append(body)
        lines.append("")
    (docs_dir / "app-use-cases.md").write_text("\n".join(lines), encoding="utf-8")


class TestParseSsotWithContent:
    def test_returns_content_for_each_uc(self, tmp_path):
        _write_spec_with_content(
            tmp_path,
            [("UC-01", "匯入", "匯入功能描述"), ("UC-02", "匯出", "匯出功能描述")],
        )
        result = uc_registry.parse_ssot_with_content(str(tmp_path))

        assert set(result.keys()) == {"UC-01", "UC-02"}
        assert "匯入功能描述" in result["UC-01"]["content"]
        assert "匯出功能描述" in result["UC-02"]["content"]
        assert result["UC-01"]["title"] == "匯入"
        assert result["UC-01"]["line"] == 1

    def test_content_starts_with_heading(self, tmp_path):
        _write_spec_with_content(tmp_path, [("UC-01", "標題", "內容")])
        result = uc_registry.parse_ssot_with_content(str(tmp_path))
        assert result["UC-01"]["content"].startswith("## UC-01: 標題")

    def test_content_does_not_leak_into_next_uc(self, tmp_path):
        _write_spec_with_content(
            tmp_path,
            [("UC-01", "A", "A 的內容"), ("UC-02", "B", "B 的內容")],
        )
        result = uc_registry.parse_ssot_with_content(str(tmp_path))
        assert "B 的內容" not in result["UC-01"]["content"]
        assert "A 的內容" not in result["UC-02"]["content"]

    def test_missing_ssot_returns_empty(self, tmp_path):
        assert uc_registry.parse_ssot_with_content(str(tmp_path)) == {}


class TestComputeFingerprint:
    def test_deterministic(self):
        fp1 = uc_registry.compute_fingerprint("hello")
        fp2 = uc_registry.compute_fingerprint("hello")
        assert fp1 == fp2

    def test_different_content_different_fingerprint(self):
        fp1 = uc_registry.compute_fingerprint("hello")
        fp2 = uc_registry.compute_fingerprint("world")
        assert fp1 != fp2

    def test_returns_hex_string(self):
        fp = uc_registry.compute_fingerprint("test")
        assert len(fp) == 64
        assert all(c in "0123456789abcdef" for c in fp)


class TestUpdateFingerprints:
    def test_creates_sidecar_json(self, tmp_path):
        _write_spec_with_content(tmp_path, [("UC-01", "標題", "內容")])
        uc_registry.update_fingerprints(str(tmp_path))

        sidecar = tmp_path / uc_registry.FINGERPRINT_SIDECAR_FILENAME
        assert sidecar.is_file()
        data = json.loads(sidecar.read_text(encoding="utf-8"))
        assert "UC-01" in data
        assert "fingerprint" in data["UC-01"]
        assert "title" in data["UC-01"]
        assert "updated_at" in data["UC-01"]

    def test_returns_fingerprint_dict(self, tmp_path):
        _write_spec_with_content(
            tmp_path,
            [("UC-01", "A", "內容A"), ("UC-02", "B", "內容B")],
        )
        result = uc_registry.update_fingerprints(str(tmp_path))
        assert len(result) == 2
        assert result["UC-01"]["title"] == "A"

    def test_empty_ssot_returns_empty(self, tmp_path):
        result = uc_registry.update_fingerprints(str(tmp_path))
        assert result == {}


class TestCheckFingerprints:
    def test_no_drift_when_unchanged(self, tmp_path):
        _write_spec_with_content(tmp_path, [("UC-01", "標題", "內容")])
        uc_registry.update_fingerprints(str(tmp_path))

        drifted, added, removed = uc_registry.check_fingerprints(str(tmp_path))
        assert drifted == []
        assert added == []
        assert removed == []

    def test_detects_content_drift(self, tmp_path):
        _write_spec_with_content(tmp_path, [("UC-01", "標題", "原始內容")])
        uc_registry.update_fingerprints(str(tmp_path))

        _write_spec_with_content(tmp_path, [("UC-01", "標題", "修改後的內容")])
        drifted, added, removed = uc_registry.check_fingerprints(str(tmp_path))
        assert drifted == ["UC-01"]
        assert added == []
        assert removed == []

    def test_detects_added_uc(self, tmp_path):
        _write_spec_with_content(tmp_path, [("UC-01", "A", "內容")])
        uc_registry.update_fingerprints(str(tmp_path))

        _write_spec_with_content(
            tmp_path,
            [("UC-01", "A", "內容"), ("UC-02", "B", "新增")],
        )
        drifted, added, removed = uc_registry.check_fingerprints(str(tmp_path))
        assert added == ["UC-02"]

    def test_detects_removed_uc(self, tmp_path):
        _write_spec_with_content(
            tmp_path,
            [("UC-01", "A", "內容"), ("UC-02", "B", "移除")],
        )
        uc_registry.update_fingerprints(str(tmp_path))

        _write_spec_with_content(tmp_path, [("UC-01", "A", "內容")])
        drifted, added, removed = uc_registry.check_fingerprints(str(tmp_path))
        assert removed == ["UC-02"]

    def test_no_sidecar_returns_empty(self, tmp_path):
        _write_spec_with_content(tmp_path, [("UC-01", "標題", "內容")])
        drifted, added, removed = uc_registry.check_fingerprints(str(tmp_path))
        assert drifted == []
        assert added == []
        assert removed == []

    def test_title_change_detected_as_drift(self, tmp_path):
        _write_spec_with_content(tmp_path, [("UC-01", "原始標題", "內容")])
        uc_registry.update_fingerprints(str(tmp_path))

        _write_spec_with_content(tmp_path, [("UC-01", "新標題", "內容")])
        drifted, _, _ = uc_registry.check_fingerprints(str(tmp_path))
        assert drifted == ["UC-01"]
