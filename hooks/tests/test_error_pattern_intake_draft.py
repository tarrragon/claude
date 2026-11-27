"""error-pattern 收錄請求草稿工具測試。

intake_draft 位於 .claude/skills/error-pattern/lib/intake_draft.py；
測試借 hooks pytest env 執行，以 tmp_path 建假的 .claude 目錄。
"""

import re
import sys
from pathlib import Path

_skill_lib = (
    Path(__file__).resolve().parent.parent.parent
    / "skills"
    / "error-pattern"
    / "lib"
)
if str(_skill_lib) not in sys.path:
    sys.path.insert(0, str(_skill_lib))

from intake_draft import build_draft, main  # noqa: E402

PATTERN_ID = "PC-ZZZ-001"
ROW = f"| {PATTERN_ID} | 範例標題 | 中 | v3.5.0 |"
HEADINGS = [
    "### 0. 請求資訊",
    "### 1. pattern 全文",
    "### 2. 索引列",
    "### 3. registry 列",
    "### 4. 可攜性判定",
    "### 5. 原樣收錄聲明",
]


def _make_claude(tmp_path, body="內文\n", carrier="rule", registered=False, row=True):
    claude = tmp_path / ".claude"
    pdir = claude / "error-patterns" / "process-compliance"
    pdir.mkdir(parents=True)
    fm = f"---\nid: {PATTERN_ID}\n"
    if carrier:
        fm += f"carrier: {carrier}\n"
    fm += "---\n"
    pattern = pdir / f"{PATTERN_ID}-demo.md"
    pattern.write_text(fm + body, encoding="utf-8")
    (claude / "VERSION").write_text("3.5.1\n", encoding="utf-8")
    readme = "| ID | 標題 | 風險 | 來源版本 |\n|----|----|----|----|\n"
    if row:
        readme += ROW + "\n"
    (claude / "error-patterns" / "README.md").write_text(readme, encoding="utf-8")
    reg = "projects:\n"
    if registered:
        reg += "  - code: ZZZ\n    dir: zzz_proj\n    note: ''\n"
    (claude / "error-patterns" / "_project-registry.yaml").write_text(
        reg, encoding="utf-8"
    )
    return claude, pattern


def test_headings_in_order(tmp_path):
    claude, pattern = _make_claude(tmp_path)
    draft = build_draft(pattern, claude)
    positions = [draft.index(h) for h in HEADINGS]
    assert positions == sorted(positions)
    assert draft.startswith("<!-- content-intake-request -->")
    assert "| framework_version | 3.5.1 |" in draft
    assert ROW in draft
    assert "| carrier | rule |" in draft


def test_outer_fence_longer_than_inner(tmp_path):
    body = "```python\nx = 1\n```\n`````\n"
    claude, pattern = _make_claude(tmp_path, body=body)
    draft = build_draft(pattern, claude)
    section = draft.split("### 1. pattern 全文")[1].split("### 2.")[0]
    fences = re.findall(r"^(`{3,})", section, re.M)
    assert max(len(f) for f in fences) >= 6


def test_missing_readme_row_exit_1(tmp_path, capsys):
    claude, pattern = _make_claude(tmp_path, row=False)
    assert main([str(pattern), "--claude-dir", str(claude)]) == 1
    err = capsys.readouterr()
    assert PATTERN_ID in err.err
    assert err.out == ""


def test_missing_carrier_exit_1(tmp_path, capsys):
    claude, pattern = _make_claude(tmp_path, carrier="")
    assert main([str(pattern), "--claude-dir", str(claude)]) == 1
    assert "carrier" in capsys.readouterr().err


def test_registered_and_unregistered(tmp_path):
    claude, pattern = _make_claude(tmp_path, registered=True)
    section = build_draft(pattern, claude).split("### 3. registry 列")[1]
    assert "已登錄" in section.split("### 4.")[0]

    claude2, pattern2 = _make_claude(tmp_path / "b", registered=False)
    section2 = build_draft(pattern2, claude2).split("### 3. registry 列")[1]
    block = section2.split("### 4.")[0]
    assert "code: ZZZ" in block
    assert "已登錄" not in block
