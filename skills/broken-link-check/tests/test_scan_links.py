"""RED tests for broken-link-check 確定性 CLI scanner (scan_links.py).

TDD Phase 2 (1.0.0-W8-030.1). 目標被測物尚未實作，全部測試應 RED
（ModuleNotFoundError / AttributeError 皆為合法 RED）。

測試切點 (規格 §6 SOLID)：
- 純函式單元：extract_refs / classify_ref / resolve_path（無 I/O，主力覆蓋）
- 整合：scan() + CLI exit code (0/1/2) + --format json schema
- 9 條 GWT 全覆蓋（正常 / 異常 / 邊界 / 確定性）

約束：
- 計數類斷言一律用受控 synthetic fixture，禁對 live .claude/ 樹斷言固定數字
  (baseline=164 為 ANA 時間點量測，會隨 W8-034 清理變動)。
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
    """W8-047 缺陷 2：placeholder 改樣式偵測（glob/角括號/模板/token）。

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


class TestBackupSourceExclusion:
    """W8-047 缺陷 1：backup 來源端排除（source 檔在 migration-backups/）。

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
        # GWT 輸出 schema（規格 §3）：W8-034 消費介面
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
# F. W8-049: documented-error 豁免 marker（excluded_documented 類別）
# ===========================================================================


class TestDocumentedExemptMarker:
    """W8-049：per-line `<!-- broken-link-exempt: documented-error -->` marker。

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
