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

# 缺口版 FR-04 段落：analytics API 行為（501 Not Implemented）僅描述於
# 驗收標準，實際只定義了 capabilities 的路徑，analytics 本身無 endpoint
# 路徑定義——與下方 SPEC_014_V1_4_FR04（已補齊 endpoint）成對照組。
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


# --- 驗證案例：SPEC-014 修復版本（v1.4，應通過檢核） ---

# 修復版 FR-04 段落：在 SPEC_014_V1_1_FR04 基礎上補上 analytics 端點定義
# （`/v1/analytics/aggregate`），與上方缺口版成對照組，示範同一段落補齊
# endpoint 路徑後應通過檢核。skill 為 portable 資產，測資自足於本檔，
# 不依賴任何消費專案的活文件路徑。
SPEC_014_V1_4_FR04 = """### FR-04: 能力偵測

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

**Analytics API**：

`GET /v1/analytics/aggregate?group_by=&metric=` 回傳彙總分析結果（僅 AnalyticsStorage 支援）：

**驗收標準**：

- [ ] `GET /v1/capabilities` 正確回傳當前 backend 能力
- [ ] SQLite 模式下 analytics API 回傳 501 Not Implemented
- [ ] PostgreSQL 模式下 analytics API 正常回傳
- [ ] type assertion 判斷正確（SQLite = BasicStorage only, PostgreSQL = AnalyticsStorage）
"""


def test_spec_014_v1_4_passes():
    """修復版 SPEC-014 FR-04（已補 endpoint 路徑）不應被列為缺口。"""
    findings = check_api_surface.check_api_surface(SPEC_014_V1_4_FR04)
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


# --- 切段終點：最後一個 FR 段落不吃入其後的非 FR 章節 ---

def test_last_fr_section_stops_at_following_non_fr_heading():
    text = "### FR-01: A\nbody a\n### 設計約束\nPOST API 回 501\n"
    sections = dict(check_api_surface.split_fr_sections(text))
    assert "body a" in sections["FR-01"]
    assert "設計約束" not in sections["FR-01"] and "POST API" not in sections["FR-01"]


def test_fr_section_keeps_deeper_subheadings_and_stops_at_higher_heading():
    """對照：較深子標題留在段內；較高階（H2）標題結束段落。"""
    text = "### FR-01: A\n#### 細節\nbody\n## 下一章\nafter\n"
    section = dict(check_api_surface.split_fr_sections(text))["FR-01"]
    assert "#### 細節" in section and "body" in section
    assert "下一章" not in section


def test_signal_line_under_deeper_subheading_inside_fr_still_reported():
    """正向對照：較深子標題留在 FR 段內，其下無路徑的 API 訊號行仍列為缺口（防新規則把子標題也切掉）。"""
    text = "### FR-01: A\n#### 細節\nanalytics API 回傳 501\n### 設計約束\n一般敘述\n"
    findings = check_api_surface.check_api_surface(text)
    assert [f["fr_id"] for f in findings] == ["FR-01"]


def test_following_non_fr_chapter_not_reported_as_fr_gap():
    text = "### FR-01: A\n一般敘述\n### 設計約束\nanalytics API 回傳 501\n"
    assert check_api_surface.check_api_surface(text) == []


# --- 0 段不印通過 ---

def test_main_zero_fr_sections_fails_not_pass(tmp_path, capsys):
    spec_file = tmp_path / "spec.md"
    spec_file.write_text("# 無 FR 的文件\nanalytics API 回傳 501\n", encoding="utf-8")
    rc = check_api_surface.main([str(spec_file)])
    out = capsys.readouterr().out
    assert rc != 0
    assert "通過" not in out and "未抽到任何 FR" in out


def test_main_format_mismatch_headers_also_fail(tmp_path, capsys):
    """設定格式不符（H2、無冒號）：與整段缺席同為 0 段分支，並列出形似行。"""
    spec_file = tmp_path / "spec.md"
    spec_file.write_text("## FR-01 名稱\n內容\n", encoding="utf-8")
    rc = check_api_surface.main([str(spec_file)])
    out = capsys.readouterr().out
    assert rc != 0 and "通過" not in out and "FR-01 名稱" in out


# --- 抽取規則只剩一份 ---

def test_split_fr_sections_is_the_single_extraction_rule():
    from domain_coverage import fr_extract
    assert check_api_surface.split_fr_sections is fr_extract.split_fr_sections
    assert not hasattr(check_api_surface, "FR_HEADER_RE")


def test_split_accepts_h4_fullwidth_colon_and_skips_fenced_header():
    text = "#### FR-01：A\nbody\n```\n### FR-09: fake\n```\n"
    assert [i for i, _ in check_api_surface.split_fr_sections(text)] == ["FR-01"]


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-v"]))
