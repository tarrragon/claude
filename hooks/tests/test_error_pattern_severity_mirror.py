"""severity_audit 的 only_body 鏡射寫入測試。

背景：only_body 類 pattern 只有內文「風險等級」，沒有 frontmatter `severity`，
`/error-pattern query` 排序讀不到等級。鏡射方向為內文 -> frontmatter（SKILL
〈機械鏡射僅限兩類〉）。

驗證範圍：
- 無 frontmatter 的檔：前置新建 id／title／severity，內文逐字不變
- 已有 frontmatter 但缺 severity 的檔：只插入 severity 一行，其餘不動
- 等級寫成英文（high／medium／low），帶括號附註的內文值取主等級
- 正向對照：鏡射前 classify 為 only_body，鏡射後為 both_match
- 非 only_body 的檔（both_match、neither）不產生寫入
- dry-run 不寫檔，--write 才寫
"""

import importlib.util
import sys
from pathlib import Path

_LIB = Path(__file__).resolve().parents[2] / "skills" / "error-pattern" / "lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

_spec = importlib.util.spec_from_file_location("severity_audit_mirror", _LIB / "severity_audit.py")
_audit = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_audit)

_NO_FM = (
    "# PC-001: 標題：含冒號的錯誤\n\n"
    "## 基本資訊\n\n"
    "- **Pattern ID**: PC-001\n"
    "- **風險等級**: 高（每次都會踩）\n"
)

_FM_NO_SEVERITY = (
    "---\n"
    "id: PC-002\n"
    "title: 已有 frontmatter\n"
    "status: active\n"
    "---\n\n"
    "# PC-002: 已有 frontmatter\n\n"
    "## 基本資訊\n\n"
    "- **風險等級**: 低-中\n"
)

_BOTH = (
    "---\nid: PC-003\ntitle: 兩邊一致\nseverity: medium\n---\n\n"
    "# PC-003: 兩邊一致\n\n## 基本資訊\n\n- **風險等級**: 中\n"
)

_NEITHER = "# PC-004: 都沒有\n\n內文沒有等級。\n"


def _setup(tmp_path):
    cat = tmp_path / "error-patterns" / "process-compliance"
    cat.mkdir(parents=True)
    files = {
        "PC-001-no-fm.md": _NO_FM,
        "PC-002-fm-no-sev.md": _FM_NO_SEVERITY,
        "PC-003-both.md": _BOTH,
        "PC-004-neither.md": _NEITHER,
    }
    for name, text in files.items():
        (cat / name).write_text(text, encoding="utf-8")
    return tmp_path / "error-patterns", cat


def _classes(ep_dir):
    return {r["id"]: _audit.classify(r) for r in _audit.scan_severity(ep_dir)}


def test_mirror_turns_only_body_into_both_match(tmp_path):
    ep_dir, _ = _setup(tmp_path)
    before = _classes(ep_dir)
    assert before["PC-001"] == "only_body"
    assert before["PC-002"] == "only_body"

    changed = _audit.mirror_only_body(ep_dir, write=True)
    assert sorted(Path(p).name for p in changed) == ["PC-001-no-fm.md", "PC-002-fm-no-sev.md"]

    after = _classes(ep_dir)
    assert after["PC-001"] == "both_match"
    assert after["PC-002"] == "both_match"
    assert after["PC-003"] == "both_match"
    assert after["PC-004"] == "neither"


def test_no_frontmatter_file_gets_new_block_and_body_unchanged(tmp_path):
    ep_dir, cat = _setup(tmp_path)
    _audit.mirror_only_body(ep_dir, write=True)
    text = (cat / "PC-001-no-fm.md").read_text(encoding="utf-8")
    fm, body = _audit._parse_frontmatter(text)
    assert fm == {"id": "PC-001", "title": "標題：含冒號的錯誤", "severity": "high"}
    assert text.endswith(_NO_FM)
    assert text.split("---\n", 2)[2] == "\n" + _NO_FM


def test_existing_frontmatter_only_gains_severity_line(tmp_path):
    ep_dir, cat = _setup(tmp_path)
    _audit.mirror_only_body(ep_dir, write=True)
    text = (cat / "PC-002-fm-no-sev.md").read_text(encoding="utf-8")
    assert text == _FM_NO_SEVERITY.replace("status: active\n", "status: active\nseverity: medium\n")


def test_dry_run_does_not_write(tmp_path):
    ep_dir, cat = _setup(tmp_path)
    changed = _audit.mirror_only_body(ep_dir, write=False)
    assert len(changed) == 2
    assert (cat / "PC-001-no-fm.md").read_text(encoding="utf-8") == _NO_FM
    assert _classes(ep_dir)["PC-001"] == "only_body"


def test_other_classes_untouched(tmp_path):
    ep_dir, cat = _setup(tmp_path)
    _audit.mirror_only_body(ep_dir, write=True)
    assert (cat / "PC-003-both.md").read_text(encoding="utf-8") == _BOTH
    assert (cat / "PC-004-neither.md").read_text(encoding="utf-8") == _NEITHER


def test_cli_write_flag(tmp_path):
    ep_dir, _ = _setup(tmp_path)
    assert _audit.main(["--claude-dir", str(tmp_path), "--mirror-only-body"]) == 0
    assert _classes(ep_dir)["PC-001"] == "only_body"
    assert _audit.main(["--claude-dir", str(tmp_path), "--mirror-only-body", "--write"]) == 0
    assert _classes(ep_dir)["PC-001"] == "both_match"
