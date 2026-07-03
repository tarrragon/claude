"""check_api_surface 測試：單元案例 + SPEC-014 v1.1（缺口）/ v1.4（通過）驗證案例。"""

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import check_api_surface  # noqa: E402


# --- 單元案例：split_fr_sections ---

def test_split_fr_sections_splits_by_header():
    text = "intro\n### FR-01: A\nbody a\n### FR-02: B\nbody b\n"
    sections = check_api_surface.split_fr_sections(text)
    assert [fr_id for fr_id, _ in sections] == ["FR-01", "FR-02"]
    assert "body a" in dict(sections)["FR-01"]
    assert "body b" in dict(sections)["FR-02"]


def test_split_fr_sections_no_header_returns_empty():
    assert check_api_surface.split_fr_sections("no FR headers here") == []


# --- 單元案例：check_api_surface 判定邏輯 ---

def test_flags_api_mention_without_any_path_in_section():
    """段落內完全無 /v1/ 路徑，且有訊號行 → 列為缺口。"""
    text = "### FR-01: 範例\n- [ ] SQLite 模式下 analytics API 回傳 501 Not Implemented\n"
    findings = check_api_surface.check_api_surface(text)
    assert len(findings) == 1
    assert findings[0]["fr_id"] == "FR-01"


def test_not_flagged_when_subject_path_defined_elsewhere_in_section():
    """訊號行本身無路徑，但段落內其他位置已定義同主題（analytics）路徑 → 不列為缺口。"""
    text = (
        "### FR-01: 範例\n"
        "`GET /v1/analytics/aggregate?group_by=&metric=` 對應 Aggregate\n"
        "- [ ] SQLite 模式下 analytics API 回傳 501 Not Implemented\n"
    )
    assert check_api_surface.check_api_surface(text) == []


def test_not_flagged_when_decoy_path_of_different_subject_exists():
    """段落內雖有其他主題（capabilities）的路徑，但 analytics 主題仍缺 → 仍列為缺口。"""
    text = (
        "### FR-04: 能力偵測\n"
        "`GET /v1/capabilities` 回傳目前 backend 能力\n"
        "- [ ] SQLite 模式下 analytics API 回傳 501 Not Implemented\n"
    )
    findings = check_api_surface.check_api_surface(text)
    assert len(findings) == 1
    assert "analytics API" in findings[0]["line"]


def test_line_with_inline_path_not_flagged():
    """訊號行自身已附路徑 → 不列為缺口。"""
    text = "### FR-01: 範例\n- [ ] `GET /v1/capabilities` 正確回傳當前 backend 能力\n"
    assert check_api_surface.check_api_surface(text) == []


def test_no_signal_line_not_flagged():
    """不含任何訊號詞的一般敘述 → 不列為缺口。"""
    text = "### FR-01: 範例\nDashboard 和 Query 透過 Go type assertion 判斷能力。\n"
    assert check_api_surface.check_api_surface(text) == []


# --- 驗證案例：SPEC-014 歷史版本（v1.1，應被抓出缺口） ---

# 摘自 v1.1 歷史版（git show 1382a5e:docs/spec/collector/postgresql.md）FR-04 段落：
# analytics API 行為（501 Not Implemented）僅描述於驗收標準，實際只定義了
# capabilities 的路徑，analytics 本身無 endpoint 路徑定義。
SPEC_014_V1_1_FR04 = """### FR-04: 能力偵測

**描述**：Dashboard 和 Query API 透過 Go type assertion 判斷 storage backend 是否支援進階分析能力。

**偵測機制**：

```go
func (h *QueryHandler) handleAnalytics(w http.ResponseWriter, r *http.Request) {
    as, ok := h.storage.(AnalyticsStorage)
    if !ok {
        http.Error(w, "analytics not available with current storage backend", http.StatusNotImplemented)
        return
    }
}
```

**能力查詢 API**：

`GET /v1/capabilities` 回傳目前 storage backend 支援的能力：

**驗收標準**：

- [ ] `GET /v1/capabilities` 正確回傳當前 backend 能力
- [ ] SQLite 模式下 analytics API 回傳 501 Not Implemented
- [ ] PostgreSQL 模式下 analytics API 正常回傳
- [ ] type assertion 判斷正確（SQLite = BasicStorage only, PostgreSQL = AnalyticsStorage）
"""


def test_spec_014_v1_1_flags_missing_analytics_endpoint():
    """v1.1 歷史版：analytics API 提及但無 endpoint 路徑定義 → 必須被抓出。"""
    findings = check_api_surface.check_api_surface(SPEC_014_V1_1_FR04)
    assert len(findings) >= 1
    assert all(f["fr_id"] == "FR-04" for f in findings)
    assert any("analytics API" in f["line"] for f in findings)


# --- 驗證案例：SPEC-014 現行版本（v1.4，應通過檢核） ---

SPEC_014_PATH = (
    Path(__file__).resolve().parents[4] / "docs" / "spec" / "collector" / "postgresql.md"
)


def test_spec_014_v1_4_passes():
    """現行 SPEC-014（v1.4，已補 endpoint 路徑）不應被列為缺口。"""
    spec_text = SPEC_014_PATH.read_text(encoding="utf-8")
    findings = check_api_surface.check_api_surface(spec_text)
    assert findings == [], f"預期無缺口，實際: {findings}"


# --- CLI ---

def test_main_exit_code_reflects_findings(tmp_path, capsys):
    spec_file = tmp_path / "spec.md"
    spec_file.write_text(SPEC_014_V1_1_FR04, encoding="utf-8")
    rc = check_api_surface.main([str(spec_file)])
    assert rc == 1
    assert "缺口" in capsys.readouterr().out


def test_main_exit_code_zero_when_clean(tmp_path, capsys):
    spec_file = tmp_path / "spec.md"
    spec_file.write_text("### FR-01: 範例\n一般敘述，無 API 訊號。\n", encoding="utf-8")
    rc = check_api_surface.main([str(spec_file)])
    assert rc == 0
    assert "通過" in capsys.readouterr().out


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-v"]))
