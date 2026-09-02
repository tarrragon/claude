"""RED tests for broken-link-check 確定性 CLI scanner (scan_links.py).

TDD Phase 2。目標被測物尚未實作，全部測試應 RED
（ModuleNotFoundError / AttributeError 皆為合法 RED）。

測試切點 (規格 §6 SOLID)：
- 純函式單元：extract_refs / classify_ref / resolve_path（無 I/O，主力覆蓋）
- 整合：scan() + CLI exit code (0/1/2) + --format json schema
- 9 條 GWT 全覆蓋（正常 / 異常 / 邊界 / 確定性）

約束：
- 計數類斷言一律用受控 synthetic fixture，禁對 live .claude/ 樹斷言固定數字
  (baseline=164 為 ANA 時間點量測，會隨後續清理變動)。
- 確定性場景 byte-for-byte 比對，禁用計時斷言 (test-assertion 規則 1)。
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

# 被測模組（尚未實作 → import 即 RED）
import scan_links  # noqa: E402

SCRIPT = Path(__file__).resolve().parent.parent / "scan_links.py"


# ---------------------------------------------------------------------------
# Fixtures: 受控 synthetic repo 樹（計數確定，不依賴 live .claude/）
# ---------------------------------------------------------------------------


@pytest.fixture
def synthetic_repo(tmp_path):
    """建立一個已知計數的 .claude/ 樹。

    內容設計（預設旋鈕：排除 code block + placeholder + backup）：
    - good.md     → 1 個有效引用 (@.claude/target.md 存在)
    - broken.md   → 1 個 broken 引用 (.claude/missing/gone.md 不存在)
    - code.md     → 1 個 broken 引用，但在 fenced code block 內 → 預設不計
    - holder.md   → 1 個 placeholder 範例 (path/file.md) → 不計 broken
    - backup ref  → resolved 落在 migration-backups/ → 預設不計
    預設旋鈕下 broken_count == 1（僅 broken.md）。
    """
    claude = tmp_path / ".claude"
    claude.mkdir()
    (claude / "target.md").write_text("# target\n")
    (claude / "good.md").write_text("see @.claude/target.md for detail\n")
    (claude / "broken.md").write_text("ref .claude/missing/gone.md here\n")
    (claude / "code.md").write_text(
        "before\n```\nref .claude/in/code/block.md\n```\nafter\n"
    )
    (claude / "holder.md").write_text(
        "| 範例 | path/file.md |\n| 另一 | ./path/file.md |\n"
    )
    # backup 引用：指向 migration-backups 下不存在檔（預設排除分類）
    (claude / "backup.md").write_text(
        "ref .claude/migration-backups/old/x.md here\n"
    )
    return tmp_path


@pytest.fixture
def clean_repo(tmp_path):
    """無任何 broken 引用的 repo（gate pass）。"""
    claude = tmp_path / ".claude"
    claude.mkdir()
    (claude / "target.md").write_text("# target\n")
    (claude / "good.md").write_text("see @.claude/target.md ok\n")
    return tmp_path


def run_cli(repo_root, *args):
    """以子進程執行 scan_links.py，回傳 CompletedProcess。"""
    cmd = [sys.executable, str(SCRIPT), str(repo_root), *args]
    return subprocess.run(cmd, capture_output=True, text=True)


# ===========================================================================
# A. 純函式單元測試（無 I/O 主力覆蓋）
# ===========================================================================


class TestExtractRefs:
    """extract_refs(text) → 抽 4 種前綴引用 + code-block 區段標記。"""

    def test_extracts_four_prefix_kinds(self):
        text = (
            "a @.claude/a.md\n"
            "b .claude/b.md\n"
            "c ../c.md\n"
            "d ./d.md\n"
        )
        refs = scan_links.extract_refs(text)
        raws = {r.raw_ref if hasattr(r, "raw_ref") else r["raw_ref"] for r in refs}
        assert "@.claude/a.md" in raws
        assert ".claude/b.md" in raws
        assert "../c.md" in raws
        assert "./d.md" in raws

    def test_records_line_numbers(self):
        text = "line1\n@.claude/x.md\nline3\n"
        refs = scan_links.extract_refs(text)
        line = refs[0].line if hasattr(refs[0], "line") else refs[0]["line"]
        assert line == 2

    def test_ignores_http_and_anchor(self):
        text = "see https://example.com/x.md and #section.md\n"
        refs = scan_links.extract_refs(text)
        assert refs == [] or len(refs) == 0

    def test_marks_refs_inside_code_block(self):
        # GWT #9：code block 內引用須被標記為 in-code-block
        text = "out @.claude/out.md\n```\nin .claude/in.md\n```\n"
        refs = scan_links.extract_refs(text)
        by_raw = {
            (r.raw_ref if hasattr(r, "raw_ref") else r["raw_ref"]): r for r in refs
        }
        in_ref = by_raw[".claude/in.md"]
        flag = (
            in_ref.in_code_block
            if hasattr(in_ref, "in_code_block")
            else in_ref["in_code_block"]
        )
        assert flag is True

    def test_unclosed_fence_extends_to_eof(self):
        # 規格：奇數 fence 視為未閉合，到檔尾
        text = "```\n.claude/a.md\n.claude/b.md\n"
        refs = scan_links.extract_refs(text)
        for r in refs:
            flag = r.in_code_block if hasattr(r, "in_code_block") else r["in_code_block"]
            assert flag is True


class TestResolvePath:
    """resolve_path(raw, source_file, root) → 引用轉實際路徑。"""

    def test_at_prefix_resolves_from_root(self, tmp_path):
        result = scan_links.resolve_path(
            "@.claude/x.md", tmp_path / ".claude" / "src.md", tmp_path
        )
        assert Path(result) == tmp_path / ".claude" / "x.md"

    def test_bare_claude_resolves_from_root(self, tmp_path):
        result = scan_links.resolve_path(
            ".claude/y.md", tmp_path / ".claude" / "sub" / "src.md", tmp_path
        )
        assert Path(result) == tmp_path / ".claude" / "y.md"

    def test_dotdot_relative_to_source_dir(self, tmp_path):
        src = tmp_path / ".claude" / "sub" / "src.md"
        result = scan_links.resolve_path("../sibling.md", src, tmp_path)
        assert Path(result) == tmp_path / ".claude" / "sibling.md"

    def test_dot_relative_to_source_dir(self, tmp_path):
        src = tmp_path / ".claude" / "sub" / "src.md"
        result = scan_links.resolve_path("./local.md", src, tmp_path)
        assert Path(result) == tmp_path / ".claude" / "sub" / "local.md"


class TestClassifyRef:
    """classify_ref(raw, resolved, knobs) → broken/placeholder/excluded_*。"""

    DEFAULT_KNOBS = {
        "include_code_block": False,
        "include_migration_backups": False,
        "include_placeholder": False,
    }

    def test_placeholder_pattern_classified_placeholder(self):
        cat = scan_links.classify_ref(
            "path/file.md", "path/file.md", self.DEFAULT_KNOBS, exists=False
        )
        assert cat == "placeholder"

    def test_backup_path_excluded_by_default(self):
        cat = scan_links.classify_ref(
            ".claude/migration-backups/o.md",
            "/repo/.claude/migration-backups/o.md",
            self.DEFAULT_KNOBS,
            exists=False,
        )
        assert cat == "excluded_backup"

    def test_missing_real_path_is_broken(self):
        cat = scan_links.classify_ref(
            "@.claude/real/gone.md",
            "/repo/.claude/real/gone.md",
            self.DEFAULT_KNOBS,
            exists=False,
        )
        assert cat == "broken"

    def test_existing_path_not_broken(self):
        cat = scan_links.classify_ref(
            "@.claude/real/here.md",
            "/repo/.claude/real/here.md",
            self.DEFAULT_KNOBS,
            exists=True,
        )
        assert cat != "broken"

    def test_backup_counted_when_knob_on(self):
        knobs = {**self.DEFAULT_KNOBS, "include_migration_backups": True}
        cat = scan_links.classify_ref(
            ".claude/migration-backups/o.md",
            "/repo/.claude/migration-backups/o.md",
            knobs,
            exists=False,
        )
        assert cat == "broken"


class TestPlaceholderPatternDetection:
    """缺陷 2：placeholder 改樣式偵測（glob/角括號/模板/token）。

    原 PLACEHOLDER_SAMPLES 4 項 exact-match 漏掉大量樣式型範例路徑，
    導致 SKILL/規則文件中的示意路徑被誤判 broken（FP）。
    """

    DEFAULT_KNOBS = {
        "include_code_block": False,
        "include_migration_backups": False,
        "include_placeholder": False,
    }

    @pytest.mark.parametrize(
        "raw",
        [
            ".claude/agents/*.md",          # 單層 glob
            ".claude/rules/**/*.md",        # 遞迴 glob
            ".claude/error-patterns/PC-061-*.md",  # 部分 glob
            ".claude/references/<檔名>.md",  # 角括號（中文）
            ".claude/agents/<agent>.md",    # 角括號（英文）
            ".claude/skills/{name}/SKILL.md",  # 模板大括號
            ".claude/rules/core/quality-{language}.md",  # 模板大括號
            "../tickets/xxx.md",            # xxx token
            ".claude/agents/TEST.md",       # TEST sentinel
            ".claude/agents/TEST_AGENT_1.md",  # TEST_ sentinel
        ],
    )
    def test_pattern_placeholders_classified_placeholder(self, raw):
        cat = scan_links.classify_ref(
            raw, "/repo/" + raw, self.DEFAULT_KNOBS, exists=False
        )
        assert cat == "placeholder", f"{raw!r} 應歸 placeholder"

    def test_lowercase_test_in_real_name_not_placeholder(self):
        # 反例守護：真實檔名含小寫 test（test-helper-design）不可被誤排除
        raw = ".claude/methodologies/test-helper-design-methodology.md"
        cat = scan_links.classify_ref(
            raw, "/repo/" + raw, self.DEFAULT_KNOBS, exists=False
        )
        assert cat == "broken", "含小寫 test 的真實檔名不應誤判為 placeholder"

    def test_pattern_counted_broken_when_placeholder_knob_on(self):
        knobs = {**self.DEFAULT_KNOBS, "include_placeholder": True}
        cat = scan_links.classify_ref(
            ".claude/agents/*.md", "/repo/.claude/agents/*.md", knobs, exists=False
        )
        assert cat == "broken"


class TestW2011PlaceholderPatternDetection:
    """triage A 類 8 筆——skill-name/vX/示範 skill 名/
    省略號縮寫樣式納入 placeholder 偵測。"""

    DEFAULT_KNOBS = {
        "include_code_block": False,
        "include_migration_backups": False,
        "include_placeholder": False,
    }

    @pytest.mark.parametrize(
        "raw",
        [
            "./../skills/skill-name/SKILL.md",  # skill-name 範本佔位
            "../vX-main.md",  # vX 版本佔位
            "../case-first/SKILL.md",  # 示範 skill 名
            "../sibling-skill/references/x.md",  # 示範 skill 名
            ".claude/error-patterns/process-compliance/PC-050-...md",  # 省略號縮寫
        ],
    )
    def test_w2011_a_class_classified_placeholder(self, raw):
        cat = scan_links.classify_ref(
            raw, "/repo/" + raw, self.DEFAULT_KNOBS, exists=False
        )
        assert cat == "placeholder", f"{raw!r} 應歸 placeholder（triage A 類）"

    def test_vx_not_confused_with_real_version_dir(self):
        # 反例守護：真實版本目錄（v0.13.0-... 以數字開頭）不可誤判為 vX 佔位
        raw = ".claude/work-logs/v0.13.0-pdf-cleanup-task.md"
        cat = scan_links.classify_ref(
            raw, "/repo/" + raw, self.DEFAULT_KNOBS, exists=False
        )
        assert cat == "broken", "真實版本目錄不應誤判為 vX 佔位"

    def test_ellipsis_not_confused_with_relative_prefix(self):
        # 反例守護：../ 相對路徑前綴不可誤判為省略號縮寫
        raw = "../real/target.md"
        cat = scan_links.classify_ref(
            raw, "/repo/" + raw, self.DEFAULT_KNOBS, exists=False
        )
        assert cat == "broken", "../ 相對路徑前綴不應誤判為省略號縮寫"


class TestArchiveSourceExclusion:
    """triage D 類 21 筆——歷史封存文件來源端排除
    （hook-specs 驗收報告/複本、*_SUMMARY/*_CHECKLIST、CHANGELOG、
    .sync-conflicts/、skills/pre-fix-eval/INDEX.md）。"""

    @pytest.mark.parametrize(
        "source_posix",
        [
            ".claude/hook-specs/pre-fix-evaluation-acceptance-report.md",
            ".claude/hook-specs/pre-fix-evaluation-implementation.md",
            ".claude/skills/pre-fix-eval/references/pre-fix-evaluation-acceptance-report.md",
            ".claude/skills/pre-fix-eval/INTEGRATION_SUMMARY.md",
            ".claude/skills/pre-fix-eval/VERIFICATION_CHECKLIST.md",
            ".claude/skills/pre-fix-eval/INDEX.md",
            ".claude/CHANGELOG.md",
            ".claude/.sync-conflicts/CHANGELOG.md",
        ],
    )
    def test_archive_basenames_classified_archive_source(self, source_posix):
        assert scan_links.is_archive_source(source_posix) is True, (
            f"{source_posix!r} 應判定為歷史封存來源"
        )

    def test_non_archive_source_not_classified(self):
        assert scan_links.is_archive_source(".claude/skills/pre-fix-eval/SKILL.md") is False

    @pytest.fixture
    def archive_source_repo(self, tmp_path):
        claude = tmp_path / ".claude"
        (claude / "hook-specs").mkdir(parents=True)
        (claude / "hook-specs" / "pre-fix-evaluation-acceptance-report.md").write_text(
            "ref .claude/plans/iterative-swimming-feather.md here\n"
        )
        # 對照：正常檔的真實斷鏈仍須被偵測
        (claude / "live.md").write_text("ref .claude/real/gone.md here\n")
        return tmp_path

    def test_archive_source_refs_excluded(self, archive_source_repo):
        result = scan_links.scan(archive_source_repo, knobs=None)
        broken = result["broken"]
        srcs = [e["source_file"] for e in broken]
        assert all("hook-specs/" not in s for s in srcs), (
            "source 為歷史封存文件的引用不應計入 broken"
        )
        assert any("live.md" in s for s in srcs)
        assert result["categories"]["excluded_archive"] == 1

    def test_archive_source_counted_when_knob_on(self, archive_source_repo):
        knobs = dict(scan_links.DEFAULT_KNOBS)
        knobs["include_archive"] = True
        result = scan_links.scan(archive_source_repo, knobs=knobs)
        srcs = [e["source_file"] for e in result["broken"]]
        assert any("hook-specs/" in s for s in srcs), (
            "旋鈕開啟時 archive-source 引用應計入"
        )


class TestBackupSourceExclusion:
    """缺陷 1：backup 來源端排除（source 檔在 migration-backups/）。

    原邏輯僅排 resolved target 端，未排除 source_file 本身在
    migration-backups/ 的引用，造成 30 筆 backup 內部斷鏈被計入 broken。
    """

    @pytest.fixture
    def backup_source_repo(self, tmp_path):
        claude = tmp_path / ".claude"
        (claude / "migration-backups" / "old").mkdir(parents=True)
        # source 在 migration-backups/，引用一個不存在的真實樣式路徑
        (claude / "migration-backups" / "old" / "legacy.md").write_text(
            "ref .claude/gone/missing.md here\n"
        )
        # 對照：正常檔的真實斷鏈仍須被偵測
        (claude / "live.md").write_text("ref .claude/real/gone.md here\n")
        return tmp_path

    def test_backup_source_refs_excluded(self, backup_source_repo):
        result = scan_links.scan(backup_source_repo, knobs=None)
        broken = result["broken"]
        srcs = [e["source_file"] for e in broken]
        assert all("migration-backups/" not in s for s in srcs), (
            "source 在 migration-backups/ 的引用不應計入 broken"
        )
        # 正常檔斷鏈仍被偵測
        assert any("live.md" in s for s in srcs)

    def test_backup_source_counted_when_knob_on(self, backup_source_repo):
        knobs = {
            "include_code_block": False,
            "include_migration_backups": True,
            "include_placeholder": False,
        }
        result = scan_links.scan(backup_source_repo, knobs=knobs)
        srcs = [e["source_file"] for e in result["broken"]]
        assert any("migration-backups/" in s for s in srcs), (
            "旋鈕開啟時 backup-source 引用應計入"
        )


# ===========================================================================
# B. scan() 整合 + GWT 場景
# ===========================================================================


class TestScanIntegration:
    def test_gwt2_clean_repo_zero_broken(self, clean_repo):
        # GWT #2：無 broken → broken_count == 0
        result = scan_links.scan(clean_repo, knobs=None)
        bc = result["broken_count"] if isinstance(result, dict) else result.broken_count
        assert bc == 0

    def test_gwt1_known_broken_detected(self, synthetic_repo):
        # GWT #1：已知 broken 被偵測，清單含 source:line
        result = scan_links.scan(synthetic_repo, knobs=None)
        broken = result["broken"] if isinstance(result, dict) else result.broken
        assert len(broken) == 1
        entry = broken[0]
        src = entry["source_file"] if isinstance(entry, dict) else entry.source_file
        assert "broken.md" in src

    def test_gwt6_placeholder_not_broken(self, synthetic_repo):
        # GWT #6：placeholder 範例不計 broken
        result = scan_links.scan(synthetic_repo, knobs=None)
        broken = result["broken"] if isinstance(result, dict) else result.broken
        srcs = [
            (e["source_file"] if isinstance(e, dict) else e.source_file) for e in broken
        ]
        assert all("holder.md" not in s for s in srcs)

    def test_gwt9_code_block_excluded_by_default(self, synthetic_repo):
        # GWT #9：code block 內 broken 引用預設不計
        result = scan_links.scan(synthetic_repo, knobs=None)
        broken = result["broken"] if isinstance(result, dict) else result.broken
        srcs = [
            (e["source_file"] if isinstance(e, dict) else e.source_file) for e in broken
        ]
        assert all("code.md" not in s for s in srcs)

    def test_gwt9_code_block_included_when_knob_on(self, synthetic_repo):
        # GWT #9：--include-code-block 時才計入
        knobs = {
            "include_code_block": True,
            "include_migration_backups": False,
            "include_placeholder": False,
        }
        result = scan_links.scan(synthetic_repo, knobs=knobs)
        broken = result["broken"] if isinstance(result, dict) else result.broken
        srcs = [
            (e["source_file"] if isinstance(e, dict) else e.source_file) for e in broken
        ]
        assert any("code.md" in s for s in srcs)

    def test_gwt5_backup_knob_increases_count(self, synthetic_repo):
        # GWT #5：--include-migration-backups → broken_count 較預設增加
        default = scan_links.scan(synthetic_repo, knobs=None)
        knobs = {
            "include_code_block": False,
            "include_migration_backups": True,
            "include_placeholder": False,
        }
        widened = scan_links.scan(synthetic_repo, knobs=knobs)
        d = default["broken_count"] if isinstance(default, dict) else default.broken_count
        w = widened["broken_count"] if isinstance(widened, dict) else widened.broken_count
        assert w > d


# ===========================================================================
# C. CLI exit code + JSON schema + 異常路徑
# ===========================================================================


class TestCliExitCodes:
    def test_gwt1_broken_exits_1(self, synthetic_repo):
        # GWT #1：偵測到 broken → exit 1（gate fail）
        proc = run_cli(synthetic_repo)
        assert proc.returncode == 1

    def test_gwt2_clean_exits_0(self, clean_repo):
        # GWT #2：零 broken → exit 0
        proc = run_cli(clean_repo)
        assert proc.returncode == 0

    def test_gwt7_missing_root_exits_2(self, tmp_path):
        # GWT #7：REPO_ROOT 不存在 → exit 2 + stderr 訊息，不輸出假計數
        missing = tmp_path / "does-not-exist"
        proc = run_cli(missing)
        assert proc.returncode == 2
        assert proc.stderr.strip() != ""

    def test_gwt8_unreadable_file_warns_continues(self, synthetic_repo):
        # GWT #8：單檔讀取失敗 → stderr warning + 繼續掃描其餘，exit 反映其餘
        bad = synthetic_repo / ".claude" / "bad.md"
        bad.write_bytes(b"\xff\xfe ref .claude/missing/zzz.md\n")
        bad.chmod(0o000)
        try:
            proc = run_cli(synthetic_repo)
        finally:
            bad.chmod(0o644)
        # 不靜默吞：exit code 為 1（其餘檔仍有 broken）或 2，且非崩潰無輸出
        assert proc.returncode in (1, 2)


class TestJsonSchema:
    def test_json_format_has_stable_schema(self, synthetic_repo):
        # GWT 輸出 schema（規格 §3）：消費介面
        proc = run_cli(synthetic_repo, "--format", "json")
        data = json.loads(proc.stdout)
        for key in (
            "scanned_files",
            "total_refs",
            "broken_count",
            "categories",
            "broken",
        ):
            assert key in data
        assert isinstance(data["broken"], list)
        if data["broken"]:
            entry = data["broken"][0]
            for field in ("source_file", "line", "raw_ref", "resolved_path", "category"):
                assert field in entry

    def test_categories_contains_expected_keys(self, synthetic_repo):
        proc = run_cli(synthetic_repo, "--format", "json")
        data = json.loads(proc.stdout)
        cats = data["categories"]
        assert "broken" in cats


# ===========================================================================
# D. 確定性（GWT #3）— byte-for-byte，禁計時斷言
# ===========================================================================


class TestDeterminism:
    def test_gwt3_consecutive_runs_byte_identical(self, synthetic_repo):
        # GWT #3：連續 2 次 stdout 逐字一致（清單排序穩定）
        p1 = run_cli(synthetic_repo, "--format", "json")
        p2 = run_cli(synthetic_repo, "--format", "json")
        assert p1.stdout == p2.stdout
        assert p1.returncode == p2.returncode

    def test_gwt3_text_format_also_deterministic(self, synthetic_repo):
        p1 = run_cli(synthetic_repo)
        p2 = run_cli(synthetic_repo)
        assert p1.stdout == p2.stdout

    def test_broken_list_sorted_by_source_then_line(self, tmp_path):
        # 排序穩定：source_file → line（規格 §5 場景 3 約束）
        claude = tmp_path / ".claude"
        claude.mkdir()
        (claude / "z.md").write_text("ref .claude/gone1.md\nref .claude/gone2.md\n")
        (claude / "a.md").write_text("ref .claude/gone3.md\n")
        result = scan_links.scan(tmp_path, knobs=None)
        broken = result["broken"] if isinstance(result, dict) else result.broken
        keys = [
            (
                (e["source_file"] if isinstance(e, dict) else e.source_file),
                (e["line"] if isinstance(e, dict) else e.line),
            )
            for e in broken
        ]
        assert keys == sorted(keys)


# ===========================================================================
# E. Live .claude/ 樹 smoke test（不斷言固定數字）
# ===========================================================================


class TestLiveTreeSmoke:
    def test_live_tree_runs_without_crash(self):
        # 約束：禁對 live 樹斷言固定計數；只 smoke（broken_count>=0, exit in {0,1}）
        repo_root = Path(__file__).resolve().parents[4]
        if not (repo_root / ".claude").is_dir():
            pytest.skip("live .claude/ 樹不在預期位置")
        proc = run_cli(repo_root, "--format", "json")
        assert proc.returncode in (0, 1)
        data = json.loads(proc.stdout)
        assert data["broken_count"] >= 0


# ===========================================================================
# F. documented-error 豁免 marker（excluded_documented 類別）
# ===========================================================================


class TestDocumentedExemptMarker:
    """per-line `<!-- broken-link-exempt: documented-error -->` marker。

    error-pattern 案例表中刻意記錄的不存在路徑（confabulation 錯誤參照 /
    歷史遷移檔案軌跡）以行內 marker 豁免，歸 excluded_documented 不計 broken。
    顯式 opt-in（per-occurrence），無 marker 的真實 broken 不受影響。
    """

    DOCUMENTED_KNOBS = {
        "include_code_block": False,
        "include_migration_backups": False,
        "include_placeholder": False,
        "include_documented": True,
    }

    @pytest.fixture
    def documented_repo(self, tmp_path):
        claude = tmp_path / ".claude"
        claude.mkdir()
        # 含 marker 行：documented-intentional broken → excluded_documented
        (claude / "case.md").write_text(
            "| 1 | `.claude/pm-rules/gone.md` | "
            "<!-- broken-link-exempt: documented-error --> |\n"
        )
        # 對照：無 marker 的真實 broken 仍須計入
        (claude / "live.md").write_text("ref .claude/real/missing.md here\n")
        return tmp_path

    def test_marker_line_ref_goes_excluded_documented(self, documented_repo):
        result = scan_links.scan(documented_repo, knobs=None)
        srcs = [e["source_file"] for e in result["broken"]]
        assert all("case.md" not in s for s in srcs)
        assert result["categories"].get("excluded_documented", 0) >= 1

    def test_non_marker_broken_still_broken(self, documented_repo):
        result = scan_links.scan(documented_repo, knobs=None)
        srcs = [e["source_file"] for e in result["broken"]]
        assert any("live.md" in s for s in srcs)

    def test_categories_contains_excluded_documented_key(self, documented_repo):
        result = scan_links.scan(documented_repo, knobs=None)
        assert "excluded_documented" in result["categories"]

    def test_marker_exempts_all_refs_on_same_line(self, tmp_path):
        # 一行多個 documented ref，marker 一次豁免全部（DOC-010:97 場景）
        claude = tmp_path / ".claude"
        claude.mkdir()
        (claude / "multi.md").write_text(
            "| `.claude/a/gone.md` `.claude/b/gone.md` `.claude/c/gone.md` "
            "<!-- broken-link-exempt: documented-error --> |\n"
        )
        result = scan_links.scan(tmp_path, knobs=None)
        assert result["broken_count"] == 0
        assert result["categories"]["excluded_documented"] == 3

    def test_marker_does_not_exempt_other_lines(self, tmp_path):
        # PC-146 防護：marker 只豁免本行，他行真實 broken 不受影響
        claude = tmp_path / ".claude"
        claude.mkdir()
        (claude / "mix.md").write_text(
            "exempt .claude/x/gone.md <!-- broken-link-exempt: documented-error -->\n"
            "real .claude/y/gone.md here\n"
        )
        result = scan_links.scan(tmp_path, knobs=None)
        broken_lines = [e["line"] for e in result["broken"]]
        assert broken_lines == [2]
        assert result["categories"]["excluded_documented"] == 1

    def test_existing_path_on_marker_line_stays_ok(self, tmp_path):
        # marker 僅影響「不存在」的引用；存在者仍歸 ok（不誤計 excluded_documented）
        claude = tmp_path / ".claude"
        claude.mkdir()
        (claude / "target.md").write_text("# t\n")
        (claude / "case.md").write_text(
            "ref @.claude/target.md <!-- broken-link-exempt: documented-error -->\n"
        )
        result = scan_links.scan(tmp_path, knobs=None)
        assert result["broken_count"] == 0
        assert result["categories"]["excluded_documented"] == 0

    def test_documented_counted_broken_when_knob_on(self, documented_repo):
        # --include-documented：marker 行也計入 broken（對稱既有三旋鈕）
        result = scan_links.scan(documented_repo, knobs=self.DOCUMENTED_KNOBS)
        srcs = [e["source_file"] for e in result["broken"]]
        assert any("case.md" in s for s in srcs)

    def test_classify_ref_exempt_only_affects_broken(self):
        # 單元：exempt=True 但 exists=True → 非 excluded_documented
        knobs = {
            "include_code_block": False,
            "include_migration_backups": False,
            "include_placeholder": False,
            "include_documented": False,
        }
        cat = scan_links.classify_ref(
            "@.claude/here.md", "/repo/.claude/here.md", knobs,
            exists=True, exempt=True,
        )
        assert cat == "ok"
        cat2 = scan_links.classify_ref(
            "@.claude/gone.md", "/repo/.claude/gone.md", knobs,
            exists=False, exempt=True,
        )
        assert cat2 == "excluded_documented"

    def test_cli_include_documented_flag(self, documented_repo):
        # CLI 旋鈕：--include-documented 使 marker 行計入 → exit 1
        default = run_cli(documented_repo, "--format", "json")
        widened = run_cli(documented_repo, "--include-documented", "--format", "json")
        d = json.loads(default.stdout)["broken_count"]
        w = json.loads(widened.stdout)["broken_count"]
        assert w > d


# ===========================================================================
# G. 掃描根擴充（docs/ 規劃文件納入偵測）
#
# 三類回歸覆蓋：預設行為不變 / 新掃描根生效 / 排除規則在新範圍正確運作。
# ===========================================================================


@pytest.fixture
def docs_scan_repo(tmp_path):
    """`.claude/` + `docs/` 雙子樹合成 repo，用於掃描根擴充回歸測試。

    `.claude/` 內容（沿用 synthetic_repo 慣例，無 broken）：
    - target.md / good.md

    `docs/` 內容（皆為 `.claude/` 路徑引用，模擬規劃文件內容）：
    - docs/tickets/broken.md      → 1 個真實斷鏈
    - docs/tickets/code.md        → 1 個斷鏈但在 fenced code block 內 → 預設不計
    - docs/tickets/holder.md      → 1 個 placeholder 範例 → 不計 broken
    - docs/tickets/backup.md      → 1 個 migration-backups 下路徑 → 預設不計
    - docs/tickets/documented.md  → 1 個含 exempt marker 的不存在路徑 → 不計 broken
    """
    claude = tmp_path / ".claude"
    claude.mkdir()
    (claude / "target.md").write_text("# target\n")
    (claude / "good.md").write_text("see @.claude/target.md for detail\n")

    docs = tmp_path / "docs" / "tickets"
    docs.mkdir(parents=True)
    (docs / "broken.md").write_text("ref .claude/docs-missing/gone.md here\n")
    (docs / "code.md").write_text(
        "before\n```\nref .claude/docs-code/block.md\n```\nafter\n"
    )
    (docs / "holder.md").write_text("| 範例 | path/file.md |\n")
    (docs / "backup.md").write_text(
        "ref .claude/migration-backups/old/y.md here\n"
    )
    (docs / "documented.md").write_text(
        "ref .claude/pm-rules/gone-doc.md here "
        "<!-- broken-link-exempt: documented-error -->\n"
    )
    return tmp_path


class TestScanRootsDefaultUnchanged:
    """類 1：不帶 scan_roots 參數／不帶 --scan-root flag 時預設行為逐字一致。"""

    def test_default_scan_roots_constant_is_claude_only(self):
        assert scan_links.DEFAULT_SCAN_ROOTS == (".claude",)

    def test_scan_without_scan_roots_ignores_docs(self, docs_scan_repo):
        result = scan_links.scan(docs_scan_repo, knobs=None)
        assert result["broken_count"] == 0
        assert result["scanned_files"] == 2  # 僅 .claude/target.md + good.md

    def test_cli_bare_invocation_ignores_docs(self, docs_scan_repo):
        proc = run_cli(docs_scan_repo, "--format", "json")
        data = json.loads(proc.stdout)
        assert data["broken_count"] == 0
        assert proc.returncode == 0


class TestScanRootsExpansion:
    """類 2：新掃描根（scan_roots 參數 / --scan-root flag）生效。"""

    def test_explicit_scan_roots_covers_docs_subtree(self, docs_scan_repo):
        result = scan_links.scan(
            docs_scan_repo, knobs=None, scan_roots=[".claude", "docs"]
        )
        srcs = [e["source_file"] for e in result["broken"]]
        assert any("docs/tickets/broken.md" in s for s in srcs)

    def test_scan_roots_union_deduplicated(self, docs_scan_repo):
        # 重複子樹不應造成同檔案重複計數
        result = scan_links.scan(
            docs_scan_repo, knobs=None, scan_roots=["docs", "docs"]
        )
        assert result["scanned_files"] == 5

    def test_cli_scan_root_flag_expands_coverage(self, docs_scan_repo):
        proc = run_cli(docs_scan_repo, "--scan-root", "docs", "--format", "json")
        data = json.loads(proc.stdout)
        srcs = [e["source_file"] for e in data["broken"]]
        assert any("docs/tickets/broken.md" in s for s in srcs)
        assert proc.returncode == 1

    def test_cli_scan_root_still_includes_default_claude(self, docs_scan_repo):
        # --scan-root 為疊加，不取代預設 .claude
        (docs_scan_repo / ".claude" / "claude-broken.md").write_text(
            "ref .claude/claude-missing/x.md here\n"
        )
        proc = run_cli(docs_scan_repo, "--scan-root", "docs", "--format", "json")
        data = json.loads(proc.stdout)
        srcs = [e["source_file"] for e in data["broken"]]
        assert any("claude-broken.md" in s for s in srcs)
        assert any("docs/tickets/broken.md" in s for s in srcs)


class TestScanRootsExclusionRulesApply:
    """類 3：既有排除旋鈕（code block / placeholder / backup / documented）
    在新掃描範圍下仍正確運作。"""

    def test_exclusions_apply_in_docs_subtree(self, docs_scan_repo):
        result = scan_links.scan(
            docs_scan_repo, knobs=None, scan_roots=[".claude", "docs"]
        )
        srcs = [e["source_file"] for e in result["broken"]]
        assert all("code.md" not in s for s in srcs), "code fence 內引用預設不計"
        assert all("holder.md" not in s for s in srcs), "placeholder 範例不計"
        assert all("backup.md" not in s for s in srcs), "migration-backups 路徑不計"
        assert all("documented.md" not in s for s in srcs), "exempt marker 行不計"
        cats = result["categories"]
        assert cats["excluded_code_block"] >= 1
        assert cats["excluded_backup"] >= 1
        assert cats["excluded_documented"] >= 1

    def test_only_real_docs_break_detected(self, docs_scan_repo):
        result = scan_links.scan(
            docs_scan_repo, knobs=None, scan_roots=[".claude", "docs"]
        )
        assert result["broken_count"] == 1
        assert result["broken"][0]["source_file"] == "docs/tickets/broken.md"


class TestKnownMissingPathSamples:
    """驗收樣本：以父票（不建新 hook、改擴充掃描根的判定依據）記錄的六個
    不存在路徑為樣本，驗證掃描根擴充後的分類正確性。

    樣本性質摘要（詳見對應 ticket 的 Solution 章節）：
    - 3 個示範佔位符（`.claude/hooks/foo.py` 等，取自已逐一列名的已知佔位符
      hook 檔名集，非任意命名）
    - 1 個真陽性（`.md` 檔案筆誤，實際檔案位於他處）
    - 2 個待查／時序性項目（皆非 `.md`，射程擴充後應被偵測為 broken，留待
      後續存量清理票依機器清單逐一判定去向，本測試只驗證「有被偵測到」）

    REF_REGEX 射程已擴至 `.py`/`.sh`：3 個佔位符樣本因命中已知佔位符 hook
    檔名 exact-match 集而不計 broken；2 個待查／時序性樣本與 1 個 `.md`
    真陽性皆應被偵測為 broken。
    """

    @pytest.fixture
    def sample_table_repo(self, tmp_path):
        claude = tmp_path / ".claude"
        claude.mkdir()
        docs = tmp_path / "docs" / "tickets"
        docs.mkdir(parents=True)
        (docs / "planning-ticket-body.md").write_text(
            "| 路徑 | 性質 |\n"
            "|------|------|\n"
            "| `.claude/hooks/foo.py` | 示範佔位符 |\n"
            "| `.claude/hooks/guard.py` | 示範佔位符 |\n"
            "| `.claude/hooks/hook-name.py` | 示範佔位符 |\n"
            "| `.claude/pm-rules/pm-role.md` | 真陽性 |\n"
            "| `.claude/hooks/acceptance-gate-hook.py` | 待查 |\n"
            "| `.claude/hooks/session-registry-stop-hook.py` | 時序性 |\n"
        )
        return tmp_path

    def test_placeholder_py_samples_not_broken(self, sample_table_repo):
        # 已知佔位符 hook 檔名（exact-match 集）不應計入 broken
        result = scan_links.scan(
            sample_table_repo, knobs=None, scan_roots=[".claude", "docs"]
        )
        raws = {e["raw_ref"] for e in result["broken"]}
        assert ".claude/hooks/foo.py" not in raws
        assert ".claude/hooks/guard.py" not in raws
        assert ".claude/hooks/hook-name.py" not in raws
        assert result["categories"]["placeholder"] >= 3

    def test_md_true_positive_and_py_missing_detected_broken(self, sample_table_repo):
        # .md 真陽性與 2 個 .py 待查／時序性樣本射程擴充後皆應被偵測
        result = scan_links.scan(
            sample_table_repo, knobs=None, scan_roots=[".claude", "docs"]
        )
        raws = {e["raw_ref"] for e in result["broken"]}
        assert ".claude/pm-rules/pm-role.md" in raws
        assert ".claude/hooks/acceptance-gate-hook.py" in raws
        assert ".claude/hooks/session-registry-stop-hook.py" in raws
        assert len(result["broken"]) == 3

    def test_without_docs_scan_root_sample_table_not_scanned(self, sample_table_repo):
        # 預設（無 docs 掃描根）：docs 下的樣本表格完全不在掃描範圍
        result = scan_links.scan(sample_table_repo, knobs=None)
        assert result["broken_count"] == 0


class TestPortabilityAllowMarker:
    """portability-allow 與 broken-link-exempt 共用同一條豁免通道。"""

    def test_portability_allow_exempts_its_line(self, tmp_path):
        claude = tmp_path / ".claude"
        (claude / "skills" / "demo").mkdir(parents=True)
        (claude / "skills" / "demo" / "SKILL.md").write_text(
            "# Demo\n\n"
            "See `.claude/pm-rules/gone.md` <!-- portability-allow: 約定位置 -->\n"
            "See `.claude/pm-rules/also-gone.md`\n"
        )
        result = scan_links.scan(tmp_path)
        broken = [b for b in result["broken"] if "demo" in b["source_file"]]
        assert len(broken) == 1
        assert "also-gone" in broken[0]["raw_ref"]

    def test_shell_comment_form_also_exempts(self, tmp_path):
        claude = tmp_path / ".claude"
        (claude / "skills" / "demo").mkdir(parents=True)
        (claude / "skills" / "demo" / "SKILL.md").write_text(
            "# Demo\n\n"
            "python3 .claude/skills/demo/scripts/x.py  # portability-allow: 共通安裝位置\n"
        )
        result = scan_links.scan(tmp_path)
        assert [b for b in result["broken"] if "demo" in b["source_file"]] == []


# ===========================================================================
# H. .py/.sh 射程擴充 + 合併宣告接手者標註
#
# REF_REGEX 曾結尾寫死 .md，.py 與 .sh 引用完全不在射程內。本節驗證射程
# 擴充後：新副檔名正確抽取與偵測、既有 .md 行為不受影響、已知佔位符 hook
# 檔名 exact-match 集正確運作、合併型遷移的接手者標註接上既有索引。
# ===========================================================================


class TestPySHExtraction:
    """REF_REGEX 射程擴至 .py/.sh：既有 4 種前綴同樣適用於新副檔名。"""

    def test_extract_refs_recognizes_py_suffix(self):
        text = "see .claude/hooks/gone-hook.py here\n"
        refs = scan_links.extract_refs(text)
        raws = {r["raw_ref"] for r in refs}
        assert ".claude/hooks/gone-hook.py" in raws

    def test_extract_refs_recognizes_sh_suffix(self):
        text = "run ./.claude/hooks/startup-check-hook.sh now\n"
        refs = scan_links.extract_refs(text)
        raws = {r["raw_ref"] for r in refs}
        assert "./.claude/hooks/startup-check-hook.sh" in raws

    def test_extract_refs_still_recognizes_md_suffix(self):
        # 回歸守護：.md 抽取行為不受射程擴充影響
        text = "see @.claude/pm-rules/pm-role.md here\n"
        refs = scan_links.extract_refs(text)
        raws = {r["raw_ref"] for r in refs}
        assert "@.claude/pm-rules/pm-role.md" in raws

    def test_py_ref_with_trailing_colon_glob_not_absorbed(self):
        # settings.local.json 常見形態（於 .md 內引述時）：尾綴 :* 不應被吞入抽取結果
        text = '"Bash(./.claude/hooks/test-summary.sh:*)"\n'
        refs = scan_links.extract_refs(text)
        raws = {r["raw_ref"] for r in refs}
        assert "./.claude/hooks/test-summary.sh" in raws
        assert not any(r.endswith(":*") for r in raws)

    def test_missing_py_ref_classified_broken_via_scan(self, tmp_path):
        claude = tmp_path / ".claude"
        claude.mkdir()
        (claude / "doc.md").write_text("ref .claude/hooks/definitely-gone-hook.py here\n")
        result = scan_links.scan(tmp_path, knobs=None)
        raws = {e["raw_ref"] for e in result["broken"]}
        assert ".claude/hooks/definitely-gone-hook.py" in raws

    def test_missing_sh_ref_classified_broken_via_scan(self, tmp_path):
        claude = tmp_path / ".claude"
        claude.mkdir()
        (claude / "doc.md").write_text("ref .claude/hooks/definitely-gone-hook.sh here\n")
        result = scan_links.scan(tmp_path, knobs=None)
        raws = {e["raw_ref"] for e in result["broken"]}
        assert ".claude/hooks/definitely-gone-hook.sh" in raws

    def test_existing_py_ref_not_broken(self, tmp_path):
        claude = tmp_path / ".claude"
        hooks = claude / "hooks"
        hooks.mkdir(parents=True)
        (hooks / "real-hook.py").write_text("# real\n")
        (claude / "doc.md").write_text("ref .claude/hooks/real-hook.py here\n")
        result = scan_links.scan(tmp_path, knobs=None)
        raws = {e["raw_ref"] for e in result["broken"]}
        assert ".claude/hooks/real-hook.py" not in raws


class TestPlaceholderHookBasenames:
    """已知佔位符 hook 檔名 exact-match 集：逐一列名，非長度代理判準。"""

    DEFAULT_KNOBS = {
        "include_code_block": False,
        "include_migration_backups": False,
        "include_placeholder": False,
    }

    @pytest.mark.parametrize(
        "raw",
        [
            ".claude/hooks/foo.py",
            ".claude/hooks/a.py",
            ".claude/hooks/x.py",
            ".claude/hooks/qux.py",
            ".claude/hooks/guard.py",
            ".claude/hooks/hook-name.py",
            ".claude/hooks/example-guard-hook.py",
            ".claude/hooks/sample-guard-hook.py",
            ".claude/hooks/some-new-guard-hook.py",
            ".claude/hooks/specific-hook.py",
            ".claude/hooks/other-hook.py",
            ".claude/hooks/keep.py",
            ".claude/hooks/foo-hook.py",
            ".claude/skills/demo/hooks/foo.py",  # skill 巢狀 hooks/ 路徑段同樣適用
        ],
    )
    def test_known_placeholder_hook_basenames_classified_placeholder(self, raw):
        cat = scan_links.classify_ref(
            raw, "/repo/" + raw, self.DEFAULT_KNOBS, exists=False
        )
        assert cat == "placeholder", f"{raw!r} 應歸 placeholder"

    def test_real_named_hook_not_in_placeholder_set_stays_broken(self):
        # 反例守護：不在已知佔位符集內的真實命名（即使短）不應被誤判
        raw = ".claude/hooks/acceptance-gate-hook.py"
        cat = scan_links.classify_ref(
            raw, "/repo/" + raw, self.DEFAULT_KNOBS, exists=False
        )
        assert cat == "broken"

    def test_same_basename_outside_hooks_segment_not_placeholder(self):
        # 佔位符判定限定 hook(s)/ 路徑段之後，其他目錄下同名不誤判
        raw = ".claude/pm-rules/foo.py"
        cat = scan_links.classify_ref(
            raw, "/repo/" + raw, self.DEFAULT_KNOBS, exists=False
        )
        assert cat == "broken"

    @pytest.mark.parametrize(
        "raw",
        [
            ".claude/hooks/archived/script-name.py",
            ".claude/hooks/archived/deprecated/foo.py",  # 多層子目錄同樣適用
        ],
    )
    def test_placeholder_hook_basename_under_nested_subdirectory(self, raw):
        # hooks/ 與檔名間允許任意層子目錄（如 archived/），涵蓋歸檔說明文件
        # 中「git mv 範本」這類巢狀路徑佔位符引用
        cat = scan_links.classify_ref(
            raw, "/repo/" + raw, self.DEFAULT_KNOBS, exists=False
        )
        assert cat == "placeholder", f"{raw!r} 應歸 placeholder"

    def test_real_named_hook_under_nested_subdirectory_stays_broken(self):
        # 反例守護：巢狀子目錄放寬不擴及非已知佔位符集的真實命名
        raw = ".claude/hooks/archived/acceptance-gate-hook.py"
        cat = scan_links.classify_ref(
            raw, "/repo/" + raw, self.DEFAULT_KNOBS, exists=False
        )
        assert cat == "broken"


class TestMergeSuccessorAnnotation:
    """broken 項標註合併型遷移的接手者（extract_merge_declarations 既有索引）。

    反查索引的組裝邏輯（scan() 內 merge_successor 標註）以 monkeypatch 替換
    scan_links.load_extract_merge_declarations 驗證，不依賴 hook-completeness-
    check.py 的 transitive pyyaml 依賴是否安裝於執行環境（scan_links.py 自身
    仍是純標準庫實作，測試環境是否裝 pyyaml 不應決定這裡的邏輯測試能不能
    跑）。動態載入鏈本身與真實 hook-completeness-check.py 的整合另以 dry-run
    驗證，記錄於對應 ticket 的 Solution 章節。
    """

    @staticmethod
    def _fake_extract_fn(hooks_dir):
        return {"post-merged-hook.py": ["old-hook-a.py", "old-hook-b.py"]}

    @pytest.fixture
    def merge_repo(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            scan_links,
            "load_extract_merge_declarations",
            lambda: TestMergeSuccessorAnnotation._fake_extract_fn,
        )
        claude = tmp_path / ".claude"
        hooks = claude / "hooks"
        hooks.mkdir(parents=True)
        (claude / "doc.md").write_text(
            "ref .claude/hooks/old-hook-a.py here\n"
            "ref .claude/hooks/totally-unrelated-gone.py here\n"
        )
        return tmp_path

    def test_merged_ref_tagged_with_successor(self, merge_repo):
        result = scan_links.scan(merge_repo, knobs=None)
        entry = next(
            e for e in result["broken"] if e["raw_ref"].endswith("old-hook-a.py")
        )
        assert entry["merge_successor"] == "post-merged-hook.py"

    def test_unrelated_broken_ref_has_none_successor(self, merge_repo):
        result = scan_links.scan(merge_repo, knobs=None)
        entry = next(
            e
            for e in result["broken"]
            if e["raw_ref"].endswith("totally-unrelated-gone.py")
        )
        assert entry["merge_successor"] is None

    def test_no_hooks_dir_defaults_to_none_successor(self, synthetic_repo):
        # fail-open：root/.claude/hooks 不存在時不中斷主掃描，merge_successor 皆 None
        result = scan_links.scan(synthetic_repo, knobs=None)
        entry = next(e for e in result["broken"] if "broken.md" in e["source_file"])
        assert entry["merge_successor"] is None

    def test_json_schema_includes_merge_successor_key(self, synthetic_repo):
        # schema 存在性：不需真實合併索引，root 無 .claude/hooks 時仍須有此欄位
        proc = run_cli(synthetic_repo, "--format", "json")
        data = json.loads(proc.stdout)
        assert data["broken"], "fixture 應至少產生一筆 broken"
        for entry in data["broken"]:
            assert "merge_successor" in entry


# ===========================================================================
# I. 案例 1：REF_REGEX 多重副檔名截斷誤報
#
# `[^\s)\]"'`]*?\.(?:md|py|sh)` 非貪婪比對在第一個已知副檔名處即停止，遇
# `worklog.md.template` 這類多重副檔名檔名時會被截斷為 `worklog.md`（不存在），
# 把有效引用誤判 broken。修法：已知副檔名後允許 `(?:\.[A-Za-z0-9_-]+)*` 延伸
# 比對真實存在的後綴延伸，句尾標點（無延伸段時）不受影響。
# ===========================================================================


class TestRefRegexMultiExtension:
    def test_extract_refs_captures_full_multi_extension_suffix(self):
        text = "cp .claude/skills/doc-flow/templates/worklog.md.template dest\n"
        refs = scan_links.extract_refs(text)
        raws = {r["raw_ref"] for r in refs}
        assert ".claude/skills/doc-flow/templates/worklog.md.template" in raws
        assert ".claude/skills/doc-flow/templates/worklog.md" not in raws

    def test_existing_multi_extension_file_not_broken_via_scan(self, tmp_path):
        claude = tmp_path / ".claude"
        templates = claude / "templates"
        templates.mkdir(parents=True)
        (templates / "worklog.md.template").write_text("# template\n")
        (claude / "doc.md").write_text(
            "cp .claude/templates/worklog.md.template dest\n"
        )
        result = scan_links.scan(tmp_path, knobs=None)
        raws = {e["raw_ref"] for e in result["broken"]}
        assert ".claude/templates/worklog.md.template" not in raws
        assert ".claude/templates/worklog.md" not in raws

    def test_trailing_sentence_period_not_absorbed_into_extension(self):
        # 回歸守護：句尾標點（非延伸副檔名）不應被吞入 raw_ref
        text = "see .claude/pm-rules/pm-role.md. for detail\n"
        refs = scan_links.extract_refs(text)
        raws = {r["raw_ref"] for r in refs}
        assert ".claude/pm-rules/pm-role.md" in raws
        assert not any(r.endswith(".md.") for r in raws)

    def test_py_ref_with_trailing_colon_glob_still_not_absorbed(self):
        # 回歸守護（既有案例 953 行）：多重副檔名修法不應破壞既有 :* 尾綴防護
        text = '"Bash(./.claude/hooks/test-summary.sh:*)"\n'
        refs = scan_links.extract_refs(text)
        raws = {r["raw_ref"] for r in refs}
        assert "./.claude/hooks/test-summary.sh" in raws
        assert not any(r.endswith(":*") for r in raws)


# ===========================================================================
# J. 案例 2：shell cp/mv 指令目的地參數的相對路徑基準誤判
#
# resolve_path() 對 `./X`（非 `./.claude/X`）一律以來源檔目錄為基準，但 fence
# 內 cp/mv 指令的相對路徑基準是執行時 cwd（通常為 repo root），靜態文字無法
# 確定 cwd。範圍窄化為「cp/mv 指令行 + 單點相對路徑」才視為信心不足，改列
# excluded_shell_dest，不下 broken 判定；不放行其他 fence 內相對路徑（如
# markdown 連結），避免遮蔽真實 drift（全庫另有 30+ 個非 cp/mv 的 `./x.md`
# 混在同一 fence 慣例內）。方向排除記錄：未採「fence 內全放行」（budget 由
# 142 應僅降至 140，全放行會遠超此數）；未採「猜測 cwd=root 再驗證存在」
# （會產生另一種猜測，ticket 明文禁止）。
# ===========================================================================


# ===========================================================================
# K. opt-in fence 稽核模式：不做語法示範/操作指引的自動分類，只提供機器
# 可靠的分組訊號（載體性質 / marker 有無 / merge_successor），語意分類
# 判斷留給人。獨立於既有 gate 路徑，恆 exit 0。
# ===========================================================================


class TestCarrierNature:
    """carrier_nature(source_posix)：依路徑段判定載體性質，機器可靠訊號。"""

    def test_commands_segment_classified(self):
        assert (
            scan_links.carrier_nature(".claude/commands/foo.md")
            == "可執行指令載體"
        )

    def test_error_patterns_segment_classified(self):
        assert (
            scan_links.carrier_nature(
                ".claude/error-patterns/process-compliance/PC-001-x.md"
            )
            == "案例敘事載體"
        )

    def test_hook_specs_segment_classified(self):
        assert (
            scan_links.carrier_nature(".claude/hook-specs/old-report.md")
            == "歷史報告載體"
        )

    def test_unknown_segment_falls_back_to_unclassified(self):
        # skills/、pm-rules/ 等混合語法示範與操作指引，不構成可靠訊號
        assert scan_links.carrier_nature(".claude/skills/demo/SKILL.md") == "未分類"
        assert scan_links.carrier_nature(".claude/pm-rules/tdd-flow.md") == "未分類"


@pytest.fixture
def fence_audit_repo(tmp_path):
    """opt-in fence 稽核模式測試樹：涵蓋三種載體 + marker 行 + 對照組。

    - commands.md（.claude/commands/ 下）：fence 內未標記失效引用
    - case.md（.claude/error-patterns/ 下）：fence 內未標記失效引用
    - report.md（.claude/hook-specs/ 下）：fence 內未標記失效引用
    - plain.md（未分類目錄）：fence 內未標記失效引用
    - marked.md（未分類目錄）：fence 內已標記 marker 的失效引用
    - existing.md：fence 內引用實際存在（不應出現在稽核清單）
    - placeholder.md：fence 內 placeholder 樣式引用（不應出現在稽核清單）
    - prose.md：同一失效引用但不在 fence 內（不應出現在稽核清單）
    """
    claude = tmp_path / ".claude"
    (claude / "commands").mkdir(parents=True)
    (claude / "commands" / "cmd.md").write_text(
        "```\nsee .claude/commands/gone-cmd.py\n```\n"
    )
    (claude / "error-patterns").mkdir(parents=True)
    (claude / "error-patterns" / "case.md").write_text(
        "```\nsee .claude/error-patterns/gone-case.md\n```\n"
    )
    (claude / "hook-specs").mkdir(parents=True)
    (claude / "hook-specs" / "report.md").write_text(
        "```\nsee .claude/hook-specs/gone-report.sh\n```\n"
    )
    (claude / "plain.md").write_text("```\nsee .claude/plain/gone-plain.md\n```\n")
    (claude / "marked.md").write_text(
        "```\nsee .claude/marked/gone-marked.md "
        "<!-- broken-link-exempt: documented-error -->\n```\n"
    )
    (claude / "target.md").write_text("# target\n")
    (claude / "existing.md").write_text("```\nsee @.claude/target.md\n```\n")
    (claude / "placeholder.md").write_text("```\nsee path/file.md\n```\n")
    (claude / "prose.md").write_text("see .claude/prose/gone-prose.md outside fence\n")
    return tmp_path


class TestFenceAudit:
    def test_default_gate_path_unaffected_by_fence_content(self, fence_audit_repo):
        # 稽核約束：fence 內容不影響既有 gate（include_code_block 預設 False）
        result = scan_links.scan(fence_audit_repo, knobs=None)
        assert result["broken_count"] == 1  # 僅 prose.md 的非 fence 引用
        assert result["broken"][0]["source_file"] == ".claude/prose.md"

    def test_fence_entries_count_covers_unmarked_and_marked(self, fence_audit_repo):
        result = scan_links.fence_audit(fence_audit_repo)
        # 4 個未標記 fence 內失效引用 + 1 個已標記 → 5 筆
        assert result["fence_entries_count"] == 5

    def test_existing_ref_in_fence_not_audited(self, fence_audit_repo):
        result = scan_links.fence_audit(fence_audit_repo)
        srcs = [e["source_file"] for e in result["entries"]]
        assert all("existing.md" not in s for s in srcs)

    def test_placeholder_ref_in_fence_not_audited(self, fence_audit_repo):
        result = scan_links.fence_audit(fence_audit_repo)
        srcs = [e["source_file"] for e in result["entries"]]
        assert all("placeholder.md" not in s for s in srcs)

    def test_non_fence_ref_not_audited(self, fence_audit_repo):
        # 稽核範圍限定 fence 內；prose.md 的引用不在 fence 內，不應出現
        result = scan_links.fence_audit(fence_audit_repo)
        srcs = [e["source_file"] for e in result["entries"]]
        assert all("prose.md" not in s for s in srcs)

    def test_carrier_nature_annotated_per_entry(self, fence_audit_repo):
        result = scan_links.fence_audit(fence_audit_repo)
        by_source = {e["source_file"]: e for e in result["entries"]}
        assert (
            by_source[".claude/commands/cmd.md"]["carrier_nature"] == "可執行指令載體"
        )
        assert (
            by_source[".claude/error-patterns/case.md"]["carrier_nature"]
            == "案例敘事載體"
        )
        assert (
            by_source[".claude/hook-specs/report.md"]["carrier_nature"]
            == "歷史報告載體"
        )
        assert by_source[".claude/plain.md"]["carrier_nature"] == "未分類"

    def test_marker_flag_distinguishes_marked_entry(self, fence_audit_repo):
        result = scan_links.fence_audit(fence_audit_repo)
        by_source = {e["source_file"]: e for e in result["entries"]}
        assert by_source[".claude/marked.md"]["has_marker"] is True
        assert by_source[".claude/marked.md"]["category"] == "excluded_documented"
        assert by_source[".claude/plain.md"]["has_marker"] is False
        assert by_source[".claude/plain.md"]["category"] == "broken"

    def test_by_carrier_nature_counts_match_entries(self, fence_audit_repo):
        result = scan_links.fence_audit(fence_audit_repo)
        cats = result["by_carrier_nature"]
        assert cats["可執行指令載體"] == 1
        assert cats["案例敘事載體"] == 1
        assert cats["歷史報告載體"] == 1
        assert cats["未分類"] == 2  # plain.md + marked.md
        assert sum(cats.values()) == result["fence_entries_count"]

    def test_marker_counts_match_entries(self, fence_audit_repo):
        result = scan_links.fence_audit(fence_audit_repo)
        mc = result["marker_counts"]
        assert mc == {"marked": 1, "unmarked": 4}
        assert sum(mc.values()) == result["fence_entries_count"]

    def test_entries_sorted_by_source_then_line(self, fence_audit_repo):
        result = scan_links.fence_audit(fence_audit_repo)
        keys = [(e["source_file"], e["line"]) for e in result["entries"]]
        assert keys == sorted(keys)

    def test_scan_roots_respected(self, fence_audit_repo):
        # 不帶 docs 掃描根時，docs/ 下內容不進稽核範圍
        docs = fence_audit_repo / "docs"
        docs.mkdir()
        (docs / "planning.md").write_text(
            "```\nsee .claude/docs-gone.md\n```\n"
        )
        default_result = scan_links.fence_audit(fence_audit_repo)
        srcs = [e["source_file"] for e in default_result["entries"]]
        assert all("docs/planning.md" not in s for s in srcs)
        widened_result = scan_links.fence_audit(
            fence_audit_repo, scan_roots=[".claude", "docs"]
        )
        srcs2 = [e["source_file"] for e in widened_result["entries"]]
        assert any("docs/planning.md" in s for s in srcs2)


class TestFenceAuditCli:
    def test_cli_fence_audit_json(self, fence_audit_repo):
        proc = run_cli(fence_audit_repo, "--fence-audit", "--format", "json")
        assert proc.returncode == 0
        data = json.loads(proc.stdout)
        for key in (
            "scanned_files",
            "fence_entries_count",
            "by_carrier_nature",
            "marker_counts",
            "entries",
        ):
            assert key in data
        assert data["fence_entries_count"] == 5

    def test_cli_fence_audit_text_smoke(self, fence_audit_repo):
        proc = run_cli(fence_audit_repo, "--fence-audit")
        assert proc.returncode == 0
        assert "fence audit" in proc.stdout
        assert "非 gate" in proc.stdout

    def test_cli_fence_audit_exit_zero_even_with_findings(self, fence_audit_repo):
        # 票 acceptance：稽核模式不納入任何阻擋 gate，即使有發現仍 exit 0
        proc = run_cli(fence_audit_repo, "--fence-audit", "--format", "json")
        data = json.loads(proc.stdout)
        assert data["fence_entries_count"] > 0
        assert proc.returncode == 0

    def test_cli_default_gate_exit_code_unaffected(self, fence_audit_repo):
        # 既有命令 exit code 語意不變：--fence-audit 不影響預設 gate 呼叫
        proc = run_cli(fence_audit_repo, "--format", "json")
        assert proc.returncode == 1  # prose.md 仍有 1 筆非 fence broken
        data = json.loads(proc.stdout)
        assert data["broken_count"] == 1


class TestShellDestAmbiguousCwd:
    def test_extract_refs_flags_cp_line_dot_relative_ref(self):
        text = "```bash\ncp .claude/templates/CLAUDE-template.md ./CLAUDE.md\n```\n"
        refs = scan_links.extract_refs(text)
        by_raw = {r["raw_ref"]: r for r in refs}
        assert by_raw["./CLAUDE.md"]["shell_ambiguous_cwd"] is True
        assert (
            by_raw[".claude/templates/CLAUDE-template.md"]["shell_ambiguous_cwd"]
            is False
        )

    def test_extract_refs_does_not_flag_outside_code_block(self):
        # 同一 cp 行若不在 fence 內（純散文提及）不豁免
        text = "cp .claude/templates/CLAUDE-template.md ./CLAUDE.md\n"
        refs = scan_links.extract_refs(text)
        by_raw = {r["raw_ref"]: r for r in refs}
        assert by_raw["./CLAUDE.md"]["shell_ambiguous_cwd"] is False

    def test_extract_refs_does_not_flag_non_cp_mv_lines(self):
        # markdown 連結（非 cp/mv 指令）即使在 fence 內也不豁免
        text = "```bash\n[link](./CLAUDE.md)\n```\n"
        refs = scan_links.extract_refs(text)
        by_raw = {r["raw_ref"]: r for r in refs}
        assert by_raw["./CLAUDE.md"]["shell_ambiguous_cwd"] is False

    def test_classify_ref_shell_ambiguous_cwd_excluded_not_broken(self):
        knobs = dict(scan_links.DEFAULT_KNOBS)
        cat = scan_links.classify_ref(
            "./CLAUDE.md",
            "/repo/.claude/templates/CLAUDE.md",
            knobs,
            exists=False,
            shell_ambiguous_cwd=True,
        )
        assert cat == "excluded_shell_dest"

    def test_classify_ref_shell_ambiguous_cwd_counted_when_knob_on(self):
        knobs = dict(scan_links.DEFAULT_KNOBS, include_shell_dest=True)
        cat = scan_links.classify_ref(
            "./CLAUDE.md",
            "/repo/.claude/templates/CLAUDE.md",
            knobs,
            exists=False,
            shell_ambiguous_cwd=True,
        )
        assert cat == "broken"

    def test_scan_excludes_readme_cp_case(self, tmp_path):
        claude = tmp_path / ".claude"
        templates = claude / "templates"
        templates.mkdir(parents=True)
        (templates / "CLAUDE-template.md").write_text("# t\n")
        (templates / "README.md").write_text(
            "```bash\ncp .claude/templates/CLAUDE-template.md ./CLAUDE.md\n```\n"
        )
        knobs = dict(scan_links.DEFAULT_KNOBS, include_code_block=True)
        result = scan_links.scan(tmp_path, knobs=knobs)
        raws = {e["raw_ref"] for e in result["broken"]}
        assert "./CLAUDE.md" not in raws
        assert result["categories"]["excluded_shell_dest"] == 1

    def test_scan_does_not_exclude_non_cp_mv_dot_relative_broken(self, tmp_path):
        # 對照：同為 fence 內 ./x.md，但非 cp/mv 指令行，範圍未被放寬
        claude = tmp_path / ".claude"
        claude.mkdir()
        (claude / "doc.md").write_text(
            "```bash\nsee [link](./definitely-gone.md)\n```\n"
        )
        knobs = dict(scan_links.DEFAULT_KNOBS, include_code_block=True)
        result = scan_links.scan(tmp_path, knobs=knobs)
        raws = {e["raw_ref"] for e in result["broken"]}
        assert "./definitely-gone.md" in raws

    def test_cli_include_shell_dest_flag(self, tmp_path):
        claude = tmp_path / ".claude"
        templates = claude / "templates"
        templates.mkdir(parents=True)
        (templates / "CLAUDE-template.md").write_text("# t\n")
        (templates / "README.md").write_text(
            "```bash\ncp .claude/templates/CLAUDE-template.md ./CLAUDE.md\n```\n"
        )
        default = run_cli(tmp_path, "--include-code-block", "--format", "json")
        widened = run_cli(
            tmp_path,
            "--include-code-block",
            "--include-shell-dest",
            "--format",
            "json",
        )
        d0 = json.loads(default.stdout)
        d1 = json.loads(widened.stdout)
        assert d0["broken_count"] == 0
        assert d1["broken_count"] == 1
