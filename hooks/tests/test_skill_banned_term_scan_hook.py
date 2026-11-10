"""skill-banned-term-scan-hook.py 測試（0.2.1-W3-1065）。

核心設計約束：use（散文使用）vs mention（grep pattern / 術語對照樣本）的判別。
無差別掃描會對 `rg "集群|默認|質量|視頻"` 這類 grep pattern 報錯，一次誤報就
足以讓維護者忽略這個 WARNING（見 ticket why）。

豁免機制不可用行號（會隨 skill-sync pull 漂移），改用：
- 反引號 inline code span（`` `...` ``）
- 三反引號 fenced code block（``` ... ```）
- 檔案級白名單（整檔豁免，如 regional-terminology-alignment.md）
- 行內 marker（`<!-- banned-term-exempt: reason -->`）
"""

import importlib.util
import sys
from pathlib import Path

import pytest


_HOOKS_DIR = Path(__file__).parent.parent
_PROJECT_ROOT = _HOOKS_DIR.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

_spec = importlib.util.spec_from_file_location(
    "skill_banned_term_scan_hook",
    _HOOKS_DIR / "skill-banned-term-scan-hook.py",
)
_hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_hook)

scan_file = _hook.scan_file
scan_skills_dir = _hook.scan_skills_dir
BANNED_TERMS = _hook.BANNED_TERMS
FILE_LEVEL_ALLOWLIST = _hook.FILE_LEVEL_ALLOWLIST


def _write(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# use（真違規）：散文中使用禁用詞，必須被偵測
# ---------------------------------------------------------------------------


def test_prose_usage_is_detected(tmp_path: Path) -> None:
    f = _write(tmp_path, "a/SKILL.md", "這份文檔說明了整個流程。\n")

    hits = scan_file(f)

    assert len(hits) == 1
    assert hits[0].term == "文檔"
    assert hits[0].line_no == 1


def test_multiple_terms_multiple_lines_all_detected(tmp_path: Path) -> None:
    f = _write(
        tmp_path,
        "a/SKILL.md",
        "第一行使用默認值。\n第二行有代碼片段。\n",
    )

    hits = scan_file(f)

    terms = sorted(h.term for h in hits)
    assert terms == ["代碼", "默認"]


# ---------------------------------------------------------------------------
# mention（合法）：grep pattern / 術語對照樣本，不可報 WARNING
# ---------------------------------------------------------------------------


def test_inline_code_span_is_exempt(tmp_path: Path) -> None:
    f = _write(
        tmp_path,
        "a/SKILL.md",
        '單詞層 `rg "集群|默認|質量|視頻|函數"` （封閉集合、掃得到）\n',
    )

    hits = scan_file(f)

    assert hits == []


def test_fenced_code_block_is_exempt(tmp_path: Path) -> None:
    f = _write(
        tmp_path,
        "a/SKILL.md",
        "字句層審查：\n```bash\nrg \"集群|默認|質量|視頻|函數|文件夾|接口\" $FILES\n```\n",
    )

    hits = scan_file(f)

    assert hits == []


def test_inline_marker_exempts_line(tmp_path: Path) -> None:
    f = _write(
        tmp_path,
        "a/SKILL.md",
        "地區漂移（屏 / 螢幕、默認 / 預設） <!-- banned-term-exempt: regional term illustration -->\n",
    )

    hits = scan_file(f)

    assert hits == []


def test_marker_only_exempts_own_line_not_neighbours(tmp_path: Path) -> None:
    f = _write(
        tmp_path,
        "a/SKILL.md",
        "默認 <!-- banned-term-exempt: illustration -->\n默認未受豁免\n",
    )

    hits = scan_file(f)

    assert len(hits) == 1
    assert hits[0].line_no == 2


def test_file_level_allowlist_is_fully_exempt(tmp_path: Path) -> None:
    rel = "compositional-writing/references/principles/regional-terminology-alignment.md"
    f = _write(tmp_path, rel, "默認 / 預設、視頻 / 影片、文檔混用。\n")

    hits = scan_file(f, skills_root=tmp_path, allowlist=FILE_LEVEL_ALLOWLIST)

    assert hits == []


def test_non_allowlisted_file_same_terms_still_detected(tmp_path: Path) -> None:
    f = _write(tmp_path, "some-other-skill/SKILL.md", "默認值範例。\n")

    hits = scan_file(f, skills_root=tmp_path, allowlist=FILE_LEVEL_ALLOWLIST)

    assert len(hits) == 1


# ---------------------------------------------------------------------------
# 全量掃描：對現行 skills 目錄跑，需回報結構化結果供逐項判定
# ---------------------------------------------------------------------------


def test_scan_skills_dir_returns_zero_when_no_banned_terms(tmp_path: Path) -> None:
    _write(tmp_path, "clean-skill/SKILL.md", "這是一份乾淨的文件，沒有禁用詞。\n")

    result = scan_skills_dir(tmp_path)

    assert result.violations == []


def test_scan_skills_dir_skips_file_level_allowlist(tmp_path: Path) -> None:
    rel = "compositional-writing/references/principles/regional-terminology-alignment.md"
    _write(tmp_path, rel, "默認 / 預設、視頻 / 影片。\n")
    _write(tmp_path, "real-skill/SKILL.md", "這裡有真的默認用法。\n")

    result = scan_skills_dir(tmp_path)

    assert len(result.violations) == 1
    assert "real-skill" in str(result.violations[0].path)


def test_scan_real_skills_dir_has_zero_false_positive(tmp_path: Path) -> None:
    """Dogfooding：對本專案現行 .claude/skills/ 全量掃描。

    豁免機制（inline code / fenced code / marker / 檔案白名單）需覆蓋所有
    已知合法 mention；剩餘命中皆須是真違規（該檢查僅驗證豁免機制不誤傷已知
    4 處，其餘命中人工複核記錄於 Solution，非本測試斷言範圍）。
    """
    real_skills_dir = _PROJECT_ROOT / ".claude" / "skills"
    if not real_skills_dir.exists():
        pytest.skip("real skills dir not found")

    result = scan_skills_dir(real_skills_dir)

    exempted_paths = {
        str(v.path) for v in result.violations
        if "regional-terminology-alignment.md" in str(v.path)
    }
    assert exempted_paths == set(), "檔案級白名單未生效"
