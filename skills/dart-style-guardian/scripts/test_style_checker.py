#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest"]
# ///
"""Tests for style_checker project calibration.

執行：uv run --no-project --with pytest pytest .claude/skills/dart-style-guardian/scripts/test_style_checker.py

命名為 test_style_checker.py 並與 style_checker.py 同置於 scripts/：本 skill 無獨立
測試目錄，另建 tests/ 只為單一檔案會多一層路徑而不增加隔離性。
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from style_checker import (  # noqa: E402
    StyleConfig,
    build_exempt_pattern,
    build_exception_patterns,
    build_pattern_groups,
    load_config,
    scan_file,
)


CONFIG = {
    "tokens": {
        "color": "AppPalette",
        "spacing": "AppSpacing",
        "font_size": "AppTypography",
        "border_radius": "AppRadius",
    },
    "i18n": {
        "accessor": "AppLocalizations.of(context).keyName",
        "compliance_pattern": r"AppLocalizations\.of\(",
    },
    "exempt_markers": ["magic-exempt", "i18n-exempt"],
}


def make_project(tmp_path: Path, config: dict | None = CONFIG) -> Path:
    """Build a minimal project tree, optionally carrying a calibration file."""
    root = tmp_path / "proj"
    (root / ".claude" / "config").mkdir(parents=True)
    (root / "lib").mkdir()
    if config is not None:
        (root / ".claude" / "config" / "dart-style-guardian.json").write_text(
            json.dumps(config), encoding="utf-8"
        )
    return root


def write_dart(root: Path, body: str, name: str = "probe.dart") -> Path:
    path = root / "lib" / name
    path.write_text(body, encoding="utf-8")
    return path


class TestConfigLoading:
    def test_reads_project_calibration(self, tmp_path):
        root = make_project(tmp_path)
        cfg = load_config(root / "lib")
        assert cfg.tokens["color"] == "AppPalette"
        assert cfg.i18n_accessor == "AppLocalizations.of(context).keyName"
        assert cfg.loaded_from is not None

    def test_missing_config_falls_back_to_neutral_defaults(self, tmp_path, capsys):
        root = make_project(tmp_path, config=None)
        cfg = load_config(root / "lib")
        assert cfg.tokens["color"] is None
        assert "未找到" in capsys.readouterr().err

    def test_malformed_config_falls_back_with_notice(self, tmp_path, capsys):
        root = make_project(tmp_path, config=None)
        (root / ".claude" / "config" / "dart-style-guardian.json").write_text(
            "{ not json", encoding="utf-8"
        )
        cfg = load_config(root / "lib")
        assert cfg.tokens["color"] is None
        assert "失敗" in capsys.readouterr().err


class TestSuggestionVocabulary:
    def test_suggestions_name_configured_tokens(self, tmp_path):
        cfg = load_config(make_project(tmp_path) / "lib")
        groups = build_pattern_groups(cfg)
        assert "AppPalette" in groups["Color"][0][1]
        assert "AppSpacing" in groups["SizedBox"][0][1]
        assert "AppTypography" in groups["FontSize"][0][1]
        assert "AppRadius" in groups["BorderRadius"][0][1]

    def test_neutral_defaults_do_not_name_any_class(self, tmp_path):
        cfg = load_config(make_project(tmp_path, config=None) / "lib")
        suggestions = [s for group in build_pattern_groups(cfg).values() for _, s in group]
        joined = " ".join(suggestions)
        for foreign in ("UIColors", "UISpacing", "UIFontSizes", "UIBorderRadius", "AppPalette"):
            assert foreign not in joined

    def test_configured_tokens_count_as_compliant(self, tmp_path):
        cfg = load_config(make_project(tmp_path) / "lib")
        patterns = build_exception_patterns(cfg)
        assert any("AppPalette" in p for p in patterns)


class TestDetection:
    def test_reports_violations_with_project_vocabulary(self, tmp_path):
        root = make_project(tmp_path)
        path = write_dart(
            root,
            "Text('硬編碼', style: TextStyle(fontSize: 14, color: Colors.blue));\n",
        )
        result = scan_file(path, load_config(root / "lib"))
        categories = {v.category for v in result.violations}
        assert {"Color", "FontSize", "i18n"} <= categories
        assert any("AppPalette" in v.suggestion for v in result.violations)

    @pytest.mark.parametrize("marker", ["magic-exempt", "i18n-exempt"])
    def test_marked_lines_are_exempt_not_violations(self, tmp_path, marker):
        root = make_project(tmp_path)
        path = write_dart(
            root,
            f"const SizedBox(height: 7); // {marker}: 探針\n",
        )
        result = scan_file(path, load_config(root / "lib"))
        assert result.violations == []
        assert result.exempt_count == 1

    def test_exemptions_are_counted_not_silently_dropped(self, tmp_path):
        """豁免必須留下計數：靜默略過的行與掃描器看不見的行無法區分。"""
        root = make_project(tmp_path)
        path = write_dart(
            root,
            "const SizedBox(height: 7); // magic-exempt: 探針\n"
            "const SizedBox(height: 9);\n",
        )
        result = scan_file(path, load_config(root / "lib"))
        assert len(result.violations) == 1
        assert result.exempt_count == 1

    def test_unconfigured_marker_does_not_exempt(self, tmp_path):
        root = make_project(tmp_path, config={**CONFIG, "exempt_markers": ["only-this"]})
        path = write_dart(
            root,
            "const SizedBox(height: 7); // magic-exempt: 未列入設定\n",
        )
        result = scan_file(path, load_config(root / "lib"))
        assert len(result.violations) == 1
        assert result.exempt_count == 0


class TestExemptPatternConstruction:
    def test_returns_none_when_no_markers_configured(self):
        assert build_exempt_pattern(StyleConfig(exempt_markers=[])) is None

    def test_markers_are_escaped(self):
        pattern = build_exempt_pattern(StyleConfig(exempt_markers=["a.b"]))
        assert pattern == r"a\.b"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
